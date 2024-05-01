#!/usr/bin/python3
#
# Copyright 2024 TVH Parts Holding NV, IT department, CoE Progress, Vichtseweg 129, 8790 Waregem, Belgium.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys
from logging.handlers import RotatingFileHandler

import adapterconfig
from enum import Enum
import logging
import os
import pathlib
import selectors
import socket
import subprocess
import time


class StreamType(Enum):
    SERVER = 0
    CLIENT = 1
    ADAPTER = 2


class AdapterProcess:
    def __init__(self, config: adapterconfig.AdapterConfig, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.process: subprocess.Popen = None
        self.output = b''

    @property
    def isRunning(self) -> bool:
        return self.process.poll() is None

    def run(self, selector: selectors.DefaultSelector) -> None:
        env = os.environ.copy()
        env.update(self.config.environment)
        command = [f'{self.config.environment["DLC"]}/bin/oemessaging', 'start', self.config.instance.brokerName]
        self.logger.info(f"Starting adapter: {command}")
        self.process = subprocess.Popen(
            command,
            bufsize=1, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, shell=False, env=env,
            text=True)
        os.set_blocking(self.process.stdout.fileno(), False)
        selector.register(self.process.stdout, selectors.EVENT_READ, StreamType.ADAPTER)
        time.sleep(1)
        result = self.process.poll()
        if result is None:
            self.logger.info(f"Adapter started: PID {self.process.pid}")
        else:
            self.logger.critical("")
            self.logger.critical("!" * 49)
            self.logger.critical(f"!! Adapter process terminated with exit code {result} !!")
            self.logger.critical("!" * 49)
            self.logger.critical("")
            line = self.process.stdout.readline()
            while line:
                self.logger.critical(line.splitlines()[0])
                line = self.process.stdout.readline()

    def readOutput(self, fileDescriptor) -> None:
        while self.process.poll() is None:
            try:
                data = os.read(fileDescriptor.fileno(), 2048)
            except IOError:
                break
            self.output += data
            time.sleep(0.1)

    def logOutput(self):
        output = self.output.decode('ascii')
        for line in output.splitlines():
            self.logger.info(f"OUT: {line}")

    def sendInput(self, message: str) -> None:
        self.logger.info(f"IN: {message.splitlines()[0]}")
        self.process.stdin.writelines([message])

    def stop(self) -> None:
        if self.isRunning:
            self.logger.info('Stopping JMS Adapter')
            self.sendInput("e")
            try:
                self.process.wait(5)
                self.logger.info('JMS Adapter stopped')
            except subprocess.TimeoutExpired:
                self.logger.warning("Timeout stopping JMS Adapter - Terminating")
                self.process.terminate()
                try:
                    self.process.wait(5)
                    self.logger.info('JMS Adapter terminated')
                except subprocess.TimeoutExpired:
                    self.logger.error("Timeout terminating JMS Adapter - Sending Kill signal")
                    self.process.kill()
        else:
            self.logger.info("Adapter has shut down")


class JmsAdapterManager:
    def __init__(self, config: adapterconfig.AdapterConfig, logger: logging.Logger):
        self.config = config
        self.brokerName = config.instance.brokerName
        self.controlPort = config.instance.controlPort
        self.logger = logger
        self.selector = selectors.DefaultSelector()
        self.adapterProcess: AdapterProcess = None
        self.serverSocket: socket.socket = None
        self.clientSocket: socket.socket = None

    def _setupServerSocket(self) -> None:
        self.logger.info(f"Setting up controller on localhost:{self.controlPort}")
        serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        serverSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        serverSocket.bind(('127.0.0.1', self.controlPort))
        serverSocket.listen()
        serverSocket.setblocking(False)
        self.selector.register(serverSocket, selectors.EVENT_READ, StreamType.SERVER)
        self.serverSocket = serverSocket

    def _startAdapter(self) -> None:
        self.adapterProcess = AdapterProcess(self.config, self.logger)
        self.adapterProcess.run(self.selector)

    def _acceptConnection(self, key) -> None:
        server = key.fileobj
        self.selector.unregister(self.serverSocket)
        client, address = server.accept()
        self.logger.info(f"Accepting client connection on {address}")
        client.setblocking(False)
        self.clientSocket = client
        self.selector.register(client, selectors.EVENT_READ, StreamType.CLIENT)

    def _readClient(self) -> None:
        client = self.clientSocket
        try:
            data = client.recv(64)
            if data:
                self.adapterProcess.sendInput(data.decode('ascii'))
            else:
                self.logger.info("Client disconnected")
                self.selector.unregister(client)
                client.close()
                self.selector.register(self.serverSocket, selectors.EVENT_READ, StreamType.SERVER)
        except OSError:
            self._deregisterClient()

    def _sendToClient(self):
        client = self.clientSocket
        self.adapterProcess.logOutput()
        if client:
            try:
                while self.adapterProcess.output:
                    sent = client.send(self.adapterProcess.output)
                    self.adapterProcess.output = self.adapterProcess.output[sent:]

            except OSError:
                self._deregisterClient()
        else:
            self.adapterProcess.output = b''

    def _deregisterClient(self):
        client = self.clientSocket
        if client:
            self.clientSocket = None
            try:
                self.selector.unregister(client)
            except ValueError:
                pass
            try:
                self.selector.register(self.serverSocket, selectors.EVENT_READ, StreamType.SERVER)
            except KeyError:
                pass

    def runAdapter(self) -> None:
        try:
            self._setupServerSocket()
            self._startAdapter()
            while self.adapterProcess.isRunning:
                events = self.selector.select(timeout=None)
                for key, mask in events:
                    match key.data:
                        case StreamType.ADAPTER:
                            self.adapterProcess.readOutput(key.fileobj)
                            self._sendToClient()
                        case StreamType.CLIENT:
                            self._readClient()
                        case StreamType.SERVER:
                            self._acceptConnection(key)
        except KeyboardInterrupt:
            print()
            print("KeyboardInterrupt: Terminating")
        finally:
            try:
                if self.adapterProcess:
                    self.adapterProcess.stop()
            finally:
                pass
            try:
                if self.serverSocket:
                    self.serverSocket.shutdown(socket.SHUT_RDWR)
                    self.serverSocket.close()
            finally:
                pass
            self.selector.close()


def main() -> None:
    config = adapterconfig.AdapterConfig()
    logger = setupLogger(config)
    try:
        jmsAdapterManager = JmsAdapterManager(config, logger)
        jmsAdapterManager.runAdapter()
    except Exception:
        logger.error(msg="Unhandled exception", exc_info=True)
        raise


def setupLogger(config: adapterconfig.AdapterConfig) -> logging.Logger:

    logger = logging.Logger(name=config.instance.brokerName, level=logging.INFO)
    formatter = logging.Formatter(fmt='%(asctime)s: %(levelname)s: %(message)s', datefmt='%Y-%m-%dT%H:%M:%S%z')
    if config.instance.logToFile:
        pathlib.Path(config.instance.logDirectory).mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(filename=f"{config.instance.logDirectory}/{config.instance.brokerName}.log",
                                      maxBytes=1048576, backupCount=3)
    else:
        handler = logging.StreamHandler(sys.stdout)

    handler.setLevel(logging.INFO)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


if __name__ == '__main__':
    main()

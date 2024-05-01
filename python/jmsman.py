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

import adapterconfig
import select
import socket
import sys


class Connection:
    def __init__(self, serverPort: int):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.socket.connect(('localhost', serverPort))
            self.socket.setblocking(False)
            self.connected = True
        except ConnectionRefusedError:
            self.connected = False
            print()
            print("=" * 27)
            print("The adapter is not running.")
            print("=" * 27)
            print()

    def fileno(self) -> int:
        return self.socket.fileno()

    def onRead(self) -> None:
        try:
            receivedData = False
            while self.connected:
                message = self.socket.recv(2048)
                if message:
                    receivedData = True
                    print(message.decode('ascii'), end='')
                    sys.stdout.flush()
                else:
                    break
            if receivedData is False:
                self.socket.close()
                self.connected = False
        except BlockingIOError:
            pass

    def send(self, message) -> None:
        self.socket.send(message)

    def disconnect(self) -> None:
        self.connected = False
        self.socket.shutdown(socket.SHUT_RDWR)
        self.socket.close()


class Input:
    def __init__(self):
        self.buffer = ''

    def fileno(self) -> int:
        return sys.stdin.fileno()

    def onRead(self) -> None:
        self.buffer += sys.stdin.readline()


class JmsAdapterUI:
    def __init__(self, serverPort: int):
        self.serverPort = serverPort
        self.connection: Connection = None
        self.input: Input = None

    def runUI(self) -> None:
        self.connection = Connection(self.serverPort)
        if self.connection.connected:
            self.input = Input()
            self.connection.send(b"s\n")
            reader, _, _ = select.select([self.connection], [], [], 3)
            if (reader):
                self.connection.onRead()
                self.printMenu()
            else:
                print('Timeout initiating connection. Another connection may be active.')
                self.connection.disconnect()
        try:
            while self.connection.connected:
                self.eventHandler()
        except KeyboardInterrupt:
            if self.connection.connected:
                self.connection.disconnect()

    def printMenu(self) -> None:
        print('------------------------')
        print('Please select an option:')
        print('------------------------')
        print('S: Summary              D: Server Detail')
        print('L: Connection Summary   C: Connection Detail')
        print('Y: All Properties       Z: Property by name')
        print('')
        print('X: Add Server(s)        T: Trim Server(s)       K: Kill a Server')
        print('')
        print('E: Stop Adapter         A: Abort Adapter')
        print('')
        print('Q: Quit the UI          H: Help')
        print('')

    def eventHandler(self) -> None:
        readers, _, _ = select.select([self.connection, self.input], [], [])
        for reader in readers:
            reader.onRead()
            if reader == self.input:
                match self.input.buffer.capitalize()[0]:
                    case "Q":
                        self.connection.disconnect()
                    case "H":
                        self.printMenu()
                    case "E":
                        ans = input('Enter "Yes" to confirm that you want to shut down the adapter: ')
                        if ans.capitalize() == "Yes":
                            self.connection.send(b"e\n")
                        else:
                            self.printMenu()
                    case "A":
                        ans = input('Enter "Yes" to confirm that you want to shut down the adapter: ')
                        if ans.capitalize() == "Yes":
                            self.connection.send(b"a\n")
                        else:
                            self.printMenu()
                    case _:
                        self.connection.send(self.input.buffer.encode('ascii'))
                self.input.buffer = ''

    def runBatch(self, args):
        self.connection = Connection(self.serverPort)
        if self.connection.connected:
            for arg in args:
                if arg.capitalize() == "H" or arg.capitalize() == "Help":
                    self.printMenu()
                else:
                    self.connection.send(arg.encode('ascii') + b'\n')
                    readers, _, _ = select.select([self.connection], [], [], 3)
                    if (readers):
                        self.connection.onRead()
                    else:
                        print('Timeout expired reading socket.  Another connection may be active.')
            self.connection.disconnect()


def main() -> None:
    config = adapterconfig.AdapterConfig()
    print()
    print(f"Connecting to broker: {config.instance.brokerName}")
    print()
    jmsAdapterUI = JmsAdapterUI(config.instance.controlPort)
    if len(sys.argv) == 1:
        jmsAdapterUI.runUI()
    else:
        args = sys.argv[1:]
        jmsAdapterUI.runBatch(args)


if __name__ == '__main__':
    main()

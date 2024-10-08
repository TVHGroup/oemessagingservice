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

import subprocess
from os import path
import platform
from adapterconfig import AdapterConfig
from configparser import ConfigParser


class Metrics:
    def __init__(self):
        pythonDir = path.dirname(path.realpath(__file__))
        baseDir = path.dirname(pythonDir)
        config = AdapterConfig()
        self.hostname = platform.uname().node
        self.brokerName = config.instance.brokerName
        self.status = 'Online'
        self.activeServers = 0
        self.busyServers = 0
        self.lockedServers = 0
        self.availableServers = 0
        self.currentActiveClients = 0
        self.maximumActiveClients = 0
        self.currentClientQueueDepth = 0
        self.maximumClientQueueDepth = 0
        self.totalRequests  = 0
        self.maximumRequestWait = 0
        self.averageRequestWait = 0
        self.maxAdptrThreads = 0
        self.maxClientInstance = 0

        status = subprocess.run([f"{baseDir}/adaptman", "s"], capture_output=True, text=True, check=True)
        lines = status.stdout.splitlines()
        for line in lines:
            try:
                parts = line.split(':')
                match parts[0].strip():
                    case 'The adapter is not running.':
                        self.status = 'Offline'
                    case 'Active Servers':
                        self.activeServers = int(parts[1])
                    case 'Busy Servers':
                        self.busyServers = int(parts[1])
                    case 'Locked Servers':
                        self.lockedServers = int(parts[1])
                    case 'Available Servers':
                        self.availableServers = int(parts[1])
                    case 'Active Clients (now, peak)':
                        current, peak = self._valueSplitter(parts[1])
                        self.currentActiveClients = current
                        self.maximumActiveClients = peak
                    case 'Client Queue Depth (cur, max)':
                        current, peak = self._valueSplitter(parts[1])
                        self.currentClientQueueDepth = current
                        self.maximumClientQueueDepth = peak
                    case 'Total Requests':
                        self.totalRequests = int(parts[1])
                    case 'Rq Wait (max, avg)':
                        mx, av = self._valueSplitter(parts[1])
                        self.maximumRequestWait = mx
                        self.averageRequestWait = av
            except ValueError:
                pass

        props = ConfigParser(comment_prefixes=('#', '%'))
        props.read(f"{config.environment['DLC']}/properties/ubroker.properties")
        if props.has_section(f"Adapter.{self.brokerName}"):
            self.maxAdptrThreads = props.getint(f"Adapter.{self.brokerName}", "maxAdptrThreads", fallback=0)
            self.maxClientInstance = props.getint(f"Adapter.{self.brokerName}", "maxClientInstance", fallback=0)


    def _valueSplitter(self, value: str):
        items = value.strip(' ()').split(',')
        value1 = 0
        value2 = 0
        try:
            value1 = int(items[0].strip(' ms'))
        except ValueError:
            pass
        try:
            if len(items) >= 2:
                value2 = int(items[1].strip(' ms'))
        except ValueError:
            pass

        return value1, value2


    def __str__(self):
        if self.status == 'Online':
            result = f"""Metrics for broker {self.brokerName} on {self.hostname}
Active Servers             : {self.activeServers}
Busy Servers               : {self.busyServers}
Locked Servers             : {self.lockedServers}
Available Servers          : {self.availableServers}
Current Active Clients     : {self.currentActiveClients}
MaximumActive Clients      : {self.maximumActiveClients}
Current Client Queue Depth : {self.currentClientQueueDepth}
Maximum Client Queue Depth : {self.maximumClientQueueDepth}
Total Requests             : {self.totalRequests}
Average Request Wait       : {self.averageRequestWait} ms
Maximum Request Wait       : {self.maximumRequestWait} ms

Configuration for broker {self.brokerName} on {self.hostname}:
Maximum Adapter Threads    : {self.maxAdptrThreads}
Maximum Clients Instances  : {self.maxClientInstance}
"""
        else:
            result = f"Broker {self.brokerName} on {self.hostname} is Offline"
        
        return result


def main() -> None:
    print(Metrics())


if __name__ == '__main__':
    main()

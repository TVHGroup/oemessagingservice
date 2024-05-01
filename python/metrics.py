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


class Metrics:
    def __init__(self):
        pythonDir = path.dirname(path.realpath(__file__))
        baseDir = path.dirname(pythonDir)
        status = subprocess.run([f"{baseDir}/adaptman", "s"], capture_output=True, text=True, check=True)
        lines = status.stdout.splitlines()
        for line in lines:
            parts = line.split(':')
            match parts[0].strip():
                case 'Broker Name':
                    self.brokerName = parts[1].strip()
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
                case 'Rq Duration (max, avg)':
                    mx, av = self._valueSplitter(parts[1])
                    self.maximumRequestDuration = mx
                    self.averageRequestDuration = av

    def _valueSplitter(self, value: str):
        items = value.strip(' ()').split(',')
        return int(items[0].strip(' ms')), int(items[1].strip(' ms'))

    def __str__(self):
        return f"""Metrics for broker {self.brokerName}
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
Average Request Duration   : {self.averageRequestDuration} ms
Maximum Request Duration   : {self.maximumRequestDuration} ms
"""


def main() -> None:
    print(Metrics())


if __name__ == '__main__':
    main()

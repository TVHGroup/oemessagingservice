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

import platform
from glob import glob
import json
from os import path


class AdapterConfig:
    def __init__(self):
        pythonDir = path.dirname(path.realpath(__file__))
        self.baseDir = path.dirname(pythonDir)
        with open(f"{self.baseDir}/config/adapter.json", "r") as jsonFile:
            config = json.load(jsonFile)
        jarFiles = glob(f"{self.baseDir}/jars/*.jar")
        self.instance = AdapterInstance(config["instance"])
        self.environment = config["environment"]
        self.environment["JMSCLIENTJAR"] = f'{":".join(jarFiles)} {" ".join(config["jvmArgs"])}'


class AdapterInstance:
    def __init__(self, config):
        self.brokerName = config["brokerName"]
        self.controlPort = config["controlPort"]
        self.logToFile = config["logToFile"]
        self.logDirectory = config["logDirectory"]

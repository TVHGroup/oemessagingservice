# OpenEdge Messaging Service

As of version 12.x, the _Progress OpenEdge JMS Adapter_ (the Adapter) supplied by 
Progress (www.progress.com) is an interactive product. This poses a problem 
for end users that needs a service similar to its predecessor, adaptman.

This software is an unofficial, unsupported solution to solve that problem.

It achieves this by wrapping the Python based process (the service) that can run
as a service which wraps around the Adapter, together with a Python based CLI
enabling the user to interact with the service and by extension the Adapter.

# Installation

## Prerequisites

- A version of Linux supporting the _Progress OpenEdge JMS Adapter_.
- Python 3.10 or later.
- A functioning instance of _Progress OpenEdge JMS Adapter_.
- The JMS Client Jar files needed to start the _Progress OpenEdge JMS Adapter_.

## Setup

1. Clone the repository to a suitable location. All examples will assume that
   the repository was cloned to `/opt/oemessagingservice`.
2. Copy `config/adapter.json.template` to `config/adapter.json`.
3. Update `config/adapter.json` with the appropriate values.

    **`environment` Section**
    
    This is a dictionary of key-value pairs defining environment variables
    and their values.
    
    Set the environment variable needed by the service and by the Adapter.
    Do NOT set `JMSCLIENTJAR`, it will be calculated and overwritten.
    At least the following needs to be set:
    - DLC - The path to the installation folder of the Adapter
    - WRKDIR - The OpenEdge work folder.
    - JMSPROVIDER - The value you would use for `JMSPROVIDER` when running
      interactively.

    **`jvmArgs` Section**
    
    This is a Json array of JVM Arguments that you wish to add to the Java
    command line when starting the Adapter.

    The example sets the maximum size of the memory allocation pool and
    forces the Adapter to bind to IPv4. This section can be an empty
    array if you do not wish to set any additional JVM Arguments.
    
    **`instance` Section**
    
    This section configures the properties of the Python service process.
    It contains the following fields that needs to be set:
    - `brokerName` The name of the configured broker that needs to be passed
      on the command line when invoking `$DLC/bin/oemessaging start`.
    - `controlPort` The service binds to this port number on the `localhost` 
      adapter. It is used by the CLI script to interact with the service.
    - `logToFile` This is a boolean that indicates if the Python service must
      log its output to a file or to the console. This can be used to redirect
      the output to the console when running the service in a container rather
      than running it on traditional server.
    - `logDirectory` This is the directory where the Python service writes its
      log files when `logToFile` is true. Note that the user running the 
      service needs to have write access to this folder, or the service will
      not start. The same is true for the location where the oemessaging
      broker will write its log.
     
4. Copy the necessary JMS client JAR files to `jars`.

    These are all the files that you need to reference in the `JMSCLIENTJAR` 
    environment variable when starting the Adapter interactively.
    
5. Create and install the service unit file.

    **Example Systemd unit file**

        # /etc/systemd/system/oemessagingservice.service
        #
        [Unit]
        Description=OpenEdge JMS Adapter
        After=network.target

        [Service]
        ExecStart=/usr/bin/python3 /opt/oemessagingservice/python/jmsadapter.py
        ExecStop=/usr/bin/python3 /opt/oemessagingservice/python/jmsman.py e
        Type=simple
        User=openedge
        Group=openedge

        [Install]
        WantedBy=default.target

6. Ensure that the user running the service has sufficient access to write both
   the service logs and the JMS Adapter broker log. The service will automatically
   create the log directory above if it is missing, but if the user does not have
   sufficient access, the service will fail to start. In such a case the user can
   either be granted access to the containing folder, or the log folder can be
   created up front and ownership can be reassigned to the service user. Similarly,
   when configuring the broker for the Adapter, a log file is specified for the
   broker and the service user will need sufficient access to write to it.

# Usage

## Python Service
The service is started by invoking `python/jmsadapter.py`. 

This program is designed to run in the background or as a service. 

When starting up it reads the configuration in config/adapter.json. It then 
starts the _Progress OpenEdge JMS Adapter_, redirecting `STDIN`, `STDOUT` 
and `STDERROR` to the service itself. By default, any data that arrives on
the Adapter's `STDOUT` or `STDERROR` is dumped to the log.

The service also opens a TCP socket on the `localhost` adapter which can be 
used by the CLI to interact with the service and by extension, the Adapter.

When something is attached to the socket, any input on the socket is logged
to the log file and also passed as-is to the Adapter's `STDIN`. The Adapter's
`STDOUT` and `STDERROR` are both dumped straight to the socket in addition to 
be written to the log file.

There is no security on the socket, thus anybody with access to the host or the
ability to connect to a socket on `localhost` could interact with the process.
As this traffic is basically just passing the Adapter's `STDIN` and `STDOUT`
around, this risk was found to be acceptable by the creator of the software.

To stop the adapter, use the CLI (see below) to pass the "Exit" instruction to
the Adapter. The service will wait for the Adapter to shut down and then 
terminate itself.

## Service CLI
The CLI is invoked by running `python/jmsman.py`. The script `adaptman` in
the project root exists as a convenient shortcut. 

When the CLI starts up, it reads `config/adapter.json` to find the control port
of the service and open a connection to it.

If no command line arguments are supplied, it starts in interactive mode.

The CLI supports all the options that would be available if the Adapter was
running interactively and it also adds two more options.

At the time of writing, the Adapter has the following menu:

    ::S-Summary D-SrvrDetail X-AddSrvr T-TrimSrvr  K-KillSrvr  E-Exit A-Abort
    ::L-ConnSummary C-ConnDetail Y-ListAllProps Z-ListPropName

The CLI adds two more options, being `Q: Quit the UI` and `H: Help`. These two
options are not passed through the socket to the service. Instead, they will
terminate the CLI or print the available options, respectively:

    ------------------------
    Please select an option:
    ------------------------
    S: Summary              D: Server Detail
    L: Connection Summary   C: Connection Detail
    Y: All Properties       Z: Property by name

    X: Add Server(s)        T: Trim Server(s)       K: Kill a Server

    E: Stop Adapter         A: Abort Adapter

    Q: Quit the UI          H: Help

With the exception of selecting E, A, Q and H, any keyboard input is passed 
as-is to the service, which in turns passed it to the `STDIN` on the Adapter. 
Any output on the Adapter's `STDOUT` will be passed back over the socket to the 
CLI, which in turn will dump it to the terminal. This way, the user can interact 
with the Adapter just like when it is running interactively.

If the received input is either "E" or "A", the CLI will confirm with the user
that the intend is to bring the Adapter down and only pass the instruction to
the service if the user answers in the affirmative. This is to prevent a user
from accidentally stopping the adapter when the intent is to exit the CLI, for
which "Q" should be used.

If command line arguments are passed to the CLI, it will pass these through to
the service and terminate without asking any questions. This includes receiving
the options "E" and "A". This enables the user to control the adapter via
scripting. Some options need more than one input, in such a case all inputs
must be passed as arguments on the same command line. For example, to add five
servers, use:
    
    python/jmsman.py x 5

## Metrics
The file `python/metrics.py` defines a Python class called `Metrics`. When this
class is instantiated, it uses the CLI to get the summary page of the Adapter
and extract the statistics on it into individual fields of the class. This can
be used by a custom Python based monitoring script to feed data about the 
Adapter to monitoring databases. The `__str__` method of the class is overridden
to output a formatted report of the data collected by the class.

If the file is invoked as if it is a program (i.e. it is invoked from the
command line) then it will create an instance of the class and print its 
string representation.

The class is immutable and there is no way to refresh the fields of the class. 
To get the latest data, simply create a new instance of the class.

## Checking if the Adapter is running
The script `probe` can be used to check if the adapter is running or not and
is suitable for use as a liveness probe on Kubernetes. It has no output and
two possible exit codes: 

    0 = The `Broker Status` of the Adapter is `ACTIVE`
    1 = The `Broker Status` of the Adapter is anything other than `ACTIVE`

**Note:** Only one process can connect at a time to the socket of the service,
thus, probes will fail if a simultaneous interactive connection of the CLI exits.

# Support

This product is supplied AS-IS and is not officially supported.

Should you discover any security vulnerabilities with this software, please 
refer to the [TVH Responsible Disclosure Policy](https://www.tvh.com/responsible-disclosure)
for guidance on reporting the issue.

# Authors and acknowledgment

This software was created by Simon L. Prinsloo (simon\_at\_vidisolve.com) on 
behalf of TVH Parts Holding NV, IT department, CoE Progress, Vichtseweg 129, 
8790 Waregem, Belgium

# License

Copyright 2024 TVH Parts Holding NV, IT department, CoE Progress, Vichtseweg 129, 
8790 Waregem, Belgium

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this software except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

# Project status

The product is currently considered feature complete.

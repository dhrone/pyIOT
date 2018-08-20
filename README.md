# pyIOT
![pyIOT Diagram](doc/source/_static/pyIOT_System.jpg)

A python module to simplify writing device drivers for the Amazon AWS IOT service

pyIOT abstracts the AWS IOT-Core service handling all of the communications between it and our device.  To implement a pyIOT application, you only need to specify how to convert from the protocol of your device into the properties that you want to expose to IOT-Core and vice-versa.  This enables IOT-Core applications to be written in a handful of lines of code.

Here's an example pyIOT application for a simple relay...

```python

import serial
import pyIOT

class Relay(Component):
  @Component.componentToProperty('relayState', '^RELAY(ON|OFF)$')
  def toRelayState(self, property, value):
      val = { 'ON': True, 'OFF': False }.get(value)
      if val: return val
      raise ValueError('{0} is not a valid value for property {1}'.format(value, property))

  @Component.propertyToComponent('relayState', 'RELAY{0}')
  def fromRelayState(self, value):
      val = { True: 'ON', False: 'OFF' }.get(value)
      if val: return val
      raise ValueError('{0} is not a valid relayState'.format(value))

  def queryStatus(self):
    return 'RELAY?\n'

try:
  ser = serial.Serial('/dev/ttyUSB0',9600, timeout=0.5)
  relayComponent = Relay(name = 'RelayComponent1', stream = ser, synchronous=True)

  relayThing = Thing(endpoint='<your endpoint>', thingName='relayOne', rootCAPath='root-CA.crt', certificatePath='relayOne.crt',
    privateKeyPath='relayOne.private.key', region='us-east-1', components=relayComponent)
  relayThing.start()
except KeyboardInterrupt:
  relayComponent.exit()
```
# Features

* Handles all communications between AWS IOT-Core and your device
* Optionally allows several components to be combined into a single IOT device
* Supports synchronous and asynchronous components
* Easily interfaces with serial and network driven components
* Allows custom communication methods including GPIO driven applications

# Documentation

For more details on pyIOT and its usage, please consult the documenation at https://pyiot.readthedocs.io

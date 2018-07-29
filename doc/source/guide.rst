Overview
========

To build an driver for an IOT you first need to decide what components will make up the IOT.  For each of these components you will also need to understand how to interact with the component.  pyIOT is somewhat opinionated in regards to interaction pattern in that the normal communication method it expects for device-to-driver interaction is a stream.  This makes integrating with devices that use a serial or network interface straight forward.  If a component you need to support does not lend itself to stream based communications, it is possible to overload the relevant `Component` methods (read, write, close) to enable whatever communications pattern you need.

Prerequisites
=============

* A device or devices interfaced with the computer or controller you are using to run your pyIOT program
* An AWS account
* An IOT Thing created within IOT-Core
* The Thing name
* A certificate created, activated and associated with the Thing
* A policy attached to the certificate which grants iot:Connect, iot:Publish, iot:Receive, and iot:Subscribe
* A file containing the Thing's certificate
* A file containing the private key of the Thing's certificate
* A file containing the certificate for the root certificate authority for AWS IoT
* The URL for your IOT-Core Rest API endpoint.

  + This is shown within the AWS IOT-Core console under the Interact page of each of your registered Things.

Basic Steps
===========

To complete an pyIOT application you will need to complete the following tasks.

* Connect your components to your controller and verify that you can communicate with them
* Determine what properties your IOT will expose to IOT-Core
* Write your `Component` classes by inheriting from `Component` and implementing `componentToProperty` and `propertyToComponent` methods for the properties that the component is responsible for

  - You may also want to implement a `queryStatus` method to periodically poll your device for its current property values.

    + This is especially useful for synchronous devices

* Instantiate each of your component classes
* Instantiate a Thing to contain your component objects

A short example:
----------------

In this example we will assume the following situation.

* We have a Relay that is controllable over a serial interface
* It is attached to `/dev/ttyUSB0` and communicates at `9600` baud with `No stop bits`, `8 bit values`, and `no parity`
* It is a synchronous device so it will only respond when spoken to
* It accepts the following three commands

  - **RELAYON** -- Circuit is completed (e.g. power on)
  - **RELAYOFF** -- Circuit is broken (e.g. power off)
  - **RELAY?** -- Return current state

* All three of these commands respond with `RELAYON` or `RELAYOFF` to indicate current relay state
* We have decided that our IOT will be composed only of this relay
* We have created an IOT within AWS IOT-Core

  - Its name is `relayOne`
  - It is located in the `us-east-1` region
  - It has a single Boolean property called `relayState` which is...

    + True to represent Relay circuit complete or
    + False to represent Relay circuit broken

  - We have downloaded the required certificates and keys

    + `root-CA.crt` contains the AWS IOT root certificate
    + `relayOne.crt` contains the certificate associated with `relayOne`
    + `relayOne.private.key` contains the private key associated with `relayOne.crt`

.. code-block:: python

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
    relayComponent1 = Relay(name = 'RelayComponent1', eol='\n', stream = ser, properties = { 'relayState': 'UNKNOWN' }, synchronous=True)

    relayThing = Thing(endpoint='<your endpoint>', thingName='relayOne', rootCAPath='root-CA.crt', certificatePath='relayOne.crt',
      privateKeyPath='relayOne.private.key', region='us-east-1', components=[relayComponent1])
    relayThing.start()
  except KeyboardInterrupt:
    relayComponent1.exit()


Component Development
=====================

Components are the core of pyIOT.  You will need to create a class that inherits from Component for each device that will make up your Thing.  This requires that you have a clear understanding of how your device is controlled.  pyIOT requires that you establish a set of properties for your device that represent the capabilities that you want to manage through the AWS IOT-Core service.  These properties will be shared with IOT-Core which keeps a copy of their values in a JSON object called a Shadow.  So the first thing you need to determine is the list of properties you will support from your device.  Property types will vary based upon the specific device being enabled but common properties include power, volume, brightness, color, and input.  You can name your property's anything you want with the following caveats.

* Property names must be unique across a Thing.  If you have a Thing that consists of multiple components, you must make sure that no component uses a property name that another component is using.
* If you are intending for your Thing to be controlled by the Alexa Smart Home Skill, it is convenient to adopt the property names of the specific interface you will be implementing.  More details on Alexa Smart Home Skill interfaces can be found at https://developer.amazon.com/docs/device-apis/message-guide.html.




The Shadow is composed of three parts; desired, reported, and delta.  Desired and reported are normally contain identical values.

pyIOT's primary communication style is streams.  This style is convenient for a wide variety of device types including devices that communicate over serial interfaces and those that communicate using network interfaces.  The primary effort in creating the Component will be writing your propertyToComponent and componentToProperty methods.

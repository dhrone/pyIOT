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

A short example
---------------

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

Device Shadow
=============

AWS IOT-Core uses a JSON document called a device Shadow to record the state of the Things that it is managing.  A Shadow document has several properties but the one of primary importance to pyIOT is state.  State has two main properties.

* desired -- The desired state of the Thing.  This is normally maintained by an application that is trying to control the Thing
* reported -- The last reported state of the Thing.  This is normally updated by the Thing itself

Inside both desired and reported are the properties that make up a Thing.  Normally both contain the same set of properties and each property has the same value.  However, when an application wants to change the state of a Thing, it modifies the value of one or more properties within the desired property.

When a property within desired is different than a property within reported, IOT-Core creates a new property within state called delta.  Delta contains the list of properties that are different and the value from desired that has been requested. This also causes a delta message to be published informing pyIOT that a change must be processed.

When pyIOT finishes processing the change, it reports back the new reported state.  If successful, this will return reported and desired back to being equivalent causing IOT-Core to remove the delta property from within state.  If the update fails, reported and desired will remain inconsistent.  Note: the most likely cause of a failed message update is an invalid property value being requested by the controlling application.


Component Development
=====================

Components are the core of pyIOT.  You will need to create a class that inherits from Component for each device that will make up your Thing.  This requires that you have a clear understanding of how your device is controlled.  pyIOT requires that you establish a set of properties for your device that represent the capabilities that you want to manage through the AWS IOT-Core service.  These properties will be shared with IOT-Core which keeps a copy of their values in a JSON object called a Shadow.  So the first thing you need to determine is the list of properties you will support from your device.  Properties will vary based upon the specific device being enabled but common properties include power, volume, brightness, color, and input.  You can name your property's anything you want with the following caveats.

* Property names must be unique across a Thing.  If you have a Thing that consists of multiple components, you must make sure that no component uses a property name that another component is using.
* If you are intending for your Thing to be controlled by the Alexa Smart Home Skill, it is convenient to adopt the property names of the specific interface you will be implementing.  More details on Alexa Smart Home Skill interfaces can be found at https://developer.amazon.com/docs/device-apis/message-guide.html.

For each of your device's properties, you will need to develop a propertyToComponent method.  These methods are used by pyIOT to determine how to take a property value received from the AWS IOT-Core service and turn it into a command that can be sent to your device to make the necessary changes so that the device is consistent with the requested change.  Similarly, you will need to develop a componentToProperty method for every message that your device sends that relates to one of the device's properties.

Writing a propertyToComponent method
------------------------------------

@Component.propertyToComponent is the decorator that you use to specify that a method handles a particular property.  It takes two parameters.  The first parameter indicates which property the method handles and the second is a format string which is combined with the return value to form the command which will be sent to the device.

The decorated method must take any valid property value and return a value that when combined with the format parameter results in a command that when sent to the device will cause the device to be consistent with the new property value.  If it receives an invalid value for the property, it should raise a ValueError.  Receipt of an invalid value will be logged and then ignored.  This will leave the desired and reported states within the shadow document inconsistent.

Simple Example
~~~~~~~~~~~~~~

.. code-block:: python

  @Component.propertyToComponent('relayState', 'RELAY{0}')
  def fromRelayState(self, value):
      val = { True: 'ON', False: 'OFF' }.get(value)
      if val: return val
      raise ValueError('{0} is not a valid relayState'.format(value))


Writing a componentToProperty method
------------------------------------

@Component.componentToProperty is the decorator that you use to specify that a method handles a particular message from your device.  It takes two parameters.  The first parameter is the name of the property that the method handles.  The second is a regex string that is used to determine which message the decorated method should handle.  It is also used to extract the value from the message that the method should use to compute the new property value.

The decorated method must convert valid messages into valid property values.  It will receive from pyIOT the name of the property it is being asked to convert and the raw value that pyIOT has extracted from the message.

Writing the regex
~~~~~~~~~~~~~~~~~

There are two purposes of the regex string.  First, it identifies the message that the method will handle and second it identifies what part of the message has the data needed to compute the new property value.

The regex string should exactly match the specific input you expect to receive from your device.  Developing the regex can be relatively straight forward if the automation protocol of your device is well designed but can be challenging if the messages from your device are ambiguous.  You must avoid situations where your regex can match messages that relate to properties that your method is not intended to handle.

The regex string also must identify the sub-string within the message that provides the raw value to be used to compute the new property.  This is specified using the regex group operator which is the parens `()`.  Normally you will only have a single group within your regex.

**Important:**  Getting the regex correct is critical to the proper function of your pyIOT driver. Do not underestimate the difficulty of writing a valid regex.

Example regex

.. code-block:: python

  '^RELAY(ON|OFF)$'

In this example we are expecting a message that contains either 'RELAYON' or 'RELAYOFF'.  There is a single group identified within the regex `(ON|OFF)`.  So the method that handles this message should expect to receive either 'ON' or 'OFF' as the value of the property.  Note that the regex begins with ^ and ends with $.  These regex operators ensure that the match begins at the start of the message must include the entirety of the message. It is generally safer to match an entire message so the use of ^ and $ is encouraged.

Example method

.. code-block:: python

  @Component.componentToProperty('relayState', '^RELAY(ON|OFF)$')
  def toRelayState(self, property, value):
      return  { 'ON': True, 'OFF': False }.get(value)

Notice in this example we are only expected to handle the two possible values ('ON' or 'OFF').  If the regex allowed values that could potentially be invalid, we would want to detect this within the method and raise a ValueError if an invalid value is received.

Supporting a message that updates multiple properties
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

componentToProperty supports the ability to update multiple properties simultaneously if your device's protocol contains messages that provide the values needed within a single message.  Using this feature requires you to provide a list of properties instead of a single property and that you specify a group within the regex for every property value that the method will handle.

Example multi-property method

.. code-block:: python

  @Component.componentToProperty(['powerState', 'brightness'], '^P([0-1])B([0-9]{1,3})$')
  def toLightProperties(self, property, value):
    if property == 'powerState':
      return { '1': True, '0': False }.get(value)
    else:
      val = int(value)
      if val <= 100: return (val)
      raise ValueError('{0} is too large.  Maximum brightness is 100'.format(val))


In this example we are using a lightbulb which sends a message that combines its power state and its brightness setting using the format P#B###.  The P# can be either P0 for power off or P1 for power on.  The B value is a three digit number from 0 to 100.  The regex is set to handle this message format and you should note that as we are supporting two property values (`powerState` and `brightness`) we have two groups within the regex.  You may also notice that the regex will accept values outside the supported brightness value. For this reason, the method verifies that the value is valid before returning it.

Choosing synchronous vs asynchronous communications
---------------------------------------------------

pyIOT's primary communication style is streams.  This style is convenient for a wide variety of device types including devices that communicate over serial interfaces and those that communicate using network interfaces.  Stream protocols fall into two camps; synchronous and asynchronous.  With synchronous communications, a device will not proactively send messages.  It only responds when a command is sent to it.  Asynchronous systems will proactively send messages whenever they have something to communicate whether they have received a command or not.

pyIOT supports both synchronous and asynchronous communications. When running asynchronously, pyIOT creates two threads for each Component, one to listen for messages from the device and one to send commands to it.  For synchronous communications, pyIOT only uses the write thread which handles both sending commands and receiving messages.

If your device supports asynchronous updates you should set synchronous to False when instantiating your Component class.  Otherwise set synchronous to True.

Instantiating Component
-----------------------

Once your Component class is developed you need to instantiate it at run time.  Once it is instantiated, you will then pass it as a parameter to your Thing class when you instantiated it.

Example:

.. code-block:: python

  ser = serial.Serial('/dev/ttyUSB0', 9600, timeout=0.5)
  relayComponent1 = Relay(name = 'RelayComponent1', eol='\n', stream = ser, properties = { 'relayState': 'UNKNOWN' }, synchronous=True)
  relayThing = Thing(endpoint='<your endpoint>', thingName='relay1', rootCAPath='root-CA.crt', certificatePath='relayOne.crt',
    privateKeyPath='relayOne.private.key', region='us-east-1', components=[relayComponent1])

Thing Development
=================

Things handle all of the communications between pyIOT and the AWS IOT-Core service.  They also are the container for all of the components that make up the Thing.  Unless you need your Thing to update some of its components based upon changes that have just occurred, you do not need to create your own subclass of Thing.  However, if you do have that need, you can create a class that inherits from Thing and then overriding the onChange method.

onChange is called whenever a component property is changing.  Its one parameter, updatedProperties, is a dictionary containing all of the properties that have changed and their new values.  onChange can use this information to determine if it wants to update any additional properties.  To do this it returns a list of tuples that contain property name and value pairs for each property that it needs to update.

Example

.. code-block:: python

  class myThing(Thing):

      def onChange(self, updatedProperties):
          rv = []
          # Make sure device is always powered on and set to the 'CD' input
          if updatedProperties.get('powerState') == 'OFF':
              print ('Returning powerState to ON and input to CD')
              rv.append(('powerState','ON'))
              rv.append(('input', 'CD'))
          return rv

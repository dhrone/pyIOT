"""**Simplying the creation of a python-based Internet of Things (IOT) device.**

.. moduleauthor:: dhrone
.. module:: pyIOT

pyIOT enables rapid integration of a device with the Amazon AWS IOT-Core service.  In IOT-Core, a thing is represented by a set of properties which represent the state of the IOT device.  Within IOT-Core, these properties are stored as key-value pairs inside a structure called a device Shadow which is a JSON object containing three key-value pair sets (desired, reported, delta).  When an application wants to cause an IOT device to do something, it changes the desired state within the Shadow to the value that will cause the requested change.  pyIOT listens for these updates and then handles the conversion of the request into the specific message needed by the device to cause the appropriate change to occur.  When the device itself changes, pyIOT also handles converting the data coming from the device into a valid property value and sending that to the IoT-Core Shadow for the IOT device.

pyIOT models an IOT device as a Thing which is composed of at least one but potentially several components.  Each component is responsible for interacting with a physical device that it controls.  This requires the component to monitor the state of the device and update the components property values as appropriate.  It must also accept changes to those property values and then cause the device to change state to be consistent with itself.  The Thing manages the collection of components that make of the IOT device.  It listens for delta messages from IOT-Core which are sent when the desired and reported states for a device differ.  It then figures out which component is responsible for each property that needs to change, and sends a request for change to it.  Similarly, if the component is what has changed, the Thing receives a message from the component and handles sending that back to the IOT-Core service.

"""

from pyIOT.Thing import Thing
from pyIOT.Component import Component

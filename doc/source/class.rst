.. py:module:: pyIOT

Overview
=========

pyIOT models an IOT device as a Thing which is composed of at least one but potentially several components.  Each component is responsible for interacting with a physical device that it controls.  This requires the component to monitor the state of the device and update the components property values as appropriate.  It must also accept changes to those property values and then cause the device to change state to be consistent with itself.  The Thing manages the collection of components that make of the IOT device.  It listens for delta messages from IOT-Core which are sent when the desired and reported states for a device differ.  It then figures out which component is responsible for each property that needs to change, and sends a request for change to it.  Similarly, if the component is what has changed, the Thing receives a message from the component and handles sending that back to the IOT-Core service.

Component
=========
.. autoclass:: Component
  :members:

  **Members:**

Thing
=====
.. autoclass:: Thing
  :members:

  **Members:**

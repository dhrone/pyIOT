Brief Overview of AWS IOT-Core
==============================

pyIOT relies upon the AWS IOT-Core service.  IOT-Core is a highly scalable system to control potentially large populations of IOT devices.  It provides a stable end-point that a controlling application can call to in order to control an IOT device, referred to within IOT-Core as a Thing.  In IOT-Core, a thing is represented by a set of properties which represent the state of the IOT device.  IOT-Core stores these properties as key-value pairs inside a structure called a device Shadow which is a JSON object containing three key-value pair sets (desired, reported, delta).  When an application wants to cause an IOT device to do something, it changes the desired state within the Shadow to the value that will cause the requested change.  pyIOT listens for these updates and then handles the conversion of the request into the specific message needed by the device to cause the appropriate change to occur.  When the device itself changes, pyIOT also handles converting the data coming from the device into a valid property value and sending that to the IoT-Core Shadow for the IOT device.

More details about AWS IOT-Core can be found at https://aws.amazon.com/iot-core/

Case Study
==========

If you have ever owned a stereo made up of separate components (preamp, amp, CD player, DVD player, etc) you know the difficulty of getting all of the settings correct in order to set it up for a particular task.  Want to play a CD?  The preamp has to be on, the CD player has to be on, the preamp has to be to the CD input, and the volume needs to be set to an appropriate level.  This gets even more complicated when you add a TV or a projector to the mix.

In this example, we are going to show how to turn a combination of a popular hi-fi preamp and a popular projector into a single Thing which acts as a TV.  The two devices that will be used are an Anthem AVM20 preamp, and an Epson 1080UB projector.  Both of these represent reasonably common devices that each have their own automation protocol accessible via their serial interfaces.  More recent versions of both are still on the market (as of Aug 2018).

Modeling the TV
===============

To build our TV, we will need to develop Components for the preamp and the projector.  Somewhat boringly we'll call these PreampComponent and ProjectorComponent.  These will both be encapsulated into a Thing we'll call TVThing.

We also need to determine what properties that we are going to use to control our TV.  The properties that we will use are:

* powerState (str): The power status of the TV.  Valid values are 'ON' if TV is on else 'OFF'
* input (str): The current selected input of the TV. Valid values are 'CD', 'DVD', 'TV'
* volume (integer): The current volume level.  Valid values are (0-100).
* muted (bool): The muted setting.  Valid values are True of the TV is muted or False if it is not muted.

These values were chosen because they are the same names that the Alexa Smart Home Skill would use so if we later decide to interface our IOT with that service, we will not have to translate property names.

There is some ambiguity though with these properties.  Our Thing is composed of two separate components, each of which has its own state.  If our TV's powerState is 'ON', is the preamp on, the projector on, both?  We need to determine how we should treat these individual states in our properties.  Volume and muted are straight forward as they only exist on the preamp.  However, the concepts of input and powerState exist on both devices.  Lets start with powerState.  If we were going to listen to music from our CD player, the preamp would be on, but not TV.  So it is reasonable for the powerState of our TV to be 'ON' when the preamp is on, but not the projector.  However, the opposite is not true.  It would not be normal to have the projector on, without the preamp also being on as this would prevent us from hearing the program that is being displayed.  So we are going to assign powerState to the preamp.  We will still need to separately control the projector power though so we will add an additional property to deal with that.  Input is not as simple.  Both devices have inputs that need to be managed.  Let's assume we have the following sources connected to our TV.

CD Player - Connected to preamp's CD input
Cable box - Connected to preamp's TV input and projector's HDMI1 input
Blueray Player - Connected to preamp's DVD input AND projectors HDMI2 input

As you can see, we will need to be able to separately control both the preamp's and the projector's inputs so we will add properties dedicated to both.  So we need to add the following three additional properties:

* inputPreamp (str): The current selected input for the preamp.  Valid values are 'CD', '2-Channel', '6-Channel', 'Tape', 'Radio', 'DVD', 'TV', 'SAT', 'VCR', 'AUX'
* inputProjector (str): The current selected input for the projector.  Valid values are 'HDMI1', 'HDMI2', 'S-VIDEO', 'Component1', 'Component2'
* powerProjector (str): The power status of the projector.  Valid values are 'ON', 'WARMING', 'COOLING', 'OFF'

The last thing we need to determine is how to map the individual component properties into the TV level properties.  We'll do this using the following state table.

.. image:: _static/pyIOT_StateDiagram.jpg

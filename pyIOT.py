# -*- coding: utf-8 -*-
"""pyIOT: making the creation of a python-based Internet of Things (IOT) device easy.

pyIOT enables rapid integration of a device with the Amazon AWS IOT-Core service.  In IOT-Core, a thing is represented by a set of properties which represent the state of the IOT device.  Within IOT-Core, these properties are stored as key-value pairs inside a structure called a device Shadow which is a JSON object containing three key-value pair sets (desired, reported, delta).  When an application wants to cause an IOT device to do something, it changes the desired state within the Shadow to the value that will cause the requested change.  pyIOT listens for these updates and then handles the conversion of the request into the specific message needed by the device to cause the appropriate change to occur.  When the device itself changes, pyIOT also handles converting the data coming from the device into a valid property value and sending that to the IoT-Core Shadow for the IOT device.

pyIOT models an IOT device as a Thing which is composed of at least one but potentially several components.  Each component is responsible for interacting with a physical device that it controls.  This requires the component to monitor the state of the device and update the components property values as appropriate.  It must also accept changes to those property values and then cause the device to change state to be consistent with itself.  The Thing manages the collection of components that make of the IOT device.  It listens for delta messages from IOT-Core which are sent when the desired and reported states for a device differ.  It then figures out which component is responsible for each property that needs to change, and sends a request for change to it.  Similarly, if the component is what has changed, the Thing receives a message from the component and handles sending that back to the IOT-Core service.

"""
from threading import Lock, Thread
import serial
import logging
import json
import re
import queue
import time

from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTShadowClient

class Thing(object):
    ''' A thing is composed of one or more components that publishes their status to the AWS IOT service in the form of a set of properties and accepts changes to those properties updating the underlying components as needed. '''
    _logger = logging.getLogger(__name__)

    def __init__(self, endpoint=None, thingName=None, rootCAPath=None, certificatePath=None, privateKeyPath=None, region=None, components=None):
        ''' Initialize connection to AWS IOT shadow service

        Args:
            endpoint (str): URL of the IOT-Core endpoint assigned.  This is provided by the AWS IOT-Core service.
            thingName (str): The name of your IOT device.  Must be globally unique within your AWS account.
            rootCAPath (str): Path to the file which holds a valid AWS root certificate.
            certificatePath (str): Path to the file which holds the certificate for your IOT device.  Received from AWS IOT-Core during device creation.
            privateKeyPath (str): Path to the file which holds the private key for your IOT device.  Received from AWS IOT-Core during device creation.
            region (str): The name of the AWS region that your IOT device was created in (e.g. 'us-east-1')
            components (:obj:`list` of :obj:`Component`): A list of the component objects that make up the IOT device
        '''

        self._eventQueue = queue.Queue()
        self._localShadow = dict() # dictionary of local property values
        self._propertyHandlers = dict() # dictionary to set which component handles which property values
        self._shadowHandler = self._iotConnect(endpoint, thingName, rootCAPath, certificatePath, privateKeyPath, region)

        components = components if type(components) is list else [ components ] # Convert components to a list of a single component has been provided
        if components is not None:
            for d in components:
                self._registerComponent(d)

    def _iotConnect(self, endpoint, thingName, rootCAPath, certificatePath, privateKeyPath, region):
        ''' Establish connection to the AWS IOT service '''
        # Init AWSIoTMQTTShadowClient
        _myAWSIoTMQTTShadowClient = None
        _myAWSIoTMQTTShadowClient = AWSIoTMQTTShadowClient(thingName)
        _myAWSIoTMQTTShadowClient.configureEndpoint(endpoint, 8883)
        _myAWSIoTMQTTShadowClient.configureCredentials(rootCAPath, privateKeyPath, certificatePath)

        # AWSIoTMQTTShadowClient configuration
        _myAWSIoTMQTTShadowClient.configureAutoReconnectBackoffTime(1, 32, 20)
        _myAWSIoTMQTTShadowClient.configureConnectDisconnectTimeout(10)
        _myAWSIoTMQTTShadowClient.configureMQTTOperationTimeout(5)

        # Connect to AWS IoT
        _myAWSIoTMQTTShadowClient.connect()

        # Create a deviceShadow with persistent subscription
        deviceShadowHandler = _myAWSIoTMQTTShadowClient.createShadowHandlerWithName(thingName, True)

        # Delete shadow JSON doc
        deviceShadowHandler.shadowDelete(self._deleteCallback, 5)

        # Listen on deltas
        deviceShadowHandler.shadowRegisterDeltaCallback(self._deltaCallback)

        return deviceShadowHandler

    def _registerComponent(self, component):
        ''' Register a component as the handler for the set of properties that the component implements '''

        for property in component.properties:
            if property in self._localShadow:
                self._logger.warn('{0} is trying to register {1} which is a property that is already in use.'.format(component.__name__, property))
            self._localShadow[property] = component.properties[property]
            self._propertyHandlers[property] = component
        component.start(self._eventQueue)

    def _deleteCallback(self, payload, responseStatus, token):
        ''' Log result when a request to delete the IOT shadow has been made '''
        if responseStatus == 'accepted':
            self._logger.info("Delete request " + token + " accepted!")
            return

        self._logger.warn({
            'timeout': "Delete request " + token + " time out!",
            'rejected': "Delete request " + token + " rejected!"
        }.get(responseStatus, "Delete request with token " + token + "contained unexpected response status " + responseStatus))

    def _updateCallback(self, payload, responseStatus, token):
        ''' Log result when a request has been made to update the IOT shadow '''
        if responseStatus == 'accepted':
            payloadDict = json.loads(payload)
            self._logger.info("Received delta request: " + json.dumps(payloadDict))
            return

        self._logger.warn({
            'timeout': "Update request " + token + " timed out!",
            'rejected': "Update request " + token + " was rejected!"
        }.get(responseStatus, "Update request " + token + " contained unexpected response status " + responseStatus))

    def _deltaCallback(self, payload, responseStatus, token):
        ''' Receive an delta message from IOT service and forward update requests for every included property to the event queue '''
        print ('Delta message received with content: {0}'.format(payload))
        payloadDict = json.loads(payload)

        for property in payloadDict['state']:
            self._logger.info('Delta Message: processing item [{0}][{1}]'.format(property, payloadDict['state'][property]))
            self._eventQueue.put({'source': '__thing__', 'action': 'UPDATE', 'property': property, 'value': payloadDict['state'][property] })

    def onChange(self, updatedProperties):
        ''' Override this function if you need to update other component properties based upon the change of another property

        Example:
            def onChange(self, updatedProperties):
                rv = []
                # Make sure component is always on and set to the CD input when not watching TV
                if updatedProperties.get('powerState') == 'OFF':
                    print ('Returning powerState to ON and input to CD')
                    rv.append(('powerState','ON'))
                    rv.append(('input', 'CD'))
                return rv

        Note that you can update all property values. This allows you to handle the situation where one IOT property impacts the state of multiple components '''

        return None

    def start(self):
        ''' Start processing events between the IOT service and the associated components '''
        self._main()

    def _main(self):

        while True:
            messages = [ self._eventQueue.get() ]
            self._eventQueue.task_done()

            ''' A new message has come in but it may be a batch of updates so wait for a short time and then read all pending messages '''
            time.sleep(0.1)
            try:
                while True:
                    messages.append( self._eventQueue.get_nowait())
                    self._eventQueue.task_done()
            except queue.Empty:
                pass

            ''' Process all received messages '''
            updatedProperties = dict()
            for message in messages:
                if message['action'] == 'EXIT':
                    ''' If an EXIT message is received then stop processing messages and exit the main thing loop '''
                    return

                if message['action'] == 'UPDATE':
                    if message['source'] == '__thing__':
                        ''' Update is from IOT service.  Determine which component supports the updated property and send an update request to it '''
                        self._propertyHandlers[message['property']].updateComponent(message['property'], message['value'])
                    else:
                        ''' Update is from component. Add it to updatedProperties '''
                        updatedProperties[message['property']] = message['value']

                        localPropertyChanges = self.onChange(updatedProperties)
                        if localPropertyChanges:
                            for k, v in localPropertyChanges:
                                self._propertyHandlers[k].updateComponent(k,v)

            ''' If there are properties to report to the IOT service, send an update message '''
            updateNeeded = False
            payloadDict = { 'state': { 'reported': {}, 'desired': {} } }
            for property, value in updatedProperties.items():
                if self._localShadow[property] != value:
                    print ('IOT UPDATED: [{0}:{1}]'.format(property, value))
                    updateNeeded = True
                    payloadDict['state']['reported'] = updatedProperties
                    payloadDict['state']['desired'] = updatedProperties
            if updateNeeded:
                self._shadowHandler.shadowUpdate(json.dumps(payloadDict), self._updateCallback, 5)

class Component(object):
    ''' Component that makes up part of an IOT thing.

    Components are responsible for monitoring the underlying physical component, updating dependent properties associated with the component, and responding to updates of those properties by sending the appropriate commands to the component to get it to update its status to be consistent with its published properites '''
    _logger = logging.getLogger(__name__)

    def __init__(self, name = None, stream = None, properties = None, eol='\n', timeout=5, synchronous=False):
        ''' Initialize component driver and set it to receive updates from the Thing

        Args:
             name (str): The name of the component
            stream (:obj:`IOBase`): A stream object that receives and can send data to the physical device
            properties (dict): A dictionary composed of the properties the component manages and their initial values
            eol (str, optional): The substring that represents end of command within the stream for the component.  Default is newline (e.g. `\\n`)
            timeout (float, optional): The time in seconds to wait for input from the device before the read attempt times out.  Default is 5 seconds.
            synchronous (bool, optional): Determines how reading and writing are handled.  Synchronous devices only respond when written to.  Default is False (e.g. asynchronous)
        '''

        self._stream = stream
        self._eol = eol
        self._timeout = timeout
        self._synchronous = synchronous
        self.properties = properties # dictionary of the properties and starting values for component
        self.__name__ = name if name is not None else self.__class__.__name__
        self._componentQueue = queue.Queue()
        self._readlock = Lock()
        self._waitFor = None # Are we waiting for a specific value from the component
        self._exit = False # Set when a request has been made to exit the component driver

    def __del__(self):
        self._close()

    def start(self, eventQueue):
        ''' Start the threads that will read and write data to the device.  If the device is asynchronous two threads will be started.  If synchronous only the write thread will be used.

        Args:
            eventQueue (:obj:`Queue`): The queue of the Thing that will be used to send back reported state messages

        '''
        self._eventQueue = eventQueue

        # Starting event loops
        _threadWrite = Thread(target=self._writeLoop)
        _threadWrite.start()

        # If component is asynchronous, start an independent read thread
        if not self._synchronous:
            _threadRead = Thread(target=self._readLoop)
            _threadRead.start()

    def updateComponent(self, property, value):
        ''' Send message to component to tell it to update one of its property values '''
        self._componentQueue.put({'source': '__thing__', 'action': 'UPDATE', 'property': property, 'value': value })

    def _updateThing(self, property, value):
        ''' Send message to thing telling it to update its thing shadow to reflect the component's reported state '''
        self._eventQueue.put({'source': self.__name__, 'action': 'UPDATE', 'property': property, 'value': value })

        # update local property value
        self.properties[property] = value

    def exit(self):
        ''' Shut down component driver '''
        self._exit = True
        self._componentQueue.put({'action': 'EXIT'})

    @classmethod
    def componentToProperty(cls, property, regex):
        ''' Specify the method that should be used to handle a particular response from the component.

        A basic challenge when creating an AWS IOT driver is how to take state information from the component and convert it to the values you want to use to represent the component's state.  componentToProperty allows you to decorate a set of methods that handle this translation.

        Parameters:
          property (str): the property name (or names) that the response is updating
          regex (str): A regex that exactly matches the input

          The regex must include a group around the value that will be used to update the property. The group value is what will be passed into the decorated function.
          The regex string should match the entire response to make sure that all of the response is correctly included in the property update.

        Decorated method:
            A method decorated by componentToProperty must accept the name of the parameter that is being handled and the value received from the component.  This value is extracted from the component's response using the regex included within the componentToProperty decoration call.  Only the matched portion of the response (e.g. the part included within the parenthesis) will be passed into your method.
            Parameters:
              property (str): provides the property name that needs to be updated
              value (str): provides the value received within the component's response

             Returns the value that the IOT service should assign to the property.  Any variable types allowed by the IOT service are supported.

        Examples: (from Anthem AVM projector)
            @Component.componentToProperty('powerState', '^P1P([01])$')
            def toPowerState(self, property, value):
                return { '1': 'ON', '0': 'OFF' }.get(value, 'ERR: {0} INVALID {1} VALUE'.format(value, property))

            In this example our component sends P1P1 or P1P0 depending on whether the components is on or off.  We have decided that the IOT property name we will use to record whether the component is on or off will be called 'powerState'.  Two things are worth noticing about the supplied regex.  First, the regex begins with the ^ symbol and ends with the $ symbol.  This forces the match to begin at the start of the response and end at the very end of the response.  This is the safest way to handle a match.  Second, the parenthesis surround the [01] term.  Because of this, the decorated function should expect to only receive a '1' or a '0' as input for its value parameter.

            @Component.componentToProperty(['input', 'volume', 'muted'], '^P1S([0-9])V([+-][0-9]{2}[\\.][0-9])M([01])D[0-9]E[0-9]$')
            def avmcombinedResponse(self, property, value):
                return { 'input': self.toInput, 'volume': self.toVolume, 'muted': self.toMuted }.get(property)(property, value)

            In our second example we have provided a list of three properties and the provided regex includes exactly three groups.  When used in this way, you should expect the decorated function to be called three times whenever the matching input is sent from the component.  This is once per property.  In each call, the property that is being handled will be provided for the property parameter and the corresponding group value will be provided for the value parameter. '''

        def decorateinterface(func):
            transform = getattr(func, '__componentToProperty__', {})
            cre = re.compile(regex)
            transform[cre] = (property, func)
            func.__componentToProperty__ = transform
            return func

        return decorateinterface

    @classmethod
    def propertyToComponent(cls, property, cmd):
        ''' Specify the method that should be used to handle a request from the IOT service to change the component's state.

        A basic challenge when creating an AWS IOT driver is how to take a request from the IOT service to update one of the IOTs properties and translate that into the input the component needs to change its state accordingly.  propertyToComponent allows you to decorate a set of methods that handle this translation.

        Parameters:
          property (str): the name of the property that has been updated
          cmd (str): A string which specifies how to format the response that will be sent to the component

        Decorated method:
            A method decorated by propertyToComponent must translate the received property value into an appropriate command which will be forwarded to the component to cause its state to change in compliance with the property's new value.

            Parameters:
              property (str): provides the property name that has been updated
              value (str): provides the updated value of the property

              Returns the value which should be sent to the component to cause it to change its state

              Note: raise a ValueError if you receive a property value that you cannot handle

        Examples: (from Anthem AVM projector)
            @Component.propertyToComponent('powerState', 'P1P{0}')
            def powerStateToComponent(self, value):
                val = { 'ON': '1', 'OFF': '0' }.get(value)
                if val:
                    return val
                raise ValueError('{0} is not a valid powerState'.format(value))

            In this example, the powerState property has two allowed values ['ON', 'OFF'] and the component expects to be sent the string 'P1P1' to turn itself on, and 'P1P0' to turn itself off.  When the IOT service updates the powerState property, the updated value will be sent to our method.  Our method returns either a '1' or a '0' as appropriate which is then combined with the format string 'P1P{0}' to compute the full value that will be sent to the component.'''

        def decorateinterface(func):
            transform = getattr(func, '__propertyToComponent__', {})
            transform[property] = (cmd, func)
            func.__propertyToComponent__ = transform
            return func

        return decorateinterface

    @classmethod
    def _componentToProperty(cls, value):
        for supercls in cls.__mro__:  # This makes inherited Appliances work
            for method in supercls.__dict__.values():
                d2pList = getattr(method, '__componentToProperty__', {})
                for cre, (property, method) in d2pList.items():
                    match = cre.match(value)
                    if match:
                        return (property, method, match)
        return None

    @classmethod
    def _propertyToComponent(cls, property):
        for supercls in cls.__mro__:  # This makes inherited Appliances work
            for method in supercls.__dict__.values():
                p2dList = getattr(method, '__propertyToComponent__', {})
                if p2dList and property in p2dList:
                    return p2dList.get(property)

    def _readLoop(self):
        ''' Main event loop for reading from component '''
        print ('Starting {0} readLoop'.format(self.__name__))
        while not self._exit:
            val = self.read()
            if val:
                #print ('{0}:[{1}]'.format(self.__name__, val.replace('\r','\\r')))
                self._processComponentResponse(val)

    def _processComponentResponse(self, val):
        ret = self._componentToProperty(val) # Retrieve appropriate handler to translate component value into property value
        if ret:
            (property, method, match) = ret
            if type(property) is not list: property = [ property ]

            for i in range(len(property)):
                # Extract out each match group and send to method to get it translated from the value from the component to the property value
                mval = match.group(i+1)
                xval = method(self, property[i], mval)

                if self.properties[property[i]] != xval:
                    # Send updated property to Thing
                    self._updateThing(property[i], xval)
#        else:
#            print ('{0}:[{1}] Ignored'.format(self.__name__, val.replace('\r','\\r')))


    def _writeLoop(self):
        ''' Main event loop for writing to component '''
        print ('Starting {0} writeLoop'.format(self.__name__))

        while not self._exit:
            try:
                # Wait for ready state to be reached
                while not self.ready():
                    print ('{0} Sleeping ...'.format(self.__name__))
                    time.sleep(5)
                    raise queue.Empty

                message = self._componentQueue.get(block=True, timeout=5)
                self._componentQueue.task_done()

                if message['action'].upper() == 'EXIT':
                    return
                elif message['action'].upper() == 'UPDATE':
                    print ('IOT requests [{0}:{1}]'.format(message['property'], message['value']))
                    ret = self._propertyToComponent(message['property'])
                    if ret:
                        (cmd, method) = ret

                        # Send updated property to component
                        try:
                            val = self.write(cmd.format(method(self,message['value'])))
                        except ValueError as e:
                            val = None
                            print ('{0}. Component state unchanged'.format(e))

                        # If component is synchronous, it likely returned a response from the command we just sent
                        if val:
                            # If so, process it
                            self._processComponentResponse(val)
                    else:
                        self._logger.warn('{0} has no property that matches {1}'.format(self.__name__,message['property']))

            except queue.Empty:
                # If nothing waiting to be written or the component is not ready, send a query to get current component status
                qs = self.queryStatus()
                if qs:
                    # Get the query to send.  If the query is a list, process each query individually
                    qs = qs if type(qs) is list else [ qs ]
                    for q in qs:
                        val = self.write(q)
                        if val:
                            self._processComponentResponse(val)

                continue

    def _read(self, eol=b'\n', timeout=5):
        eol = eol.encode() if type(eol) is str else eol
        with self._readlock:
            retval = self._readresponse(eol, timeout)
        return retval

    def _readresponse(self, eol=b'\n', timeout=5):
        last_activity = time.time()
        buffer = b''
        while True:
            c = self._stream.read()
            if c:
                buffer += c
                last_activity = time.time()
                if buffer.find(eol)>=0:
                    retval = buffer[:buffer.find(eol)]
                    break
            elif time.time() - last_activity > timeout:
                retval = buffer
                break
        return retval.decode()

    def _write(self, value, eol=b'\n', timeout=5, synchronous=False):
        value = value.encode() if type(value) is str else value
        eol = eol.encode() if type(eol) is str else eol

        # If component communicates synchronously, after sending request, wait for response
        # reading input until receiving the eol value indicating that it is done responding
        if synchronous:
            with self._readlock:
                self._stream.write(value)
                retval = self._readresponse(eol, timeout)
        else:
            self._stream.write(value)
            retval = b''
        return retval.decode()

    def _close(self):
        self._stream.close()

    ''' Customize IO functionality by overriding these methods '''
    def read(self):
        ''' Override this method if your component does not support a standard stream for input/output '''
        return self._read(self._eol, self._timeout)

    def write(self,value):
        ''' Override this method if your component does not support a standard stream for input/output'''
        return self._write(value, self._eol, self._timeout, self._synchronous)

    def close(self):
        ''' Override this method if your component does not support a standard stream for input/output '''
        self._close()

    def ready(self):
        ''' Override this method if your component occasionally stops responding during a state change such as power on/off '''
        return True

    def queryStatus(self):
        ''' Override this function if you want to periodically query your component for status.  You can check the component state (such as power status) to determine what query to send.  The response can be either a string or a list of strings.  If you return a list, each list item will be sent to the component individually including gathering and handling any response the query generates.

        Example: (from an Epson ESC/VP21 compliant projector)
            def queryStatus(self):
                if self.properties['powerState'] == 'ON':
                    return ['PWR?\r','SOURCE?\r'] # Send two queries; PWR? to request current power status and SOURCE? to determine what video input is selected
                else:
                    return 'PWR?\r' # If power is off, the project will not respond to the SOURCE? query so only check to see if the power state has changed.
        '''
        return None

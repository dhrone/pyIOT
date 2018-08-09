# -*- coding: utf-8 -*-
from threading import Lock, Thread
import serial
import logging
import json
import re
import queue
import time

class Component(object):
    ''' Components are responsible for monitoring the underlying physical component, updating dependent properties associated with the component, and responding to updates of those properties by sending the appropriate commands to the component to get it to update its status to be consistent with its published properites

    Args:
        name (str): The name of the component
        stream (:obj:`IOBase`): A stream object that receives and can send data to the physical device
        eol (str, optional): The substring that represents end of command within the stream for the component.  Default is newline (e.g. `\\n`)
        timeout (float, optional): The time in seconds to wait for input from the device before the read attempt times out.  Default is 5 seconds.
        synchronous (bool, optional): Determines how reading and writing are handled.  Synchronous devices only respond when written to.  Default is False (e.g. asynchronous)

    '''
    _logger = logging.getLogger(__name__)

    def __init__(self, name = None, stream = None, eol='\n', timeout=5, synchronous=False):
        ''' Initialize component driver and set it to receive updates from the Thing '''

        self._stream = stream
        self._eol = eol
        self._timeout = timeout
        self._synchronous = synchronous
        self.__name__ = name if name is not None else self.__class__.__name__
        self._componentQueue = queue.Queue()
        self._readlock = Lock()
        self._waitFor = None # Are we waiting for a specific value from the component
        self._exit = False # Set when a request has been made to exit the component driver

        self._initializeProperties() # Determine what properties are being handled

    def __del__(self):
        self._close()

    def _start(self, eventQueue):
        ''' Start the threads that will read and write data to the device.  If the device is asynchronous two threads will be started.  If synchronous only the write thread will be used.

        Args:
            eventQueue (:obj:`Queue`): The eventQueue allows the component to send property updates back to the Thing that it belongs to.

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
        ''' This method is normally called by the Thing that contains the component to tell the component to update its status.  It can also be called by other processes that need to tell the component to update itself

        Args:
            property (`str`): The name of the property being updated
            value (any valid property value): The value the property has changed to

        '''
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
        ''' Decorates the method that should be used to convert a particular response from the component to a property value.

        A basic challenge when creating an AWS IOT driver is how to take state information from the component and convert it to the values you want to use to represent the component's state.  **componentToProperty** allows you to decorate methods to handle each required translation from raw component input into the resulting property value(s).

        Args:
          property (str or `list` of str): the property name (or names) that the response is updating
          regex (str): A regex that exactly matches a valid message coming from the physical component.  The regex must include a group around each value that will be used to update the properties. The group value is what will be passed into the decorated function.  The regex string should match the entire response to make sure that all of the message is correctly included in the property update.

        **Examples:**

            *These examples are from code used to control an Anthem AVM processor*

            A method decorated by **componentToProperty** must accept the name of the parameter that is being handled and the value extracted from the message that was received from the component.  This value is extracted using the regex included within the componentToProperty decoration call.  Only the matched portion of the response (e.g. the part included within the parenthesis) will be passed into your method.  The method must return the value that the IOT service should assign to the property.  Any variable types allowed by the IOT service are supported.

            If the method receives a property name or value that it can not handle, it should raise a TypeError or ValueError.

            1st example:

            .. code-block:: python

                @Component.componentToProperty('powerState', '^P1P([01])$')
                def toPowerState(self, property, value):
                    retval =  { '1': 'ON', '0': 'OFF' }.get(value)
                    if retval:
                        return retval
                    raise ValueError('{0} INVALID {1} VALUE'.format(value, property))

            In this example our AVM processor sends `P1P1` or `P1P0` depending on whether the AVM processor is on or off.  We have decided that the IOT property name we will use to record whether the AVM processor is on or off will be called 'powerState'.  Two things are worth noticing about the supplied regex.  First, the regex begins with the ^ symbol and ends with the $ symbol.  This forces the match to begin at the start of the response and end at the very end of the response.  This is the safest way to handle a match.  Second, the parenthesis surrounding the `[01]` term.  The parens designate that the term inside is a match group.  It is this term that controls what value the decorated function should expect to receive.  In this case it will be either a '1' or a '0'.

            2nd example:

            .. code-block:: python

                @Component.componentToProperty(['input', 'volume', 'muted'], '^P1S([0-9])V([+-][0-9]{2}[\\.][0-9])M([01])D[0-9]E[0-9]$')
                def avmcombinedResponse(self, property, value):
                    if property == 'input':
                        val = { '0': 'CD', '3': 'TAPE', '5': 'DVD', '6': 'TV', '7': 'SAT', '8': 'VCR', '9': 'AUX' }.get(value)
                        if val:
                            return val
                        raise ValueError('{0} is not a valid value for property {1}'.format(value, property))
                    elif property == 'volume':
                        try:
                            rawvol = float(value)
                        except:
                            raise ValueError('{0} is not a valid value for property {1}'.format(value, property))
                        volarray = [-50, -35, -25, -21, -18, -12, -8, -4, 0, 5, 10 ]
                        for i in range(len(volarray)):
                            if rawvol <= volarray[i]:
                                return i*10
                        else:
                            # volume greater than max array value
                            return 100
                    elif property == 'muted':
                        val = { '1': True, '0': False }.get(value)
                        if val is not None:
                            return val
                        raise ValueError('{0} is not a valid value for property {1}'.format(value, property))
                    else:
                        raise TypeError('ERR: {0} INVALID {1} VALUE'.format(value, property))

            In our second example we show how to handle multiple properties from a single device message.  The AVM processor can send messages which refer to multiple properties.  In this example we are handling a message which provides the selected input, current volume, the mute status.  We want to extract those three properties.  So, the provided regex includes exactly three match groups.  When used in this way, you should expect the decorated function to be called three times whenever the matching input is sent from the component.  This is once per property.  In each call, the property that is being handled will be provided for the property parameter and the corresponding group value will be provided for the value parameter.

        '''

        def decorateinterface(func):
            transform = getattr(func, '__componentToProperty__', {})
            cre = re.compile(regex)
            transform[cre] = (property, func)
            func.__componentToProperty__ = transform
            return func

        return decorateinterface

    @classmethod
    def propertyToComponent(cls, property, cmd):
        ''' Decorates the method that should be used to convert a property value into a component command.

        A basic challenge when creating an AWS IOT driver is how to respond to a change in a property value and translate that into the input the component needs to change its state accordingly.  propertyToComponent allows you to decorate a set of methods that handle these translations.

        Args:
          property (str): the name of the property that has been updated
          cmd (str): A string which specifies how to format the response that will be sent to the component

        **Example:**

            *This examples is from code used to control an Anthem AVM processor*

            A method decorated by **propertyToComponent** must translate the received property value into an appropriate command which will be forwarded to the component to cause its state to change in compliance with the property's new value.  It must accept two parameters; property (str) which provides the property name that has been updated and value (str) which provides the new property value.  The function must return the command that needs to be send to the component to get it to change to the desired state.

            If the method can not determine what command to return because of an unexpected property name or value, you should raise a TypeError or a ValueError.

            .. code-block:: python

                @Component.propertyToComponent('powerState', 'P1P{0}')
                def powerStateToComponent(self, value):
                    val = { 'ON': '1', 'OFF': '0' }.get(value)
                    if val:
                        return val
                    raise ValueError('{0} is not a valid powerState'.format(value))

            In this example, the powerState property has two allowed values ['ON', 'OFF'] and the AVM processor expects to be sent the string 'P1P1' to turn itself on, and 'P1P0' to turn itself off.  When the IOT service updates the powerState property, the updated value will be sent to our method.  Our method returns either a '1' or a '0' as appropriate which is then combined with the format string 'P1P{0}' to compute the full value that will be sent to the component.

    '''

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
                c2pList = getattr(method, '__componentToProperty__', {})
                for cre, (property, method) in c2pList.items():
                    match = cre.match(value)
                    if match:
                        return (property, method, match)
        return None

    @classmethod
    def _propertyToComponent(cls, property):
        for supercls in cls.__mro__:  # This makes inherited Appliances work
            for method in supercls.__dict__.values():
                p2cList = getattr(method, '__propertyToComponent__', {})
                if p2cList and property in p2cList:
                    return p2cList.get(property)

    def _initializeProperties(self):
        cls = self.__class__
        p2cProperties = {}
        c2pProperties = {}
        for supercls in cls.__mro__:  # This makes inherited Appliances work
            for method in supercls.__dict__.values():
                c2pList = getattr(method, '__componentToProperty__', {})
                p2cList = getattr(method, '__propertyToComponent__', {})
                if p2cList:
                    for k in p2cList:
                        p2cProperties[k] = 'UNKNOWN'
                if c2pList:
                    for cre, (property, method) in c2pList.items():
                        if type(property) is list:
                            for p in property:
                                c2pProperties[p] = 'UNKNOWN'
                        else:
                            c2pProperties[property] = 'UNKNOWN'

        # Normally, every property should have both a componentToProperty and propertyToComponent method

        # Log any properties included in propertyToComponent methods that do not show up in a componentToProperty method
        for p in { k: p2cProperties[k] for k in p2cProperties if k not in c2pProperties }:
            self._logger.warn('No componentToProperty method found for {0}'.format(p))

        # Log any properties included in componentToProperty methods that do not show up in a propertyToComponent method
        for p in { k: c2pProperties[k] for k in c2pProperties if k not in p2cProperties }:
            self._logger.warn('No propertyToComponent method found for {0}'.format(p))

        # Combine lists
        self.properties = p2cProperties
        for p in c2pProperties:
            self.properties[p] = c2pProperties[p]

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
                try:
                    xval = method(self, property[i], mval)
                    if self.properties[property[i]] != xval:
                        # Send updated property to Thing
                        self._updateThing(property[i], xval)
                except (ValueError, AssertionError, TypeError) as e:
                    self._logger.warn('Unable to process component response.  Error: {0}'.format(e))

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
                        except (ValueError, TypeError, AssertionError) as e:
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
        ''' Override this method if your component occasionally stops responding during a state change such as power on/off

        Returns:
            `True` if device can receive new commands

            `False` if device is busy and ignoring input

        '''
        return True

    def queryStatus(self):
        ''' Override this function if you want to periodically query your component for status.  You can check the component state (such as power status) to determine what query to send.  The response can be either a string or a list of strings.  If you return a list, each list item will be sent to the component individually including gathering and handling any response the query generates.

        **Example:**

            *This example is from code used to control an Epson ESC/VP21 compliant projector*

            .. code-block:: python

                def queryStatus(self):
                    if self.properties['powerState'] == 'ON':
                        return ['PWR?\\r','SOURCE?\\r'] # Send two queries; PWR? to request current power status and SOURCE? to determine what video input is selected
                    else:
                        return 'PWR?\\r' # If power is off, the project will not respond to the SOURCE? query so only check to see if the power state has changed.
        '''
        return None

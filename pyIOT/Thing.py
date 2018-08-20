# -*- coding: utf-8 -*-
import logging
import json
import queue
import time

from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTShadowClient

class Thing(object):
    ''' A thing is composed of one or more components that publishes their status to the AWS IOT service in the form of a set of properties and accepts changes to those properties updating the underlying components as needed.

        Args:
            endpoint (`str`): URL of the IOT-Core endpoint assigned.  This is provided by the AWS IOT-Core service
            thingName (`str`): The name of your IOT device.  Must be globally unique within your AWS account
            rootCAPath (`str`): Path to the file which holds a valid AWS root certificate
            certificatePath (`str`): Path to the file which holds the certificate for your IOT device.  Received from AWS IOT-Core during device creation
            privateKeyPath (`str`): Path to the file which holds the private key for your IOT device.  Received from AWS IOT-Core during device creation
            region (`str`): The name of the AWS region that your IOT device was created in (e.g. 'us-east-1')
            components (`list` of :obj:`Component`): A list of the component objects that make up the IOT device

    '''
    _logger = logging.getLogger(__name__)

    def __init__(self, endpoint=None, thingName=None, rootCAPath=None, certificatePath=None, privateKeyPath=None, region=None, components=None):
        ''' Initialize connection to AWS IOT shadow service '''

        self.__name__ = thingName
        self._eventQueue = queue.Queue()
        self._localShadow = dict() # dictionary of local property values
        self._propertyHandlers = dict() # dictionary to set which component handles which property values
        self._iotConnect(endpoint, thingName, rootCAPath, certificatePath, privateKeyPath, region)

        self._components = components if type(components) is list else [ components ] # Convert components to a list of a single component has been provided
        if self._components is not None:
            for d in self._components:
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

        self._shadowClient = _myAWSIoTMQTTShadowClient
        self._shadowHandler = deviceShadowHandler

    def _iotDisconnect(self):
        self._shadowHandler.shadowUnregisterDeltaCallback()
        self._shadowClient.disconnect()

    def _registerComponent(self, component):
        ''' Register a component as the handler for the set of properties that the component implements '''

        for property in component.properties:
            if property in self._localShadow:
                self._logger.warn("{0}'s component {1} is trying to register {2} which is a property that is already in use.".format(self.__name__, component.__name__, property))
            self._localShadow[property] = component.properties[property]
            self._propertyHandlers[property] = component
        component._start(self._eventQueue)

    def _deleteCallback(self, payload, responseStatus, token):
        ''' Log result when a request to delete the IOT shadow has been made '''
        if responseStatus == 'accepted':
            return

        self._logger.warn("{0}'s request to delete shadow failed.  Reason given: {1}".format(self.__name__, responseStatus))

    def _updateCallback(self, payload, responseStatus, token):
        ''' Log result when a request has been made to update the IOT shadow '''
        if responseStatus == 'accepted':
            payloadDict = json.loads(payload)
            return

        self._logger.warn("{0}'s request to update shadow failed.  Reason given: {1}".format(self.__name__, responseStatus))

    def _deltaCallback(self, payload, responseStatus, token):
        ''' Receive an delta message from IOT service and forward update requests for every included property to the event queue '''
        payloadDict = json.loads(payload)

        for property in payloadDict['state']:
            self._eventQueue.put({'source': '__thing__', 'action': 'UPDATE', 'property': property, 'value': payloadDict['state'][property] })

    def start(self):
        ''' Start processing events between the IOT service and the associated components '''
        self._main()

    def onChange(self, updatedProperties):
        ''' Override this function if you need to update other component properties based upon the change of another property

        Args:
            updatedProperties (`dict`): A dictionary of property values that have just changed

        Returns:
            A dictionary consisting of property:values changed by the onChange method (e.g. {'powerState', 'ON'})

        Example:

        .. code-block:: python

            def onChange(self, updatedProperties):
                rv = {}
                # Make sure component is always on and set to the CD input when not watching TV
                if updatedProperties.get('powerState') == 'OFF':
                    rv['powerState'] = 'ON'
                    rv['input'] = 'CD'
                return rv

        Note that you can update all property values. This allows you to handle the situation where one IOT property impacts the state of multiple components

        '''

        return None

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
                    self._logger.info("{0} is exiting".format(self.__name__))
                    self._iotDisconnect()
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
                            for k, v in localPropertyChanges.items():
                                try:
                                    self._propertyHandlers[k].updateComponent(k,v)
                                except KeyError:
                                    self._logger.warn("{0}'s onChange method requested a change for {1} which is not handled by any component".format(self.__name__,k))

            ''' If there are properties to report to the IOT service, send an update message '''
            updateNeeded = False
            payloadDict = { 'state': { 'reported': {}, 'desired': {} } }
            for property, value in updatedProperties.items():
                if self._localShadow[property] != value:
                    self._logger.info('{0} updated IOT [{1}:{2}]'.format(self.__name__, property, value))
                    self._localShadow[property] = value
                    updateNeeded = True
                    payloadDict['state']['reported'] = updatedProperties
                    payloadDict['state']['desired'] = updatedProperties
            if updateNeeded:
                self._shadowHandler.shadowUpdate(json.dumps(payloadDict), self._updateCallback, 5)

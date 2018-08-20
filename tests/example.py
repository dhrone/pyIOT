from pyIOT import Thing, Component


# For SPHINX: Start preampComponent
class preampComponent(Component):

    ''' COMPONENT TO PROPERTY METHODS '''

    # convert anthem power message into powerState property
    @Component.componentToProperty('powerState', '^P1P([0-1])$')
    def avmToPowerState(self, property, value):
        val = { '1': 'ON', '0': 'OFF' }.get(value)
        if val:
            if val == 'ON' and self.properties['powerState'] == 'OFF':
                ''' When the preamp turns on, request an immediate status query '''
                self.requestStatus()
            return val
        raise ValueError('{0} is not a valid value for property {1}'.format(value, property))

    # convert anthem input message into input property
    @Component.componentToProperty('input', '^P1S([0-9])$')
    def avmToInput(self, property, value):
        val = { '0': 'CD', '1': '2-Ch', '2': '6-Ch', '3': 'TAPE', '4':'RADIO', '5': 'DVD', '6': 'TV', '7': 'SAT', '8': 'VCR', '9': 'AUX' }.get(value)
        if val: return val
        raise ValueError('{0} is not a valid value for property {1}'.format(value, property))

    # convert anthem volume message into volume property
    @Component.componentToProperty('volume', '^P1VM([+-][0-9]{1,2}(?:[\\.][0-9])?)$')
    def avmToVolume(self, property, value):
        try:
            rawvol = float(value)
            return self._dbToVolume(rawvol)
        except:
            raise ValueError('{0} is not a valid value for property {1}'.format(value, property))

    # convert muted message into muted property
    @Component.componentToProperty('muted', '^P1M([0-1])$')
    def avmToMuted(self, property, value):
        val = { '1': True, '0': False }.get(value)
        if val is not None: return val
        raise ValueError('{0} is not a valid value for property {1}'.format(value, property))

    # This is the response to the query command.  It returns information for several properties
    # Note that we are passing it a list of properties and that the regex has multiple match groups
    @Component.componentToProperty(['input', 'volume', 'muted'], '^P1S([0-9])V([+-][0-9]{1,2}[\\.][0-9])M([0-1])D[0-9]E[0-9]$')
    def avmcombinedResponse(self, property, value):
        return { 'input': self.avmToInput, 'volume': self.avmToVolume, 'muted': self.avmToMuted }.get(property)(property, value)

    ''' PROPERTY TO COMPONENT METHODS '''

    # Command preamp to turn on or off
    @Component.propertyToComponent('powerState', 'P1P{0}\n')
    def powerStateToAVM(self, value):
        val = { 'ON': '1', 'OFF': '0' }.get(value)
        if val: return val
        raise ValueError('{0} is not a valid powerState'.format(value))

    # Command preamp to change input
    @Component.propertyToComponent('input', 'P1S{0}\n')
    def inputToAVM(self, value):
        val = { 'CD': '0', '2-Ch': '1', '6-Ch': '2', 'TAPE': '3', 'RADIO': '4', 'DVD': '5', 'TV': '6', 'SAT': '7', 'VCR': '8', 'AUX': '9' }.get(value)
        if val: return val
        raise ValueError('{0} is not a valid input'.format(value))

    # Command preamp to change its volume
    @Component.propertyToComponent('volume', 'P1VM{0}\n')
    def volumeToAVM(self, value):
        if type(value) is int: return self._volumeToDb(value)
        raise ValueError('{0} is not a valid volume'.format(value))

    # Command preamp to mute or unmute
    @Component.propertyToComponent('muted', 'P1M{0}\n')
    def muteToAVM(self, value):
        val = { True: '1', False: '0' }.get(value)
        if val: return val
        raise ValueError('{0} is not a valid muted value'.format(value))

    ''' STATUS QUERY METHOD '''

    def queryStatus(self):
        ''' The preamp only allows you to query its full status when it is on.  When it is off you can only ask for power state '''
        if self.properties['powerState'] == 'ON':
            return 'P1?\n'
        else:
            return 'P1P?\n'

    ''' UTILITY METHODS '''

    ''' The remaining methods are to handle the conversion from volume to db and vice-versa '''
    @staticmethod
    def _computeVolumeToDb(v):
        ''' Convert a volume in the range 0 to 100 into a db value.  This provides an exponential curve from -69db to +10db. '''
        return float( -1*((100-v)**2.25)/400)+10

    ''' compute array of possible volume to db values '''
    _volArray = []
    for v in range (0,101):
      _volArray.append(_computeVolumeToDb.__func__(v))
    del v

    @classmethod
    def _volumeToDb(cls, v):
        ''' Get volume from volArray and round to nearest 0.5db '''
        return int(5*round(float(cls._volArray[v])/5*10))/10

    @classmethod
    def _dbToVolume(cls, db):
        ''' Find the closest db value from volArray and return corresponding volume value '''
        ar = cls._volArray
        s = 0
        e = len(ar)-1
        cp = int(e/2)
        while True:
            if e == s: return e
            if e-s == 1:
                if db <= ((ar[e] - ar[s])/2)+ar[s]: return s
                return e
            if db == ar[cp]: # Exact match.  Got lucky
                for i in range(cp+1, e+1):
                    if db < ar[i]: return cp
                    cp = i
                return cp
            if db < ar[cp]: # value is less than the current position
                if cp == 0: return cp # If we are already at the start of the array then the value is below the lowest value.  Return 0.
                e = cp
            if db > ar[cp]: # value is greater than current position
                if cp == len(ar)-1: return cp # If we are at the end of the array, the value is bigger than the highest value.  Return len of array
                s = cp
            cp = int((e-s)/2)+s
# For SPHINX: End preampComponent

# For SPHINX: Start projectorComponent
class projectorComponent(Component):


    ''' COMPONENT TO PROPERTY METHODS '''

    @Component.componentToProperty('projPowerState', '^PWR=([0-9]{2})\\r?$')
    def toProjPowerState(self, property, value):
        val = { '00': 'OFF', '01': 'ON', '02': 'WARMING', '03': 'COOLING', '04': 'STANDBY', '05': 'ABNORMAL' }.get(value)
        if val:
            if val in ['ON', 'WARMING'] and self.properties['projPowerState'] == 'OFF':
                self.requestStatus()
            return val
        raise ValueError('{0} is not a valid value for property {1}'.format(value, property))

    @Component.componentToProperty('projInput', '^SOURCE=([a-zA-Z0-9]{2})\\r?$')
    def toProjInput(self, property, value):
        val = { '30': 'HDMI1', 'A0': 'HDMI2', '41': 'VIDEO', '42': 'S-VIDEO' }.get(value)
        if val: return val
        raise ValueError('{0} is not a valid value for property {1}'.format(value, property))

    ''' PROPERTY TO COMPONENT METHODS '''

    @Component.propertyToComponent('projPowerState', 'PWR {0}\r')
    def projPowerStateToProj(self, value):
        if value in ['ON', 'OFF']: return value
        raise ValueError('{0} is not a valid powerState'.format(value))

    @Component.propertyToComponent('projInput', 'SOURCE {0}\r')
    def projInputToProj(self, value):
        val = { 'HDMI1': '30', 'HDMI2': 'A0', 'VIDEO': '41', 'S-VIDEO': '42' }.get(value)
        if val: return val
        raise ValueError('{0} is not a valid input'.format(value))

    ''' STATUS QUERY METHOD '''

    def queryStatus(self):
        if self.properties['projPowerState'] in ['ON', 'WARMING']:
            return ['PWR?\r','SOURCE?\r']
        else:
            return 'PWR?\r'

    ''' READY STATE METHOD '''

    def ready(self):
        ''' Projector stops accepting commands while turning on or off (up to 30 seconds) '''
        return False if self.properties['projPowerState'] in ['ON', 'WARMING', 'OFF', None] else 5
# For SPHINX: End projectorComponent

# For SPHINX: Start TVThing
class TVThing(Thing):

    def onChange(self, updatedProperties):
        rv = {}
        # An Alexa dot is connected to the AUX input.  Make sure preamp is always on and set to the AUX input when not doing something else
        if updatedProperties.get('powerState') == 'OFF':
            self._logger.info('THING {0} has been turned off.  Turning it back ON and setting input to AUX.'.format(self.__name__))
            rv['powerState'] = 'ON'
            rv['input'] = 'AUX'
            rv['projPowerState'] = 'OFF'
            rv['muted'] = False

        # If preamp is not set to an input associated with Video, turn projector off
        if 'input' in updatedProperties and updatedProperties.get('input') not in ['TV', 'DVD']:
            self._logger.info('THING {0} turning projector off.'.format(self.__name__))
            rv['projPowerState'] = 'OFF'

        # If preamp is set to an input associated with Video, turn projector on and set to correct projector input for the chosen preamp input
        if self._localShadow.get('powerState') == 'ON' and updatedProperties.get('input') in ['TV', 'DVD']:
            self._logger.info('THING {0} turning projector on.'.format(self.__name__))
            rv['projPowerState'] = 'ON'
            if updatedProperties.get('input') == 'TV':
                rv['projInput'] = 'HDMI1'
            else:
                rv['projInput'] = 'HDMI2'
        return rv
# For SPHINX: End TVThing

# For SPHINX: Start MAIN
if __name__ == u'__main__':

    import serial
    import logging
    import os, sys

    logger = logging.getLogger('pyIOT')
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)-15s - %(message)s')
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    del logger
    del ch
    del formatter

    try:
        ''' Connected to serial interfaces for preamp and projector '''
        preampStream = serial.Serial('/dev/ttyUSB0', 9600, timeout=1)
        projectorStream = serial.Serial('/dev/ttyUSB1', 9600, timeout=60)

        ''' instantiate Component classes '''
        preamp = preampComponent(name='AVM20', stream=preampStream)
        projector = projectorComponent(name='EPSON1080UB', stream=projectorStream, eol=':', synchronous=True)

        ''' instantiate Thing '''
        TV = TVThing(endpoint='aamloz0nbas89.iot.us-east-1.amazonaws.com', thingName='TV', rootCAPath='root-CA.crt', certificatePath='TV.crt', privateKeyPath='TV.private.key', region='us-east-1', components=[preamp, projector])

        ''' Start Thing '''
        TV.start()
    except KeyboardInterrupt:
        ''' Shut down components.  This will also cause the Thing to shut down '''
        preamp.exit()
        projector.exit()
# For SPHINX: End MAIN

from pyIOT import Thing, Component

import serial


class preampComponent(Component):

    ''' COMPONENT TO PROPERTY METHODS '''

    # convert anthem power message into powerState property
    @Component.componentToProperty('powerState', '^P1P([0-1])$')
    def avmToPowerState(self, property, value):
        val = { '1': 'ON', '0': 'OFF' }.get(value)
        if val: return val
        raise ValueError('{0} is not a valid value for property {1}'.format(value, property))

    # convert anthem input message into input property
    @Component.componentToProperty('input', '^P1S([0-9])$')
    def avmToInput(self, property, value):
        val = { '0': 'CD', '3': 'TAPE', '5': 'DVD', '6': 'TV', '7': 'SAT', '8': 'VCR', '9': 'AUX' }.get(value)
        if val: return val
        raise ValueError('{0} is not a valid value for property {1}'.format(value, property))

    # convert anthem volume message into volume property
    @Component.componentToProperty('volume', '^P1VM([+-][0-9]{1,2}(?:[\\.][0-9]{1,2})?)$')
    def avmToVolume(self, property, value):
        try:
            rawvol = float(value)
            return self._db(rawvol)
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
    @Component.componentToProperty(['input', 'volume', 'muted'], '^P1S([0-9])V([+-][0-9]{2}[\\.][0-9])M([0-1])D[0-9]E[0-9]$')
    def avmcombinedResponse(self, property, value):
        return { 'input': self.avmToInput, 'volume': self.avmToVolume, 'muted': self.avmToMuted }.get(property)(property, value)

    ''' PROPERTY TO COMPONENT METHODS '''

    # Command preamp to turn on or off
    @Component.propertyToComponent('powerState', 'P1P{0}')
    def powerStateToAVM(self, value):
        val = { 'ON': '1', 'OFF': '0' }.get(value)
        if val: return val
        raise ValueError('{0} is not a valid powerState'.format(value))

    # Command preamp to change input
    @Component.propertyToComponent('input', 'P1S{0}')
    def inputToAVM(self, value):
        val = { 'CD': '0', 'TAPE': '3', 'DVD': '5', 'TV': '6', 'SAT': '7', 'VCR': '8', 'AUX': '9' }.get(value)
        if val: return val
        raise ValueError('{0} is not a valid input'.format(value))

    # Command preamp to change its volume
    @Component.propertyToComponent('volume', 'P1VM{0}')
    def volumeToAVM(self, value):
        if type(value) is int: return _volume(value)
        raise ValueError('{0} is not a valid volume'.format(value))

    # Command preamp to mute or unmute
    @Component.propertyToComponent('muted', 'P1M{0}')
    def muteToAVM(self, value):
        val = { True: '1', False: '0' }.get(value)
        if val: return val
        raise ValueError('{0} is not a valid muted value'.format(value))

    ''' STATUS QUERY METHOD '''

    def queryStatus(self):
        ''' The Anthem only allows you to query its status when it is on.  When it is off you can only ask for power state '''
        if self.properties['powerState'] == 'ON':
            return 'P1?\n'
        else:
            return 'P1P?\n'

	''' UTILITY METHODS '''

    ''' The remaining methods are to handle the conversation from volume to db and vice-versa '''
    @staticmethod
    def _volumeToDb(v):
        ''' Convert a volume in the range 0 to 100 into a db value.  This provides an exponential curve from -69db to +10db. '''
        return float( -1*((100-v)**2.25)/400)+10

    ''' compute array of possible volume to db values '''
    _volArray = []
    for v in range (0,101):
      _volArray.append(_volumeToDb(v))
    del v

    @staticmethod
    def _volume(v):
        ''' Get volume from volArray and round to nearest 0.5db '''
        return int(5*round(float(_volArray[v])/5*10))/10

    @staticmethod
    def _db(db):
        ''' Find the closest db value from volArray and return corresponding volume value '''
        ar = self._volArray
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

class projectorComponent(Component):


    ''' COMPONENT TO PROPERTY METHODS '''

    @Component.componentToProperty('projPowerState', '^PWR=([0-9]{2})$')
    def toProjPowerState(self, property, value):
        val = { '00': 'OFF', '01': 'ON', '02': 'WARMING', '03': 'COOLING', '04': 'STANDBY', '05': 'ABNORMAL' }.get(value)
        if val: return val
        raise ValueError('{0} is not a valid value for property {1}'.format(value, property))

    @Component.componentToProperty('projInput', '^SOURCE=([a-zA-Z0-9]{2})$')
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
        if self.properties['projPowerState'] == 'ON':
            return ['PWR?\r','SOURCE?\r']
        else:
            return 'PWR?\r'

	''' READY STATE METHOD '''

    def ready(self):
		''' Projector stops accepting commands while turning on or off (up to 30 seconds) '''
        return True if self.properties['projPowerState'] in ['ON', 'OFF', 'UNKNOWN'] else False


class AVM(Component):

    def __init__(self, port, baud):
        self._ser = serial.Serial(port, baud, timeout=0.25)
        self._timeout=0.25
        if not self._ser:
            raise IOError('Unable to open serial connection on power {0}'.format(port))
        super(AVM, self).__init__(name = 'AVM', stream = self._ser, properties = { 'powerState': 'UNKNOWN', 'input':'UNKNOWN', 'volume': 'UNKNOWN', 'muted': 'UNKNOWN' })
        self.volarray = [-50, -35, -25, -21, -18, -12, -8, -4, 0, 5, 10 ]

    def queryStatus(self):
        if self.properties['powerState'] == 'ON':
            return 'P1?\n'
        else:
            return 'P1P?\n'

    @Component.componentToProperty('powerState', '^P1P([0-1])$')
    def avmToPowerState(self, property, value):
        assert (property == 'powerState'), 'Wrong property received: ' + property
        val = { '1': 'ON', '0': 'OFF' }.get(value)
        if val:
            return val
        raise ValueError('{0} is not a valid value for property {1}'.format(value, property))

    @Component.componentToProperty('input', '^P1S([0-9])$')
    def avmToInput(self, property, value):
        assert (property == 'input'), 'Wrong property received: ' + property
        val = { '0': 'CD', '3': 'TAPE', '5': 'DVD', '6': 'TV', '7': 'SAT', '8': 'VCR', '9': 'AUX' }.get(value)
        if val:
            return val
        raise ValueError('{0} is not a valid value for property {1}'.format(value, property))

    @Component.componentToProperty('volume', '^P1VM([+-][0-9]{1,2}(?:[\\.][0-9]{1,2})?)$')
    def avmToVolume(self, property, value):
        assert (property == 'volume'), 'Wrong property received: ' + property
        try:
            rawvol = float(value)
        except:
            raise ValueError('{0} is not a valid value for property {1}'.format(value, property))
        for i in range(len(self.volarray)):
            if rawvol <= self.volarray[i]:
                return i*10
        else:
            # volume greater than max array value
            return 100

    @Component.componentToProperty('muted', '^P1M([0-1])$')
    def avmToMuted(self, property, value):
        assert (property == 'muted'), 'Wrong property received: ' + property
        val = { '1': True, '0': False }.get(value)
        if val is not None:
            return val
        raise ValueError('{0} is not a valid value for property {1}'.format(value, property))

    @Component.componentToProperty(['input', 'volume', 'muted'], '^P1S([0-9])V([+-][0-9]{2}[\\.][0-9])M([0-1])D[0-9]E[0-9]$')
    def avmcombinedResponse(self, property, value):
        assert (property in ['input','volume', 'muted']), 'Wrong property received: {0}'.format(property)
        return { 'input': self.avmToInput, 'volume': self.avmToVolume, 'muted': self.avmToMuted }.get(property)(property, value)

    @Component.propertyToComponent('powerState', 'P1P{0}')
    def powerStateToAVM(self, value):
        val = { 'ON': '1', 'OFF': '0' }.get(value)
        if val:
            return val
        raise ValueError('{0} is not a valid powerState'.format(value))

    @Component.propertyToComponent('input', 'P1S{0}')
    def inputToAVM(self, value):
        val = { 'CD': '0', 'TAPE': '3', 'DVD': '5', 'TV': '6', 'SAT': '7', 'VCR': '8', 'AUX': '9' }.get(value)
        if val:
            return val
        raise ValueError('{0} is not a valid input'.format(value))

    @Component.propertyToComponent('volume', 'P1VM{0}')
    def volumeToAVM(self, value):
        if type(value) is int:
            value = int(value/10)
            value = 0 if value < 0 else 10 if value > 10 else value
            return self.volarray[value]
        raise ValueError('{0} is not a valid volume'.format(value))

    @Component.propertyToComponent('muted', 'P1M{0}')
    def muteToAVM(self, value):
        val = { True: '1', False: '0' }.get(value)
        if val:
            return val
        raise ValueError('{0} is not a valid muted value'.format(value))

class Epson1080UB(Component):

    def __init__(self, port, baud):
        self._ser = serial.Serial(port, baud, timeout=0.25)
        self._timeout=0.25
        if not self._ser:
            raise IOError('Unable to open serial connection on power {0}'.format(port))
        super(Epson1080UB, self).__init__(name = 'Epson1080UB', eol='\r:', stream = self._ser, properties = { 'projPowerState': 'UNKNOWN', 'projInput':'UNKNOWN'  }, synchronous=True)

        self.write('PWR?\r')

    def close(self):
        self._ser.close()

    def queryStatus(self):
        if self.properties['projPowerState'] == 'ON':
            return ['PWR?\r','SOURCE?\r']
        else:
            return 'PWR?\r'

    def ready(self):
        return True if self.properties['projPowerState'] in ['ON', 'OFF', 'UNKNOWN'] else False

    @Component.componentToProperty('projPowerState', '^PWR=([0-9]{2})$')
    def toProjPowerState(self, property, value):
        assert (property == 'projPowerState'), 'Wrong property received: ' + property
        val = { '00': 'OFF', '01': 'ON', '02': 'WARMING', '03': 'COOLING', '04': 'STANDBY', '05': 'ABNORMAL' }.get(value)
        if val:
            return val
        raise ValueError('{0} is not a valid value for property {1}'.format(value, property))

    @Component.componentToProperty('projInput', '^SOURCE=([a-zA-Z0-9]{2})$')
    def toProjInput(self, property, value):
        assert (property == 'projInput'), 'Wrong property received: ' + property
        val = { '30': 'HDMI1', 'A0': 'HDMI2', '41': 'VIDEO', '42': 'S-VIDEO' }.get(value)
        if val:
            return val
        raise ValueError('{0} is not a valid value for property {1}'.format(value, property))

    @Component.propertyToComponent('projPowerState', 'PWR {0}\r')
    def projPowerStateToProj(self, value):
        if value in ['ON', 'OFF']:
            return value
        raise ValueError('{0} is not a valid powerState'.format(value))

    @Component.propertyToComponent('projInput', 'SOURCE {0}\r')
    def projInputToProj(self, value):
        val = { 'HDMI1': '30', 'HDMI2': 'A0', 'VIDEO': '41', 'S-VIDEO': '42' }.get(value)
        if val:
            return val
        raise ValueError('{0} is not a valid input'.format(value))


class TVThing(Thing):

    def onChange(self, updatedProperties):
        rv = []
        # An Alexa dot is connected to the AUX input.  Make sure preamp is always on and set to the AUX input when not doing something else
        if updatedProperties.get('powerState') == 'OFF':
            print ('Returning powerState to ON and input to Alexa')
            rv.append(('powerState','ON'))
            rv.append(('input', 'AUX'))
			rv.append(('powerProjector', 'OFF'))

		# If preamp is not set to an input associated with Video, turn projector off
		if updatedProperties.get('powerState') == 'ON' and updatedProperties.get('input') not in ['TV', 'DVD']:
			rv.append(('powerProjector', 'OFF'))

		# If preamp is set to an input associated with Video, turn projector on and set to correct projector input for the chosen preamp input
		if updatedProperties.get('powerState') == 'ON' and (updatedProperties.get('input') in ['TV', 'DVD']:
			rv.append(('powerProjector', 'ON'))
			if updatedProperties.get('input') == 'TV':
				rv.append('inputProjector', 'HDMI1')
			else:
				rv.append('inputProjector', 'HDMI2')
        return rv

if __name__ == u'__main__':

    try:
        condoAVM = AVM('/dev/ttyUSB0',9600)

        condoTV = condoTVThing(endpoint='aamloz0nbas89.iot.us-east-1.amazonaws.com', thingName='condoTV', rootCAPath='root-CA.crt', certificatePath='condoTV.crt', privateKeyPath='condoTV.private.key', region='us-east-1', components=[condoAVM])
        condoTV.start()
    except KeyboardInterrupt:
        condoAVM.exit()

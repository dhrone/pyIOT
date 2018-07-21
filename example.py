import pyIOT

class AVM(Device):

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

    @Device.deviceToProperty('powerState', '^P1P([0-1])$')
    def avmToPowerState(self, property, value):
        assert (property == 'powerState'), 'Wrong property received: ' + property
        val = { '1': 'ON', '0': 'OFF' }.get(value)
        if val:
            return val
        raise ValueError('{0} is not a valid value for property {1}'.format(value, property))

    @Device.deviceToProperty('input', '^P1S([0-9])$')
    def avmToInput(self, property, value):
        assert (property == 'input'), 'Wrong property received: ' + property
        val = { '0': 'CD', '3': 'TAPE', '5': 'DVD', '6': 'TV', '7': 'SAT', '8': 'VCR', '9': 'AUX' }.get(value)
        if val:
            return val
        raise ValueError('{0} is not a valid value for property {1}'.format(value, property))

    @Device.deviceToProperty('volume', '^P1VM([+-][0-9]{1,2}(?:[\\.][0-9]{1,2})?)$')
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

    @Device.deviceToProperty('muted', '^P1M([0-1])$')
    def avmToMuted(self, property, value):
        assert (property == 'muted'), 'Wrong property received: ' + property
        val = { '1': True, '0': False }.get(value)
        if val is not None:
            return val
        raise ValueError('{0} is not a valid value for property {1}'.format(value, property))

    @Device.deviceToProperty(['input', 'volume', 'muted'], '^P1S([0-9])V([+-][0-9]{2}[\\.][0-9])M([0-1])D[0-9]E[0-9]$')
    def avmcombinedResponse(self, property, value):
        assert (property in ['input','volume', 'muted']), 'Wrong property received: {0}'.format(property)
        return { 'input': self.avmToInput, 'volume': self.avmToVolume, 'muted': self.avmToMuted }.get(property)(property, value)

    @Device.propertyToDevice('powerState', 'P1P{0}')
    def powerStateToAVM(self, value):
        val = { 'ON': '1', 'OFF': '0' }.get(value)
        if val:
            return val
        raise ValueError('{0} is not a valid powerState'.format(value))

    @Device.propertyToDevice('input', 'P1S{0}')
    def inputToAVM(self, value):
        val = { 'CD': '0', 'TAPE': '3', 'DVD': '5', 'TV': '6', 'SAT': '7', 'VCR': '8', 'AUX': '9' }.get(value)
        if val:
            return val
        raise ValueError('{0} is not a valid input'.format(value))

    @Device.propertyToDevice('volume', 'P1VM{0}')
    def volumeToAVM(self, value):
        if type(value) is int:
            value = int(value/10)
            value = 0 if value < 0 else 10 if value > 10 else value
            return self.volarray[value]
        raise ValueError('{0} is not a valid volume'.format(value))

    @Device.propertyToDevice('muted', 'P1M{0}')
    def muteToAVM(self, value):
        val = { True: '1', False: '0' }.get(value)
        if val:
            return val
        raise ValueError('{0} is not a valid muted value'.format(value))

class Epson1080UB(Device):

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

    @Device.deviceToProperty('projPowerState', '^PWR=([0-9]{2})$')
    def toProjPowerState(self, property, value):
        assert (property == 'projPowerState'), 'Wrong property received: ' + property
        val = { '00': 'OFF', '01': 'ON', '02': 'WARMING', '03': 'COOLING', '04': 'STANDBY', '05': 'ABNORMAL' }.get(value)
        if val:
            return val
        raise ValueError('{0} is not a valid value for property {1}'.format(value, property))

    @Device.deviceToProperty('projInput', '^SOURCE=([a-zA-Z0-9]{2})$')
    def toProjInput(self, property, value):
        assert (property == 'projInput'), 'Wrong property received: ' + property
        val = { '30': 'HDMI1', 'A0': 'HDMI2', '41': 'VIDEO', '42': 'S-VIDEO' }.get(value)
        if val:
            return val
        raise ValueError('{0} is not a valid value for property {1}'.format(value, property))

    @Device.propertyToDevice('projPowerState', 'PWR {0}\r')
    def projPowerStateToProj(self, value):
        if value in ['ON', 'OFF']:
            return value
        raise ValueError('{0} is not a valid powerState'.format(value))

    @Device.propertyToDevice('projInput', 'SOURCE {0}\r')
    def projInputToProj(self, value):
        val = { 'HDMI1': '30', 'HDMI2': 'A0', 'VIDEO': '41', 'S-VIDEO': '42' }.get(value)
        if val:
            return val
        raise ValueError('{0} is not a valid input'.format(value))


class denTVThing(Thing):

    def onChange(self, updatedProperties):
        rv = []
        # Make sure AVM is always on and set to the Alexa input when not watching TV
        if updatedProperties.get('powerState') == 'OFF':
            print ('Returning powerState to ON and input to Alexa')
            rv.append(('powerState','ON'))
            rv.append(('input', 'CD'))
        return rv

if __name__ == u'__main__':

    try:
        denAVM = AVM('/dev/ttyUSB1',9600)
        denEpson = Epson1080UB('/dev/ttyUSB0',9600)

        denTV = denTVThing(endpoint='aamloz0nbas89.iot.us-east-1.amazonaws.com', thingName='denTVThing', rootCAPath='root-CA.crt', certificatePath='denTVThing.crt', privateKeyPath='denTVThing.private.key', region='us-east-1', devices=[denAVM,denEpson])
        denTV.start()
    except KeyboardInterrupt:
        denAVM.exit()
        denEpson.exit()

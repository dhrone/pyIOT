from threading import Lock
import re

class simulator(object):

    ## init(): the constructor.  Many of the arguments have default values
    # and can be skipped when calling the constructor.
    def __init__( self, name='simulator', data=b'', eol=b'\n'):
        self._name = name if name else self.__class__.__name__
        self._isOpen  = True
        self._receivedData = b''
        self._data = data
        self._eol = eol
        self._rwlock = Lock()

    def isOpen( self ):
        return self._isOpen

    def open( self ):
        self._isOpen = True

    def close( self ):
        self._isOpen = False

    def write( self, string ):
        with self._rwlock:
            self._receivedData += string
        self.computeResponse()

    def read( self, n=1 ):
        with self._rwlock:
            s = self._data[0:n]
            self._data = self._data[n:]
        return s

    def readline( self ):
        with self._rwlock:
            try:
                returnIndex = self._data.index( self._eol )
                s = self._data[0:returnIndex+1]
                self._data = self._data[returnIndex+1:]
                retval = s
            except ValueError:
                retval = b''
        return retval

    def computeResponse(self):
        ''' Overload this to implement the device you are simulating '''
        with self._rwlock:
            self._data += self._receivedData
            self._receivedData = b''

    def __str__( self ):
        return  ('Simulating '+self._name )

class preampSim(simulator):


    def __init__(self):
        super(preampSim, self).__init__()
        self.properties = {
            'power': False,
            'input': 'CD',
            'volume': 0.0,
            'muted': False
        }

    def fpVolume(self, value):
        self.properties['volume'] = float(value)
        with self._rwlock:
            self._data += 'P1VM{:+.1f}\n'.format(self.properties['volume']).encode()

    def fpPower(self, value):
        self.properties['power'] = bool(value)
        with self._rwlock:
            self._data += 'P1P{0}\n'.format(int(self.properties['power'])).encode()

    def fpMuted(self, value):
        self.properties['muted'] = bool(value)
        with self._rwlock:
            self._data += 'P1M{0}\n'.format(int(self.properties['muted'])).encode()

    def fpInput(self, value):
        self.properties['input'] = value if value in ['CD', '2-Ch', '6-Ch', 'TAPE', 'DVD', 'TV', 'SAT', 'VCR', 'AUX'] else 'CD'
        with self._rwlock:
            self._data += 'P1S{0}\n'.format(self.inputStr(value)).encode()

    def frontPanel(self, property, value):
        if self.properties['power']:
            {
                'power': self.fpPower,
                'volume': self.fpVolume,
                'input': self.fpInput,
                'muted': self.fpMuted
            }.get(property)(value)
        else:
            if property == 'power':
                self.fpPower(value)

    def crPower(self, match, value):
        self.properties['power'] = bool(int(value))
        self._data += match.strip(self._eol) + b'\n'

    @staticmethod
    def inputStr(val):
        return {
            'CD': '0',
            '2-Ch': '1',
            '6-Ch': '2',
            'TAPE': '3',
            'RADIO': '4',
            'DVD': '5',
            'TV': '6',
            'SAT': '7',
            'VCR': '8',
            'AUX': '9'
        }.get(val,'0')

    @staticmethod
    def inputNr(val):
        val = val.decode() if type(val) == bytes else val
        print ('inputNr ', val)
        return {
            '0':'CD',
            '1':'2-Ch',
            '2':'6-Ch',
            '3':'TAPE',
            '4':'RADIO',
            '5':'DVD',
            '6':'TV',
            '7':'SAT',
            '8':'VCR',
            '9':'AUX'
        }.get(val,'CD')

    def crInput(self, match, value):
        if self.properties['power']:
            self.properties['input'] = self.inputNr(value)
            self._data += match.strip(self._eol) + b'\n'
        else:
            self._data += b'ERR\n'

    def crMuted(self, match, value):
        if self.properties['power']:
            self.properties['muted'] = bool(int(value))
            self._data += match.strip(self._eol) + b'\n'
        else:
            self._data += b'ERR\n'

    def crVolume(self, match, value):
        if self.properties['power']:
            self.properties['volume'] = float(value)
            self._data += match.strip(self._eol) + b'\n'
        else:
            self._data += b'ERR\n'

    def crStatusOn(self, match, value):
        if self.properties['power']:
            self._data += 'P1S{0}V{1:+.1f}M{0}D0E0\n'.format(self.inputStr(self.properties['input']), self.properties['volume'], self.properties['muted']).encode()
        else:
            self._data += b'ERR\n'

    def crStatusPower(self, match, value):
        self._data += 'P1P{0}\n'.format(int(self.properties['power'])).encode()

    def computeResponse(self):
        while True:

            with self._rwlock:
                print ('computeResponse ', self._receivedData)

                for k, v in {
                    b'^P1P([0-1])\n': self.crPower,
                    b'^P1S([0-9])\n': self.crInput,
                    b'^P1VM([+-][0-9]{1,2}(?:[\\.][0-9]{1,2})?)\n': self.crVolume,
                    b'^P1M([0-1])\n': self.crMuted,
                    b'^P1\?\n': self.crStatusOn,
                    b'^P1P\?\n': self.crStatusPower
                }.items():
                    m = re.match(k,self._receivedData)
                    if m:
                        v = v if type(v) is list else [v]
                        if len(m.groups()) > 0:
                            for i in range(0, len(m.groups())):
                                v[i](m.group(0), m.group(i+1))
                        else:
                            v[0](m.group(0), b'')
                        self._receivedData = self._receivedData[len(m.group(0)):]
                else:
                    break

            # If all of the received data has been consumed exit
            if len(self._receivedData) == 0:
                break

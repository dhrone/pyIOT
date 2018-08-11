from threading import Lock
import re
import logging

class simulator(object):
    _logger = logging.getLogger(__name__)

    ## init(): the constructor.  Many of the arguments have default values
    # and can be skipped when calling the constructor.
    def __init__( self, name='simulator', data=b'', eol=b'\n'):
        self.__name__ = name if name else self.__class__.__name__
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
            self._logger.info('SIM {0} receiving [{1}]'.format(self.__name__, string))
            self._receivedData += string
        self.computeResponse()

    def read( self, n=1 ):
        with self._rwlock:
            s = self._data[0:n]
            self._data = self._data[n:]
            if s:
                self._logger.debug('SIM {0} read [{1}]'.format(self.__name__, s))
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
        self._logger.debug('SIM {0} read [{1}]'.format(self.__name__, retval))
        return retval

    def computeResponse(self):
        ''' Overload this to implement the device you are simulating '''
        with self._rwlock:
            ''' Default behavior is to echo what is received '''
            self._data += self._receivedData
            self._receivedData = b''

class preampSim(simulator):

    def __init__(self, name='preampSim', data=b'', eol=b'\n'):
        super(preampSim, self).__init__(name, data, eol)
        self.properties = {
            'power': False,
            'input': 'CD',
            'volume': 0.0,
            'muted': False
        }
        self._logger.debug('SIM {0} starting with properties {1}'.format(self.__name__, self.properties))

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
        self._logger.debug('SIM {0} power changed to [{1}]'.format(self.__name__, self.properties['power']))
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
            self._logger.debug('SIM {0} input changed to [{1}]'.format(self.__name__, self.properties['input']))
            response = match.strip(self._eol) + b'\n'
        else:
            response = b'ERR\n'
        self._data += response
        self._logger.debug('SIM {0} transmitting [{1}]'.format(self.__name__, response))

    def crMuted(self, match, value):
        if self.properties['power']:
            self.properties['muted'] = bool(int(value))
            self._logger.debug('SIM {0} muted changed to [{1}]'.format(self.__name__, self.properties['muted']))
            response = match.strip(self._eol) + b'\n'
        else:
            response = b'ERR\n'
        self._data += response
        self._logger.debug('SIM {0} transmitting [{1}]'.format(self.__name__, response))

    def crVolume(self, match, value):
        if self.properties['power']:
            self.properties['volume'] = float(value)
            self._logger.debug('SIM {0} volume changed to [{1}]'.format(self.__name__, self.properties['volume']))
            response = match.strip(self._eol) + b'\n'
        else:
            response = b'ERR\n'
        self._data += response
        self._logger.debug('SIM {0} transmitting [{1}]'.format(self.__name__, response))

    def crStatusOn(self, match, value):
        self._logger.debug('SIM {0} crStatusOn properties [{1}]'.format(self.__name__, self.properties))
        if self.properties['power']:
            response = 'P1S{0}V{1:+.1f}M{2}D0E0\n'.format(self.inputStr(self.properties['input']), self.properties['volume'], int(self.properties['muted'])).encode()
        else:
            response = b'ERR\n'
        self._data += response
        self._logger.debug('SIM {0} transmitting [{1}]'.format(self.__name__, response))

    def crStatusPower(self, match, value):
        response = 'P1P{0}\n'.format(int(self.properties['power'])).encode()
        self._data += response
        self._logger.debug('SIM {0} transmitting [{1}]'.format(self.__name__, response))

    def computeResponse(self):
        while True:

            with self._rwlock:
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

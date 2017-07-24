from extronlib.interface import EthernetClientInterface, SerialInterface
from extronlib.system import Wait

import re

debug = False
if not debug:
    print = lambda *args, **kwargs: None


class DeviceClass():
    def __init__(self):
        self._status = [
            # (command, value, qualifier),
        ]

        self._userCallbacks = [
            # (command, qualifier, callback),
        ]

        self._regexMap = [
            # (regex, callback),
        ]

        self._buffer = ''

        self._AddRegex('Password:', self._MatchPassword)

        self.password = 'extron'

        self.ReceiveData = self._ReceiveData
        self.Connected = self._ConnectionHandler
        self.Disconnected = self._ConnectionHandler

    def _AddRegex(self, pattern, callback):
        regex = re.compile(pattern)
        self._regexMap.append((regex, callback))

    def _ConnectionHandler(self, interface, state):
        print('DeviceClass._ConnectionHandler(interface{}, state={})'.format(interface, state))
        self._WriteStatus('ConnectionStatus', state)

    def _WriteStatus(self, command, value, qualifier=None):
        print('DeviceClass._WriteStatus(command={}, value={}, qualifier={})'.format(command, value, qualifier))
        pass
        # commandFound = False
        # qualifierFound = False
        #
        ##See if the
        # for tup in self._status:
        # if command == tup[0]:
        # commandFound = True
        # if qualifier == tup[2]:
        # qualifierFound = True
        #
        # if commandFound and qualifierFound:
        # break

    def Set(self, command, value, qualifier=None):
        pass

    def ReadStatus(self, command, qualifier=None):
        pass

    def Update(self, command, qualifier=None):
        pass

    def SubscribeStatus(self, command, qualifier, callback):
        pass

    def _ReceiveData(self, _, data):
        print('DeviceClass._ReceiveData(data={})'.format(data))
        self._buffer += data.decode()

        for tup in self._regexMap:
            pattern = tup[0]
            callback = tup[1]

            for match in pattern.finditer(self._buffer):
                callback(match)
                self._buffer = self._buffer.replace(match.group(0), '')

        if len(self._buffer > 10000):
            self._buffer = ''

    def _MatchPassword(self, match):
        self.Send(self.password)

    def Send(self, data):
        print('DeviceClass.Send(data={})'.format(data))
        super().Send(data)


class EthernetClass(EthernetClientInterface, DeviceClass):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        DeviceClass.__init__(self)


class SerialClass(SerialInterface, DeviceClass):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        DeviceClass.__init__(self)

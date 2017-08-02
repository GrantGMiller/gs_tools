from extronlib.interface import EthernetClientInterface, SerialInterface
from extronlib.system import Wait, ProgramLog

import re
import json

debug = False
if not debug:
    print = lambda *args, **kwargs: None
else:
    # print = lambda *args, **kwargs: ProgramLog(str(args), 'info')
    pass


class DeviceClass():
    def __init__(self):
        self._status = {
            # qualifier: value,
        }

        self._userCallbacks = {
            # qualifier: user_callback,
        }

        self._regexMap = [
            # (regex, callback),
        ]

        self._buffer = ''

        self._AddRegex('Password:', self._MatchPassword)
        self._AddRegex('(\{.*?\})\r', self._MatchJson)

        self.password = 'extron'

        self.ReceiveData = self._ReceiveData
        self.Connected = self._ConnectionHandler
        self.Disconnected = self._ConnectionHandler

    def _AddRegex(self, pattern, callback):
        regex = re.compile(pattern)
        self._regexMap.append((regex, callback))

    def _ConnectionHandler(self, interface, state):
        print('VT.EthernetClass._ConnectionHandler(interface{}, state={})'.format(interface, state))
        self._WriteStatus('ConnectionStatus', state)

    def _WriteStatus(self, command, value, qualifier=None):
        print('VT.EthernetClass._WriteStatus(command={}, value={}, qualifier={})'.format(command, value, qualifier))

        oldValue = self.ReadStatus(command, qualifier)

        if oldValue != value:
            # do user callback
            pass

        self._status[qualifier] = value

    def Set(self, command, value, qualifier=None):
        data = {'command': command, 'value': value, 'qualifier': qualifier}
        jsonData = json.dumps(data, indent=4)
        self.Send(jsonData + '\r')

    def ReadStatus(self, command, qualifier=None):
        return self._status.get(qualifier, None)

    def Update(self, command, qualifier=None):
        data = {'command': command, 'qualifier': qualifier}
        self.Send(json.dumps(data, indent=4) + '\r')

    def SubscribeStatus(self, command, qualifier, callback):
        self._userCallbacks[qualifier] = callback

    def _ReceiveData(self, _, data):
        print('VT.EthernetClass._ReceiveData(data={})'.format(data))
        self._buffer += data.decode()

        for tup in self._regexMap:
            pattern = tup[0]
            callback = tup[1]

            for match in pattern.finditer(self._buffer):
                callback(match)
                self._buffer = self._buffer.replace(match.group(0), '')

        if len(self._buffer) > 10000:
            self._buffer = ''

    def _MatchPassword(self, match):
        self.Send(self.password)

    def _MatchJson(self, match):
        data = json.loads(match.group(1))
        qualifier = data['qualifier']
        value = data['value']

        self._WriteStatus(None, value, qualifier)

    def Send(self, data):
        print('VT.EthernetClass.Send(data={})'.format(data))
        super().Send(data)


class EthernetClass(EthernetClientInterface, DeviceClass):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        DeviceClass.__init__(self)


class SerialClass(SerialInterface, DeviceClass):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        DeviceClass.__init__(self)

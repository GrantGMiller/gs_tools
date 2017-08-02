from extronlib.interface import EthernetClientInterface, SerialInterface
from extronlib.system import Wait

import re
import json

debug = True  # True = enable print statments; False = disable print statments
if not debug:
    print = lambda *args, **kwargs: None


class DeviceClass():
    def __init__(self):
        self._status = {
            # 'command': {
            # "qualifier":{
            # 'value',
            # {
            # {
        }

        self._userCallbacks = {
            # 'command': {
            # "qualifier":{
            # 'value',
            # {
            # {
        }

        self._regexMap = [
            # (regex, callback),
        ]

        self._buffer = ''

        self._sendCounter = 0
        self._MISS_LIMIT = 5

        self._AddRegex('Password:', self._MatchPassword)
        self._AddRegex('Cpn(\d{1,2}) Rly(0|1)\r\n', self._MatchPower)
        self._AddRegex('Ver01\*(.*?)\r\n', self._MatchFW)
        self._AddRegex('(\d\.\d\d)\r\n', self._MatchFW)

        self.password = 'extron'

        self.ReceiveData = self._ReceiveData

    def _AddRegex(self, pattern, callback):
        regex = re.compile(pattern)
        self._regexMap.append((regex, callback))

    def _WriteStatus(self, command, value, qualifier=None):
        print('DeviceClass._WriteStatus(command={}, value={}, qualifier={})'.format(command, value, qualifier))
        # We have recieved a known response. Set ConnectionStatus to Connected
        if self.ReadStatus('ConnectionStatus') in ['Disconnected', None]:
            if 'ConnectionStatus' not in self._status:
                self._status['ConnectionStatus'] = {}
            self._status['ConnectionStatus']['null'] = 'Connected'
            if 'ConnectionStatus' in self._userCallbacks:
                connectionCallback = self._userCallbacks['ConnectionStatus'].get(None, None)
                if callable(connectionCallback):
                    connectionCallback('ConnectionStatus', 'Connected', None)
            self.Send('w3cv\r')

        # Save the status
        qualifier = json.dumps(qualifier, sort_keys=True)

        if command not in self._status:
            self._status[command] = {}

        oldValue = self.ReadStatus(command, qualifier)
        if value != value:
            if command in self._userCallbacks:
                if qualifier in self._userCallbacks[command]:
                    callback = self._userCallbacks[command][qualifier]
                    callback(command, value, qualifier)

        self._status[command][qualifier] = value
        print('self._status=', self._status)

    def Set(self, command, value, qualifier=None):
        pass

    def SetPower(self, command, value, qualifier):
        if value == 'On':
            self.Send('1*1o')
        elif value == 'Off':
            self.Send('1*0o')

    def _MatchPower(self, match):
        print('DeviceClass._MatchPower(match={})'.format(match.group(0)))
        relay = match.group(1)
        state = match.group(2)
        print('relay=', relay)
        print('state=', state)

        if int(relay) == 1:
            if int(state) == 1:
                self._WriteStatus('Power', 'On')
            elif int(state) == 0:
                self._WriteStatus('Power', 'Off')

    def UpdateFirmware(self, *args, **kwargs):
        self.Send('q')

    def _MatchFW(self, match):
        print('DeviceClass._MatchFW(match={})'.format(match.group(0)))
        version = match.group(1)
        self._WriteStatus('FirmwareVersion', version)

    def ReadStatus(self, command, qualifier=None):
        qualifier = json.dumps(qualifier, sort_keys=True)
        return self._status.get(command, {}).get(qualifier, None)

    def Update(self, command, qualifier=None):
        method = getattr(self, 'Update{}'.format(command))
        method(command, qualifier)

    def SubscribeStatus(self, command, qualifier=None, callback=None):
        print('DeviceClass.SubscribeStatus(command={}, qualifier={}, callback={})'.format(command, qualifier, callback))
        if callback is None:
            raise Exception('Gimme a callback')
        qualifier = json.dumps(qualifier, sort_keys=True)

        if command not in self._userCallbacks:
            self._userCallbacks[command] = {}

        self._userCallbacks[command][qualifier] = callback

    def _ReceiveData(self, _, data):
        print('DeviceClass._ReceiveData(data={})'.format(data))
        self._buffer += data.decode()

        for tup in self._regexMap:
            pattern = tup[0]
            callback = tup[1]

            for match in pattern.finditer(self._buffer):
                callback(match)
                self._buffer = self._buffer.replace(match.group(0), '')

        if len(self._buffer) > 10000:  # just in case the buffer gets flooded with garbage
            self._buffer = ''

    def _MatchPassword(self, match):
        self.Send(self.password)

    def Send(self, data):
        print('DeviceClass.Send(data={})'.format(data))
        self._sendCounter += 1
        if self._sendCounter > self._MISS_LIMIT:
            self._WriteStatus('ConnectionStatus', 'Disconnected')
        super().Send(data)


class EthernetClass(EthernetClientInterface, DeviceClass):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        DeviceClass.__init__(self)


class SerialClass(SerialInterface, DeviceClass):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        DeviceClass.__init__(self)

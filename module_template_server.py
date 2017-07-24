from gs_tools import (
    EthernetServerInterfaceEx,
    SerialInterface,
    HandleConnection,
)

import re

debug = True
if not debug:
    print = lambda *args, **kwargs: None


class DeviceClass:
    def __init__(self):
        self._reMap = [
            #(regex, callback), #tuple
            ]
        self._buffers = {
            #clientObject: '',
        }

        self.Connected = self._ConnectionHandler
        self.Disconnected = self._ConnectionHandler
        self.ReceiveData = self._ReceiveData

        HandleConnection(self)


    def _AddRegex(self, pattern, callback):
        self._reMap.append(re.compile(pattern), callback)

    def _ConnectionHandler(self, client, state):
        print('_ConnectionHandler(client={}, state={})'.format(client, state))
        if state is 'Connected':
            self._buffers[client] = ''
        elif state is 'Disconnected':
            self._buffers.pop(client, None)

    def _ReceiveData(self, client, data):
        print('_ReceiveData(client={}, data={}'.format(client, data))
        buffer = self._buffers[client]
        buffer += data.decode()

        for regex, callback in self._reMap:
            for match in regex.finditer(buffer):
                callback(match, client)
                buffer = buffer.replace(match.group(0), '')

        if len(buffer) > 10000:
            buffer = ''

class EthernetClass(EthernetServerInterfaceEx, DeviceClass):
    def __init__(self, *args, **kwargs):
        EthernetServerInterfaceEx.__init__(self, *args, **kwargs)
        DeviceClass.__init__(self)


class SerialClass(SerialInterface, DeviceClass):
    def __init__(self, *args, **kwargs):
        SerialInterface.__init__(self, *args, **kwargs)
        DeviceClass.__init__(self)

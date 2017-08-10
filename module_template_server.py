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
            # (regex, callback), #tuple
            ]
        self._buffers = {
            # clientObject: '',
        }
        self._regexStatusTag = {
            # regex: 'status tag',
        }
        self._status = {
            # 'status tag': value,
        }
        self._GenericResponses = {
            # 'status tag': responseStr,
        }

        self.Connected = self._ConnectionHandler
        self.Disconnected = self._ConnectionHandler
        self.ReceiveData = self._ReceiveData

        HandleConnection(self)
        self._Initialize()

    def _NewStatus(self, statusTag, newStatus):
        self._status[statusTag] = newStatus

    def _GetStatusTag(self, regex):
        return self._regexStatusTag.get(regex, 'Status Tag Not Found')

    def _ConnectionHandler(self, client, state):
        print('_ConnectionHandler(client={}, state={})'.format(client, state))
        if state is 'Connected':
            self._buffers[client] = ''
        elif state is 'Disconnected':
            self._buffers.pop(client, None)

    def _ReceiveData(self, client, data):
        print('_ReceiveData(client={}, data={}'.format(client, data))
        if client not in self._buffers:
            self._buffers[client] = ''
        self._buffers[client] += data.decode()
        buffer = self._buffers[client]
        print('buffer=', buffer)

        for regex, callback in self._reMap:
            for match in regex.finditer(buffer):
                statusTag = self._regexStatusTag[regex]
                currentStatus = self._status[statusTag]

                callback(match, client, statusTag, currentStatus)

                self._buffers[client] = self._buffers[client].replace(match.group(0), '')

        if len(self._buffers[client]) > 10000:
            self._buffers[client] = ''

    #Set/Get *****************************************************************
    def _AddRegex(self, pattern, callback, statusTag=None):
        regex = re.compile(pattern)
        self._reMap.append((regex, callback))

        if statusTag is None:
            statusTag = 'Status {}'.format(len(self._status))

        self._status[statusTag] = None
        self._regexStatusTag[regex] = statusTag

    def _Initialize(self):

        self._AddRegex('wcv\r', self._MatchUpdateGeneric, 'Verbose Mode')
        self._AddRegex('w3cv\r', self._MatchSetGeneric, 'Verbose Mode')
        self._GenericResponses['Verbose Mode'] = 'Vrb3\r\n'


    def _MatchUpdateGeneric(self, match, client, statusTag, currentStatus):
        print('_MatchUpdateGeneric')
        response = self._GenericResponses.get(statusTag, '{}\r\n')
        client.Send(response.format(currentStatus))

    def _MatchSetGeneric(self, match, client, statusTag, currentStatus):
        print('_MatchSetGeneric')
        try:
            newStatus = match.group(1)
        except:
            newStatus = None
        self._NewStatus(statusTag, newStatus)
        response = self._GenericResponses.get(statusTag, '{}\r\n')
        client.Send(response.format(newStatus))

    def Send(self, data):
        print('Send: {}'.format(data))
        super().Send(data)

    def ReadStatus(self, tag):
        return self._status.get(tag, None)

class EthernetClass(EthernetServerInterfaceEx, DeviceClass):
    def __init__(self, *args, **kwargs):
        EthernetServerInterfaceEx.__init__(self, *args, **kwargs)
        DeviceClass.__init__(self)


class SerialClass(SerialInterface, DeviceClass):
    def __init__(self, *args, **kwargs):
        SerialInterface.__init__(self, *args, **kwargs)
        DeviceClass.__init__(self)

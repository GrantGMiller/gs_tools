from extronlib.interface import EthernetClientInterface, SerialInterface
from extronlib.system import Wait

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

        self.ReceiveData = self._ReceiveData

        self._DoDisconnected()

    def _AddRegex(self, pattern, callback):
        pass

    def _DoDisconnected(self):
        self._WriteStatus('_connection_status', 'Disconnected')

    def _WriteStatus(self, command, value, qualifier=None):
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
        print('secure_switch.EthernetClass._ReceiveData(data={})'.format(data))
        data = data.decode()
        if 'Password:' in data:
            self.Send('extron\r')

    def Send(self, data):
        print('secure_switch.EthernetClass.Send(data={})'.format(data))
        super().Send(data)


class EthernetClass(EthernetClientInterface, DeviceClass):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        DeviceClass.__init__(self)


class SerialClass(SerialInterface, DeviceClass):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        DeviceClass.__init__(self)

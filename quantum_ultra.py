'''
There is not an official Quantum Ultra module available, so this one gets the job done for now.
'''

from extronlib.interface import EthernetClientInterface, SerialInterface
from extronlib.system import Wait


class DeviceClass():
    def __init__(self):
        self.EmulatedStatus = {
            # 'CommandName': {qualifier: value},
        }
        self.LiveStatus = {}  # Same structure as EmulatedStatus
        self.Callbacks = {
            # 'CommandName': {qualifier: callback},
        }

        def DoDisconnected():
            self._WriteStatus('_connection_status', 'Disconnected')

        self.WaitConnectionStatus = Wait(30, DoDisconnected)

    def _WriteStatus(self, command, value, qualifier=None):
        if command not in self.EmulatedStatus:
            self.EmulatedStatus[command] = {qualifier: None}

        OldValue = self.EmulatedStatus[command][qualifier]

        # If the value changes, do the callback
        if command not in self.Callbacks:
            self.Callbacks[command] = {qualifier: None}

        Callback = self.Callbacks[command][qualifier]
        if Callback:
            Callback(command, value, qualifier)

    def Set(self, command, value, qualifier=None):
        if command == 'PresetRecall':
            PresetNumber = value
            Canvas = qualifier['Canvas']

            self.Send('1*{}*{}.'.format(Canvas, PresetNumber))

        elif command == 'SourceRoute':
            Source = qualifier['Source']
            Window = qualifier['Window']
            Canvas = qualifier['Canvas']

            self.Send('{}*{}*{}!'.format(Canvas, Window, Source))

        # Save this value
        self.EmulatedStatus[command] = {'Qualifier': qualifier,
                                        'Value': value,
                                        }

    def ReadStatus(self, command, qualifier):
        return self.EmulatedStatus[command][qualifier]

    def Update(self, command, qualifier):
        pass

    def SubscribeStatus(self, command, qualifier, callback):
        self.Callbacks[command] = {qualifier: callback}

    def ReceiveData(self, data):
        self._WriteStatus('_connection_status', 'Connected')
        self.WaitConnectionStatus.Restart()


class EthernetClass(EthernetClientInterface, DeviceClass):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        DeviceClass.__init__(self)


class SerialClass(SerialInterface, DeviceClass):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        DeviceClass.__init__(self)

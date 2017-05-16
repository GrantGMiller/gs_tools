'''
 This module was made to accommodate the following scenario:
 There are two independent GS system that need to share information.
 Each system needs the ability to be asynchrously updated of changes to specific values, as well as send an update to the other system.

 This is a working example of a main.py

## Begin ControlScript Import --------------------------------------------------
from extronlib import event, Version
from extronlib.device import ProcessorDevice, UIDevice
from extronlib.interface import (EthernetClientInterface, 
    EthernetServerInterface, SerialInterface, IRInterface, RelayInterface, 
    ContactInterface, DigitalIOInterface, FlexIOInterface, SWPowerInterface, 
    VolumeInterface)
from extronlib.ui import Button, Knob, Label, Level
from extronlib.system import Clock, MESet, Wait

print(Version())

from file_sync_v2_0_0 import SystemSync
import time

TLP = UIDevice('TLP')

#File Sync *********************************************************************
Syncer = SystemSync()
Syncer.AddSystem('10.8.27.117') #The IP of the other system's processor

@event(Syncer, 'NewData')
def NewDataEvent(interface, data): #This event will be fired any time the other system updates a value.
    print('NewDataEvent()\ndata=', data)
    for key in data:
        if key == 'Volume':
            LvlVolume.SetLevel(data['Volume'])

        elif key == 'Mute':
            BtnVolumeMute.SetState(data['Mute'])

#GUI ***************************************************************************
BtnVolumeUp = Button(TLP, 1, repeatTime=0.1)
BtnVolumeDown = Button(TLP, 2, repeatTime=0.1)
BtnVolumeMute = Button(TLP, 3)

LvlVolume = Level(TLP, 4)

@event(BtnVolumeUp, 'Pressed')
@event(BtnVolumeUp, 'Repeated')
@event(BtnVolumeUp, 'Released')

@event(BtnVolumeDown, 'Pressed')
@event(BtnVolumeDown, 'Repeated')
@event(BtnVolumeDown, 'Released')

@event(BtnVolumeMute, 'Pressed')
@event(BtnVolumeMute, 'Released')
def BtnVolumeEvent(button, state):
    print(button.Name, button.ID, state)
    if state in ['Pressed', 'Repeated']:

        if button == BtnVolumeUp:
            LvlVolume.Inc()

        elif button == BtnVolumeDown:
            LvlVolume.Dec()

        elif button == BtnVolumeMute:
            #print('BtnVolumeMute.State=', BtnVolumeMute.State)
            #print('not BtnVolumeMute.State=', int(not BtnVolumeMute.State))
            BtnVolumeMute.SetState(int(not BtnVolumeMute.State))

    elif state == 'Released':
        if button in [BtnVolumeUp, BtnVolumeDown]:
            Syncer.Set('Volume', LvlVolume.Level)

        elif button == BtnVolumeMute:
            Syncer.Set('Mute', BtnVolumeMute.State) #This will update the other system with the new value

print('Project Loaded')


'''

from extronlib.system import (
    File,
    Wait,
)
from extronlib.interface import (
    EthernetClientInterface,
    EthernetServerInterfaceEx,
)
from extronlib.device import (
    UIDevice,
    ProcessorDevice,
)
import extronlib

import json


class SystemSync:
    def __init__(self, filename='system_data.json'):
        self.clients = []
        self.filename = filename
        self._RxBuffer = {}

        self._Data = {}  # A dict that holds all the system data
        if File.Exists(self.filename):
            self._ReadData()

        self._Server = EthernetServerInterfaceEx(3888)
        self._Server.ReceiveData = self._ReceiveData
        print('SystemSync Server {}'.format(self._Server.StartListen()))

        self._NewData = None  # This is a callback to execute when new data is available

    def AddSystem(self, otherIP):
        Client = EthernetClientInterface(otherIP, 3888)
        Client.ReceiveData = self._ReceiveData
        HandleConnection(Client)
        self.clients.append(Client)

    def _SaveData(self):
        # This will save the most recent data to non-volatile storage
        file = File(self.filename, mode='wt')
        dataJson = json.dumps(self._Data)
        file.write(dataJson)
        file.close()

    def _ReadData(self):
        # This will read the data from non-volatile storage
        file = File(self.filename, mode='rt')
        dataJson = file.read()
        self._Data = json.loads(dataJson)
        file.close()

    def _UpdateOtherSystems(self):
        # This method will send the new data to the other systems
        msg = {'Type': 'NewData',
               'dataJson': json.dumps(self._Data)
               }
        msgJson = json.dumps(msg)

        for client in self.clients:
            client.Send(msgJson)

    def Set(self, name, value):
        # Set the new value and update all the clients
        self._Data[name] = value
        self._UpdateOtherSystems()
        self._SaveData()

    def Update(self, name=None):
        # Request an update from the clients for a particular value
        msg = {'Type': 'Update'}
        msgJson = json.dumps(msg)

        for client in self.clients:
            client.Send(msgJson)

        for client in self._Server.Clients:
            client.Send(msgJson)

    def _ReceiveData(self, interface, data):
        print('RxData from {}:\ndata={}'.format(interface.IPAddress, data))
        # If we have never received data from this interface before, create a buffer for it
        if interface not in self._RxBuffer:
            self._RxBuffer[interface] = ''

        # Concatinate the data
        self._RxBuffer[interface] += data.decode()
        if len(self._RxBuffer[interface]) > 100:
            # Probably some junk data in the buffer. Clear it all out
            self._RxBuffer[interface] = ''

        msgJson = self._RxBuffer[interface]
        print('msgJson=', msgJson)
        try:
            msg = json.loads(msgJson)
            self._RxBuffer[interface] = ''  # Clear the buffer

        except Exception as e:
            # Probably not a full json string
            print(e)
            raise e

        DoCallback = False

        # Check the type of message
        if msg['Type'] == 'Update':
            # Send an update to the interface with the lastest info
            responseJson = json.dumps(self._Data)
            interface.Send(responseJson)

        elif msg['Type'] == 'NewData':
            # New data received from this interface, update this controller with new info
            newData = json.loads(msg['dataJson'])

            # Update this controller, trigger a NewData event if needed
            for key in newData:
                if key not in self._Data:
                    self._Data[key] = newData[key]
                    DoCallback = True

                elif self._Data[key] != newData[key]:
                    DoCallback = True
                    self._Data[key] = newData[key]

        if DoCallback:
            if self.NewData:
                self.NewData(self, self._Data)

    @property
    def NewData(self):
        return self._NewData

    @NewData.setter
    def NewData(self, callback):
        self._NewData = callback


# *******************************************************************************
ConnectionStatus = {}


def HandleConnection(interface):
    '''
    This will try to open a IP connection to the interface.
    It will retry every X seconds until it is connected.

    v1_0_3 - also handles UIDevice, ProcessorDevice, SerialInterface, UDP
    v1_0_2 - calls interface.OnConnected when connected, if it exist
    '''
    print('HandleConnection(interface={})'.format(interface))
    ConnectionStatus[interface] = 'Disconnected'

    # Physical connection status
    def PhysicalConnectionHandler(interface, state):

        if state in ['Disconnected', 'Offline']:
            if isinstance(interface, extronlib.interface.EthernetClientInterface):
                if interface.Protocol == 'TCP':  # UDP is "connection-less"
                    WaitReconnect.Restart()

        elif state in ['Connected', 'Online']:
            if hasattr(interface, 'OnConnected'):
                interface.OnConnected()

            if isinstance(interface, extronlib.interface.EthernetClientInterface):
                if interface.Protocol == 'TCP':  # UDP is "connection-less"
                    WaitReconnect.Cancel()

        if ConnectionStatus[interface] != state:
            if isinstance(interface, extronlib.interface.EthernetClientInterface):
                print('{}:{} {}'.format(interface.IPAddress, str(interface.IPPort), state))

            elif (isinstance(interface, UIDevice) or
                      isinstance(interface, ProcessorDevice)):
                print('{} {}'.format(interface.DeviceAlias, state))

            elif isinstance(interface, extronlib.interface.SerialInterface):
                print('Proc {} Port {} {}'.format(interface.Host.DeviceAlias, interface.Port, state))

        ConnectionStatus[interface] = state

    if isinstance(interface, UIDevice):
        interface.Online = PhysicalConnectionHandler
        interface.Offline = PhysicalConnectionHandler

    elif (isinstance(interface, extronlib.interface.EthernetClientInterface) or
              isinstance(interface, extronlib.interface.SerialInterface)):
        interface.Connected = PhysicalConnectionHandler
        interface.Disconnected = PhysicalConnectionHandler

    # Module Connection status
    if hasattr(interface, 'SubscribeStatus'):
        def GetModuleCallback(interface):
            def ModuleConnectionCallback(command, value, qualifier):
                ConnectionStatus[interface] = value
                if value == 'Disconnected':
                    if isinstance(interface, extronlib.interface.EthernetClientInterface):
                        interface.Disconnect()

            return ModuleConnectionCallback

        interface.SubscribeStatus('_connection_status', None, GetModuleCallback(interface))

    if isinstance(interface, extronlib.interface.EthernetClientInterface):
        if interface.Protocol == 'TCP':  # UDP is "connection-less"
            WaitReconnect = Wait(5, interface.Connect)
            WaitReconnect.Cancel()

    # Start the connection
    if isinstance(interface, extronlib.interface.EthernetClientInterface):
        Wait(0.1, interface.Connect)

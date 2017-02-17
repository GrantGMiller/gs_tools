'''
This module handles connection for UDP/TCP/Serial interfaces.
Added a log file for when a device connects/disconnects
'''

from extronlib import event
from extronlib.system import Wait, File
from extronlib.device import UIDevice, ProcessorDevice
from extronlib.interface import EthernetClientInterface, SerialInterface
import extronlib
import time

if not File.Exists('connection.log'):
    file = File('connection.log', mode='wt')
    file.close()

with File('connection.log', mode='at') as file:
    file.write('\n{} - Processor Restarted\n\n'.format(time.asctime()))

ConnectionStatus = {}

GREEN = 2
RED = 1
WHITE = 0


def NewStatus(interface, state, Type='Unknown'):
    if not interface in ConnectionStatus:
        ConnectionStatus[interface] = 'Default'

    oldStatus = ConnectionStatus[interface]

    if state != oldStatus:
        # New status
        ConnectionStatus[interface] = state
        with File('connection.log', mode='at') as file:

            if isinstance(interface, EthernetClientInterface):
                ip = interface.IPAddress
                port = interface.IPPort
                file.write('{} - {}:{} {} {}\n'.format(time.asctime(), ip, port, Type, state))

            elif isinstance(interface, SerialInterface):
                alias = interface.Host.DeviceAlias
                port = interface.Port
                file.write('{} - {}:{} {} {}\n'.format(time.asctime(), alias, port, Type, state))

            elif isinstance(interface, ProcessorDevice):
                alias = interface.DeviceAlias
                file.write('{} - ProcessorDevice:{} {} {}\n'.format(time.asctime(), alias, Type, state))

            elif isinstance(interface, UIDevice):
                alias = interface.DeviceAlias
                file.write('{} - UIDevice:{} {} {}\n'.format(time.asctime(), alias, Type, state))

            else:
                file.write('{} - {} {} {}\n'.format(time.asctime(), interface, Type, state))

    if interface in StatusButtons:
        btnList = StatusButtons[interface]
        for btn in btnList:
            if state in ['Connected', 'Online']:
                btn.SetState(GREEN)
                btn.SetText('Connected')
            elif state in ['Disconnected', 'Offline']:
                btn.SetState(RED)
                btn.SetText('Disconnected')
            else:
                btn.SetState(WHITE)
                btn.SetText('Error')


StatusButtons = {}


def AddStatusButton(interface, btn):
    if interface not in StatusButtons:
        StatusButtons[interface] = []

    StatusButtons[interface].append(btn)


def HandleConnection(interface):
    '''
    This will try to open a IP connection to the interface.
    It will retry every X seconds until it is connected.

    v1_0_3 - also handles UIDevice, ProcessorDevice, SerialInterface, UDP
    v1_0_2 - calls interface.OnConnected when connected, if it exist
    '''
    print('HandleConnection(interface={})'.format(interface))
    NewStatus(interface, 'Default')

    # Physical connection status
    def PhysicalConnectionHandler(interface, state):
        print('connection_handler_v1_0_6 PhysicalConnectionHandler\ninterface={}\nstate={}'.format(interface, state))

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

        NewStatus(interface, state, 'Physically')

    if isinstance(interface, UIDevice):
        interface.Online = PhysicalConnectionHandler
        interface.Offline = PhysicalConnectionHandler

    elif (isinstance(interface, extronlib.interface.EthernetClientInterface) or
              isinstance(interface, extronlib.interface.SerialInterface)):
        interface.Connected = PhysicalConnectionHandler
        interface.Disconnected = PhysicalConnectionHandler

    # Module Connection status
    def GetModuleCallback(interface):
        def ModuleConnectionCallback(command, value, qualifier):
            print('connection_handler_v1_0_6 ModuleConnectionCallback\ninterface={}\nvalue={}'.format(interface, value))

            NewStatus(interface, value, 'Logically')
            if value == 'Disconnected':
                if isinstance(interface, extronlib.interface.EthernetClientInterface):
                    interface.Disconnect()

        return ModuleConnectionCallback

    if hasattr(interface, 'SubscribeStatus'):
        interface.SubscribeStatus('ConnectionStatus', None, GetModuleCallback(interface))

    else:  # Does not have attribute 'SubscribeStatus'
        AddLogicalConnectionHandling(interface, limit=3, callback=GetModuleCallback(interface))

    if isinstance(interface, extronlib.interface.EthernetClientInterface):
        if interface.Protocol == 'TCP':  # UDP is "connection-less"
            WaitReconnect = Wait(5, interface.Connect)
            WaitReconnect.Cancel()

    # Start the connection
    if isinstance(interface, extronlib.interface.EthernetClientInterface):
        Wait(0.1, interface.Connect)


def isConnected(interface):
    if interface in ConnectionStatus:
        if ConnectionStatus[interface] in ['Online', 'Connected']:
            return True
        else:
            return False
    else:
        return False


# Logical Handler ***************************************************************
SendCounter = {  # interface: count
    # count = int(), number of queries that have been send since the last Rx
}
Callbacks = {}


def AddLogicalConnectionHandling(interface, limit=3, callback=None):
    '''
    callback should accept 3 params
        interface > extronlib.interface.EthernetClientInterface or extronlib.interface.SerialInterface or sub-class
        state > 'Connected' or 'Disconnected'
    '''
    if (isinstance(interface, EthernetClientInterface) or
            isinstance(interface, SerialInterface)
        ):
        Callbacks[interface] = callback

        if interface not in SendCounter:
            SendCounter[interface] = 0

        # Make new send method
        OldSend = interface.Send

        def NewSend(*args, **kwargs):
            # print('NewSend *args=', args, ', kwargs=', kwargs) # debugging
            SendCounter[interface] += 1

            if callback:
                if SendCounter[interface] > limit:
                    callback('ConnectionStatus', 'Disconnected', None)

            OldSend(*args, **kwargs)

        interface.Send = NewSend

        OldSendAndWait = interface.SendAndWait

        def NewSendAndWait(*args, **kwargs):
            # print('NewSendAndWait *args=', args, ', kwargs=', kwargs) # debugging

            SendCounter[interface] += 1

            if callback:
                if SendCounter[interface] > limit:
                    callback('ConnectionStatus', 'Disconnected', None)

            return OldSendAndWait(*args, **kwargs)

        interface.SendAndWait = NewSendAndWait

        ##Make new Rx handler - took this out because it was being overwritten by @event
        # OldRx = interface.ReceiveData
        # def NewRx(*args, **kwargs):
        # print('NewRx *args=', args, ', kwargs=', kwargs)
        # SendCounter[interface] = 0
        # if callback:
        # callback('ConnectionStatus', 'Connected', None)
        #
        # OldRx(*args, **kwargs)
        #
        # interface.ReceiveData = NewRx


def ConnectionHandlerLogicalReset(interface):
    # This needs to be called by the ReceiveData event elsewhere in code
    SendCounter[interface] = 0
    Callbacks[interface]('ConnectionStatus', 'Connected', None)
import extronlib
from extronlib.system import File, Wait
from extronlib import event
import time

debug = True  # Set to false to disable all print statements in this module
if not debug:
    def _new_print(*args, **kwargs):
        pass


    print = _new_print

'''
Examples of how to use this UniversalConnectionHandler class:

Proc = ProcessorDevice('ProcessorAlias')

CH = connection_handler.UniversalConnectionHandler()

@event(CH, 'Connected')
@event(CH, 'Disconnected')
def CHevent(interface, state):
    print('CHevent {} {}'.format(interface, state))

##SerialInterface Test *******************************************************
Serial = SerialInterface(Proc, 'COM1', Baud=9600)
CH.maintain(
    Serial,
    keep_alive_query_cmd='q', # The command you want to send regularly to elicit a response from the device
    poll_freq=1, # How often to send the keep_alive_query_cmd command (in seconds)
    disconnect_limit=5, # How many queries get missed before the "Disconnected" event it triggered
    )

@event(Serial, 'ReceiveData')
def SerialRxData(interface, data):
    print('SerialRxData\ninterface={}\ndata={}'.format(interface, data))
    #Do something useful here

##EthernetClientInterface TCP Test *******************************************

TCPClient = EthernetClientInterface('10.166.200.2', 23)

CH.maintain(
    TCPClient,
    keep_alive_query_cmd='q', # The command you want to send regularly to elicit a response from the device
    poll_freq=1, # How often to send the keep_alive_query_cmd command (in seconds)
    disconnect_limit=5, # How many queries get missed before the "Disconnected" event it triggered
    )

@event(TCPClient, 'ReceiveData')
def TCPClientRxData(interface, data):
    print('TCPClientRxData\ninterface={}\ndata={}'.format(interface, data))
    #Do something useful here

##Extron EthernetClass TCP Module Test *********************************************

import extr_dsp_DMP64_v1_0_0_1 as DMP_Module
ModuleEthernet = DMP_Module.EthernetClass('10.166.200.2', 23)

CH.maintain(
    ModuleEthernet,
    keep_alive_query_cmd='OutputMute', # The module command to query regularly to elicit a response from the device
    keep_alive_query_qual={'Output': '1'}, # The module qualifier to query regularly to elicit a response from the device
    poll_freq=1, # How often to send the keep_alive_query_cmd command(in seconds)
    )

##Extron SerialClass Module Test ***********************************************

ModuleSerial = DMP_Module.SerialClass(Proc, 'COM1', Baud=9600)
CH.maintain(
    ModuleSerial,
    keep_alive_query_cmd='OutputMute', #The module command to query regularly to elicit a response from the device
    keep_alive_query_qual={'Output': '1'}, #The module qualifier to query regularly to elicit a response from the device
    poll_freq=1, # How often to send the keep_alive_query_cmd command (in seconds)
    )

##EthernetServerInterfaceEx TCP Test *******************************************

ServerEx = EthernetServerInterfaceEx(1024)
CH.maintain(
    ServerEx,
    timeout=15, # After this many seconds, a client who has not sent any data to the server will be disconnected.
    )

@event(ServerEx, 'ReceiveData')
def ServerExRxData(client, data):
    print('ServerExRxData(client={}, data={})'.format(client, data))
    #Do something useful here

##EthernetClientInterface UDP Test *******************************************

UDPClient = EthernetClientInterface('10.166.200.13', 1024, Protocol='UDP', ServicePort=1024)

CH.maintain(
    UDPClient,
    keep_alive_query_cmd='ping', # The command you want to send regularly to elicit a response from the device
    poll_freq=1, # How often to send the keep_alive_query_cmd command (in seconds)
    )

@event(UDPClient, 'ReceiveData')
def UDPClientRxData(client, data):
    print('UDPClientRxData(client.IP={}, data={})'.format(client.IPAddress, data))
    #Do something useful here

##Extron EthernetClass UDP Module Test *****************************************

import sony_camera_SRG_300_Series_v1_4_1_0 as Sony_Module #uses UDP
UDPModule = Sony_Module.EthernetClass('10.166.200.13', 1024, ServicePort=1024)

CH.maintain(
    UDPModule,
    keep_alive_query_cmd='Power',  # The module command to query regularly to elicit a response from the device
    keep_alive_query_qual={'Device ID': '1'}, # The module qualifier to query regularly to elicit a response from the device
    poll_freq=1, # How often to send the keep_alive_query_cmd command (in seconds)
    )


##EthernetServerInterface TCP Test *********************************************

ServerNonExUDP = EthernetServerInterface(1024, Protocol='UDP')
print(ServerNonExUDP.StartListen())

CH.maintain(
    ServerNonExUDP
    )

@event(ServerNonExUDP, 'ReceiveData')
def ServerNonExUDPRxData(client, data):
    print('ServerNonExUDPRxData(client={}, data={})'.format(client, data))
    #Do something useful here


'''
GREEN = 2
RED = 1
WHITE = 0



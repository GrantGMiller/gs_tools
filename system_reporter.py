print('Begin system_reporter.py')

## Begin ControlScript Import --------------------------------------------------
from extronlib import event, Version
from extronlib.device import eBUSDevice, ProcessorDevice, UIDevice
from extronlib.interface import (ContactInterface, DigitalIOInterface,
    EthernetClientInterface, EthernetServerInterfaceEx, FlexIOInterface,
    IRInterface, RelayInterface, SerialInterface, SWPowerInterface,
    VolumeInterface)
from extronlib.ui import Button, Knob, Label, Level
from extronlib.system import Clock, MESet, Wait, File

from devices import *
import SMTP_client
import time

AttributeList = ['DeviceAlias',
                 'Host',
                 'ID',
                 'InactivityTime',
                 'ModelName',
                 'PartNumber',
                 'SleepState',
                 'SleepTimer',
                 
                 'CurrentLoad',
                 'FirmwareVersion',
                 'Hostname',
                 'IPAddress',
                 'MACAddress',
                 'SerialNumber',
                 'UserUsage',
                 
                 'AmbientLightValue',
                 'AutoBrightness',
                 'Brightness',
                 'DisplayState',
                 'DisplayTimer',
                 'DisplayTimerEnabled',
                 'InactivityTime',
                 'LidState',
                 'LightDetectedState',
                 'MotionDecayTime',
                 'MotionState',
                 'SleepTimerEnabled',
                 'WakeOnMotion',
                 
                 'ServicePort',
                 'Port',
                 'State',
                 
                 'Mode',
                 'Pullup',
                 
                 'Credentials',
                 'IPPort',
                 'Protocol',
                 
                 'Interface',
                 
                 'Clients',
                 'MaxClients',
                 
                 'AnalogVoltage',
                 'Lower',
                 'Upper',
                 
                 'File',
                 
                 'Baud',
                 'CharDelay',
                 'Data',
                 'FlowControl',
                 'Parity',
                 'Stop',
                 
                 'Level',
                 'Max',
                 'Min',
                 'Mute',
                 'SoftStart',
                 
                 'Days',
                 'Function',
                 'Times',
                 'WEEKDAYS',
                 
                 'Objects',
                 
                 'Function',
                 'Time',
                 
                 'BlinkState',
                 'Enabled',
                 'Name',
                 'PressedState',
                 'Visible',
                 
                 'Turned',
                 ]
AttributeList.sort()

DeviceList = [

            ProRoom115B,
            TLPRoom115B,
            
            # Fire Alarm
            FlexIOAlarm,
            
            # Screen Control
            RelayScreenUp,
            RelayScreenDown,
            
            # Power Sequencer
            RelayPowerSequencer,
            
            Display,
            
            Screen,
            
            Matrix,
            
            DSC1,
            
            AudioDSP,
            
            Bluray,
            ]

def MakeSystemReport(filename='system_report.txt'):
    print('MakeSystemReport()')
    newFile = File(filename, mode='wt')
    
    newFile.write('System Report\nTime: {}\n\n'.format(time.asctime()))
                     
    for device in DeviceList:
        newFile.write('Device: {}\n'.format(device))
        
        if hasattr(device, 'connectionFlag'):
            if getattr(device, 'connectionFlag'):
                status = 'Connected'
            else:
                status = 'Disconnected'
                
            newFile.write('{} = {}\n'.format('Connection Status', status))
             
        for att in AttributeList:
            try:
                if hasattr(device, att):
                    newFile.write('{} = {}\n'.format(att, getattr(device, att)))
            except Exception as e:
                newFile.write('{} = {}\n'.format(att, e))
                
        newFile.write('\n')
    
    newFile.close()
    print('End MakeSystemReport()')
    
def EmailSystemReport(email='gmiller@extron.com', filename='system_report.txt'):
    Email = SMTP_client.SMTP_Client('10.1.5.49', 25)
    Email.Receiver([email])
    Email.Subject('Extron Toronto Classroom - System Report')
    Email.Sender('ExtronTorontoCR@extron.com')
    Email.AddAttachement(filename)
    Email.SendMessage(msg='Please see the attached report.')
    
    
Server = EthernetServerInterfaceEx(3888)

buffer = ''
@event(Server, 'ReceiveData')
def RxDataHandler(client, data):
    global buffer
    
    data = data.decode()
    buffer += data
    print('buffer=', buffer)
    
    if buffer[-1] == '\r':
        
        if '@' in buffer:
            client.Send('Generating report.\n')
            MakeSystemReport()
            client.Send('Report Complete.\n')
            try:
                client.Send('Sending Email to {}\n'.format(buffer))
                EmailSystemReport(data)
                client.Send('Your report has been sent.\n')
            except Exception as e:
                client.Send('An error occurred.\nError:{}\n'.format(e))
            
            client.Send('Goodbye')
            client.Disconnect()
        
        buffer = ''
        
@event(Server, 'Connected')
def ServerConnectedEvent(client, data):
    client.Send('Please enter the email address to send the report to:\n')
    
Server.StartListen()
        
print('End system_reporter.py')

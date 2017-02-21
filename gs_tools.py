'''
This module is meant to handle common functionality.

v1.0.1 - Sept 16, 2016
Button.AutoStateChange('Pressed', 1)
Button.AutoStateChange('Released', 0)

This will automatically change the button state without affecting the programmers Pressed/Released handlers.

'''
print('Begin GST')

import extronlib
from extronlib import event
from extronlib.device import ProcessorDevice, UIDevice
from extronlib.interface import (EthernetClientInterface, SerialInterface)
from extronlib.system import Wait, ProgramLog, File
from extronlib.ui import Button, Level

import json
import itertools
import time


# extronlib.ui *****************************************************************
class Button(extronlib.ui.Button):
    AllButtons = []  # This will hold every instance of all buttons

    EventNames = ['Pressed',
                  'Tapped',
                  'Held',
                  'Repeated',
                  'Released',
                  ]

    def __init__(self, Host, ID, holdTime=None, repeatTime=None, PressFeedback='State'):
        extronlib.ui.Button.__init__(self, Host, ID, holdTime=holdTime, repeatTime=repeatTime)

        self.StateChangeMap = {}  # ex. {'Pressed': 1, 'Released': 0}

        for EventName in self.EventNames:
            setattr(self, 'Last' + EventName, None)

        if PressFeedback == 'State':
            self.AutoStateChange('Pressed', 1)
            self.AutoStateChange('Tapped', 0)
            self.AutoStateChange('Released', 0)

        self.Text = ''
        self.ToggleStateList = None

        self.AllButtons.append(self)

    def CheckEventHandlers(self):
        for EventName in self.EventNames:
            if EventName in self.StateChangeMap:
                CurrentAtt = getattr(self, EventName)
                LastAtt = getattr(self, 'Last' + EventName)
                if CurrentAtt != LastAtt:
                    # The curretn att has changed. make a new handler

                    def GetNewHandler(obj, evt):
                        # print('GetNewHandler Button ID {}, evt {}'.format(obj.ID, evt))
                        OldHandler = getattr(obj, evt)

                        # print('OldHandler=', OldHandler)

                        def NewHandler(button, state):
                            self._DoStateChange(state)
                            if OldHandler:
                                OldHandler(button, state)

                        return NewHandler

                    setattr(self, EventName, GetNewHandler(self, EventName))
                    NewAtt = getattr(self, EventName)
                    setattr(self, 'Last' + EventName, NewAtt)

                    # print(getattr(self, EventName))
                    # print(getattr(self, 'Last' + EventName))

    def RemoveStateChange(self):
        self.StateChangeMap = {}

    def AutoStateChange(self, eventName, buttonState):
        '''Automatically change the button to state buttonState when the eventName handler is called'''
        self.StateChangeMap[eventName] = buttonState
        Handler = getattr(self, eventName)
        if Handler == None:
            setattr(self, eventName, lambda *args: None)
            self.CheckEventHandlers()

    def _DoStateChange(self, state):
        # print(self.ID, '_DoStateChange')
        if state in self.StateChangeMap:
            # print(self.ID, 'state in self.StateChangeMap')
            NewState = self.StateChangeMap[state]
            self.SetState(NewState)

    def ShowPopup(self, popup, duration=0):
        '''This method is used to simplify a button that just needs to show a popup
        Example:
        Button(TLP, 8022).ShowPopup('Confirm - Shutdown')
        '''

        def NewFunc(button, state):
            button.Host.ShowPopup(popup, duration)

        self.Released = NewFunc
        self.CheckEventHandlers()

    def HidePopup(self, popup):
        '''This method is used to simplify a button that just needs to show a popup
        Example:
        Button(TLP, 8023).HidePopup('Confirm - Shutdown')
        '''

        def NewFunc(button, state):
            button.Host.HidePopup(popup)

        self.Released = NewFunc
        self.CheckEventHandlers()

    def SetText(self, text):
        super().SetText(text)
        self.Text = text

    def AppendText(self, text):
        self.SetText(self.Text + text)

    def ToggleVisibility(self):
        if self.Visible:
            self.SetVisible(False)
        else:
            self.SetVisible(True)

    def ToggleState(self):
        if self.ToggleStateList is None:
            if self.State == 0:
                self.SetState(1)
            else:
                self.SetState(0)
        else:
            self.SetState(next(self.ToggleStateList))

    def SetToggleList(self, toggleList):
        """Sets the list of button states that ToggleState goes through"""
        if toggleList is not None:
            self.ToggleStateList = itertools.cycle(toggleList)
        else:
            self.ToggleStateList = None


class Knob(extronlib.ui.Knob):
    pass


class Label(extronlib.ui.Label):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.Text = ''

    def SetText(self, text):
        super().SetText(text)
        self.Text = text

    def AppendText(self, text):
        self.SetText(self.Text + text)


class Level(extronlib.ui.Level):
    pass


# extronlib.system **************************************************************
class Clock(extronlib.system.Clock):
    pass


class MESet(extronlib.system.MESet):
    pass


class Wait(extronlib.system.Wait):
    """Functions that are decorated with Wait now are callable elsewhere."""

    def __call__(self, function):
        super().__call__(function)
        return function


class File(extronlib.system.File):
    pass


# extronlib.interface **************************************************************
class ContactInterface(extronlib.interface.ContactInterface):
    pass


class DigitalIOInterface(extronlib.interface.DigitalIOInterface):
    pass


class EthernetClientInterface(extronlib.interface.EthernetClientInterface):
    pass


class EthernetServerInterfaceEx(extronlib.interface.EthernetServerInterfaceEx):
    pass


class EthernetServerInterface(extronlib.interface.EthernetServerInterface):
    pass


class FlexIOInterface(extronlib.interface.FlexIOInterface):
    pass


class IRInterface(extronlib.interface.IRInterface):
    pass


class RelayInterface(extronlib.interface.RelayInterface):
    pass


class SerialInterface(extronlib.interface.SerialInterface):
    pass


class SWPowerInterface(extronlib.interface.SWPowerInterface):
    pass


class VolumeInterface(extronlib.interface.VolumeInterface):
    pass


# extronlib.device **************************************************************
class ProcessorDevice(extronlib.device.ProcessorDevice):
    pass


class UIDevice(extronlib.device.UIDevice):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.PageData = {
            #            'Page Name': 'Showing', #Possible values: 'Showing', 'Hidden', 'Unknown'
        }

        self.PopupData = {
            #            'Popup Name': 'Showing', #Possible values: 'Showing', 'Hidden', 'Unknown'
        }

        self.PopupWaits = {
            #               'Popup Name': WaitObject,
        }

    def ShowPopup(self, popup, duration=0):
        super().ShowPopup(popup)
        if duration is not 0:
            if popup in self.PopupWaits:
                self.PopupWaits[popup].Cancel()
                self.PopupWaits[popup].Change(duration)
                self.PopupWaits[popup].Restart()
            else:
                NewWait = Wait(duration, lambda: self.HidePopup(popup))
                self.PopupWaits[popup] = NewWait

        for PopupName in self.PopupData:
            if PopupName != popup:
                self.PopupData[PopupName] = 'Unknown'

        self.PopupData[popup] = 'Showing'

    def HidePopup(self, popup):
        super().HidePopup(popup)

        if popup in self.PopupWaits:
            self.PopupWaits[popup].Cancel()

        for PopupName in self.PopupData:
            if PopupName == popup:
                self.PopupData[PopupName] = 'Hidden'
            else:
                self.PopupData[PopupName] = 'Unknown'

    def HideAllPopups(self):
        super().HideAllPopups()
        for PopupName in self.PopupData:
            self.PopupData[PopupName] = 'Hidden'

    def ShowPage(self, page):
        super().ShowPage(page)

        for PageName in self.PageData:
            if PageName != page:
                self.PageData[PageName] = 'Hidden'

        self.PageData[page] = 'Showing'

    def IsShowing(self, pageOrPopupName):
        for PageName in self.PageData:
            if PageName == pageOrPopupName:
                Result = self.PageData[PageName]
                break

        # If we get to this point, the page name was not found in self.PageData
        # Check self.PopupData
        Result = 'Unknown'

        for PopupName in self.PopupData:
            if PopupName == pageOrPopupName:
                Result = self.PopupData[PopupName]
                break

        # If we get here we did not find the page/popup in self.PopupData or self.PageData
        if Result in ['Hidden', 'Unknown']:
            return False
        elif Result == 'Showing':
            return True
        elif Result == None:
            return False
            print('GST Line 202 Result == None')
        else:
            print('GST Line 207 "else"')

    def GetAllButtons(self, ID=None):
        '''
        Return list with all button objects with ID = ID
        If ID == None, return list of all buttons
        '''

        ReturnBtns = []

        for button in Button.AllButtons:
            if button.Host == self:
                if ID == None:
                    ReturnBtns.append(button)
                else:
                    if button.ID == ID:
                        ReturnBtns.append(button)

        return ReturnBtns


# extronlib *********************************************************************

class event():
    def __init__(self, objs, eventNames):
        # print('__init__(objs={}, eventNames={})'.format(objs, eventNames))
        if not isinstance(objs, list):
            objs = [objs]
        self.objs = objs

        if not isinstance(eventNames, list):
            eventNames = [eventNames]
        self.eventNames = eventNames

    def __call__(self, func):
        # print('__call__(func={})'.format(func))
        for obj in self.objs:
            for eventName in self.eventNames:
                setattr(obj, eventName, func)
            if hasattr(obj, 'CheckEventHandlers'):
                obj.CheckEventHandlers()
        return func


# Volume Handler ****************************************************************
class VolumeHandler():
    '''
    This class will take 3 buttons (up/down/mute) and info about the interface 
        and will setup the button events to send the command to the interface.
    This class does NOT handle feedback
    '''

    def __init__(self,
                 BtnUp=None,
                 BtnDown=None,
                 BtnMute=None,
                 repeatTime=0.1,
                 stepSize=1,

                 Interface=None,
                 GainCommand=None,
                 GainQualifier=None,
                 MuteCommand=None,
                 MuteQualifier=None,
                 ):

        BtnUp._repeatTime = repeatTime
        BtnDown._repeatTime = repeatTime

        @event([BtnUp, BtnDown], ['Pressed', 'Repeated'])
        def BtnUpDownEvent(button, state):
            CurrentLevel = Interface.ReadStatus(GainCommand, GainQualifier)

            if button == BtnUp:
                NewLevel = CurrentLevel + stepSize
            elif button == BtnDown:
                NewLevel = CurrentLevel - stepSize

            Interface.Set(GainCommand, NewLevel, GainQualifier)

        @event(BtnMute, 'Pressed')
        def BtnMutePressed(button, state):
            CurrentMute = Interface.ReadStatus(MuteCommand, MuteQualifier)
            if CurrentMute == 'Off':
                NewMute = 'On'
            else:
                NewMute = 'Off'
            Interface.Set(MuteCommand, NewMute, MuteQualifier)


# These functions/classes help to assign feedback to Buttons/Labels/Levels, etc

def AddTrace(InterfaceObject):
    print('AddTrace({})'.format(InterfaceObject))
    OldRxHandler = InterfaceObject.ReceiveData

    # Create a new Send Method that will also print what is sent
    def _NewSend(data):
        try:  # isinstance(InterfaceObject, SerialInterface):
            print('TRACE {} Data Out: {}'.format(InterfaceObject.Port, data))
        except:  # isinstance(InterfaceObject, EthernetClientInterface):
            print('TRACE {}:{} Data Out: {}'.format(InterfaceObject.IPAddress, InterfaceObject.IPPort, data))

        type(InterfaceObject).Send(InterfaceObject, data)

    # print('_NewSend=', _NewSend)
    InterfaceObject.Send = _NewSend

    # Create a new RxData Method that will also print what is received
    def _NewRx(interface, data):
        try:  # if isinstance(interface, SerialInterface):
            print('TRACE {} Data In: {}'.format(InterfaceObject.Port, data))
        except:  # elif isinstance(interface, EthernetClientInterface):
            print('TRACE {}:{} Data In: {}'.format(InterfaceObject.IPAddress, InterfaceObject.IPPort, data))

        if OldRxHandler is not None:
            try:
                OldRxHandler(interface, data)
            except Exception as e:
                print(e)

    # print('_NewRx=', _NewRx)
    InterfaceObject.ReceiveData = _NewRx

    #    #Create new SendAndWait
    def _NewSendAndWait(data, timeout, **delimiter):

        # Apparently SendAndWait uses the Send method. So no need to print the Send data again
        ReturnValue = type(InterfaceObject).SendAndWait(InterfaceObject, data, timeout, **delimiter)

        if isinstance(InterfaceObject, SerialInterface):
            print('TRACE', InterfaceObject.Port, 'Data In:' + str(ReturnValue))

        elif isinstance(InterfaceObject, EthernetClientInterface):

            print('TRACE', InterfaceObject.IPAddress + ':' + str(InterfaceObject.IPPort),
                  'Data In:' + str(ReturnValue))

        return ReturnValue

    # print('_NewSendAndWait=', _NewSendAndWait)
    InterfaceObject.SendAndWait = _NewSendAndWait


# Connection handler ************************************************************

ConnectionStatus = {}


def isConnected(interface):
    if interface in ConnectionStatus:
        c = ConnectionStatus[interface]
        if c == 'Connected':
            return True
        else:
            return False
    else:
        return False


# Connection Handler ***************************************************************
# Globals
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
        # If this is a server interface, then only report 'Disconnected' when there are no clients connected.
        if isinstance(interface, extronlib.interface.EthernetServerInterfaceEx):
            if len(interface.Clients) > 0:
                state = 'Connected'
            elif len(interface.Clients) == 0:
                state = 'Disconnected'

        print('connection_handler_v1_0_6 PhysicalConnectionHandler\ninterface={}\nstate={}'.format(interface, state))

        # Handle the Disconnectec/Offline event
        if state in ['Disconnected', 'Offline']:
            if isinstance(interface, extronlib.interface.EthernetClientInterface):
                if interface.Protocol == 'TCP':  # UDP is "connection-less"
                    WaitReconnect.Restart()

        # Handle the Connected/Online event
        elif state in ['Connected', 'Online']:
            if hasattr(interface, 'OnConnected'):
                interface.OnConnected()

            if isinstance(interface, extronlib.interface.EthernetClientInterface):
                if interface.Protocol == 'TCP':  # UDP is "connection-less"
                    WaitReconnect.Cancel()

        # If the status has changed from Connected to Disconnected or vice versa, log the change
        if ConnectionStatus[interface] != state:
            if isinstance(interface, extronlib.interface.EthernetClientInterface):
                print('{}:{} {}'.format(interface.IPAddress, str(interface.IPPort), state))

            elif (isinstance(interface, UIDevice) or
                      isinstance(interface, ProcessorDevice)):
                print('{} {}'.format(interface.DeviceAlias, state))

            elif isinstance(interface, extronlib.interface.SerialInterface):
                print('Proc {} Port {} {}'.format(interface.Host.DeviceAlias, interface.Port, state))

        NewStatus(interface, state, 'Physically')

    # Assign the pysical handler appropriately
    if isinstance(interface, UIDevice):
        interface.Online = PhysicalConnectionHandler
        interface.Offline = PhysicalConnectionHandler

    elif (isinstance(interface, extronlib.interface.EthernetClientInterface) or
              isinstance(interface, extronlib.interface.SerialInterface) or
              isinstance(interface, exronlib.interface.EthernetServerInterfaceEx):
        interface.Connected = PhysicalConnectionHandler
    interface.Disconnected = PhysicalConnectionHandler

    # Module Connection status

    def GetModuleCallback(interface):
        def ModuleConnectionCallback(command, value, qualifier):
            print('connection_handler_v1_0_6 ModuleConnectionCallback\ninterface={}\nvalue={}'.format(interface,
                                                                                                      value))

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


# Polling Engine ****************************************************************
class PollingEngine():
    '''
    This class lets you add a bunch of queries for differnt devices.
    The PollingEngine object will then send 1 query per second when started
    '''

    def __init__(self):

        self.Queries = []

        self.Generator = self.GetNewGenerator()

        self.PollLoop = Wait(1, self.__DoAQuery)
        self.PollLoop.Cancel()

        self.Running = False

    def GetNewGenerator(self):
        def TheGenerator():
            while True:
                # print('TheGenerator while True')
                if len(self.Queries) == 0:
                    yield None
                else:
                    for Dict in self.Queries:
                        # print('TheGenerator for Dict=', Dict)
                        yield Dict

        return TheGenerator()

    def AddQuery(self, interface, command, qualifier=None):
        '''
        This adds a query to the list of queries that will be sent. 
        One query per second.

        QueryDict should be a dictionary in the following format
        {'Interface' : DMP3,
         'Command'   : 'GroupMute',
         'Qualifier' : {'Group' : '1'},
         }

        '''
        QueryDict = {'Interface': interface,
                     'Command': command,
                     'Qualifier': qualifier,
                     }

        print('PollingEngine.AddQuery({})'.format(QueryDict))
        if ('Interface' in QueryDict and
                    'Command' in QueryDict and
                    'Qualifier' in QueryDict):
            # This is a valid QueryDict
            self.Queries.append(QueryDict)
            self.Generator = self.GetNewGenerator()
        else:
            raise Exception('Not a valid Query Dict')

    def RemoveQuery(self, QueryDict):
        '''
        Removes the query from self.Queries. 
        For example, if the system is off, we do not need to poll for input signal status on a video switcher.
        '''
        for Dict in self.Queries:
            if QueryDict['Interface'] == Dict['Interface']:
                if QueryDict['Command'] == Dict['Command']:
                    if QueryDict['Qualifier'] == Dict['Qualifier']:
                        # The QueryDict matches a dict in self.Queries. Remove it
                        self.Queries.remove(Dict)

    def Start(self):
        '''
        Start sending the queries. One query per second.
        '''
        print('PollingEngine.Start()')
        self.Running = True
        self.PollLoop.Restart()

    def Stop(self):
        '''
        Stop sending all queries.
        '''
        print('PollingEngine.Stop()')
        self.PollLoop.Cancel()
        self.Running = False

    def __DoAQuery(self):
        '''
        Private method. This actually sends the query to the device.
        '''
        # print('PollingEngine.__DoAQuery()')
        # Get the next query from the generator
        QueryInfo = next(self.Generator)
        try:
            # Parse the Query info
            Interface = QueryInfo['Interface']
            Command = QueryInfo['Command']
            Qualifier = QueryInfo['Qualifier']

            # For debugging
            # print('QueryInfo=', QueryInfo)

            # Send the Query
            Interface.Update(Command, Qualifier)

        except Exception as e:
            print(
                'PollingEngine Error:\ninterface={}\nCommand={}\nQualifier={}\nException={}'.format(Interface, Command,
                                                                                                    Qualifier, e))

        # If the polling engine is running. Do another query in 1 second.
        if self.Running:
            self.PollLoop.Restart()


# Feedback helpers **************************************************************

class VisualFeedbackHandler():
    # Class functions
    FeedbackDicts = []

    def MainVisualFeedbackHandler(self, interface, command, value, qualifier):
        # print('MainVisualFeedbackHandler(\n interface={},\n command={},\n value={},\n qualifier={})'.format(interface, command, value, qualifier))
        doCallbacks = []
        for d in self.FeedbackDicts:
            if d['interface'] == interface:
                if d['command'] == command:
                    if d['qualifier'] == qualifier:
                        obj = d['feedbackObject']
                        if 'value' in d:

                            if d[
                                'value'] == None:  # if the user didnt provide a 'value' parameter, then set the text/state for any value
                                if 'match' in d:
                                    if d['match'] == True:
                                        if 'text' in d:
                                            obj.SetText(value)

                                            # state feedback doesnt have match option

                                    else:  # match = False
                                        raise Exception(
                                            'value = None, but match = False\nSet value to not None or set match to True')

                            else:  # value is not None
                                if d['value'] == value:

                                    if 'text' in d:
                                        text = d['text']
                                        obj.SetText(text)

                                    elif 'state' in d:
                                        state = d['state']
                                        if state is not None:
                                            if isinstance(state, list):
                                                obj.SetBlinking('Slow', state)
                                            else:
                                                obj.SetState(state)

                        elif isinstance(obj, Level):
                            obj.SetLevel(int(value))

                        # Do the callback if it exist
                        if 'callback' in d:
                            if d['callback'] is not None:
                                doCallbacks.append(d['callback'])

        # Its possible for doCallbacks to contain several copies of the same callback function.
        # The code below makes sure to only call each callback once
        doneCallbacks = []
        for callback in doCallbacks:
            if callback not in doneCallbacks:
                callback(command, value, qualifier)
                doneCallbacks.append(callback)

                # Instance methods

    def TextFeedback(self, feedbackObject, text=None, interface=None, command=None, value=None, qualifier=None,
                     callback=None, match=False):
        # print('TextFeedback')
        # Create the new dict to be saved
        NewDict = {'feedbackObject': feedbackObject,
                   'text': text,
                   # if text == None, the feedbackObject will have its text set to whatever the driver returns in value
                   'interface': interface,
                   'command': command,
                   'value': value,  # if value == None: check match
                   'qualifier': qualifier,
                   'callback': callback,
                   'match': match,  # if match == True, then the value from driver will bet set to obj.SetText
                   }

        if NewDict not in self.FeedbackDicts:
            self.FeedbackDicts.append(NewDict)

        # Make the new handler so it calls the class handler with the interface parameter added
        def NewHandler(command, value, qualifier):
            # print('NewHandler(\n command={},\n value={},\n qualifier={})'.format(command, value, qualifier))
            self.MainVisualFeedbackHandler(interface, command, value, qualifier)

        interface.SubscribeStatus(command, qualifier, NewHandler)
        try:
            if hasattr(interface, 'Update{}'.format(command)):
                interface.Update(command, qualifier)
        except:
            pass

    def StateFeedback(self, feedbackObject, state, interface, command, value, qualifier=None, callback=None):
        # print('StateFeedback')
        # Create the new dict to be saved
        NewDict = {'feedbackObject': feedbackObject,
                   'state': state,  # pass a list to cause blinking
                   'interface': interface,
                   'command': command,
                   'value': value,
                   'qualifier': qualifier,
                   'callback': callback,
                   }

        if NewDict not in self.FeedbackDicts:
            self.FeedbackDicts.append(NewDict)

        # Make the new handler so it calls the class handler with the interface parameter added
        def NewHandler(command, value, qualifier):
            # print('NewHandler(\n command={},\n value={},\n qualifier={})'.format(command, value, qualifier))
            self.MainVisualFeedbackHandler(interface, command, value, qualifier)

        interface.SubscribeStatus(command, qualifier, NewHandler)
        try:
            if hasattr(interface, 'Update{}'.format(command)):
                interface.Update(command, qualifier)
        except:
            pass

    def LevelFeedback(self, feedbackObject, interface, command, qualifier=None, callback=None, max_=100, min_=0,
                      step=1):
        # print('StateFeedback')
        # Create the new dict to be saved
        NewDict = {'feedbackObject': feedbackObject,
                   'interface': interface,
                   'command': command,
                   'qualifier': qualifier,
                   'callback': callback,
                   'max': max_,
                   'min': min_,
                   'step': step,
                   }

        feedbackObject.SetRange(min_, max_, step)

        if NewDict not in self.FeedbackDicts:
            self.FeedbackDicts.append(NewDict)

        # Make the new handler so it calls the class handler with the interface parameter added
        def NewHandler(command, value, qualifier):
            # print('NewHandler(\n command={},\n value={},\n qualifier={})'.format(command, value, qualifier))
            self.MainVisualFeedbackHandler(interface, command, value, qualifier)

        interface.SubscribeStatus(command, qualifier, NewHandler)
        try:
            if hasattr(interface, 'Update{}'.format(command)):
                interface.Update(command, qualifier)
        except:
            pass


# Helpful functions *************************************************************
def ShortenText(text, MaxLength=7, LineNums=2):
    text = text.replace('Lectern', 'Lect')
    text = text.replace('Quantum', 'Qtm')
    text = text.replace('Projector', 'Proj')
    text = text.replace('Confidence', 'Conf')
    text = text.replace('Monitor', 'Mon')
    text = text.replace('Left', 'L')
    text = text.replace('Right', 'R')
    text = text.replace('Program', 'Pgm')
    text = text.replace('Annotator', 'Antr')
    text = text.replace('Preview', 'Prev')
    text = text.replace('From', 'Frm')
    text = text.replace('Display', 'Disp')
    text = text.replace('Audio', 'Aud')
    text = text.replace('Wireless', 'Wless')
    text = text.replace('Handheld', 'HH')
    text = text.replace('Display', 'Disp')
    text = text.replace('Floorbox', 'FlrBx')
    text = text.replace('Laptop', 'Lap')

    if len(text) > MaxLength:
        text = text[:MaxLength * LineNums]
        textSplit = text.split()
        if len(textSplit) > 0:
            NewText = ''
            while True:
                if len(textSplit) > 0:
                    if len(NewText) + len(' ') + len(textSplit[0]) <= MaxLength:
                        NewText += ' ' + textSplit.pop(0)
                    else:
                        break
                else:
                    break
            NewText += '\n'
            NewText += ' '.join(textSplit)
            text = NewText

    return text


def PrintProgramLog():
    """usage:
   print = PrintProgramLog()
   """

    def print(*args, sep=' ', end='\n', severity='info',
              **kwargs):  # override the print function to write to program log instead
        # Following is done to emulate behavior Python's print keyword arguments
        # (ie. you can set the arguments to None and it will do the default behavior)
        if sep is None:
            sep = ' '

        if end is None:
            end = '\n'

        string = []
        for arg in args:
            string.append(str(arg))
        ProgramLog(sep.join(string) + end, severity)

    return print


class PersistantVariables():
    def __init__(self, filename):
        self.filename = filename

        if not File.Exists(filename):
            # If the file doesnt exist yet, create a blank file
            file = File(filename, mode='wt')
            file.write(json.dumps({}))
            file.close()

    def Set(self, varName, varValue):
        # load the current file
        file = File(self.filename, mode='rt')
        data = json.loads(file.read())
        file.close()

        # Add/change the value
        data[varName] = varValue

        # Write new file
        file = File(self.filename, mode='wt')
        file.write(json.dumps(data))
        file.close()

    def Get(self, varName):
        # If the varName does not exist, return None

        # load the current file
        file = File(self.filename, mode='rt')
        data = json.loads(file.read())
        file.close()

        # Grab the value and return it
        try:
            varValue = data[varName]
        except KeyError:
            varValue = None
            self.Set(varName, varValue)

        return varValue


RemoteTraceServer = None


def RemoteTrace(IPPort=1024):
    # this method return a new print function that will print to stdout and also send to any clients connected to the server defined on port IPPort
    global RemoteTraceServer

    # Start a new server
    if RemoteTraceServer == None:
        RemoteTraceServer = EthernetServerInterfaceEx(IPPort)

        @event(RemoteTraceServer, ['Connected', 'Disconnected'])
        def RemoteTraceServerConnectEvent(client, state):
            print('Client {}:{} {}'.format(client.IPAddress, client.ServicePort, state))

        result = RemoteTraceServer.StartListen()
        print('RemoteTraceServer {}'.format(result))

    def print2(*args):  # override the print function to write to program log instead
        string = ''
        for arg in args:
            string += ' ' + str(arg)

        for client in RemoteTraceServer.Clients:
            client.Send(string + '\n')
        print(string)

    return print2


def toPercent(Value, Min=0, Max=100):
    if Value < Min:
        return 0
    elif Value > Max:
        return 100

    TotalRange = Max - Min
    # print('TotalRange=', TotalRange)

    FromMinToValue = Value - Min
    # print('FromMinToValue=', FromMinToValue)

    Percent = (FromMinToValue / TotalRange) * 100

    return Percent


def IncrementIP(IP):
    IPsplit = IP.split('.')

    Oct1 = int(IPsplit[0])
    Oct2 = int(IPsplit[1])
    Oct3 = int(IPsplit[2])
    Oct4 = int(IPsplit[3])

    Oct4 += 1
    if Oct4 > 255:
        Oct4 = 0
        Oct3 += 1
        if Oct3 > 255:
            Oct3 = 0
            Oct2 += 1
            if Oct2 > 255:
                Oct2 = 0
                Oct1 += 1
                if Oct1 > 255:
                    Oct1 = 0

    return str(Oct1) + '.' + str(Oct2) + '.' + str(Oct3) + '.' + str(Oct4)


print('End  GST')

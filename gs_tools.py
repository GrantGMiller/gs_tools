'''
This module is meant to be a collection of tools to simplify common task in AV control systems.
March 28, 2017
'''
print('Begin GST')

import extronlib
from extronlib import event, Version
from extronlib.device import ProcessorDevice, UIDevice
from extronlib.interface import (EthernetClientInterface, SerialInterface)
from extronlib.system import Wait, ProgramLog, File, Ping, RFile
from extronlib.ui import Button, Level

import json
import itertools
import time
import copy
import hashlib

# Set this false to disable all print statements ********************************
debug = True
if not debug:
    def newPrint(*args, **kwargs):
        pass

    print = newPrint

# *******************************************************************************

# extronlib.ui *****************************************************************
class Button(extronlib.ui.Button):
    AllButtons = []  # This will hold every instance of all buttons

    EventNames = ['Pressed',
                  'Tapped',
                  'Held',
                  'Repeated',
                  'Released',
                  ]

    def __init__(self, Host, ID, holdTime=None, repeatTime=None, PressFeedback=None):
        '''

        :param Host: extronlib.device.UIDevice instance
        :param ID: int()
        :param holdTime: float()
        :param repeatTime: float()
        :param PressFeedback: If you want the button to change states when you press/release, set this to 'State'
        '''
        extronlib.ui.Button.__init__(self, Host, ID, holdTime=holdTime, repeatTime=repeatTime)

        self.StateChangeMap = {}  # ex. {'Pressed': 1, 'Released': 0}

        for EventName in self.EventNames:
            setattr(self, 'Last' + EventName, None)

        if not debug:
            if PressFeedback == 'State':
                self.AutoStateChange('Pressed', 1)
                self.AutoStateChange('Tapped', 0)
                self.AutoStateChange('Released', 0)

        self.Text = ''
        self.ToggleStateList = None

        self.AllButtons.append(self)

    def _CheckEventHandlers(self):
        for EventName in self.EventNames:
            if EventName in self.StateChangeMap:
                CurrentAtt = getattr(self, EventName)
                LastAtt = getattr(self, 'Last' + EventName)
                if CurrentAtt != LastAtt:
                    # The current att has changed. Make a new handler

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
        '''
        This will disable all states changes based on press/release
        :return:
        '''
        self.StateChangeMap = {}

    def AutoStateChange(self, eventName, buttonState):
        '''
        This is used to change the button state based on a certain event.
        This is non-destructive. Your previously defined events will be maintained.
        :param eventName: ie. 'Pressed', 'Released', etc
        :param buttonState: The button will change to this state when the event happens.
        :return:
        '''
        self.StateChangeMap[eventName] = buttonState
        Handler = getattr(self, eventName)
        if Handler == None:
            setattr(self, eventName, lambda *args: None)
            self._CheckEventHandlers()

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
        self._CheckEventHandlers()

    def ShowPage(self, page):
        def NewFunc(button, state):
            button.Host.ShowPage(page)

        self.Released = NewFunc
        self._CheckEventHandlers()

    def HidePopup(self, popup):
        '''This method is used to simplify a button that just needs to hide a popup
        Example:
        Button(TLP, 8023).HidePopup('Confirm - Shutdown')
        '''

        def NewFunc(button, state):
            button.Host.HidePopup(popup)

        self.Released = NewFunc
        self._CheckEventHandlers()

    def SetText(self, text):
        if not isinstance(text, str):
            text = str(text)
        super().SetText(text)
        self.Text = text

    def GetText(self):
        '''
        This object will store the last value assigned with .SetText()
        You can retrieve the current text using this method.
        Note: If you call .GetText() without first calling .SetText() this method will return ''
        :return:
        '''
        return self.Text

    def AppendText(self, text):
        '''
        This method will append to the current text.
        Note: you must call .SetText() before you call .AppendText()
        :param text:
        :return:
        '''
        self.SetText(self.Text + text)

    def BackspaceText(self):
        self.SetText(self.Text[:-1])

    def ToggleVisibility(self):
        '''
        An easy way to toggle visibility
        :return:
        '''
        if self.Visible:
            self.SetVisible(False)
        else:
            self.SetVisible(True)

    def ToggleState(self):
        '''
        An easy way to toggle state
        :return:
        '''
        if self.ToggleStateList is None:
            if self.State == 0:
                self.SetState(1)
            else:
                self.SetState(0)
        else:
            self.SetState(next(self.ToggleStateList))

    def SetToggleList(self, toggleList):
        '''
        This toggles a button through the list of states every time .ToggleState() is called.
        :param toggleList: The list of button states to toggle through.
        :return:
        '''
        if toggleList is not None:
            self.ToggleStateList = itertools.cycle(toggleList)
        else:
            self.ToggleStateList = None

    def __str__(self):
        return '{}, Host.DeviceAlias={}, ID={}'.format(super().__str__(), self.Host.DeviceAlias, self.ID)


class Knob(extronlib.ui.Knob):
    def __str__(self):
        return '{}, Host.DeviceAlias={}, ID={}'.format(super().__str__(), self.Host.DeviceAlias, self.ID)


class Label(extronlib.ui.Label):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.Text = ''

    def SetText(self, text):
        super().SetText(text)
        self.Text = text

    def AppendText(self, text):
        self.SetText(self.Text + text)

    def BackspaceText(self):
        self.SetText(self.Text[:-1])

    def __str__(self):
        return '{}, Host.DeviceAlias={}, ID={}'.format(super().__str__(), self.Host.DeviceAlias, self.ID)


class Level(extronlib.ui.Level):
    def __str__(self):
        return '{}, Host.DeviceAlias={}, ID={}'.format(super().__str__(), self.Host.DeviceAlias, self.ID)


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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._keep_alive_running = False
        self._keep_alive_Timer = None

    def __str__(self):
        return '{}, IPAddress={}, IPPort={}'.format(super().__str__(), self.IPAddress, self.IPPort)

    def __iter__(self):
        '''
        This allows an interface to be cast as a dict
        '''
        for item in ['Credentials',
                     'Hostname',
                     'IPAddress',
                     'IPPort',
                     'Protocol',
                     'ServicePort',
                     ]:
            yield item, getattr(self, item)

        yield 'Type', str(type(self))

    def StartKeepAlive(self, t, cmd):
        #super().StartKeepAlive does not call .Send apparently so im doing it differnt
        if self._keep_alive_running is False:
            self._keep_alive_running = True

            if self._keep_alive_Timer is None:
                def SendCMD():
                    self.Send(cmd)

                self._keep_alive_Timer = Timer(t, SendCMD)

            self._keep_alive_Timer.Start()


    def StopKeepAlive(self):
        if self._keep_alive_running is True:
            self._keep_alive_running = False

            if self._keep_alive_Timer is not None:
                self._keep_alive_Timer.Stop()

def get_parent(client_obj):
    '''
    This function is used to get the parent EthernetServerInterfaceEx from a ClientObject
    :param client_obj: extronlib.interface.EthernetServerInterfaceEx.ClientObject
    :return:
    '''
    for interface in EthernetServerInterfaceEx._all_servers_ex.values():
        for client in interface.Clients:
            if client.IPAddress == client_obj.IPAddress:
                if client.ServicePort == client_obj.ServicePort:
                    return interface

class EthernetServerInterfaceEx(extronlib.interface.EthernetServerInterfaceEx):
    '''
    If the programmer tries to instantiate 2 objects with the same port number,
        a Exception will be thrown.
    However, if the programmer wishes, they can call EthernetServerInterfaceEx.clear_port_in_use().
        This will allow the programmer to instantiate the object again, but any event associated with the first object
        will be overridden by @events on the second object.
    '''
    _all_servers_ex = {  # int(port_number): EthernetServerInterfaceExObject,
    }
    _ports_in_use = []  # list of ints representing ports that are in use

    def __new__(cls, *args, **kwargs):
        print('EthernetServerInterfaceEx.__new__(args={}, kwargs={})'.format(args, kwargs))

        if len(args) > 0:
            port = args[0]
        else:
            port = kwargs.get('IPPort')

        if port is not None:
            if port in cls._ports_in_use:
                ProgramLog(
                    'EthernetServerInterfaceEx IPPort {} is already in use.\nIf you really want to instantiate another object on this same port, you can first call EthernetServerInterfaceEx.clear_port_in_use({})'.format(
                        port, port), 'error')
                raise Exception('EthernetServerInterfaceEx IPPort {} is already in use.'.format(port))
            else:
                # port is not in use. either because the programmer hasnt instantiated one yet, or he called "clear_port_in_use"
                if port in cls._all_servers_ex:
                    print(
                        'EthernetServerInterfaceEx.__new__\n This server already exist. return old server for port {}\n old_server={}'.format(
                            port, cls._all_servers_ex[port]))
                    ProgramLog(
                        'This EthernetServerInterfaceEx is already in use.\n New events will now override old events.\n This may not be the expected behavior.\n Consider choosing a different port.',
                        'warning')
                    return cls._all_servers_ex[port]
                else:
                    print('EthernetServerInterfaceEx.__new__\n Creating new EthernetServerInterfaceEx')
                    return super().__new__(cls)
        else:
            print('Error in EthernetServerInterfaceEx.__new__\n port={}'.format(port))

    def __init__(self, *args, **kwargs):
        print('EthernetServerInterfaceEx.__init__\n, args={}\n kwargs={}'.format(args, kwargs))

        if len(args) > 0:
            port = args[0]
        else:
            port = kwargs.get('IPPort')

        if self not in self._all_servers_ex.values():
            print('This interface has never been init before. init for the first time')
            print('super(EthernetServerInterfaceEx).__init__')
            self._listen_state = None

            self._all_servers_ex[port] = self

            if port not in self._ports_in_use:
                self._ports_in_use.append(port)

            super().__init__(*args, **kwargs)

        else:
            print('EthernetServerInterfaceEx.__init__\n This interface has been instantiated before. do nothing')
            pass

        print('EthernetServerInterfaceEx.__init__ complete')

    def StartListen(self):
        print('EthernetServerInterfaceEx.StartListen() before={}'.format(self._listen_state))
        if self._listen_state is not 'Listening':
            self._listen_state = super().StartListen()

        print(
            'EthernetServerInterfaceEx.StartListen\n self={}\n self._listen_state={}'.format(self, self._listen_state))
        return self._listen_state

    def StopListen(self):
        super().StopListen()
        self._listen_state = 'Not Listening'

    @classmethod
    def port_in_use(cls, port_number):
        if port_number in cls._ports_in_use:
            print('EthernetServerInterfaceEx.port_in_use({}) return True'.format(port_number))
            return True
        else:
            print('EthernetServerInterfaceEx.port_in_use({}) return False'.format(port_number))
            return False

    @classmethod
    def clear_port_in_use(cls, port_number):
        print('EthernetServerInterfaceEx.clear_port_in_use({})'.format(port_number))
        if port_number in cls._ports_in_use:
            cls._ports_in_use.remove(port_number)

    def __str__(self):
        return '{}, IPPort={}'.format(super(), self.IPPort)

    def __iter__(self):
        '''
        This allows an interface to be cast as a dict.
        This can be used to save data about this ServerEx so that it can be re-instantiated after a power cycle.
        '''
        for item in ['IPPort',
                     'Interface',
                     'MaxClients',
                     'Protocol',
                     ]:
            yield item, getattr(self, item)

        yield 'Type', str(type(self))


class EthernetServerInterface(extronlib.interface.EthernetServerInterface):
    pass


class FlexIOInterface(extronlib.interface.FlexIOInterface):
    pass


class IRInterface(extronlib.interface.IRInterface):
    pass


class RelayInterface(extronlib.interface.RelayInterface):
    pass


class SerialInterface(extronlib.interface.SerialInterface):
    def __new__(cls, *args, **kwargs):
        '''
        https://docs.python.org/3/reference/datamodel.html#object.__new__

        The return value of __new__() should be the new object instance (usually an instance of cls).
        '''
        print('SerialInterface.__new__(args={}, kwargs={})'.format(args, kwargs))

        if len(args) > 0:
            Host = args[0]
        else:
            Host = kwargs.get('Host')

        if len(args) > 1:
            Port = args[1]
        else:
            Port = kwargs.get('Port')

        if not Host.port_in_use(Port):
            serial_interface = ProcessorDevice._get_serial_instance(*args, **kwargs)
            if serial_interface is not None:
                print('An old serial_interface has been found. use it')
                return serial_interface

            elif serial_interface is None:
                print('This is the first time this interface has been instantiated. call super new')
                return super().__new__(cls)
        else:
            raise Exception(
                'This com port is already in use.\nConsider using Host.make_port_available({})'.format(Port))

    def __init__(self, *args, **kwargs):
        Host = None
        if len(args) > 0:
            Host = args[0]
        else:
            Host = kwargs['Host']

        Port = None
        if len(args) > 1:
            Port = args[1]
        else:
            Port = kwargs['Port']

        if Port not in ProcessorDevice._serial_instances[Host.DeviceAlias].keys():
            print('This is the first time this port has been init')
            super().__init__(*args, **kwargs)
        else:
            print('This has been init before. do nothing')
            pass

        ProcessorDevice._register_new_serial_instance(self)

    def Initialize(self, **kwargs):
        print('SerialInterface.Initialize(kwargs={})'.format(kwargs))
        super().Initialize(**kwargs)
        print('end Initialize')

    def __str__(self):
        try:
            return '{}, Host.DeviceAlias={}, Port={}'.format(super().__str__(), self.Host.DeviceAlias, self.Port)
        except:
            return super().__str__()

    def __iter__(self):
        '''
        This allows an interface to be cast as a dict
        '''
        for item in ['Baud',
                     'CharDelay',
                     'Data',
                     'FlowControl',
                     'Mode',
                     'Parity',
                     'Port',
                     'Stop',
                     ]:
            yield item, getattr(self, item)

        yield 'Host.DeviceAlias', self.Host.DeviceAlias
        yield 'Type', str(type(self))


class SWPowerInterface(extronlib.interface.SWPowerInterface):
    pass


class VolumeInterface(extronlib.interface.VolumeInterface):
    pass


# extronlib.device **************************************************************
class ProcessorDevice(extronlib.device.ProcessorDevice):
    _serial_ports_in_use = {  # ProcessorDevice.DeviceAlias: ['COM1', 'COM2', ...]
    }

    _serial_instances = {  # ProcessorDevice.DeviceAliasA: {'COM1': SerialInterfaceObjectA1,
        # 'COM2': SerialInterfaceObjectA2,
        # },
        # ProcessorDevice.DeviceAliasB: {'COM1': SerialInterfaceObjectB1,
        # 'COM2': SerialInterfaceObjectB2,
        # },
    }

    _processor_device_instances = {  # ProcessorDevice.DeviceAlias: ProcessorDeviceObject
    }

    @classmethod
    def _register_new_serial_instance(cls, instance):
        print('ProcessorDevice._register_new_serial_instance(instance={})'.format(instance))
        cls._serial_instances[instance.Host.DeviceAlias][instance.Port] = instance

        if instance.Port not in cls._serial_ports_in_use[instance.Host.DeviceAlias]:
            cls._serial_ports_in_use[instance.Host.DeviceAlias].append(instance.Port)

    @classmethod
    def _get_serial_instance(cls, Host, Port, **kwargs):
        print('ProcessorDevice._get_serial_instance(Host={}\n Port={}\n kwargs={}'.format(Host, Port, kwargs))
        # return new/old serial instance
        if Port not in cls._serial_ports_in_use[Host.DeviceAlias]:
            print(
                'The port is availble. Either becuase it has never been instantiated or cuz the programmer called "_make_port_available"')

            if Port in cls._serial_instances[Host.DeviceAlias].keys():
                print('A SerialInterface already exist. Re-initialize it and return the old serial_interface')
                serial_interface = cls._serial_instances[Host.DeviceAlias][Port]
                serial_interface.Initialize(**kwargs)
                print('serial_interface=', serial_interface)
                return serial_interface
            else:
                print('This SerialInterface has NOT been instantiated before. return None')
                return None
        else:
            print('This port is not available')
            raise Exception(
                'This port is not available.\n Consider calling ProcessorDevice._make_port_available(Host, Port)')

    @classmethod
    def _make_port_available(cls, Host, Port):
        print('ProcessorDevice._make_port_available(Host={}\n Port={}'.format(Host, Port))
        # return None
        if Port in cls._serial_ports_in_use[Host.DeviceAlias]:
            print('The port has already been instantiated. but make it available again')
            cls._serial_ports_in_use[Host.DeviceAlias].remove(Port)
        else:
            print('The port has never been instantiated. do nothing.')
            pass

    def __new__(cls, *args, **kwargs):
        '''
        If the programmer instantiates the same processor twice, the instantiation will return the same object instead of creating a new object
        '''
        print('ProcessorDevice.__new__(args={}, kwargs={})'.format(args, kwargs))

        device_alias = args[0]

        if device_alias not in cls._serial_ports_in_use:
            cls._serial_ports_in_use[device_alias] = []

        if device_alias not in cls._serial_instances:
            cls._serial_instances[device_alias] = {}

        if device_alias not in cls._processor_device_instances:
            # no processor with this device_alias has ever been instantiated. super().__new__
            return super().__new__(cls)
        else:
            old_proc = cls._processor_device_instances[device_alias]
            return old_proc

    def __init__(self, *args, **kwargs):
        print('ProcessorDevice.__init__\n self={}\n args={}, kwargs={}'.format(self, args, kwargs))

        device_alias = args[0]
        if device_alias not in self._processor_device_instances:
            # this is the first time .__init__ has been called on this processor
            super().__init__(*args, **kwargs)
            self._processor_device_instances[device_alias] = self
        else:
            # this processor has been init before. do nothing
            pass

    def port_in_use(self, port_str):
        print('ProcessorDevice.port_in_use\n self={}\n port_str={}\n\n self._serial_ports_in_use={}'.format(self,
                                                                                                            port_str,
                                                                                                            self._serial_ports_in_use))

        if port_str in self._serial_ports_in_use[self.DeviceAlias]:
            return True
        else:
            return False

    def make_port_available(self, port_str):
        print('ProcessorDevice.clear_port_in_use\n self={}\n port_str={}'.format(self, port_str))
        self._make_port_available(self.Host, self.Port)

    def __str__(self):
        try:
            return 'self={}, self.DeviceAlias={}, self.IPAddress={}'.format(super().__str__(), self.DeviceAlias,
                                                                            self.IPAddress)
        except:
            return super().__str__()


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

        self._exclusive_modals = []

    def ShowPopup(self, popup, duration=0):
        if popup in self._exclusive_modals:
            for modal_name in self._exclusive_modals:
                if modal_name != popup:
                    self.HidePopup(modal_name)
                else:
                    self._DoShowPopup(modal_name)
        else:
            self._DoShowPopup(popup, duration)

    def _DoShowPopup(self, popup, duration=0):
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
        '''
        Returns True if popup with name pageOrPopupName is definitely showing.
        Returns False if it might be showing, or is hidden. This depends on weather the popup is exclusive to other popups.
        :param pageOrPopupName: string
        :return: bool
        '''

        Result = 'Unknown'

        for PageName in self.PageData:
            if PageName == pageOrPopupName:
                Result = self.PageData[PageName]
                break

        # If we get to this point, the page name was not found in self.PageData
        # Check self.PopupData

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
        Returns button objects with this ID.
        This will return any button object that has been instantiated from any UIDevice host.
        :param ID: int
        :return: Button object
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

    def SetExclusiveModals(self, modals):
        self._exclusive_modals = modals


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
            if hasattr(obj, '_CheckEventHandlers'):
                obj._CheckEventHandlers()
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
        '''

        :param BtnUp: extronlib.ui.Button instance
        :param BtnDown: extronlib.ui.Button instance
        :param BtnMute: extronlib.ui.Button instance
        :param repeatTime: float
        :param stepSize: float
        :param Interface: Extron driver module.
        :param GainCommand: str
        :param GainQualifier: dict
        :param MuteCommand: str
        :param MuteQualifier: dict
        '''

        BtnUp._repeatTime = repeatTime
        BtnDown._repeatTime = repeatTime

        @event([BtnUp, BtnDown], ['Pressed', 'Repeated'])
        def BtnUpDownEvent(button, state):
            CurrentLevel = Interface.ReadStatus(GainCommand, GainQualifier)
            if CurrentLevel is None:
                CurrentLevel = -100

            if button == BtnUp:
                NewLevel = CurrentLevel + stepSize
            elif button == BtnDown:
                NewLevel = CurrentLevel - stepSize

            Interface.Set(GainCommand, NewLevel, GainQualifier)

        if BtnMute:
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
    '''
    Calling AddTrace(extronlib.interface.* ) will add a print statement to all Send/SendAndWait/ReceiveData calls
    This is non-destructive to the event handlers that have already been defined.
    :param InterfaceObject:
    :return:
    '''
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

_connection_status = {}


def isConnected(interface):
    '''
    The programmer must call HandleConnection(interface) before caling isConnected(). If not this will return False always.
    This will return True if the interface is logically or physically connected .
    This will return False if the interface is logically or physically disconnected.
    :param interface: extronlib.interface.*
    :return: bool
    '''
    if interface in _connection_status:
        c = _connection_status[interface]
        if c == 'Connected':
            return True
        else:
            return False
    else:
        return False


# Connection Handler ***************************************************************
# Globals
if not File.Exists('connection_handler.log'):
    file = File('connection_handler.log', mode='wt')
    file.close()

with File('connection_handler.log', mode='at') as file:
    file.write('\n{} - Processor Restarted\n\n'.format(time.asctime()))

_connection_status = {}

GREEN = 2
RED = 1
WHITE = 0


def _NewStatus(interface, state, Type='Unknown'):
    if not interface in _connection_status:
        _connection_status[interface] = 'Default'

    oldStatus = _connection_status[interface]

    if state != oldStatus:
        # New status
        _connection_status[interface] = state

        if interface in user_physical_connection_callbacks:
            callback = user_physical_connection_callbacks[interface]
            callback(interface, state)

        with File('connection_handler.log', mode='at') as file:
            write_str = '{}\n    {}:{}\n'.format(time.asctime(), 'type', type(interface))

            for att in [
                'IPAddress',
                'IPPort',
                'DeviceAlias',
                'Port',
                'Host',
                'ServicePort',
            ]:
                if hasattr(interface, att):
                    write_str += '    {}:{}\n'.format(att, getattr(interface, att))

            write_str += '    {}:{}\n'.format('ConnectionStatus', state)

            file.write(write_str)

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


user_physical_connection_callbacks = {}


def AddConnectionCallback(interface, callback):
    user_physical_connection_callbacks[interface] = callback


_server_timeout_counters = {  # TODO - implement into HandleConnection
    # extronlib.EthernetServerInterfaceEx.ClientObject : float(lastCommTime),
}


def RemoveConnectionHandlers(interface):
    print('RemoveConnectionHandlers\n interface={}'.format(interface))
    interface.Connected = None
    interface.Disconnected = None
    if interface in _connection_status:
        _connection_status.pop(interface)
    print('_connection_status=', _connection_status)


def HandleConnection(interface, serverLimit=None):
    '''
    This will attempt to maintain the connection to the interface.
     The programmer can call isConnected(interface) to find if this interface is connected.
     Also the connection status will be logged to a file 'connection_handler.log' on the processor.
    :param interface: extronlib.interface.* or extronlib.device.*
    :param serverLimit: str(), None or 'One connection per IP'
    :return:
    '''
    print('HandleConnection(interface={})'.format(interface))
    _NewStatus(interface, 'Default')

    if isinstance(interface, extronlib.interface.EthernetClientInterface):
        if interface.Protocol == 'TCP':  # UDP is "connection-less"
            WaitReconnect = Wait(5, interface.Connect)
            WaitReconnect.Cancel()

    # Physical connection status
    def _PhysicalConnectionHandler(interface, state):
        # TODO: Add socket timeout. If no comunication for X seconds, disconnect the client.

        # Reset the send-counter if applicable
        if interface in _connection_send_counter:
            if state == 'Connected':
                _connection_send_counter[interface] = 0

        if isinstance(interface, extronlib.interface.EthernetServerInterfaceEx.ClientObject):

            if serverLimit == 'One connection per IP':
                if state == 'Connected':
                    # Disconnect any other sockets that have connected from the same IP.
                    # print('interface._parent.Clients=', interface._parent.Clients)
                    # print('interface=', interface)
                    for client in interface._parent.Clients:
                        if client != interface:
                            if client.IPAddress == interface.IPAddress:
                                print('Only one connection allowed per IP.\nDisconnecting client=', client)
                                client.Disconnect()  # There is another client connected from the same IP. Disconnect it.

            # Convert ClientObjects to ServerEx
            interface = interface._parent  # This "_parent" attribute is not documented. Shhhh...

        # If this is a server interface, then only report 'Disconnected' when there are no clients connected.
        if isinstance(interface, extronlib.interface.EthernetServerInterfaceEx):
            if len(interface.Clients) > 0:
                state = 'Connected'
            elif len(interface.Clients) == 0:
                state = 'Disconnected'

        print('PhysicalConnectionHandler\ninterface={}\nstate={}'.format(interface, state))

        # Handle the Disconnected/Offline event
        if state in ['Disconnected', 'Offline']:
            if isinstance(interface, extronlib.interface.EthernetClientInterface):
                if interface.Protocol == 'TCP':  # UDP is "connection-less"
                    if interface in _connection_status:
                        print('_PhysicalConnectionHandler Disconnected WaitReconnect.Restart()')
                        WaitReconnect.Restart()

        # Handle the Connected/Online event
        elif state in ['Connected', 'Online']:
            if hasattr(interface, 'OnConnected'):
                interface.OnConnected()

            if isinstance(interface, extronlib.interface.EthernetClientInterface):
                if interface.Protocol == 'TCP':  # UDP is "connection-less"
                    if interface in _connection_status:
                        print('_PhysicalConnectionHandler Connected WaitReconnect.Restart()')
                        WaitReconnect.Cancel()

        # If the status has changed from Connected to Disconnected or vice versa, log the change
        if _connection_status[interface] != state:
            if isinstance(interface, extronlib.interface.EthernetClientInterface):
                print('{}:{} {}'.format(interface.IPAddress, str(interface.IPPort), state))

            elif (isinstance(interface, extronlib.device.UIDevice) or
                      isinstance(interface, extronlib.device.ProcessorDevice)):
                print('{} {}'.format(interface.DeviceAlias, state))

            elif isinstance(interface, extronlib.interface.SerialInterface):
                print('Proc {} Port {} {}'.format(interface.Host.DeviceAlias, interface.Port, state))

        _NewStatus(interface, state, 'Physically')

    # Assign the pysical handler appropriately
    if isinstance(interface, extronlib.device.UIDevice):
        interface.Online = _PhysicalConnectionHandler
        interface.Offline = _PhysicalConnectionHandler

    elif (isinstance(interface, extronlib.interface.EthernetClientInterface) or
              isinstance(interface, extronlib.interface.SerialInterface) or
              isinstance(interface, extronlib.interface.EthernetServerInterfaceEx)
          ):
        interface.Connected = _PhysicalConnectionHandler
        interface.Disconnected = _PhysicalConnectionHandler

    # Module Connection status
    def _GetModuleCallback(interface):
        def _module_connection_callback(command, value, qualifier):
            print('_module_connection_callback\ninterface={}\nvalue={}'.format(interface, value))

            _NewStatus(interface, value, 'Logically')

            if value == 'Disconnected':
                if isinstance(interface, extronlib.interface.EthernetClientInterface):
                    interface.Disconnect()

        return _module_connection_callback

    if hasattr(interface, 'SubscribeStatus'):
        interface.SubscribeStatus('_connection_status', None, _GetModuleCallback(interface))

    else:  # Does not have attribute 'SubscribeStatus'
        if isinstance(interface, extronlib.interface.SerialInterface):
            limit = 15  # serial data tends to get "chopped up" so this limit should be larger
        else:
            limit = 15
        _AddLogicalConnectionHandling(interface, limit=limit, callback=_GetModuleCallback(interface))

    # Start the connection
    if isinstance(interface, extronlib.interface.EthernetClientInterface):
        Wait(0.1, interface.Connect)
    elif isinstance(interface, extronlib.interface.EthernetServerInterfaceEx):
        interface.StartListen()


# Logical Handler ***************************************************************
_connection_send_counter = {  # interface: count
    # count = int(), number of queries that have been send since the last Rx
}
_connection_callbacks = {}


def _AddLogicalConnectionHandling(interface, limit=3, callback=None):
    '''
    callback should accept 3 params
        interface > extronlib.interface.EthernetClientInterface or extronlib.interface.SerialInterface or sub-class
        state > 'Connected' or 'Disconnected'
    '''

    if (isinstance(interface, extronlib.interface.EthernetClientInterface) or
            isinstance(interface, SerialInterface)
        ):
        _connection_callbacks[interface] = callback

        if interface not in _connection_send_counter:
            _connection_send_counter[interface] = 0

        # Make new send method
        OldSend = interface.Send

        def NewSend(*args, **kwargs):
            print('NewSend\n interface={}\n args={}\n kwargs={}\n count={}\n limit={}'.format(interface, args, kwargs,
                                                                                              _connection_send_counter[
                                                                                                  interface],
                                                                                              limit))  # debugging
            _connection_send_counter[interface] += 1

            if callback:
                if _connection_send_counter[interface] > limit:
                    callback('_connection_status', 'Disconnected', None)

            OldSend(*args, **kwargs)

        interface.Send = NewSend

        OldSendAndWait = interface.SendAndWait

        def NewSendAndWait(*args, **kwargs):
            print('NewSendAndWait *args=', args, ', kwargs=', kwargs) # debugging

            _connection_send_counter[interface] += 1

            if callback:
                if _connection_send_counter[interface] > limit:
                    callback('_connection_status', 'Disconnected', None)

            return OldSendAndWait(*args, **kwargs)

        interface.SendAndWait = NewSendAndWait

def ConnectionHandlerLogicalReset(interface):
    '''
    This needs to be called by the programmer when a valid command is received by the interface.
    Usually called within ReceiveData event.
    :param interface: extronlib.interface.* instance
    :return:
    '''
    global _connection_callbacks
    _connection_send_counter[interface] = 0

    if interface in _connection_callbacks:
        _connection_callbacks[interface]('_connection_status', 'Connected', None)
    else:
        # ProgramLog(
        # 'interface {} has no connection callback\n_connection_callbacks={}\n_connection_send_counter={}'.format(
        # interface, _connection_callbacks, _connection_send_counter), 'info')
        pass


# Polling Engine ****************************************************************
class PollingEngine():
    '''
    This class lets you add a bunch of queries for different devices.
    The PollingEngine object will then send 1 query per second when started
    '''

    def __init__(self):

        self.Queries = []

        self.Generator = self.GetNewGenerator()

        self.PollLoop = Timer(1, self.__DoAQuery)
        self.PollLoop.Stop()

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
        This info will be used to send a interface.Update(command, qualifier) later.

        :param interface: extronlib.interface.*
        :param command: str
        :param qualifier: dict
        :return:
        '''
        QueryDict = {'Interface': interface,
                     'Command': command,
                     'Qualifier': qualifier,
                     'Type': 'Module',
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

    def AddRawQuery(self, interface, command='q'):
        QueryDict = {'Interface': interface,
                     'Command': command,
                     'Qualifier': None,
                     'Type': 'Raw',
                     }
        print('PollingEngine.AddRawQuery({})'.format(QueryDict))
        self.Queries.append(QueryDict)
        self.Generator = self.GetNewGenerator()

    def RemoveQuery(self, QueryDict):
        '''
        Removes the query from polling engine
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
        self.PollLoop.Start()

    def Stop(self):
        '''
        Stop sending all queries.
        '''
        print('PollingEngine.Stop()')
        self.PollLoop.Stop()
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
            Type = QueryInfo['Type']

            # For debugging
            # print('QueryInfo=', QueryInfo)

            # Send the Query
            if Type == 'Module':
                Interface.Update(Command, Qualifier)
            elif Type == 'Raw':
                Interface.Send(Command)

        except Exception as e:
            print(
                'PollingEngine Error:\ninterface={}\nCommand={}\nQualifier={}\nException={}'.format(Interface, Command,
                                                                                                    Qualifier, e))



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

    def TextFeedback(self,
                     feedbackObject,
                     text=None,
                     interface=None,
                     command=None,
                     value=None,
                     qualifier=None,
                     callback=None,
                     match=False):
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

    def LevelFeedback(self,
                      feedbackObject,  # extronlib.ui.Level instance
                      interface,  # Extron driver module
                      command,  # str
                      qualifier=None,  # dict
                      callback=None,  # function
                      max_=100,  # float
                      min_=0,  # float
                      step=1):  # float
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
    try:
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
    except Exception as e:
        print(e)
        #ProgramLog('gs_tools toPercent Erorr: {}'.format(e), 'error')
        return 0


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

    return '{}.{}.{}.{}'.format(Oct1, Oct2, Oct3, Oct4)


def is_valid_ipv4(ip):
    """Validates IPv4 addresses.
    """
    ip_split = ip.split('.')
    if len(ip_split) != 4:
        return False

    for octet in ip_split:
        try:
            octet_int = int(octet)
            if not 0 <= octet_int <= 255:
                return False
        except:
            return False

    return True


def GetKeyFromValue(d, v):
    '''
    This function does a "reverse-lookup" in a dictionary.
    You give this function a value and it returns the key
    :param d: dictionary
    :param v: value within d
    :return: first key from d that has the value = v. If v is not found in v, return None
    '''
    for k in d:
        if d[k] == v:
            return k


def phone_format(n):
    try:
        n = strip_non_numbers(n)
        return format(int(n[:-1]), ",").replace(",", "-") + n[-1]
    except:
        return n


def strip_non_numbers(s):
    new_s = ''
    for ch in s:
        if ch.isdigit():
            new_s += ch
    return new_s


class Keyboard():
    '''
    An object that manages the keyboard buttons.
    If a keyboard button is pressed, self.string will be updated accordingly.

    This will allow the programmer to copy/paste the keyboard GUI page into their GUID project without worrying about the KeyIDs
    '''

    def __init__(self, TLP=None, KeyIDs=[], BackspaceID=None, ClearID=None, FeedbackObject=None, SpaceBarID=None,
                 ShiftID=None):
        print('Keyboard object initializing')

        self.TLP = TLP
        self.KeyIDs = KeyIDs
        self.KeyButtons = []
        self.ShiftID = ShiftID
        self.FeedbackObject = FeedbackObject

        self.TextFields = {}  # Format: {FeedbackObject : 'Text'}, this keeps track of the text on various Label objects.

        self.bDelete = extronlib.ui.Button(TLP, BackspaceID, holdTime=0.2, repeatTime=0.1)

        self.string = ''

        self.CapsLock = True  # default caps lock setting at boot-up
        self.ShiftMode = 'Upper'
        self._password_mode = False

        # Clear Key
        if ClearID is not None:
            self.bClear = extronlib.ui.Button(TLP, ClearID)

            @event(self.bClear, 'Pressed')
            def clearPressed(button, state):
                # print(button.Name, state)
                self.ClearString()

        # Delete key
        @event(self.bDelete, 'Pressed')
        @event(self.bDelete, 'Tapped')
        @event(self.bDelete, 'Repeated')
        @event(self.bDelete, 'Released')
        def deletePressed(button, state):
            # print(button.Name, state)
            if state == 'Pressed':
                button.SetState(1)

            elif state in ['Tapped', 'Released']:
                button.SetState(0)

            if state in ['Pressed', 'Repeated']:
                self.deleteCharacter()

                # Spacebar

        if SpaceBarID is not None:
            @event(extronlib.ui.Button(TLP, SpaceBarID), 'Pressed')
            def SpacePressed(button, state):
                # print(button.Name, state)
                self.AppendToString(' ')

        # Character Keys
        def CharacterPressed(button, state):
            # print(button.Name, state)
            # print('Before self.CapsLock=', self.CapsLock)
            # print('Before self.ShiftMode=', self.ShiftMode)

            if state == 'Pressed':
                button.SetState(1)
                Char = button.Name

                if ShiftID is not None:
                    if self.ShiftMode == 'Upper':
                        Char = Char.upper()
                    else:
                        Char = Char.lower()

                self.AppendToString(Char)

            elif state == 'Released':
                if self.CapsLock == False:
                    if self.ShiftMode == 'Upper':
                        self.ShiftMode = 'Lower'
                        self.updateKeysShiftMode()

                button.SetState(0)

                # print('After self.CapsLock=', self.CapsLock)
                # print('After self.ShiftMode=', self.ShiftMode)

        for ID in KeyIDs:
            NewButton = extronlib.ui.Button(TLP, ID)
            NewButton.Pressed = CharacterPressed
            NewButton.Released = CharacterPressed
            self.KeyButtons.append(NewButton)

        # Shift Key
        if ShiftID is not None:
            self.ShiftKey = extronlib.ui.Button(TLP, ShiftID, holdTime=1)

            @event(self.ShiftKey, 'Pressed')
            @event(self.ShiftKey, 'Tapped')
            @event(self.ShiftKey, 'Held')
            @event(self.ShiftKey, 'Released')
            def ShiftKeyEvent(button, state):
                # print(button.Name, state)
                # print('Before self.CapsLock=', self.CapsLock)
                # print('Before self.ShiftMode=', self.ShiftMode)

                if state == 'Pressed':
                    button.SetState(1)
                    button.SetState(0)

                elif state == 'Tapped':
                    if self.CapsLock == True:
                        self.CapsLock = False
                        self.ShiftMode = 'Lower'

                    elif self.CapsLock == False:
                        if self.ShiftMode == 'Upper':
                            self.ShiftMode = 'Lower'

                        elif self.ShiftMode == 'Lower':
                            self.ShiftMode = 'Upper'

                    self.updateKeysShiftMode()

                elif state == 'Held':
                    self.CapsLock = not self.CapsLock

                    if self.CapsLock == True:
                        self.ShiftMode = 'Upper'

                    elif self.CapsLock == False:
                        self.ShiftMode = 'Lower'

                    self.updateKeysShiftMode()

                    # print('After self.CapsLock=', self.CapsLock)
                    # print('After self.ShiftMode=', self.ShiftMode)

            self.updateKeysShiftMode()

        self.updateLabel()

    def updateKeysShiftMode(self):
        if self.ShiftID is not None:
            if self.ShiftMode == 'Upper':
                self.ShiftKey.SetState(1)

            elif self.ShiftMode == 'Lower':
                self.ShiftKey.SetState(0)

            for button in self.KeyButtons:
                Char = button.Name
                if Char:
                    if self.ShiftID is not None:
                        if self.ShiftMode == 'Upper':
                            Char = Char.upper()
                        else:
                            Char = Char.lower()

                        button.SetText(Char)

    # Define the class methods
    def GetString(self):
        '''
        return the value of the keyboard buffer
        '''
        # print('Keyboard.GetString()=',self.string)
        return self.string

    def ClearString(self):
        '''
        clear the keyboard buffer
        '''
        # print('Keyboard.ClearString()')
        self.string = ''
        self.ShiftID = 'Upper'
        self.updateLabel()

    def AppendToString(self, character=''):
        '''
        Add a character(s) to the string
        '''
        # print('Keyboard.AppendToString()')
        self.string += character
        self.updateLabel()

    def deleteCharacter(self):
        '''
        Removes one character from the end of the string.
        '''
        # print('deleteCharacter before=',self.string)
        self.string = self.string[0:len(self.string) - 1]
        print('deleteCharacter after=', self.string)
        self.updateLabel()

    def updateLabel(self):
        '''
        Updates the TLP label with the current self.string
        '''
        # print('updateLabel()')
        if self._password_mode:
            pw_string = ''
            for ch in self.GetString():
                pw_string += '*'
            if self.FeedbackObject:
                self.FeedbackObject.SetText(pw_string)
        else:
            if self.FeedbackObject:
                self.FeedbackObject.SetText(self.GetString())
                # print('self.FeedbackObject=', self.FeedbackObject)

        if len(self.GetString()) == 0:
            if self.bClear.Visible:
                self.bClear.SetVisible(False)
        else:
            if not self.bClear.Visible:
                self.bClear.SetVisible(True)

    def SetFeedbackObject(self, NewFeedbackObject):
        '''
        Changes the ID of the object to receive feedback.
        This class will remember the text that should be applied to each feedback object.
        Allowing the user/programmer to switch which field the keyboard is modifiying, on the fly.
        '''
        # Save the current text
        self.TextFields[self.FeedbackObject] = self.GetString()

        # Load new text (if available)
        try:
            self.string = self.TextFields[NewFeedbackObject]
        except:
            self.string = ''

        # Update the TLP
        self.FeedbackObject = NewFeedbackObject
        self.updateLabel()

    def GetFeedbackObject(self):
        return self.FeedbackObject

    def set_password_mode(self, mode):
        self._password_mode = mode


# ScrollingTable ****************************************************************
ScrollingTable_debug = False


class ScrollingTable():
    # helper class **************************************************************
    class Cell():
        def __init__(self, parent_table, row, col, btn=None, callback=None):
            self._parent_table = parent_table
            self._row = row
            self._col = col
            self._btn = btn
            self._callback = callback
            self._Text = ''

            OldHandler = self._btn.Released

            def NewHandler(button, state):
                if ScrollingTable_debug and debug: print(
                    'Cell NewHandler(\n button={}\n state={}'.format(button, state))
                if OldHandler:
                    OldHandler(button, state)
                if self._callback:
                    self._callback(self._parent_table, self)

            self._btn.Released = NewHandler

        def SetText(self, text):
            if self._Text is not text:
                self._btn.SetText(text)
                self._Text = text

        def get_col(self):
            return self._col

        def get_row(self):
            return self._row

        def get_value(self):
            return self._Text

        def get_button(self):
            return self._btn

        def __str__(self):
            return 'Cell Object:\nrow={}\ncol={}\nbtn={}\ncallback={}'.format(self._row, self._col, self._btn,
                                                                              self._callback)

    # class ********************************************************************
    def __init__(self):

        self._header_btns = []
        self._cells = []
        self._data_rows = []  # list of dicts. each list element is a row of data. represents the full spreadsheet.
        self._current_row_offset = 0  # indicates the data row in the top left corner
        self._current_col_offset = 0  # indicates the data col in the top left corner
        self._max_row = 0  # height of ui table. 0 = no ui table, 1 = single row ui table, etc...
        self._max_col = 0  # width of ui table. 0 = no ui table, 1 = single column ui table, etc
        self._table_header_order = []

        self._cell_pressed_callback = None
        self._scroll_level = None

        # _cell_pressed_callback should accept 2 params; the scrolling table object, and the cell object

        def UpdateTable():
            try:
                self._update_table()
            except Exception as e:
                # need this try/except because current Wait class only shows generic "Wait error" message
                if ScrollingTable_debug and debug: print('Exception in self._update_table()\n', e)

        self._refresh_Wait = Wait(0.2,
                                  UpdateTable)  # This controls how often the table UI gets updated. 0.2 seconds means the TLP has a  max refresh of 5 times per second.
        self._refresh_Wait.Cancel()

    @property
    def CellPressed(self):  # getter
        return self._cell_pressed_callback

    @CellPressed.setter
    def CellPressed(self, func):
        #func should accept two params the ScrollingTable object and the Cell object
        self._cell_pressed_callback = func
        for cell in self._cells:
            cell._callback = func

    def set_table_header_order(self, header_list=[]):
        # header_list example: ['IP Address', 'Port']
        all_headers = []
        for row in self._data_rows:
            for key in row:
                if key not in all_headers:
                    all_headers.append(key)

        all_headers.sort()  # if some headers are not defined, put them alphabetically

        for key in header_list:
            if key in all_headers:
                all_headers.remove(key)

        # now all_headers contains all headers that are not in header_list
        header_list.extend(all_headers)
        self._table_header_order = header_list

        self._refresh_Wait.Restart()

    def register_header_buttons(self, *args):
        '''
        example: ScrollingTable.register_header_buttons(Button(TLP, 1), Button(TLP, 2) )
        '''
        self._header_btns = []
        for arg in args:
            self._header_btns.append(arg)

        @event(self._header_btns, 'Released')
        def header_btn_event(button, state):
            index = self._header_btns.index(button)
            self.sort_by_column(index)

        self._refresh_Wait.Restart()

    def register_row_buttons(self, row_number, *args):
        ''' *args = tuple of Button objects
        example:
        ScrollingTable.register_row(row_number=1, Button(TLP, 1), Button(TLP, 2) )
        '''
        index = 0
        for arg in args:
            arg.SetText('')
            col_number = index
            self.register_cell(row_number, col_number, btn=arg, callback=self._cell_pressed_callback)
            index += 1

        self._refresh_Wait.Restart()

    def add_new_row_data(self, row_dict):
        '''example:
        ScrollingTable.register_data_row({'key1':'value1', 'key2':'value2', ...})
        '''
        if ScrollingTable_debug and debug: print('ScrollingTable.add_new_row_data(row_dict={})'.format(row_dict))
        self._data_rows.append(row_dict)

        for key in row_dict:
            if key not in self._table_header_order:
                self._table_header_order.append(key)

        self._refresh_Wait.Restart()

    def clear_all_data(self):
        if ScrollingTable_debug and debug: print('ScrollingTable.clear_all_data()')
        self._data_rows = []
        self.reset_scroll()
        self._update_table()

    def update_row_data(self, where_dict, replace_dict):
        '''
        Find a row in self._data_rows that containts all the key/value pairs from where_dict
        replace/append the key/value pairs in that row with the key/values from replace_dict

        '''
        if ScrollingTable_debug and debug: print(
            'ScrollingTable.update_row_data(where_dict={}, replace_dict={})'.format(where_dict, replace_dict))
        # Check the data for a row that containts the key/value pair from where_dict

        if len(self._data_rows) == 0:
            return False

        for row in self._data_rows:
            # verify all the keys from where_dict are in row and the values match
            all_keys_match = True
            for key in where_dict:
                if key in row:
                    if where_dict[key] != row[key]:
                        all_keys_match = False
                        break
                else:
                    all_keys_match = False
                    break

            if all_keys_match:
                # All the key/values from where_dict match row, update row with replace dict values
                for key in replace_dict:
                    row[key] = replace_dict[key]

        self._refresh_Wait.Restart()

    def has_row(self, where_dict):
        if ScrollingTable_debug and debug: print('ScrollingTable.has_row(where_dict={})'.format(where_dict))
        if ScrollingTable_debug and debug:
            if ScrollingTable_debug and debug: print('self._data_rows=', self._data_rows)
        # Check the data for a row that containts the key/value pair from where_dict

        if len(self._data_rows) == 0:
            if ScrollingTable_debug and debug: print('ScrollingTable.has_row return False')
            return False

        for row in self._data_rows:
            # verify all the keys from where_dict are in row and the values match
            all_keys_match = True
            for key in where_dict:
                if key in row:
                    if where_dict[key] != row[key]:
                        all_keys_match = False
                        break
                else:
                    all_keys_match = False
                    break

            if all_keys_match:
                if ScrollingTable_debug and debug: print('ScrollingTable.has_row return True')
                return True

        if ScrollingTable_debug and debug: print('ScrollingTable.has_row return False')
        return False

    def delete_row(self, where_dict):
        if not self.has_row(where_dict):
            return
        else:
            for row in self._data_rows.copy():
                # verify all the keys from where_dict are in row and the values match
                all_keys_match = True
                for key in where_dict:
                    if key in row:
                        if where_dict[key] != row[key]:
                            all_keys_match = False
                            break
                    else:
                        all_keys_match = False
                        break

                if all_keys_match:
                    # all keys match in this row. remove it
                    if ScrollingTable_debug and debug: print('ScrollingTable.delete_row\nremoving row={}'.format(row))
                    self._data_rows.remove(row)

        self._update_table()

    def register_cell(self, *args, **kwargs):
        NewCell = self.Cell(self, *args, **kwargs)
        self._cells.append(NewCell)

        self._find_max_row_col()

        self._refresh_Wait.Restart()

    def _find_max_row_col(self):
        for cell in self._cells:
            if cell._col > self._max_col:
                self._max_col = cell._col + 1  # self._max_col is width of ui table(not 0 base)

            if cell._row > self._max_row:
                self._max_row = cell._row + 1  # self._max_row is height of ui table(not 0 base)

    def scroll_up(self):
        if ScrollingTable_debug and debug: print('ScrollingTable.scroll_up(self={})'.format(self))
        if ScrollingTable_debug and debug: print('self._current_row_offset=', self._current_row_offset)
        self._current_row_offset -= 1
        if self._current_row_offset < 0:
            self._current_row_offset = 0

        self._update_table()

    def scroll_down(self):
        if ScrollingTable_debug and debug: print('ScrollingTable.scroll_down(self={})'.format(self))
        if ScrollingTable_debug and debug: print('self._current_row_offset=', self._current_row_offset)
        if ScrollingTable_debug and debug: print('self._max_row=', self._max_row)
        if ScrollingTable_debug and debug: print('len(self._data_rows)=', len(self._data_rows))

        max_offset = len(self._data_rows) - self._max_row
        if max_offset < 0:
            max_offset = 0
        if ScrollingTable_debug and debug: print('max_offset=', max_offset)

        self._current_row_offset += 1
        if self._current_row_offset > max_offset:
            self._current_row_offset = max_offset

        self._update_table()

    def scroll_left(self):
        if ScrollingTable_debug and debug: print('ScrollingTable.scroll_left(self={})'.format(self))
        self._current_col_offset -= 1
        if self._current_col_offset < 0:
            self._current_col_offset = 0

        self._update_table()

    def scroll_right(self):
        if ScrollingTable_debug and debug: print('ScrollingTable.scroll_right(self={})'.format(self))

        max_offset = len(self._table_header_order) - self._max_col
        if max_offset < 0:
            max_offset = 0

        self._current_col_offset += 1
        if self._current_col_offset > max_offset:
            self._current_col_offset = max_offset

        self._update_table()

    def _update_table(self):
        if ScrollingTable_debug and debug: print('ScrollingTable._update_table()')

        # iterate over all the cell objects
        for cell in self._cells:
            row_index = cell._row + self._current_row_offset
            if ScrollingTable_debug and debug:
                print('cell=', cell)
                print('cell._row=', cell._row)
                print('self._current_row_offset=', self._current_row_offset)
                print('row_index=', row_index)
                print('self._data_rows=', self._data_rows)
                print('len(self._data_rows)=', len(self._data_rows))
                pass

            # Is there data for this cell to display?
            if row_index <= len(self._data_rows) - 1:
                # Yes there is data for this cell to display

                row_dict = self._data_rows[row_index]
                # row_dict holds the data for this row
                if ScrollingTable_debug and debug: print('row_dict=', row_dict)

                col_header_index = cell._col + self._current_col_offset
                if col_header_index >= len(self._table_header_order):
                    # There is a cell button that does not header associated.
                    cell.SetText('')
                    continue
                # col_header_index is int() base 0 (left most col is 0)
                # if ScrollingTable_debug and debug: print('col_header_index=', col_header_index)

                # if ScrollingTable_debug and debug: print('self._table_header_order=', self._table_header_order)
                col_header = self._table_header_order[col_header_index]
                # if ScrollingTable_debug and debug: print('col_header=', col_header)

                # if ScrollingTable_debug and debug: print('row_dict=', row_dict)

                if col_header in row_dict:
                    cell_data = row_dict[col_header]  # cell_data holds data for this cell
                else:
                    # There is no data for this column header
                    cell_data = ''

                # if ScrollingTable_debug and debug: print('cell_data=', cell_data)

                cell.SetText(str(cell_data))
            else:
                # no data for this cell
                cell.SetText('')

        # update scroll_level
        if self._scroll_level:
            max_row_offset = len(self._data_rows) - self._max_row
            percent = toPercent(self._current_row_offset, 0, max_row_offset)
            self._scroll_level.SetLevel(percent)

    def get_column_buttons(self, col_number):
        # returns all buttons in the column.
        # Note: they may not be in order
        btn_list = []

        for cell in self._cells:
            if cell._col == col_number:
                btn_list.append(cell._btn)

        return btn_list

    def get_row_from_button(self, button):
        for cell in self._cells:
            if cell._btn == button:
                return cell._row

        raise Exception('Button {} not found in table'.format(button))

    def get_cell_value(self, row_number, col_number):
        for cell in self._cells:
            if cell._row == row_number:
                if cell._col == col_number:
                    return cell._btn.Text

        raise Exception(
            'ScrollingTable.get_cell_value Not found. row_number={}, col_number={}'.format(row_number, col_number))

    def reset_scroll(self):
        self._current_row_offset = 0
        self._refresh_Wait.Restart()

    def sort_by_column(self, col_number):
        if ScrollingTable_debug and debug: print('ScrollingTable sort_by_column(col_number={})'.format(col_number))
        if ScrollingTable_debug and debug: print('self._data_rows=', self._data_rows)
        all_values = []

        col_header = self._table_header_order[col_number]

        for row in self._data_rows:
            if col_header in row:
                all_values.append(row[col_header])

        # We now have all the row values in all_values
        try:
            all_values.sort()  # Sort them
        except exception as e:
            print('ScrollingTable.sort_by_column ERROR\n {}'.format(e))

        # We now have all the values sorted, but there may be duplicats
        all_values_no_dup = []
        for value in all_values:
            if value not in all_values_no_dup:
                all_values_no_dup.append(value)

        all_values = all_values_no_dup
        # We now have all the sorted values with no duplicates

        new_rows = []
        old_rows = copy.copy(self._data_rows)  # dont want to modify the real data yet. in case this method crashes
        temp_rows = copy.copy(old_rows)  # dont want to change a list while interating thru it

        for this_value in all_values:
            for row in temp_rows:
                index = old_rows.index(row)
                if col_header in row:
                    if row[col_header] == this_value:
                        move_row = old_rows.pop(index)
                        new_rows.append(move_row)

            # reset temp_rows
            temp_rows = copy.copy(old_rows)

        # new_rows now contains all the row data from the sorted values
        # new_rows may be missing some rows that did not have col_header

        # old_rows contains any leftovers, move them to new_rows
        new_rows.extend(old_rows)
        if ScrollingTable_debug and debug: print('sorted new_rows=', new_rows)
        self._data_rows = new_rows
        self._refresh_Wait.Restart()

    def register_scroll_level(self, level):
        # level = extronlib.ui.Level
        self._scroll_level = level


# UserInput *********************************************************************
class UserInputClass:
    def __init__(self, TLP):
        self._TLP = TLP

        self._kb_feedback_btn = None
        self._kb_text_feedback = None

    def setup_list(self,
                   list_popup_name,  # str()
                   list_btn_hide,  # Button object
                   list_btn_table,  # list()
                   list_btn_scroll_up=None,  # Button object
                   list_btn_scroll_down=None,  # Button object
                   list_label_message=None,  # Button/Label object
                   ):

        self._list_popup_name = list_popup_name
        self._list_table = ScrollingTable()
        self._list_callback = None
        self._list_label_message = list_label_message

        # Setup the ScrollingTable
        for btn in list_btn_table:

            # Add an event handler for the table buttons
            @event(btn, 'Released')
            def list_btn_event(button, state):
                print('list_btn_event')
                print('self._list_passthru=', self._list_passthru)
                print('button=', button)
                print('button.Text=', button.Text)

                # If a button with no text is selected. Do nothing.
                if button.Text == '':
                    print('button.Text == ''\nPlease select a button with text')
                    return

                if self._list_callback:
                    if self._list_passthru is not None:
                        self._list_callback(self, button.Text, self._list_passthru)
                    else:
                        self._list_callback(self, button.Text)

                if self._list_feedback_btn:
                    self._list_feedback_btn.SetText(button.Text)

                self._TLP.HidePopup(self._list_popup_name)

            # Register the btn with the ScrollingTable instance
            row_number = list_btn_table.index(btn)
            self._list_table.register_row_buttons(row_number, btn)

        # Setup Scroll buttons
        if list_btn_scroll_up:
            if not list_btn_scroll_up._repeatTime:
                list_btn_scroll_up._repeatTime = 0.1

            @event(list_btn_scroll_up, ['Pressed', 'Repeated'])
            def list_btn_scroll_upEvent(button, state):
                self._list_table.scroll_up()

        if list_btn_scroll_down:
            if not list_btn_scroll_down._repeatTime:
                list_btn_scroll_down._repeatTime = 0.1

            @event(list_btn_scroll_down, ['Pressed', 'Repeated'])
            def list_btn_scroll_downEvent(button, state):
                self._list_table.scroll_down()

        # Hide button
        @event(list_btn_hide, 'Released')
        def list_btn_hideEvent(button, state):
            button.Host.HidePopup(list_popup_name)

    def get_list(self,
                 options=None,  # list()
                 callback=None,
                 # function - should take 2 params, the UserInput instance and the value the user submitted
                 feedback_btn=None,
                 passthru=None,  # any object that you want to pass thru to the callback
                 message=None,
                 sort=False,
                 ):
        self._list_callback = callback
        self._list_feedback_btn = feedback_btn
        self._list_passthru = passthru

        # Update the table with new data
        self._list_table.clear_all_data()

        # try to sort the options
        if sort == True:
            try:
                options.sort()
            except:
                pass

        for option in options:
            self._list_table.add_new_row_data({'Option': option})

        if self._list_label_message:
            if message:
                self._list_label_message.SetText(message)
            else:
                self._list_label_message.SetText('Select an item from the list.')

        # Show the list popup
        self._TLP.ShowPopup(self._list_popup_name)

    def setup_keyboard(self,
                       kb_popup_name,  # str()
                       kb_btn_submit,  # Button()
                       kb_btn_cancel=None,  # Button()

                       KeyIDs=None,  # list()
                       BackspaceID=None,  # int()
                       ClearID=None,  # int()
                       SpaceBarID=None,  # int()
                       ShiftID=None,  # int()
                       FeedbackObject=None,  # object with .SetText() method
                       kb_btn_message=None,
                       ):

        self._kb_popup_name = kb_popup_name
        self._kb_btn_message = kb_btn_message

        @event(kb_btn_submit, 'Released')
        def kb_btn_submitEvent(button, state):
            string = self._kb_Keyboard.GetString()
            print('kb_btn_submitEvent\n button.ID={}\n state={}\n string={}'.format(button.ID, state, string))

            self._TLP.HidePopup(self._kb_popup_name)

            if self._kb_callback:
                if self._kb_passthru:
                    self._kb_callback(self, string, self._kb_passthru)
                else:
                    self._kb_callback(self, string)

            if self._kb_feedback_btn:
                self._kb_feedback_btn.SetText(string)

        if kb_btn_cancel:
            @event(kb_btn_cancel, 'Released')
            def kb_btn_cancelEvent(button, state):
                self._TLP.HidePopup(self._kb_popup_name)

        self._kb_Keyboard = Keyboard(
            TLP=self._TLP,
            KeyIDs=KeyIDs,  # list()
            BackspaceID=BackspaceID,  # int()
            ClearID=ClearID,  # int()
            SpaceBarID=SpaceBarID,  # int()
            ShiftID=ShiftID,  # int()
            FeedbackObject=FeedbackObject,  # object with .SetText() method
        )

    def get_keyboard(self,
                     kb_popup_name=None,
                     callback=None,
                     # function - should take 2 params, the UserInput instance and the value the user submitted
                     feedback_btn=None,
                     password_mode=False,
                     text_feedback=None,  # button()
                     passthru=None,  # any object that you want to also come thru the callback
                     message=None,
                     ):

        if kb_popup_name:
            self._kb_popup_name = kb_popup_name

        if message:
            if self._kb_btn_message:
                self._kb_btn_message.SetText(message)
        else:
            if self._kb_btn_message:
                self._kb_btn_message.SetText('Please enter your text.')

        self._kb_Keyboard.set_password_mode(password_mode)

        if text_feedback:
            self._kb_text_feedback = text_feedback  # button to show text as it is typed
            self._kb_Keyboard.SetFeedbackObject(self._kb_text_feedback)

        self._kb_callback = callback  # function accepts 2 params; this UserInput instance and the value submitted
        self._kb_feedback_btn = feedback_btn  # button to assign submitted value
        self._kb_passthru = passthru

        self._kb_Keyboard.ClearString()

        self._TLP.ShowPopup(self._kb_popup_name)

    def setup_boolean(self,
                      bool_popup_name,  # str()

                      bool_btn_true,  # Button()
                      bool_btn_false,  # Button()
                      bool_btn_cancel=None,  # Button()

                      bool_btn_message=None,
                      ):
        self._bool_callback = None
        self._bool_true_text = 'Yes'
        self._bool_false_text = 'No'

        self._bool_popup_name = bool_popup_name

        self._bool_btn_true = bool_btn_true
        self._bool_btn_false = bool_btn_false
        self._bool_btn_cancel = bool_btn_cancel

        self._bool_btn_message = bool_btn_message

        @event(self._bool_btn_true, 'Released')
        @event(self._bool_btn_false, 'Released')
        def _bool_btn_event(button, state):
            if button == self._bool_btn_true:
                if self._bool_callback:
                    if self._bool_passthru:
                        self._bool_callback(self, True, self._bool_passthru)
                    else:
                        self._bool_callback(self, True)

                    if self._bool_feedback_btn:
                        self._bool_feedback_btn.SetText(self._bool_true_text)

            elif button == self._bool_btn_false:
                if self._bool_callback:
                    if self._bool_passthru:
                        self._bool_callback(self, False, self._bool_passthru)
                    else:
                        self._bool_callback(self, False)

                    if self._bool_feedback_btn:
                        self._bool_feedback_btn.SetText(self._bool_false_text)

            button.Host.HidePopup(self._bool_popup_name)

        if self._bool_btn_cancel:
            @event(self._bool_btn_cancel, 'Released')
            def _bool_btn_cancelEvent(button, state):
                _bool_btn_event(button, state)

    def get_boolean(self,
                    callback=None,
                    # function - should take 2 params, the UserInput instance and the value the user submitted
                    feedback_btn=None,
                    passthru=None,  # any object that you want to also come thru the callback
                    message=None,
                    true_text=None,
                    false_text=None,
                    ):
        self._bool_callback = callback
        self._bool_passthru = passthru
        self._bool_true_text = true_text
        self._bool_false_text = false_text
        self._bool_feedback_btn = feedback_btn

        if message:
            self._bool_btn_message.SetText(message)
        else:
            self._bool_btn_message.SetText('Are you sure?')

        if true_text:
            self._bool_btn_true.SetText(true_text)
        else:
            self._bool_btn_true.SetText('Yes')

        if false_text:
            self._bool_btn_false.SetText(false_text)
        else:
            self._bool_btn_false.SetText('No')

        self._bool_btn_true.Host.ShowPopup(self._bool_popup_name)


# Non-global variables **********************************************************
class NonGlobal:
    '''
    This class could be replaced by global vars, but it makes the management and readability better
    '''

    def Set(self, name_of_value_str, value):
        setattr(self, name_of_value_str, value)

    def Get(self, name_of_value_str):
        return getattr(self, name_of_value_str)


# Hash function *****************************************************************
def hash_it(string=''):
    '''This method takes in a string and returns a SHA512 hash of that string'''
    arbitrary_string = 'gs_tools_arbitrary_string'
    string += arbitrary_string
    return hashlib.sha512(bytes(string, 'utf-8')).hexdigest()

#Timer class (safer than recursive Wait objects per PD)
class Timer:
    def __init__(self, t, func):
        '''
        This class calls self.func every t-seconds until Timer.Stop() is called.
        :param t: float
        :param func: callable (no parameters)
        '''
        print('Timer.__init__(t={}, func={})'.format(t, func))
        self._func = func
        self._t = t
        self._run = False

    def Stop(self):
        print('Timer.Stop()')
        self._run = False

    def Start(self):
        print('Timer.Start()')
        if self._run is False:
            self._run = True

            @Wait(0.0001)  # Start immediately
            def loop():
                #print('entering loop()')
                while self._run:
                    #print('in while self._run')
                    time.sleep(self._t)
                    self._func()
                #print('exiting loop()')

    def Restart(self):
        #To easily replace a Wait object
        self.Start()

    def Cancel(self):
        #To easily replace a Wait object
        self.Stop()


print('End  GST')

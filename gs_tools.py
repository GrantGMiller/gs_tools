'''
This module is meant to be a collection of tools to simplify common task in AV control systems.
Started: March 28, 2017 and appended to continuously
'''


import extronlib
from extronlib import event, Version
from extronlib.device import ProcessorDevice, UIDevice
from extronlib.interface import (EthernetClientInterface, SerialInterface)
from extronlib.system import Wait, ProgramLog, File, Ping, RFile, Clock
from extronlib.ui import Button, Level

try:
    import aes_tools
except:
    pass

import json
import itertools
import time
import copy
import hashlib
import datetime
import calendar
import base64
import re
import random

# Set this false to disable all print statements ********************************
debug = True
if not debug:
    #Disable print statements
    #print = lambda *args, **kwargs: None
    pass
else:
    #print = lambda *args, **kwargs: ProgramLog(' '.join(str(arg) for arg in args), 'info')
    pass

print('Begin GST')
# *******************************************************************************

# extronlib.ui *****************************************************************
class Button(extronlib.ui.Button):
    _allGSTButtons = set()  # This will hold every instance of all buttons

    EventNames = [
        'Pressed',
        'Tapped',
        'Held',
        'Repeated',
        'Released',
    ]

    def __new__(cls, Host, ID, holdTime=None, repeatTime=None, PressFeedback=None):
        for btn in cls._allGSTButtons:
            if btn.ID == ID and btn.Host == Host:
                print('This button has been created before. Returning old Button object.')
                return btn

        print('This button has never been created before, instantiate for the first time')
        return super().__new__(cls)


    def __init__(self, Host, ID, holdTime=None, repeatTime=None, PressFeedback=None):
        '''

        :param Host: extronlib.device.UIDevice instance
        :param ID: int()
        :param holdTime: float()
        :param repeatTime: float()
        :param PressFeedback: If you want the button to change states when you press/release, set this to 'State'
        '''
        print('gs_tools.Button.__init__(Host={}, ID={})'.format(Host, ID))
        extronlib.ui.Button.__init__(self, Host, ID, holdTime=holdTime, repeatTime=repeatTime)

        self.StateChangeMap = {}  # ex. {'Pressed': 1, 'Released': 0}

        for EventName in self.EventNames:
            setattr(self, 'Last' + EventName, None)

        if PressFeedback == 'State':
            self.AutoStateChange('Pressed', 1)
            self.AutoStateChange('Tapped', 0)
            self.AutoStateChange('Released', 0)

        self.Text = ''
        self.SetVisible(True)
        self.ToggleStateList = None

        self._allGSTButtons.add(self)

        #
        self._autostate_callbacks = {
            'Pressed': None,
            'Tapped': None,
            'Held': None,
            'Repeated': None,
            'Released': None,
        }
        for event_name in self._autostate_callbacks.keys():
            setattr(self, event_name, self._DoEvent)

        self._CreateMissingButton(Host, ID, holdTime=holdTime, repeatTime=repeatTime, PressFeedback=PressFeedback)

    def _CreateMissingButton(self, Host, ID, holdTime=None, repeatTime=None, PressFeedback=None):
        print('UIDevice._allUIDevices=', UIDevice._allUIDevices)
        allHost = UIDevice._allUIDevices.copy()
        allHost.remove(self.Host)
        otherHosts = allHost
        print('otherHosts=', otherHosts)

        for otherHost in otherHosts:
            thisHostAlreadyHasButton = False
            for btn in self._allGSTButtons:
                if btn.ID == ID and btn.Host == otherHost:
                    thisHostAlreadyHasButton = True
                    break

            if not thisHostAlreadyHasButton:
                print('Creating duplicate button on otherHost={}, ID={}'.format(otherHost, ID))
                Button(otherHost, ID, holdTime=holdTime, repeatTime=repeatTime, PressFeedback=PressFeedback)

    def _DoMirrorMethod(self, methodName, *args, **kwargs):
        # This is called by self when SetText, SetState, etc.. methods are called when self.Host is a mirror master
        # #Find all the slave objects and do same method on them with same args
        print('Button._DoMirrorMethod(methodName={}, *args={}, **kwargs={})'.format(methodName, args, kwargs))
        masterTLP = self.Host
        print('masterTLP=', masterTLP)
        slaveTLPs = self.Host.MirrorSlaves
        print('slaveTLPs=', slaveTLPs)
        allTLPs = [masterTLP] + slaveTLPs

        slaveButtons = UIDevice.GetAllButtons(self.ID, slaveTLPs)
        print('slaveButtons=', slaveButtons)
        for btn in slaveButtons:
            slaveMethod = getattr(btn, methodName)
            print('slaveMethod=', slaveMethod)
            slaveMethod(*args, **kwargs) #slave buttons will detect they are in slave mode and will simply do a normal SetText...

    def _DoMirrorEvent(self, eventName):
        # if self.Host is a slave, then call the master event
        # if self.Host is a master, do nothing. _DoEvent will process as normal
        print('Button._DoMirrorEvent(eventName={})'.format(eventName))
        print('self.Host.MirrorMaster=', self.Host.MirrorMaster)
        print('111 self.Host=', self.Host)
        if self.Host.MirrorMaster is not None:
            #We are in a mirror mode, might be slave, might be master
            if self.Host.MirrorMaster is not self.Host:
                # self.Host is a slave button
                # find the master button and call its event instead
                masterTLP = self.Host.MirrorMaster
                print('masterTLP=', masterTLP)
                print('self.ID=', self.ID)
                masterButton = UIDevice.GetAllButtons(ID=self.ID, host=masterTLP)[0]
                print('masterButton=', masterButton)
                masterEvent = getattr(masterButton, eventName)
                print('masterEvent=', masterEvent)
                masterEvent(masterButton, eventName)
            else:
                # self.Host is master, do nothing, _DoEvent will process normally
                pass
        pass

    def _DoEvent(self, button, state):
        #This method gets called every time a button is pressed/released
        #It first calls the internal method to change state, then calls the users method
        print('Button._DoEvent(self, state={}) self.Host={}, self.ID={}, '.format(state, self.Host, self.ID ))

        print('self.Host.IsSlave()=', self.Host.IsSlave())
        print('self=', self)
        print('self.SetState=', self.SetState)
        if self.Host.IsSlave():
            self._DoMirrorEvent(state) #This will call the master event instead
        else:
            # self is the master button,
            self._DoStateChange(state)
            if self._autostate_callbacks[state] is not None:
                self._autostate_callbacks[state](button, state)

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

    def _DoStateChange(self, state):
        print('Button._DoStateChange(state={}) self={}'.format(state, self))
        print('state in self.StateChangeMap =', state in self.StateChangeMap)
        if state in self.StateChangeMap:
            # print(self.ID, 'state in self.StateChangeMap')
            NewState = self.StateChangeMap[state]
            print('NewState=', NewState)
            self.SetState(NewState)

    def ShowPopup(self, popup, duration=0):
        '''This method is used to simplify a button that just needs to show a popup
        Example:
        Button(TLP, 8022).ShowPopup('Confirm - Shutdown')
        '''
        @event(self, 'Released')
        def NewFunc(button, state):
            button.Host.ShowPopup(popup, duration)

    def ShowPage(self, page):
        @event(self, 'Released')
        def NewFunc(button, state):
            button.Host.ShowPage(page)

    def HidePopup(self, popup):
        '''This method is used to simplify a button that just needs to hide a popup
        Example:
        Button(TLP, 8023).HidePopup('Confirm - Shutdown')
        '''
        @event(self, 'Released')
        def NewFunc(button, state):
            button.Host.HidePopup(popup)

    def SetText(self, text, limitLen=None, elipses=False, justify='Left'):
        self._DoMirrorMethod('SetText', text)

        if not isinstance(text, str):
            text = str(text)

        self.Text = text

        displayText = text
        if limitLen is not None:
            if len(displayText) > limitLen:

                #chop off extra text
                if justify == 'Right': #chop off the left
                    displayText = displayText[-limitLen:]

                elif justify == 'Left': #chop off the left
                    displayText = displayText[:limitLen]

                #add elipses if needed
                if elipses is True:
                    if justify == 'Left':
                        displayText = displayText[:-3] + '...'
                    elif justify == 'Right':
                        displayText = '...' + displayText[3:]

        super().SetText(displayText)

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

    def SetBlinking(self, *args, **kwargs):
        print('gs_tools.Button.SetBlinking(args={}, kwargs={}) self={}'.format(args, kwargs, self))
        if self.Host.IsMaster():
            self._DoMirrorMethod('SetBlinking', *args, **kwargs)
        super().SetBlinking(*args, **kwargs)

    def CustomBlink(self, *args, **kwargs):
        print('gs_tools.Button.CustomBlink(args={}, kwargs={}) self={}'.format(args, kwargs, self))
        if self.Host.IsMaster():
            self._DoMirrorMethod('CustomBlink', *args, **kwargs)
        super().CustomBlink(*args, **kwargs)

    def SetEnable(self, *args, **kwargs):
        print('gs_tools.Button.SetEnable(args={}, kwargs={}) self={}'.format(args, kwargs, self))
        if self.Host.IsMaster():
            self._DoMirrorMethod('SetEnable', *args, **kwargs)
        super().SetEnable(*args, **kwargs)

    def SetState(self, *args, **kwargs):
        print('gs_tools.Button.SetState(args={}, kwargs={}) self={}'.format(args, kwargs, self))
        if self.Host.IsMaster():
            self._DoMirrorMethod('SetState', *args, **kwargs)
        super().SetState(*args, **kwargs)

    def SetVisible(self, *args, **kwargs):
        print('gs_tools.Button.SetVisible(args={}, kwargs={}) self={}'.format(args, kwargs, self))
        if self.Host.IsMaster():
            self._DoMirrorMethod('SetVisible', *args, **kwargs)
        super().SetVisible(*args, **kwargs)

    def __str__(self):
        return '<{}, Host.DeviceAlias={}, ID={}>'.format(super().__str__(), self.Host.DeviceAlias, self.ID)


class Knob(extronlib.ui.Knob):
    def __str__(self):
        return '<{}, Host.DeviceAlias={}, ID={}>'.format(super().__str__(), self.Host.DeviceAlias, self.ID)


class Label(extronlib.ui.Label):
    _allLabels = set()

    def __new__(cls, Host, ID):
        for lbl in cls._allLabels:
            if lbl.ID == ID and lbl.Host == Host:
                print('This Label has been created before. Returning old Label object.')
                return lbl

        print('This Level has never been created before, instantiate for the first time')
        return super().__new__(cls)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.Text = ''
        self.SetVisible(True)

    def SetText(self, text, limitLen=None, elipses=False, justify='Left'):
        #justify='Left' means chop off the right side
        #justify='Right' means chop off the left side
        self.Text = text

        displayText = text
        if limitLen is not None:
            if len(displayText) > limitLen:

                #chop off extra text
                if justify == 'Right': #chop off the left
                    displayText = displayText[-limitLen:]

                elif justify == 'Left': #chop off the left
                    displayText = displayText[:limitLen]

                #add elipses if needed
                if elipses is True:
                    if justify == 'Left':
                        displayText = displayText[:-3] + '...'
                    elif justify == 'Right':
                        displayText = '...' + displayText[3:]

        super().SetText(displayText)

    def AppendText(self, text):
        self.SetText(self.Text + text)

    def BackspaceText(self):
        self.SetText(self.Text[:-1])

    def __str__(self):
        return '{}, Host.DeviceAlias={}, ID={}'.format(super().__str__(), self.Host.DeviceAlias, self.ID)


class Level(extronlib.ui.Level):
    _allLevels = set()  # This will hold every instance of all buttons


    def __new__(cls, Host, ID):
        for lvl in cls._allLevels:
            if lvl.ID == ID and lvl.Host == Host:
                print('This Level has been created before. Returning old Button object.')
                return lvl

        print('This Level has never been created before, instantiate for the first time')
        return super().__new__(cls)

    def __init__(self, Host, ID):
        super().__init__(Host, ID)
        self._allLevels.add(self)
        self._CreateMissingLevel(Host, ID)

    def _CreateMissingLevel(self, Host, ID):
        print('UIDevice._allUIDevices=', UIDevice._allUIDevices)
        allHost = UIDevice._allUIDevices.copy()
        allHost.remove(self.Host)
        otherHosts = allHost
        print('otherHosts=', otherHosts)

        for otherHost in otherHosts:
            thisHostAlreadyHasButton = False
            for lvl in self._allLevels:
                if lvl.ID == ID and lvl.Host == otherHost:
                    thisHostAlreadyHasButton = True
                    break

            if not thisHostAlreadyHasButton:
                print('Creating duplicate Level on otherHost={}, ID={}'.format(otherHost, ID))
                Level(otherHost, ID)

    def _DoMirrorMethod(self, methodName, *args, **kwargs):
        # This is called by self when SetText, SetState, etc.. methods are called when self.Host is a mirror master
        # #Find all the slave objects and do same method on them with same args
        print('gs_tools.Level._DoMirrorMethod(methodName={}, *args={}, **kwargs={})'.format(methodName, args, kwargs))
        masterTLP = self.Host
        print('masterTLP=', masterTLP)
        slaveTLPs = self.Host.MirrorSlaves
        print('slaveTLPs=', slaveTLPs)
        allTLPs = [masterTLP] + slaveTLPs

        slaveLevels = UIDevice.GetAllLevels(self.ID, slaveTLPs)
        print('slaveLevels=', slaveLevels)
        for lvl in slaveLevels:
            slaveMethod = getattr(lvl, methodName)
            print('slaveMethod=', slaveMethod)
            slaveMethod(*args, **kwargs) #slave levels will detect they are in slave mode and will simply do a normal SetText...

    def Dec(self, *args, **kwargs):
        print('gs_tools.Level.Dec(args={}, kwargs={}) self={}'.format(args, kwargs, self))
        if self.Host.IsMaster():
            self._DoMirrorMethod('Dec', *args, **kwargs)
        super().Dec(*args, **kwargs)

    def Inc(self, *args, **kwargs):
        print('gs_tools.Level.Inc(args={}, kwargs={}) self={}'.format(args, kwargs, self))
        if self.Host.IsMaster():
            self._DoMirrorMethod('Inc', *args, **kwargs)
        super().Inc(*args, **kwargs)

    def SetLevel(self, *args, **kwargs):
        print('gs_tools.Level.SetLevel(args={}, kwargs={}) self={}'.format(args, kwargs, self))
        if self.Host.IsMaster():
            self._DoMirrorMethod('SetLevel', *args, **kwargs)
        super().SetLevel(*args, **kwargs)

    def SetRange(self, *args, **kwargs):
        print('gs_tools.Level.SetRange(args={}, kwargs={}) self={}'.format(args, kwargs, self))
        if self.Host.IsMaster():
            self._DoMirrorMethod('SetRange', *args, **kwargs)
        super().SetRange(*args, **kwargs)

    def SetVisible(self, *args, **kwargs):
        print('gs_tools.Level.SetVisible(args={}, kwargs={}) self={}'.format(args, kwargs, self))
        if self.Host.IsMaster():
            self._DoMirrorMethod('SetVisible', *args, **kwargs)
        super().SetVisible(*args, **kwargs)

    def __str__(self):
        return '{}, Host.DeviceAlias={}, ID={}'.format(super().__str__(), self.Host.DeviceAlias, self.ID)


# extronlib.system **************************************************************
class Clock(extronlib.system.Clock):
    pass


class MESet(extronlib.system.MESet):
    pass


class Wait(extronlib.system.Wait):
    """Functions that are decorated with Wait now are callable elsewhere.

    Exceptions that happen in waits wil now print the error message to TRACE as well as throwing the "Wait callback error" message in ProgramLog

    The programmer can now pass arguments to Wait callbacks
    for example:

    @Wait(2, args=('one', 'two'))
    def loop(arg1, arg2):
        print('loop(arg1={}, arg2={})'.format(arg1, arg2))
        int('hello') #this causes an exception. Notice the full traceback message shows in the ProgramLog and Trace

    **OR**

    def TestFunc(arg1, arg2):
        print('TestFunc(arg1={}, arg2={})'.format(arg1, arg2))
        raise Exception('TestFunc Exception')

    Wait(3, TestFunc, args=('three', 'four'))

    **OR**
    def TestFunc2(arg1):
        print('TestFunc(arg1={})'.format(arg1))
        raise Exception('TestFunc2 Exception')

    Wait(3, TestFunc2, args=('three',)) #Note the extra comma to create a tuple

    """

    def __init__(self, *args, **kwargs):
        if 'args' in kwargs:
            self._userArgs = kwargs.pop('args')
        else:
            self._userArgs = None

        if len(args) >= 2:
            if callable(args[1]):
                callback = args[1]
                newCallback = self._getNewFunc(callback)
                tempArgs = list(args)
                tempArgs[1] = newCallback
                newArgs = tuple(tempArgs)
                args = newArgs

        super().__init__(*args, **kwargs)

    def _getNewFunc(self, oldFunc):
        def newFunc():
            try:
                if self._userArgs is None:
                    oldFunc()
                else:
                    oldFunc(*self._userArgs)

            except Exception as e:
                ProgramLog('Wait Exception: {}\nException in function:{}\nargs={}'.format(e, oldFunc, self._userArgs), 'error')
                raise e

        print('Wait.oldFunc=', oldFunc, 'args=', self._userArgs)
        return newFunc

    def __call__(self, callback):
        newCallback = self._getNewFunc(callback)

        super().__call__(newCallback)
        return newCallback


class File(extronlib.system.File):

    @classmethod
    def ListDirWithSub(cls, dir='/'):
        #returns a list of str, each item is a file or subdir with the full path
        allFiles = []
        thisListDir = cls.ListDir(dir)
        print('dir={}, thisListDir={}'.format(dir, thisListDir))
        for item in thisListDir:
            if item.endswith('/'):
                allFiles.extend(cls.ListDirWithSub(dir+item))
                allFiles.append(dir+item)
            else:
                allFiles.append(dir+item)
        print('ListDirWithSub=', '\n'.join(allFiles))
        return allFiles

    @classmethod
    def DeleteDirRecursive(cls, dir='/'):
        print('File.DeleteDirRecursive(dir={})'.format(dir))
        items = File.ListDir(dir)
        print('dir={}, items='.format(dir), items)
        for item in items:
            itempath = dir + '/' + item
            try:
                File.DeleteFile(itempath)
            except Exception as e:
                print('Exception DeleteFile:', e)
            try:
                File.DeleteDir(itempath)
            except Exception as e:
                print('Exception DeleteDir:', e)
                if 'is not empty' in str(e):
                    File.DeleteDirRecursive(itempath)

        File.DeleteDir(dir)#now that its empty


# extronlib.interface **************************************************************
class ContactInterface(extronlib.interface.ContactInterface):
    def __iter__(self):
        '''
        This allows an interface to be cast as a dict
        '''
        yield 'Host.DeviceAlias', self.Host.DeviceAlias
        yield 'Port', self.Port
        yield 'Type', str(type(self))


class DigitalIOInterface(extronlib.interface.DigitalIOInterface):
    def __iter__(self):
        '''
        This allows an interface to be cast as a dict
        '''
        yield 'Host.DeviceAlias', self.Host.DeviceAlias
        yield 'Port', self.Port
        yield 'Mode', self.Mode
        yield 'Pullup', self.Pullup
        yield 'Type', str(type(self))


class EthernetClientInterface(extronlib.interface.EthernetClientInterface):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._keep_alive_running = False
        self._keep_alive_Timer = None

    def __str__(self):
        return '<gs_tools.EthernetClientInterface, IPAddress={}, IPPort={}, ServicePort={}>'.format(self.IPAddress, self.IPPort, self.ServicePort)

    #def __repr__(self):
        #return str(self)

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
        # super().StartKeepAlive does not call .Send apparently so im doing it differnt
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

    def Send(self, data):
        # Send data in chunks.
        chunkSize = 256  # 256 seems to work well on an actual IPCP
        numberOfChunks = int(len(data) / chunkSize) + 1
        ##print('NumberOfChunks=', NumberOfChunks)
        lastPrint = 0
        for i in range(numberOfChunks):
            if numberOfChunks > 1:
                if i % 1000 == 0:
                    percent = int((i / numberOfChunks) * 100)
                    if percent > lastPrint:
                        lastPrint = percent
                        print('Sending in chunks: {}%'.format(lastPrint))
            ##print('Sending Chunk', i)
            StartIndex = i * chunkSize
            EndIndex = (i + 1) * chunkSize

            if EndIndex > len(data):
                Chunk = data[StartIndex:]
            else:
                Chunk = data[StartIndex:EndIndex]

            try:
                self._ChunkSend(Chunk)
                ##print('Chunk', i, '=', Chunk)
                time.sleep(0.001)  # 256bytes/0.001seconds = 2.5MB/s max transfer speed = 2.0 Mbps
                pass
            except Exception as e:
                print(e)

    def _ChunkSend(self, data):
        super().Send(data)

def get_parent(client_obj):
    '''
    This function is used to get the parent EthernetServerInterfaceEx from a ClientObject
    :param client_obj: extronlib.interface.EthernetServerInterfaceEx.ClientObject
    :return: extronlib.interface.EthernetServerInterfaceEx
    '''
    for server in EthernetServerInterfaceEx._all_servers_ex.copy().values():
        print('get_parent\nserver={}\nClients={}\nclient_obj={}'.format(server, server.Clients, client_obj))
        if client_obj in server.Clients:
            return server

    if hasattr(client_obj, '_parent'):
        return client_obj._parent


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

        print('EthernetServerInterfaceEx._ports_in_use={}'.format(cls._ports_in_use))
        print('EthernetServerInterfaceEx._all_servers_ex={}'.format(cls._all_servers_ex))

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

        print('EthernetServerInterfaceEx._ports_in_use={}'.format(self._ports_in_use))
        print('EthernetServerInterfaceEx._all_servers_ex={}'.format(self._all_servers_ex))

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
        if not isinstance(port_number, int):
            raise Exception('port_number must be of type "int"')

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


class EthernetServerInterfaceExEncrypted(EthernetServerInterfaceEx):
    # TODO: a class that can send/rx encrypted data
    pass


class EthernetServerInterface(extronlib.interface.EthernetServerInterface):
    pass


class FlexIOInterface(extronlib.interface.FlexIOInterface):
    def __iter__(self):
        '''
        This allows an interface to be cast as a dict
        '''
        yield 'Port', self.Port
        yield 'Host.DeviceAlias', self.Host.DeviceAlias
        yield 'Mode', self.Mode
        yield 'Pullup', self.Pullup
        yield 'Upper', self.Upper
        yield 'Lower', self.Lower
        yield 'Type', str(type(self))

class IRInterface(extronlib.interface.IRInterface):
    pass


class RelayInterface(extronlib.interface.RelayInterface):
    def __iter__(self):
        '''
        This allows an interface to be cast as a dict
        '''
        yield 'Port', self.Port
        yield 'Host.DeviceAlias', self.Host.DeviceAlias
        yield 'Type', str(type(self))

    def __new__(cls, *args, **kwargs):
        '''
        https://docs.python.org/3/reference/datamodel.html#object.__new__

        The return value of __new__() should be the new object instance (usually an instance of cls).
        '''
        print('RelayInterface.__new__(args={}, kwargs={})'.format(args, kwargs))

        if len(args) > 0:
            Host = args[0]
        else:
            Host = kwargs.get('Host')

        if len(args) > 1:
            Port = args[1]
        else:
            Port = kwargs.get('Port')

        if not Host.port_in_use(Port):
            relay_interface = ProcessorDevice._get_relay_instance(*args, **kwargs)
            if relay_interface is not None:
                print('An old relay instance has been found. use it')
                return relay_interface

            elif relay_interface is None:
                print('__new__ This is the first time this relay interface has been instantiated. call super new')
                return super().__new__(cls)
        else:
            raise Exception(
                'This relay port is already in use.\nConsider using Host.make_port_available({})'.format(Port))


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

        if Port not in ProcessorDevice._relay_instances[Host.DeviceAlias].keys():
            print('__init__ This is the first time this RelayInterface has been init')
            super().__init__(*args, **kwargs)
        else:
            print('This has been init before. do nothing')
            pass

        ProcessorDevice._register_new_relay_instance(self)


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
                print('__new__ This is the first time this SerialInterface has been instantiated. call super new')
                return super().__new__(cls)
        else:
            raise Exception(
                'This com port is already in use.\nConsider using Host.make_port_available({})'.format(Port))

    def __init__(self, *args, **kwargs):
        print('SerialInterface.__init__(args={}, kwargs={})'.format(args, kwargs))

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
            print('__init__ This is the first time this SerialInterface has been init')
            super().__init__(*args, **kwargs)
            print('After super().__init__(*args, **kwargs)\nself=', self)
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

    '''2017-07-28
    DO NOT OVERRIDE THIS __repr__ method!
    It will cause SerialInterface instantiation to hang and you will waste an entire day tracking it down.
    '''
    #def __repr__(self):
        #return str(self)

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
    def __iter__(self):
        '''
        This allows an interface to be cast as a dict
        '''
        yield 'Host.DeviceAlias', self.Host.DeviceAlias
        yield 'Port', self.Port
        yield 'Type', str(type(self))


class VolumeInterface(extronlib.interface.VolumeInterface):
    pass


# extronlib.device **************************************************************
class ProcessorDevice(extronlib.device.ProcessorDevice):
    _relay_ports_in_use = {# ProcessorDevice.DeviceAlias: ['RLY1', 'RLY2', ...]
    }

    _relay_instances = {  # ProcessorDevice.DeviceAliasA: {
        # 'RLY1': RelayInterfaceObjectA1,
        # 'RLY2': RelayInterfaceObjectA2,
        # },
        # ProcessorDevice.DeviceAliasB: {'RLY1': RelayInterfaceObjectB1,
        # 'RLY2': RelayInterfaceObjectB2,
        # },
    }

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
        #instance is a SerialInterface object
        print('ProcessorDevice._register_new_serial_instance(instance={})'.format(instance))
        cls._serial_instances[instance.Host.DeviceAlias][instance.Port] = instance

        if instance.Port not in cls._serial_ports_in_use[instance.Host.DeviceAlias]:
            cls._serial_ports_in_use[instance.Host.DeviceAlias].append(instance.Port)

    @classmethod
    def _register_new_relay_instance(cls, instance):
        #instance is a RelayInterface object
        print('ProcessorDevice._register_new_relay_instance(instance={})'.format(instance))

        cls._relay_instances[instance.Host.DeviceAlias][instance.Port] = instance

        if instance.Port not in cls._relay_ports_in_use[instance.Host.DeviceAlias]:
            cls._relay_ports_in_use[instance.Host.DeviceAlias].append(instance.Port)

    @classmethod
    def _get_serial_instance(cls, Host, Port, **kwargs):
        print('ProcessorDevice._get_serial_instance(Host={}\n Port={}\n kwargs={}'.format(Host, Port, kwargs))
        # return new/old serial instance
        if Port not in cls._serial_ports_in_use[Host.DeviceAlias]:
            print(
                'The port is availble. Either becuase it has never been instantiated or because the programmer called "_make_port_available"')

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
    def _get_relay_instance(cls, Host, Port, **kwargs):
        print('ProcessorDevice._get_relay_instance(Host={}\n Port={}\n kwargs={}'.format(Host, Port, kwargs))
        # return new/old serial instance
        if Port not in cls._relay_ports_in_use[Host.DeviceAlias]:
            print(
                'The relay port is availble. Either becuase it has never been instantiated or because the programmer called "_make_port_available"')

            if Port in cls._relay_instances[Host.DeviceAlias].keys():
                print('A RelayInterface already exist. Return the old relay_interface')
                relay_interface = cls._relay_instances[Host.DeviceAlias][Port]
                print('relay_interface=', relay_interface)
                return relay_interface
            else:
                print('This RelayInterface has NOT been instantiated before. return None')
                return None
        else:
            print('This relay port is not available')
            raise Exception(
                'This relay port is not available.\n Consider calling ProcessorDevice._make_port_available(Host, Port)')

    @classmethod
    def _make_port_available(cls, Host, Port):
        print('ProcessorDevice._make_port_available(Host={}\n Port={}'.format(Host, Port))
        # return None

        if 'COM' in Port:
            if Port in cls._serial_ports_in_use[Host.DeviceAlias]:
                print('The serial port {} has already been instantiated. but make it available again'.format(Port))
                cls._serial_ports_in_use[Host.DeviceAlias].remove(Port)
            else:
                print('The serial port has never been instantiated. do nothing.')
                pass

        elif 'RLY' in Port:
            if Port in cls._relay_ports_in_use[Host.DeviceAlias]:
                print('The relay port {} has already been instantiated. but make it available again'.format(Port))
                cls._relay_ports_in_use[Host.DeviceAlias].remove(Port)
            else:
                print('The relay port has never been instantiated. do nothing.')
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


        if device_alias not in cls._relay_ports_in_use:
            cls._relay_ports_in_use[device_alias] = []

        if device_alias not in cls._relay_instances:
            cls._relay_instances[device_alias] = {}


        if device_alias not in cls._processor_device_instances:
            # no processor with this device_alias has ever been instantiated. super().__new__
            return super().__new__(cls)
        else:
            old_proc = cls._processor_device_instances[device_alias]
            return old_proc

    _allProcessorDevices = []

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

        if self not in self._allProcessorDevices:
            try:
                StartVTLPServer(self.IPAddress)
            except Exception as e:
                print(e) #probably a secondary processor

            self._allProcessorDevices.append(self)

    def port_in_use(self, port_str):
        print('ProcessorDevice.port_in_use\n self={}\n port_str={}\n\n self._serial_ports_in_use={}'.format(self,
                                                                                                            port_str,
                                                                                                            self._serial_ports_in_use))
        if 'COM' in port_str:
            if port_str in self._serial_ports_in_use[self.DeviceAlias]:
                return True
            else:
                return False

        elif 'RLY' in port_str:
            if port_str in self._relay_ports_in_use[self.DeviceAlias]:
                return True
            else:
                return False

    def make_port_available(self, port_str):
        print('ProcessorDevice.clear_port_in_use\n self={}\n port_str={}'.format(self, port_str))
        self._make_port_available(self, port_str)

    def __str__(self):
        try:
            return 'self={}, self.DeviceAlias={}, self.IPAddress={}'.format(super().__str__(), self.DeviceAlias,
                                                                            self.IPAddress)
        except:
            return super().__str__()

#Mirror *****************************************************************************
'''
Theory: A dict() will keep track of which UIDevices are mirrored and which is the master/slave.
All Button/Label/Level/Knobs will check this dict and either execute their native event or mirrored event.
'''
mirrorDict = {} #This dict will keep track of which UIDevices are mirrored

class UIDevice(extronlib.device.UIDevice):

    _allUIDevices = set()

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

        self._PageHistory = []  # hold last X pages
        self._PageOffset = 0  # 0 = last entry in

        self._mirrorMaster = None # Points to the master TLP, might be self, or None if not in mirror mode
        self._mirrorSlaves = [] #list of UIDevice objects (does not include self)

        if self not in self._allUIDevices:
            self._allUIDevices.add(self)

    def ShowPopup(self, popup, duration=0):
        #print('ShowPopup popup={}, duration={}'.format(popup, duration))
        self._DoShowPopup(popup, duration)

        if popup in self._exclusive_modals:
            for modal_name in self._exclusive_modals:
                if modal_name != popup:
                    self.HidePopup(modal_name)

        if self.IsMaster():
            for slave in self._mirrorSlaves:
                slave.ShowPopup(popup, duration)

    def _DoShowPopup(self, popup, duration=0):
        super().ShowPopup(popup, duration)
        if duration is not 0:
            if popup in self.PopupWaits:
                self.PopupWaits[popup].Cancel()

            NewWait = Wait(duration, lambda: self.HidePopup(popup))
            self.PopupWaits[popup] = NewWait

        for PopupName in self.PopupData:
            if PopupName != popup:
                self.PopupData[PopupName] = 'Unknown'

        self.PopupData[popup] = 'Showing'

    def HidePopup(self, popup):
        #print('HidePopup popup=', popup)
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
        print('gs_tools.UIDevice.ShowPage(page={}) self.DeviceAlias={}'.format(page, self.DeviceAlias))
        super().ShowPage(page)

        for PageName in self.PageData:
            if PageName != page:
                self.PageData[PageName] = 'Hidden'

        self.PageData[page] = 'Showing'

        if page not in self._PageHistory:
            self._PageHistory.append(page)

        if self.IsMaster():
            for slave in self._mirrorSlaves:
                slave.ShowPage(page)

    def PageBack(self):
        # TODO
        pass

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

    @classmethod
    def GetAllButtons(cls, ID=None, host=None):
        print('GetAllButtons(ID={}, host={})'.format(ID, host))
        return cls.GetAllObjects(ID, host, type='Button')

    @classmethod
    def GetAllLevels(cls, ID=None, host=None):
        print('GetAllLevels(ID={}, host={})'.format(ID, host))
        return cls.GetAllObjects(ID, host, type='Level')

    @classmethod
    def GetAllLabels(cls, ID=None, host=None):
        print('GetAllLabels(ID={}, host={})'.format(ID, host))
        return cls.GetAllObjects(ID, host, type='Label')

    @classmethod
    def GetAllKnobs(cls, ID=None, host=None):
        print('GetAllKnobs(ID={}, host={})'.format(ID, host))
        return cls.GetAllObjects(ID, host, type='Knob')

    @classmethod
    def GetAllObjects(cls, ID=None, host=None, type=None):
        '''
        Returns button objects with this ID.
        This will return any button object that has been instantiated from any UIDevice host.
        :param ID: int
        :param host: list - host to include (None or [] means all host)
        :return: Button object
        '''
        print('GetAllObjects(ID={}, host={}, type={})'.format(ID, host, type))
        if type == 'Button':
            allObjects = Button._allGSTButtons
        elif type == 'Level':
            allObjects = Level._allLevels
        elif type == 'Label':
            allObjects = Label._allLables
        elif type == 'Knob':
            allObjects = Knob._allKnobs

        print('allObjects=', allObjects)

        rtnObjects = []

        if host is not None:
            if not isinstance(host, list):
                host = [host]
                print('host changed to', host)

        if ID is None:
            if host is None or len(host) == 0:
                # If ID and host are None, return all objecs
                return allObjects
            else:
                # If ID is None, but host is not None, return all buttons that are for included host
                for obj in allObjects:
                    if obj.Host in host:
                        rtnObjects.append(obj)
        else:
            if host is None or len(host) == 0:
                # If ID is not None, but host is None, return all buttons with ID for all UIDevices
                for obj in allObjects:
                    if obj.ID == ID:
                        rtnObjects.append(obj)
            else:
                #print('If ID is not None and host is not None, return all buttons with given ID and included host')
                for obj in allObjects:
                    #print('btn=', obj)
                    if obj.ID == ID:
                        #print('btn.ID == ID')
                        if obj.Host in host:
                            #print('btn.Host in host')
                            rtnObjects.append(obj)

        print('rtnObjects=', rtnObjects)
        return rtnObjects

    def SetExclusiveModals(self, modals):
        self._exclusive_modals = modals

    def SetVisible(self, id, state):
        for btn in Button._allGSTButtons:
            if btn.ID == id:
                if btn.Host == self:
                    btn.SetVisible(state)

    def __str__(self):
        return '<gs_tools.UIDevice object DeviceAlias={}, IPAddress={}>'.format(self.DeviceAlias, self.IPAddress)

    #def __repr__(self):
        #Leave this alone. Seems like extronlib is sensitive to changes to repr
        #return str(self)

    #def __setattr__(self, *args, **kwargs):
        #Enable this to see all setattr calls
        #print('UIDevice.__setattr__:', args, kwargs)
        #super().__setattr__(*args, **kwargs)


    #Methods for Mirroring UIDevices **********************************************
    def AttachSlave(self, *slaveTLPs):
        #This will attach slave TLPs to self (self is the master)
        print('UIDevice.AttachSlave(*slaveTLPs={})'.format(slaveTLPs))
        if self._mirrorMaster is None:
            self._mirrorMaster = self
            for slave in slaveTLPs:
                slave._MakeSlave(self)
                self._mirrorSlaves.append(slave)
        else:
            raise Exception('Error: UIDevice with alias "{}" is already a slave of UIDevice with alias "{}"'.format(self.DeviceAlias, self._mirrorMaster.DeviceAlias))
        print('self={}, self._mirrorMaster={}'.format(self, self._mirrorMaster))
        print('self={}, self._mirrorSlaves={}'.format(self, self._mirrorSlaves))

    @property
    def MirrorMaster(self):
        # return UIDevice that is master (might be self), or None if not in mirror mode
        return self._mirrorMaster

    def IsSlave(self):
        #alias of self.MirrorMaster
        if self._mirrorMaster is not None:
            if self._mirrorMaster is self:
                return False
            elif self._mirrorMaster is not self:
                return True
        else:
            return False

    def IsMaster(self):
        # alias of self.MirrorMaster
        if self._mirrorMaster is not None:
            if self._mirrorMaster is self:
                return True
            elif self._mirrorMaster is not self:
                return False
        else:
            return False

    @property
    def MirrorSlaves(self):
        # return list of slave UIDevices
        return self._mirrorSlaves

    def ReleaseSlave(self, *slaveTLPs):
        # Releases slaves listed, they will return to native mode
        # If all slaves are released, self returns to native mode also
        print('UIDevice.ReleaseSlave(*slaveTLPs={})'.format(slaveTLPs))
        for slave in slaveTLPs:
            self._mirrorSlaves.pop(slave)
            slave._RemoveMaster()

        if len(self._mirrorSlaves) == 0:
            #all slaves have been removed, return to non-mirrored mode
            self._RemoveMaster()

    #These methods are called by another UIDevice to enable/disable slave settings
    def _MakeSlave(self, masterTLP):
        print('self={}, UIDevice._MakeSlave(*masterTLP={})'.format(self, masterTLP))
        if self._mirrorMaster is None:
            self._mirrorMaster = masterTLP
            self._mirrorSlaves = []
        else:
            raise Exception('UIDevice with alias "{}" is already a slave to UIDevice with alias "{}"'.format(self.DeviceAlias, self._mirrorMaster.DeviceAlias))

    def _RemoveMaster(self):
        print('UIDevice._MakeSlave()')
        # takes tlp out of mirror mode. works independently again
        self._mirrorMaster = None
        self._mirrorSlaves = []

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
                if hasattr(obj, '_autostate_callbacks'):
                    obj._autostate_callbacks[eventName] = func
                else:
                    setattr(obj, eventName, func)
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

                 LvlFakeFeedback=None,
                 LvlMax=None,
                 LvlMin=None,
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

        if LvlMax is None:
            LvlMax = 100
        if LvlMin is None:
            LvlMin = 0

        if LvlFakeFeedback is not None:
            LvlFakeFeedback.SetRange(LvlMin, LvlMax, stepSize)

        @event([BtnUp, BtnDown], ['Pressed', 'Repeated'])
        def BtnUpDownEvent(button, state):
            if LvlFakeFeedback is None:
                CurrentLevel = Interface.ReadStatus(GainCommand, GainQualifier)
                if CurrentLevel is None:
                    CurrentLevel = -100
            else:
                CurrentLevel = LvlFakeFeedback.Level

            if button == BtnUp:
                NewLevel = CurrentLevel + stepSize
            elif button == BtnDown:
                NewLevel = CurrentLevel - stepSize

            if LvlFakeFeedback is not None:
                LvlFakeFeedback.SetLevel(NewLevel)
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

def isConnected(interface):
    '''
    The programmer must call HandleConnection(interface) before caling isConnected(). If not this will return False always.
    This will return True if the interface is logically or physically connected .
    This will return False if the interface is logically or physically disconnected.
    :param interface: extronlib.interface.*
    :return: bool
    '''
    state = UniversalConnectionHandler._defaultCH.get_connection_status(interface)
    if state in ['Connected', 'Online']:
        return True
    else:
        return False


if not File.Exists('connection_handler.log'):
    file = File('connection_handler.log', mode='wt')
    file.close()

with File('connection_handler.log', mode='at') as file:
    file.write('\n{} - Processor Restarted\n\n'.format(time.asctime()))
    file.close()

_connection_status = {}

GREEN = 2
RED = 1
WHITE = 0


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

    def _MainVisualFeedbackHandler(self, interface, command, value, qualifier):
        # print('MainVisualFeedbackHandler(\n interface={},\n command={},\n value={},\n qualifier={})'.format(interface, command, value, qualifier))
        doCallbacks = []
        for d in self.FeedbackDicts:
            if d['interface'] == interface:
                if d['command'] == command:
                    if d['qualifier'] == qualifier:
                        # print('matched d=', d)
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

                        elif isinstance(obj, extronlib.ui.Level):
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
            self._MainVisualFeedbackHandler(interface, command, value, qualifier)

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
            self._MainVisualFeedbackHandler(interface, command, value, qualifier)

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
            self._MainVisualFeedbackHandler(interface, command, value, qualifier)

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


class PersistentVariables():
    '''
    This class is used to easily manage non-volatile variables using the extronlib.system.File class
    '''

    def __init__(self, filename=None):
        '''

        :param filename: string like 'data.json' that will be used as the file name for the File class
        '''
        if filename is None:
            filename = 'persistent_variables.json'
        self.filename = filename

        self._valueChangesCallback = None

        self._CreateFileIfMissing()

    def _CreateFileIfMissing(self):
        if not File.Exists(self.filename):
            # If the file doesnt exist yet, create a blank file
            with File(self.filename, mode='wt') as file:
                file.write(json.dumps({}))
                file.close()

    def Set(self, varName, newValue):
        '''
        This will save the variable to non-volatile memory with the name varName
        :param varName: str that will be used to identify this variable in the future with .Get()
        :param newValue: any value hashable by the json library
        :return:
        '''
        self._CreateFileIfMissing()

        # load the current file
        with File(self.filename, mode='rt') as file:
            data = json.loads(file.read())
            file.close()

        #get the old value
        oldValue = data.get(varName, None)

        #if the value is different do the callback
        if oldValue != newValue:
            if callable(self._valueChangesCallback):
                self._valueChangesCallback(varName, newValue)

        # Add/update the new value
        data[varName] = newValue

        # Write new file
        with File(self.filename, mode='wt') as file:
            file.write(json.dumps(data, indent=4))
            file.close()

    def Get(self, varName):
        '''
        This will return the value of the variable with varName. Or None if no value is found
        :param varName: name of the variable that was used with .Set()
        :return:
        '''
        self._CreateFileIfMissing()
        # If the varName does not exist, return None

        # load the current file
        with File(self.filename, mode='rt') as file:
            data = json.loads(file.read())
            file.close()

        # Grab the value and return it
        try:
            varValue = data[varName]
        except KeyError:
            varValue = None
            self.Set(varName, varValue)

        return varValue

    @property
    def ValueChanges(self):
        return self._valueChangesCallback

    @ValueChanges.setter
    def ValueChanges(self, callback):
        self._valueChangesCallback = callback


RemoteTraceServer = None


def RemoteTrace(IPPort=1024):
    '''
    This function return a new print function that will print to stdout and also send to any clients connected to the server defined on port IPPort
    :param IPPort: int
    :return:
    '''
    global RemoteTraceServer

    # Start a new server
    if RemoteTraceServer == None:
        RemoteTraceServer = EthernetServerInterfaceEx(IPPort)

        @event(RemoteTraceServer, ['Connected', 'Disconnected'])
        def RemoteTraceServerConnectEvent(client, state):
            print('Client {}:{} {}'.format(client.IPAddress, client.ServicePort, state))

        HandleConnection(
            RemoteTraceServer,
            timeout=60*60*9,#60*60 = 1 hour
            # After this many seconds, a client who has not sent any data to the server will be disconnected.
        )

        result = RemoteTraceServer.StartListen()
        ProgramLog('RemoteTraceServer {}'.format(result), 'info')

    def NewPrint(*args):  # override the print function to write to program log instead
        string = '\r\n' + str(time.time()) + ': ' + ' '.join(str(arg) for arg in args)

        for client in RemoteTraceServer.Clients:
            client.Send(string + '\r\n')
        #ProgramLog(string, 'info')

    return NewPrint


def toPercent(Value, Min=0, Max=100):
    '''
    This function will take the Value, Min and Max and return a percentage
    :param Value: float
    :param Min: float
    :param Max: float
    :return: float from 0.0 to 100.0
    '''
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
        # print(e)
        # ProgramLog('gs_tools toPercent Erorr: {}'.format(e), 'error')
        return 0


def IncrementIP(IP):
    '''
    This function will take an IP and increment it by one.
    For example: IP='192.168.254.255' will return '192.168.255.0'
    :param IP: str like '192.168.254.254'
    :return: str like '192.168.254.255'
    '''
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
    '''
    Returns True if ip is a valid IPv4 IP like '192.168.254.254'
    Example '192.168.254.254' > return True
    Example '192.168.254.300' > return False
    :param ip: str like '192.168.254.254'
    :return: bool
    '''
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
    :return: first key from d that has the value == v. If v is not found in v, return None
    '''
    for k in d:
        if d[k] == v:
            return k


def phone_format(n):
    '''
    This function formats a string like a phone number
    Example: '8006339876' > '800-633-9876'
    :param n:
    :return:
    '''
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
                self.DeleteCharacter()

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
                if Char is not None:
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

        self._updateLabel()

    def updateKeysShiftMode(self):
        if self.ShiftID is not None:
            if self.ShiftMode == 'Upper':
                self.ShiftKey.SetState(1)

            elif self.ShiftMode == 'Lower':
                self.ShiftKey.SetState(0)

            for button in self.KeyButtons:
                Char = button.Name
                #print('Keyboard.updateKeysShiftMode Char=', Char)
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
        self._updateLabel()

    def AppendToString(self, character=''):
        '''
        Add a character(s) to the string
        '''
        # print('Keyboard.AppendToString()')
        self.string += character
        self._updateLabel()

    def DeleteCharacter(self):
        '''
        Removes one character from the end of the string.
        '''
        # print('deleteCharacter before=',self.string)
        self.string = self.string[0:len(self.string) - 1]
        print('deleteCharacter after=', self.string)
        self._updateLabel()

    def _updateLabel(self):
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
        self._updateLabel()

    def GetFeedbackObject(self):
        return self.FeedbackObject

    def SetPasswordMode(self, mode):
        self._password_mode = mode


# ScrollingTable ****************************************************************
ScrollingTable_debug = True


class ScrollingTable():
    # helper class Cell()**************************************************************
    class Cell():
        '''
        Represents a single cell in a scrolling table
        '''

        def __init__(self, parent_table, row, col, btn=None,
                pressedCallback=None,
                tappedCallback=None,
                heldCallback=None,
                repeatedCallback=None,
                releasedCallback=None,
                ):
            self._parent_table = parent_table
            self._row = row
            self._col = col
            self._btn = btn
            self._btnNewCallbacks = {
                'Pressed': pressedCallback,
                'Tapped': tappedCallback,
                'Held': heldCallback,
                'Repeated': repeatedCallback,
                'Released': releasedCallback,
                }
            self._Text = ''
            self._btn.SetState(0)

            oldHandlers = {
                'Pressed': self._btn.Pressed,
                'Tapped': self._btn.Tapped,
                'Held': self._btn.Held,
                'Repeated': self._btn.Repeated,
                'Released': self._btn.Released,
                }

            def NewHandler(button, state):
                if ScrollingTable_debug and debug: print(
                    'Cell NewHandler(\n button={}\n state={})\nself._btnNewCallbacks={}'.format(button, state, self._btnNewCallbacks))

                # Handle Mutually exclusive cells
                if self._parent_table._cellMutex == True:
                    for cell in self._parent_table._cells:
                        if cell._row != self._row:
                            cell.SetState(0)
                        else:
                            cell.SetState(1)

                if oldHandlers[state] is not None:
                    oldHandlers[state](button, state)

                if self._btnNewCallbacks[state]:
                    self._btnNewCallbacks[state](self._parent_table, self)

            for state in oldHandlers:
                setattr(self._btn, state, NewHandler)

        def SetText(self, text):
            if self._Text is not text:
                self._btn.SetText(text)
                self._Text = text

        def SetState(self, State):
            if self._btn.State is not State:
                self._btn.SetState(State)

        def get_col(self):
            return self._col

        def get_row(self):
            return self._row

        def get_value(self):
            return self._Text

        def get_button(self):
            return self._btn

        def __str__(self):
            return 'Cell Object:\nrow={}\ncol={}\nbtn={}'.format(self._row, self._col, self._btn)

    # class ********************************************************************
    def __init__(self):
        '''
        This class represents a spreadsheet with many cells.
        The cells will be filled with data and scrollable on a TLP.
        '''
        self._header_btns = []
        self._cells = []
        self._data_rows = []  # list of dicts. each list element is a row of data. represents the full spreadsheet.
        self._current_row_offset = 0  # indicates the data row in the top left corner
        self._current_col_offset = 0  # indicates the data col in the top left corner
        self._max_height = 0  # height of ui table. 0 = no ui table, 1 = single row ui table, etc...
        self._max_width = 0  # width of ui table. 0 = no ui table, 1 = single column ui table, etc
        self._table_header_order = []

        self._cell_pressed_callback = None
        self._cell_tapped_callback = None
        self._cell_held_callback = None
        self._cell_repeated_callback = None
        self._cell_released_callback = None

        self._scroll_updown_level = None
        self._scroll_up_button = None
        self._scroll_down_button = None
        self._scroll_updown_label = None

        self._scroll_leftright_level = None
        self._scroll_left_button = None
        self._scroll_right_button = None
        self._scroll_leftright_label = None

        self._cellMutex = False
        self._freeze = False

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

        self._initialized = False

    #Setup the table ***********************************************************
    @property
    def CellPressed(self):  # getter
        return self._cell_pressed_callback

    @CellPressed.setter
    def CellPressed(self, func):
        print('CellPressed.setter')
        # func should accept two params the ScrollingTable object and the Cell object
        self._cell_pressed_callback = func
        for cell in self._cells:
            cell._btnNewCallbacks['Pressed'] = func

    @property
    def CellTapped(self):  # getter
        return self._cell_tapped_callback

    @CellTapped.setter
    def CellTapped(self, func):
        print('CellTapped.setter')
        # func should accept two params the ScrollingTable object and the Cell object
        self._cell_tapped_callback = func
        for cell in self._cells:
            cell._btnNewCallbacks['Tapped'] = func

    @property
    def CellHeld(self):  # getter
        return self._cell_held_callback

    @CellHeld.setter
    def CellHeld(self, func):
        print('CellHeld.setter')
        # func should accept two params the ScrollingTable object and the Cell object
        self._cell_held_callback = func
        for cell in self._cells:
            cell._btnNewCallbacks['Held'] = func

    @property
    def CellRepeated(self):  # getter
        return self._cell_repeated_callback

    @CellRepeated.setter
    def CellRepeated(self, func):
        print('CellRepeated.setter')
        # func should accept two params the ScrollingTable object and the Cell object
        self._cell_repeated_callback = func
        for cell in self._cells:
            cell._btnNewCallbacks['Repeated'] = func

    @property
    def CellReleased(self):  # getter
        return self._cell_released_callback

    @CellReleased.setter
    def CellReleased(self, func):
        print('CellReleased.setter')
        # func should accept two params the ScrollingTable object and the Cell object
        self._cell_released_callback = func
        for cell in self._cells:
            cell._btnNewCallbacks['Released'] = func


    def SetCellMutex(self, state):
        # Setting this true will highlight a row when it is pressed
        self._cellMutex = state

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
        for index, arg in enumerate(args):
            arg.SetText('')
            col_number = index
            self.register_cell(row_number, col_number, btn=arg,
                pressedCallback = self._cell_pressed_callback,
                tappedCallback = self._cell_tapped_callback,
                heldCallback = self._cell_held_callback,
                repeatedCallback = self._cell_repeated_callback,
                releasedCallback = self._cell_released_callback,
                )

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

        self.IsScrollable()
        self._initialized = True #assuming that if the user is adding data to the table, then they are done setting up the table
        self._refresh_Wait.Restart()

    def ClearMutex(self):
        if self._cellMutex is True:
            for cell in self._cells:
                cell.SetState(0)

    def clear_all_data(self):
        if ScrollingTable_debug and debug: print('ScrollingTable.clear_all_data()')
        self._data_rows = []
        self.reset_scroll()

        self.ClearMutex()

        self.IsScrollable()
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

        self.IsScrollable()
        self._refresh_Wait.Restart()

    #Manipulating the table data************************************************

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

        self.IsScrollable()
        self._update_table()

    def register_cell(self, *args, **kwargs):
        NewCell = self.Cell(self, *args, **kwargs)
        self._cells.append(NewCell)

        self._find_max_row_col()

        self._refresh_Wait.Restart()

    # Displaying the table data ************************************************

    def _find_max_row_col(self):
        '''
        Determine the height and width of the viewable table
        '''
        for cell in self._cells:
            if cell._col > self._max_width:
                self._max_width = cell._col + 1  # self._max_width is width of ui table(not 0 base); 0 means no width

            if cell._row > self._max_height:
                self._max_height = cell._row + 1  # self._max_height is height of ui table(not 0 base); 0 means no height

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
        if ScrollingTable_debug and debug: print('self._max_height=', self._max_height)
        if ScrollingTable_debug and debug: print('len(self._data_rows)=', len(self._data_rows))

        max_offset = len(self._data_rows) - self._max_height  #want to show a blank row when we reach the bottom. This is a visual indicator to the user that there is no more data
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

        max_offset = len(self._table_header_order) - self._max_width  # want to show a blank col when we reach the right end. This is a visual indicator to the user that there is no more data
        if max_offset < 0:
            max_offset = 0

        self._current_col_offset += 1
        if self._current_col_offset > max_offset:
            self._current_col_offset = max_offset

        self._update_table()

    def freeze(self, state):
        #If the programmer knows they are going to be updating a bunch of data. They can freeze the table, do all their updates, then unfreeze it.
        #Unfreezing will update the table
        self._freeze = state
        if state is False:
            self._update_table() #immediate update

    def _update_table(self):
        if self._initialized and not self._freeze:
            if ScrollingTable_debug and debug: print('ScrollingTable._update_table()')

            # iterate over all the cell objects
            for cell in self._cells:
                data_row_index = cell._row + self._current_row_offset
                if ScrollingTable_debug and debug:
                    #print('cell._row={}, data_row_index={}'.format(cell._row, data_row_index))
                    pass

                # Is there data for this cell to display?
                if data_row_index < len(self._data_rows):
                    # Yes there is data for this cell to display

                    row_dict = self._data_rows[data_row_index]
                    # row_dict holds the data for this row
                    if ScrollingTable_debug and debug: print('cell._row={}\ndata_row_index={}\nrow_dict={}'.format(cell._row, data_row_index, row_dict))

                    col_header_index = cell._col + self._current_col_offset
                    # col_header_index is int() base 0 (left most col is 0)
                    # if ScrollingTable_debug and debug: print('col_header_index=', col_header_index)

                    # if ScrollingTable_debug and debug: print('self._table_header_order=', self._table_header_order)
                    if col_header_index < len(self._table_header_order):
                        col_header_text = self._table_header_order[col_header_index]
                    else:
                        col_header_text = ''
                    # if ScrollingTable_debug and debug: print('col_header=', col_header)

                    # if ScrollingTable_debug and debug: print('row_dict=', row_dict)

                    if col_header_text in row_dict:
                        cell_text = row_dict[col_header_text]  # cell_text holds data for this cell
                    else:
                        # There is no data for this column header
                        cell_text = ''

                    # if ScrollingTable_debug and debug: print('cell_text=', cell_text)

                    cell.SetText(str(cell_text))
                else:
                    # no data for this cell
                    cell.SetText('')

            # update scroll up/down controls
            if self._scroll_updown_level:
                max_row_offset = len(self._data_rows) - self._max_height
                percent = toPercent(self._current_row_offset, 0, max_row_offset)
                self._scroll_updown_level.SetLevel(percent)

            # update scroll left/right controls
            if self._scroll_leftright_level:
                max_col_offset = len(self._table_header_order) - self._max_width
                percent = toPercent(self._current_col_offset, 0, max_col_offset)
                self._scroll_leftright_level.SetLevel(percent)

            #update col headers
            for headerButton in self._header_btns:
                headerButtonIndex = self._header_btns.index(headerButton)
                headerTextIndex = self._current_col_offset + headerButtonIndex
                if headerTextIndex < len(self._table_header_order):
                    text = self._table_header_order[headerTextIndex]
                    headerButton.SetText(text)

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

    def get_row_data_from_cell(self, cell):
        # returns a dict of the row data
        rowIndex = cell.get_row()
        dataIndex = rowIndex + self._current_row_offset
        return self._data_rows[dataIndex]

    def get_row_data(self, where_dict=None):
        # returns a list of dicts that match whereDict
        # if where_dict == None, will return all data
        if where_dict == None:
            where_dict = {}

        result = []

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
                result.append(row)

        return result

    def reset_scroll(self):
        self._current_row_offset = 0
        self._refresh_Wait.Restart()

    def sort_by_column_list(self, colNumberList, reverse=False):
        colHeaderList = []
        for colNumber in colNumberList:
            colHeaderList.append(self._table_header_order[colNumber])
        print('colHeaderList=', colHeaderList)

        print('sort_by_column_list before=', self._data_rows)
        self._data_rows = SortListOfDictsByKeys(self._data_rows, colHeaderList, reverse)
        print('sort_by_column_list after=', self._data_rows)

        self._refresh_Wait.Restart()

    def sort_by_column(self, col_number, reverse=False):
        '''
        '''
        key = self._table_header_order[col_number]
        self._data_rows = SortListDictByKey(self._data_rows, key, reverse)
        self._refresh_Wait.Restart()

    def register_scroll_updown_level(self, level):
        # level = extronlib.ui.Level
        self._scroll_updown_level = level

    def register_scroll_up_button(self, button):
        self._scroll_up_button = button

    def register_scroll_down_button(self, button):
        self._scroll_down_button = button

    def register_scroll_updown_label(self, label):
        self._scroll_updown_label = label

    def register_scroll_leftright_level(self, level):
        # level = extronlib.ui.Level
        self._scroll_leftright_level = level

    def register_scroll_left_button(self, button):
        self._scroll_left_button = button

    def register_scroll_right_button(self, button):
        self._scroll_right_button = button

    def register_scroll_leftright_label(self, label):
        self._scroll_leftright_label = label

    def IsScrollable(self):
        '''
        basically if there are 10 rows on your TLP, but you only have 5 rows of data, then you dont need to show scroll buttons, hide the controls assiciated with scrolling
        '''
        #up/down scroll controls
        if len(self._data_rows) > self._max_height:
            if self._scroll_updown_level is not None:
                self._scroll_updown_level.SetVisible(True)

            if self._scroll_up_button is not None:
                self._scroll_up_button.SetVisible(True)

            if self._scroll_down_button is not None:
                self._scroll_down_button.SetVisible(True)

            if self._scroll_updown_label is not None:
                self._scroll_updown_label.SetVisible(True)

        else:
            if self._scroll_updown_level is not None:
                self._scroll_updown_level.SetVisible(False)

            if self._scroll_up_button is not None:
                self._scroll_up_button.SetVisible(False)

            if self._scroll_down_button is not None:
                self._scroll_down_button.SetVisible(False)

            if self._scroll_updown_label is not None:
                self._scroll_updown_label.SetVisible(False)

        #left/right scroll controls
        if len(self._table_header_order) > self._max_width:
            if self._scroll_leftright_level is not None:
                self._scroll_leftright_level.SetVisible(True)

            if self._scroll_left_button is not None:
                self._scroll_left_button.SetVisible(True)

            if self._scroll_right_button is not None:
                self._scroll_right_button.SetVisible(True)

            if self._scroll_leftright_label is not None:
                self._scroll_leftright_label.SetVisible(True)

        else:
            if self._scroll_leftright_level is not None:
                self._scroll_leftright_level.SetVisible(False)

            if self._scroll_left_button is not None:
                self._scroll_left_button.SetVisible(False)

            if self._scroll_right_button is not None:
                self._scroll_right_button.SetVisible(False)

            if self._scroll_leftright_label is not None:
                self._scroll_leftright_label.SetVisible(False)


# UserInput *********************************************************************
class UserInputClass:
    '''
    A one-time setup of the buttons/popups and the programmer can easily grab info from the user like so:

    Get an integer/float/text from the user: UserInput.get_keyboard('popupname', callback=CallbackFunction)
    Get a calendar data as a datetime.datetime object: UserInput.get_date(**kwargs)
    etc...
    '''
    _instances = [] #hold all instances so that instances can request each other to update


    def __init__(self, TLP):
        self._TLP = TLP

        self._kb_feedback_btn = None
        self._kb_text_feedback = None
        self._kb_callback = None
        self._instances.append(self)

    def set_file_explorer_parameters(self, d):
        for key, value in d.items():
            method = getattr(self._dirNav, key)
            method(value)

    def setup_file_explorer(self,
            lblCurrentDirectory=None,
            btnScrollUp=None,
            btnScrollDown=None,
            lvlScrollFeedback=None,
            lblScrollText=None,
            btnNavUp=None,

            lblMessage=None,
            btnClosePopup=None,
            popupName=None,
            limitStringLen=25,
            btnSubmit=None,
            ):

        self._file_explorer_lblMessage = lblMessage
        self._file_explorer_popupName = popupName
        self._btnSubmit = btnSubmit

        self._dirNav = DirectoryNavigationClass(
                 lblCurrentDirectory,
                 btnScrollUp,
                 btnScrollDown,
                 lvlScrollFeedback,
                 lblScrollText,
                 btnNavUp,
                 limitStringLen=limitStringLen,
                 lblMessage=lblMessage,
                 )

        self._file_explorer_filename = None
        self._file_explorer_filepath = None
        self._file_explorer_getFileCallback = None

        self._dirNav.FileSelected = self._file_explorer_fileSelectedCallback
        self._dirNav.FileHeld = self._file_explorer_fileHeldCallback

        if btnClosePopup:
            @event(btnClosePopup, 'Released')
            def btnClosePopupEvent(button, state):
                btnClosePopup.Host.HidePopup(self._file_explorer_popupName)


    def _file_explorer_fileSelectedCallback(self, dirNav, path, passthru=None):
        self._file_explorer_filepath = path
        self._file_explorer_filename = path.split('/')[-1]

        if callable(self._file_explorer_getFileCallback):
            self._file_explorer_getFileCallback(self, path, self._file_explorer_passthru)

        if self._file_explorer_feedback_btn is not None:
            self._file_explorer_feedback_btn.SetText(self._file_explorer_filename)

        if self._file_explorer_popupName is not None:
            self._TLP.HidePopup(self._file_explorer_popupName)

    def _file_explorer_fileHeldCallback(self, dirNav, filepath):
        print('_file_explorer_fileHeldCallback(dirNav={}, filepath={})'.format(dirNav, filepath))

        def DirNavActionCallback(input, value, passthru):
            filepath = passthru['filepath']

            if 'Delete' in value:
                if self._dirNav.IsFile(filepath):
                    File.DeleteFile(filepath)
                    self._dirNav.UpdateData()

                elif self._dirNav.IsDirectory(filepath):
                    File.DeleteDirRecursive(filepath)
                    self._dirNav.UpdateData()

            elif 'Make New Directory' == value:
                self.make_new_directory(
                    data=None, #internal file system
                    callback=None,
                    passthru=None,
                    makeDir=True, #whether to actually create the dir, False will just return the new path to the user, True will actually create the dir in the internal filesystem
                    )

            elif 'Make New File' == value:
                self.make_new_file(
                    data=None, #internal file system
                    callback=None,
                    feedback_btn=None,
                    passthru=None,
                    extension=None, #'.json', '.dat', etc...
                    keyboardPopupName=None,
                    )

        options = []
        if self._dirNav.AllowMakeNewFolder():
            options.append('Make New Directory')

        if self._dirNav.AllowMakeNewFile():
            options.append('Make New File')

        if self._dirNav.AllowDelete() and (self._dirNav.IsFile(filepath) or self._dirNav.IsDirectory(filepath)):
            options.append('Delete this {}'.format(self._dirNav.GetType(filepath)))

        self.get_list(
            options=options,  # list()
            callback=DirNavActionCallback,
            # function - should take 2 params, the UserInput instance and the value the user submitted
            feedback_btn=None,
            passthru={'filepath': filepath},  # any object that you want to pass thru to the callback
            message='Choose an action.',
            sort=True,
            )

    def file_explorer_register_row(self, *args, **kwargs):
        '''
        Example:
        for rowNumber in range(0, 7+1):
            file_explorer_register_rowObject.RegisterRow(
                rowNumber=rowNumber,
                btnIcon=Button(ui, 2000+rowNumber),
                btnSelection=Button(ui, 1000+rowNumber, PressFeedback='State'),
        )
        '''
        self._dirNav.RegisterRow(*args, **kwargs)

    def get_file(self,
                data=None,
                callback=None,
                feedback_btn=None,
                passthru=None,
                message=None,
                submitText='Submit',
                submitCallback=None, #(button, state),
                startingDir=None
                ):

        self._dirNav.SetShowFiles(True)

        if startingDir is not None:
            self._dirNav.SetCurrentDirectory(startingDir)

        if data is None:
            data = File.ListDirWithSub()

        self._dirNav.UpdateData(data)
        self._file_explorer_getFileCallback = callback
        self._file_explorer_feedback_btn = feedback_btn
        self._file_explorer_passthru = passthru

        if self._file_explorer_lblMessage is not None and message is not None:
            self._file_explorer_lblMessage.SetText(message)

        if self._btnSubmit:
            if submitCallback is None:
                self._btnSubmit.SetVisible(False)
            else:
                self._btnSubmit.SetText(submitText)
                self._btnSubmit.SetVisible(True)
                @event(self._btnSubmit, 'Released')
                def self_btnSubmitEvent(button, state):
                    submitCallback(button, state)

        def SubCallback(dirNavObject, value, passthru=None):
            self._TLP.HidePopup(self._file_explorer_popupName)
            callback(self, value, self._file_explorer_passthru)

        self._dirNav.FileSelected = SubCallback

        if self._file_explorer_popupName is not None:
            Wait(0.1, lambda: self._TLP.ShowPopup(self._file_explorer_popupName))

    def make_new_directory(self,
                data=None,
                callback=None,
                passthru=None,
                makeDir=False, #whether to actually create the dir, False will just return the new path to the user, True will actually create the dir in the internal filesystem
                ):
        if data is None:
            data = File.ListDirWithSub()

        self._dirNav.SetShowFiles(False)

        def getNewDirNameCallback(input, value, passthru3=None):
            newFolderName = value
            currentDir = self._dirNav.GetDir()
            File.MakeDir(currentDir + '/' + newFolderName)
            self._dirNav.UpdateData()


        popup = self._kb_other_popups.get('AlphaNumeric', self._kb_popup_name)

        self.get_keyboard(
            kb_popup_name=popup,
            callback=getNewDirNameCallback, # function - should take 2 params, the UserInput instance and the value the user submitted
            feedback_btn=None,
            password_mode=False,
            text_feedback=None,  # button()
            passthru=None,  # any object that you want to also come thru the callback
            message='Enter a name for the new directory.',
            )

    def make_new_file(self,
                data=None, #list of filePath as str, or None means use the IPCP internal file system
                callback=None,
                feedback_btn=None,
                passthru=None,
                extension=None, #'.json', '.dat', etc...
                keyboardPopupName=None,
                ):
        '''Use this method to create a new filePath and let the user choose the name and which directory to save it in
        returns: path to the new file. THe user will have to use File(path, mode='wt') to actually write data to the file
        return type: str (example: '/folder1/subfolder2/filename.txt')
        '''

        self._dirNav.SetShowFiles(False)

        if keyboardPopupName is None:
            keyboardPopupName = self._kb_popup_name

        if extension is None:
            extension = '.dat'

        def newFileDirectoryCallback(input, value, passthru2):
            print('newFileDirectoryCallback(input={}, value={}, passthru2={})'.format(input, value, passthru2))
            if callable(callback):
                value = value + passthru2

                callback(self, value, passthru)

        def newFileNameCallback(input, value, passthru3=None):
            print('newFileNameCallback(input={}, value={}, passthru3={})'.format(input, value, passthru3))
            value = value+extension

            #let the user choose which directory to save this file to
            self.get_directory(
                data=None,
                callback=newFileDirectoryCallback,
                feedback_btn=None,
                passthru=value,
                message='Choose where to save {}'.format(value),
                )

        self.get_keyboard(
            kb_popup_name=keyboardPopupName,
            callback=newFileNameCallback, # function - should take 2 params, the UserInput instance and the value the user submitted
            feedback_btn=None,
            password_mode=False,
            text_feedback=None,  # button()
            passthru=None,  # any object that you want to also come thru the callback
            message='Enter a new name for the file.',
            )

    def get_directory(self,
                data=None,
                callback=None,
                feedback_btn=None,
                passthru=None,
                message=None,
                ):
        self._dirNav.SetShowFiles(False)

        if data is None:
            data = File.ListDirWithSub()

        if message is None:
            message = 'Select a folder'

        self._dirNav.UpdateData(data)
        self._dirNav.FileSelected = None #dont do anything when a file is selected. A file should never be selected anyway.
        self._dirNav.UpdateMessage(message)

        if self._btnSubmit:

            @event(self._btnSubmit, 'Released')
            def btnSubmitEvent(button, state):
                if callable(callback):
                    callback(self, self._dirNav.GetDir(), passthru)
                self._btnSubmit.Host.HidePopup(self._file_explorer_popupName)

            self._btnSubmit.SetText('Select this folder')
            self._btnSubmit.SetVisible(True)

            if self._file_explorer_popupName is not None:
                Wait(0.1, lambda: self._TLP.ShowPopup(self._file_explorer_popupName))

        else:
            raise Exception('"get_directory" requires "setup_file_explorer()" with btnSubmit parameter')


    def setup_calendar(self,
                       calDayNumBtns,
                       # list of int() where the first int is the first day of the first week. Assuming 5 weeks of 7 days
                       calDayAgendaBtns=None,
                       calBtnNext=None,  # button that when pressed will show the next month
                       calBtnPrev=None,  # button that when pressed will show the previous month
                       calBtnCancel=None,  # button when presses will hide the modal
                       calLblMessage=None,  # Button or Label
                       calLblMonthYear=None,
                       calPopupName=None,
                       startDay=None,
                       maxAgendaWidth=None

                       ):
        '''
        This func must be called before self.get_date()
        :param calDayNumBtns:
        :param calDayAgendaBtns:
        :param calBtnNext:
        :param calBtnPrev:
        :param calBtnCancel:
        :param calLblMessage:
        :param calLblMonthYear:
        :param calPopupName:
        :param startDay:
        :param maxAgendaWidth:
        :return:
        '''

        # Save args
        self._calDayNumBtns = calDayNumBtns
        self._calDayAgendaBtns = calDayAgendaBtns
        self._calBtnNext = calBtnNext
        self._calBtnPrev = calBtnPrev
        self._calBtnCancel = calBtnCancel
        self._calLblMessage = calLblMessage
        self._calLblMonthYear = calLblMonthYear
        self._calPopupName = calPopupName
        self._maxAgendaWidth = maxAgendaWidth

        # Create attributes
        if startDay is None:
            startDay = 6  # sunday
        self._calObj = calendar.Calendar(startDay)

        self._currentYear = 0
        self._currentMonth = 0
        self._currentDatetime = datetime.datetime.now()
        self._calEvents = [
            # {'datetime': dt,
            # 'name': 'name of event',
            # 'meta': {'Room Name': 'Room1',
            #          'Device Name': 'Room2',
            #           }
            # }
        ]
        self._calCallback = None
        self._dtMap = {}
        self._calHeldEvent = None

        # Hide/Cancel button
        if self._calBtnCancel is not None:
            @event(self._calBtnCancel, 'Released')
            def calBtnCancelEvent(button, state):
                if self._calPopupName is not None:
                    self._TLP.HidePopup(self._calPopupName)

        # Next/Prev buttons
        @event(self._calBtnNext, 'Released')
        def calBtnNextEvent(button, state):
            self._currentMonth += 1
            if self._currentMonth > 12:
                self._currentYear += 1
                self._currentMonth = 1

            self._calDisplayMonth(datetime.datetime(year=self._currentYear, month=self._currentMonth, day=1))

        @event(self._calBtnPrev, 'Released')
        def _calBtnPrevEvent(button, state):
            self._currentMonth -= 1
            if self._currentMonth < 1:
                self._currentYear -= 1
                self._currentMonth = 12

            self._calDisplayMonth(datetime.datetime(year=self._currentYear, month=self._currentMonth, day=1))

        # Day/Agenda buttons
        @event(self._calDayNumBtns, 'Released')
        @event(self._calDayAgendaBtns, 'Released')
        def calDayNumBtnsEvent(button, state):
            pass

        # Init the button states
        for btn in self._calDayNumBtns:
            btn.SetState(0)
        for btn in self._calDayAgendaBtns:
            btn.SetState(0)

        # Load previous data
        self._LoadCalData()

    def get_date(self,
                 popupName,
                 callback=None,
                 # function - should take 2 params, the UserInput instance and the value the user submitted
                 feedback_btn=None,
                 passthru=None,  # any object that you want to pass thru to the callback
                 message=None,
                 startMonth=None,
                 startYear=None,
                 ):
        '''
        The programmer must call self.setup_calendar() before calling this method.
        :param popupName:
        :param callback:
        :param feedback_btn:
        :param passthru:
        :param message:
        :param startMonth:
        :param startYear:
        :return:
        '''

        self._calCallback = callback

        if self._calLblMessage is not None:
            if message is None:
                self._calLblMessage.SetText('Select a date')
            else:
                self._calLblMessage.SetText(message)

        # Populate the calendar info
        now = datetime.datetime.now()
        if startMonth is None:
            startMonth = now.month

        if startYear is None:
            startYear = now.year

        self._currentYear = startYear
        self._currentMonth = startMonth

        self._calDisplayMonth(datetime.datetime(year=startYear, month=startMonth, day=1))

        # Show the calendar
        self._TLP.ShowPopup(popupName)

        @event(self._calDayNumBtns, 'Released')
        @event(self._calDayAgendaBtns, 'Released')
        def calDayNumBtnsEvent(button, state):
            if callable(self._calCallback):
                dt = self._GetDatetimeFromButton(button)
                self._calCallback(self, dt)
                self._currentDatetime = dt

    def CalOffsetTimedelta(self, delta):
        '''
        Change the calendar by delta time.
        For example if I am currently looking at info for today and I want to see next week's info,
            I would call UserInput.CalOffsetTimedelta(datetime.timedelta(days=7))
            This would cause the UI to update to show next weeks info.
        :param delta: datetime.timedelta object
        :return:
        '''
        if self._currentDatetime is None:
            self._currentDatetime = datetime.datetime.now()

        self._currentDatetime += delta

        return self._currentDatetime

    def GetCalCurrentDatetime(self):
        '''
        return a datetime.datetime object of the info currently being displayed.
        :return:
        '''
        return self._currentDatetime

    def _GetDatetimeFromButton(self, button):
        for date in self._dtMap:
            if button in self._dtMap[date]:
                return date

    def UpdateMonthDisplay(self, dt=None):
        '''
        The programmer can call this to update the buttons with info for the month contained in dt
        :param dt: datetime.datetime object
        :return:
        '''
        if dt is None:
            dt = self.GetCalCurrentDatetime()

        for instance in self._instances:
            instance._calDisplayMonth(dt)

    def _calDisplayMonth(self, dt):
        # date = datetime.datetime object
        # this will update the TLP with data for the month of the datetime.date

        self._dtMap = {}

        self._calLblMonthYear.SetText(dt.strftime('%B %Y'))

        monthDates = list(self._calObj.itermonthdates(dt.year, dt.month))
        for date in monthDates:
            index = monthDates.index(date)
            if index >= len(self._calDayNumBtns):
                continue
            btnDayNum = self._calDayNumBtns[index]
            btnDayAgenda = self._calDayAgendaBtns[index]

            # Save the datetime and map it to the buttons for later use
            self._dtMap[date] = [btnDayNum, btnDayAgenda]

            if date.month != self._currentMonth:  # Not part of the month
                newState = 1
                newText = date.strftime('%d ')
            else:  # is part of the month
                newState = 0
                newText = date.strftime('%d ')

            agendaText = self._GetAgendaText(date)

            # btnDayNum
            if btnDayNum.State != newState:
                btnDayNum.SetState(newState)

            if btnDayNum.Text != newText:
                btnDayNum.SetText(newText)

            # btnDayAgenda
            if btnDayAgenda.State != newState:
                btnDayAgenda.SetState(newState)

            if btnDayAgenda.Text != agendaText:
                btnDayAgenda.SetText(agendaText)

    def _GetAgendaText(self, date):
        result = ''

        for item in self._calEvents:
            dt = item['datetime']
            if date.year == dt.year:
                if date.month == dt.month:
                    if date.day == dt.day:
                        name = item['name']
                        string = '{} - {}\n'.format(dt.strftime('%-I:%M%p'), name)

                        # Make sure the string isnt too long
                        if self._maxAgendaWidth is not None:
                            if len(string) > self._maxAgendaWidth:
                                string = string[:self._maxAgendaWidth - 4] + '...\n'

                        result += string

        return result

    def GetAgendaFromDatetime(self, date):
        '''
        Returns a list of eventDicts that are happening on the date

        eventDict looks like:
        {
        'datetime': dt, #datetime.datetime object representing the time the event is happening
        'name': 'Name Of The Event', #str representing the name of the event
        'meta': {'Room Number': 'Room 101'}, #dict with any custom values that the user may want to hold about the event. For example a room number.
        }

        :param date: datetime.date or datetime.datetime
        :return: list like [{eventDict1, eventDict2, ...]
        '''

        result = []

        for item in self._calEvents:
            dt = item['datetime']
            if date.year == dt.year:
                if date.month == dt.month:
                    if date.day == dt.day:
                        name = item['name']
                        result.append(item)

        return result

    def GetAllCalendarEvents(self):
        '''
        eventDict looks like:
        {
        'datetime': dt, #datetime.datetime object representing the time the event is happening
        'name': 'Name Of The Event', #str representing the name of the event
        'meta': {'Room Number': 'Room 101'}, #dict with any custom values that the user may want to hold about the event. For example a room number.
        }
        :return: list of all eventDicts
        '''
        return self._calEvents.copy()

    def AddCalendarEvent(self, dt, name, metaDict=None):
        '''
        Add an event to the calendar
        :param dt: datetime.datetime
        :param name: str
        :param metaDict: {}
        :return:
        '''
        if metaDict is None:
            metaDict = {}

        eventDict = {
            'datetime': dt,
            'name': name,
            'meta': metaDict,
        }

        self._calEvents.append(eventDict)

        self._SaveCalData()
        self._calDisplayMonth(dt)

    def _SaveCalData(self):
        # Write the data to a file
        saveItems = []

        for item in self._calEvents:
            dt = item['datetime']
            saveItem = {'datetime': GetDatetimeKwargs(dt),
                        'name': item['name'],
                        'meta': item['meta'],
                        }
            saveItems.append(saveItem)

        with File('calendar.json', mode='wt') as file:
            file.write(json.dumps(saveItems, indent=4))
            file.close()

    def _LoadCalData(self):
        if not File.Exists('calendar.json'):
            self._calEvents = []
            return

        with File('calendar.json', mode='rt') as file:
            saveItems = json.loads(file.read())
            file.close()

            for saveItem in saveItems:
                dt = datetime.datetime(**saveItem['datetime'])

                loadItem = {
                    'datetime': dt,
                    'name': saveItem['name'],
                    'meta': saveItem['meta'],
                }

                self._calEvents.append(loadItem)

    def GetCalEvents(self, dt):
        '''
        return list of eventDicts happening at a specific datetime.datetime

        eventDict looks like:
        {
        'datetime': dt, #datetime.datetime object representing the time the event is happening
        'name': 'Name Of The Event', #str representing the name of the event
        'meta': {'Room Number': 'Room 101'}, #dict with any custom values that the user may want to hold about the event. For example a room number.
        }
        :param dt: datetime.datetime
        :return: list
        '''
        result = []
        for item in self._calEvents:
            dataDT = item['datetime']
            if dt.year == dataDT.year:
                if dt.month == dataDT.month:
                    if dt.day == dataDT.day:
                        if isinstance(dt, datetime.datetime):
                            if dt.hour is not 0:
                                if dt.hour == dataDT.hour:
                                    if dt.minute is not 0:
                                        if dt.minute == dataDT.minute:
                                            result.append(item)
                                    else:
                                        result.append(item)
                            else:
                                result.append(item)
                        else:  # probably a datetime.date object
                            result.append(item)

        return result

    def HoldThisEvent(self, eventDict):
        '''
        This class can hold one eventDict for the programmer.
        :param eventDict:
        :return:
        '''
        self._calHeldEvent = eventDict

    def GetHeldEvent(self):
        '''
        Returns the held eventDict
        :return: eventDict or None
        '''
        return self._calHeldEvent

    def TrashHeldEvent(self):
        '''
        Deletes the held event from memory.
        :return:
        '''
        self.DeleteEvent(self._calHeldEvent)
        self._calHeldEvent = None

    def DeleteEvent(self, eventDict):
        '''
        Deletes the specified eventDict
        :param eventDict:
        :return:
        '''
        if eventDict in self._calEvents:
            self._calEvents.remove(eventDict)
        else:
            raise Exception('Exception in DeleteEvent\neventDict not in self._calEvents')

        self._SaveCalData()

    def setup_list(self,
                   list_popup_name,  # str()
                   list_btn_hide,  # Button object
                   list_btn_table,  # list()
                   list_btn_scroll_up=None,  # Button object
                   list_btn_scroll_down=None,  # Button object
                   list_label_message=None,  # Button/Label object
                   list_label_scroll=None,# Button/Label object
                   list_level_scroll=None,

                   ):

        self._list_popup_name = list_popup_name
        self._list_table = ScrollingTable()

        if list_level_scroll is not None:
            self._list_table.register_scroll_updown_level(list_level_scroll)

        if list_label_message is not None:
            self._list_table.register_scroll_updown_label(list_label_scroll)

        if list_btn_scroll_up:
            self._list_table.register_scroll_up_button(list_btn_scroll_up)

        if list_btn_scroll_down:
            self._list_table.register_scroll_down_button(list_btn_scroll_down)

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

                #Set text feedback
                if self._list_feedback_btn:
                    self._list_feedback_btn.SetText(button.Text)

                #do callback
                if self._list_callback:
                    if self._list_passthru is not None:
                        self._list_callback(self, button.Text, self._list_passthru)
                    else:
                        self._list_callback(self, button.Text)

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
                       kb_popup_name,  # str() #default popup name
                       kb_btn_submit,  # Button()
                       kb_btn_cancel=None,  # Button()
                       kb_other_popups = {}, # {'Integer': 'User Input - Integer', 'Float': 'User Input - Float', 'AlphaNumeric': 'User Input - AlphaNumeric'}

                       KeyIDs=None,  # list()
                       BackspaceID=None,  # int()
                       ClearID=None,  # int()
                       SpaceBarID=None,  # int()
                       ShiftID=None,  # int()
                       FeedbackObject=None,  # object with .SetText() method
                       kb_btn_message=None,
                       ):

        self._kb_popup_name = kb_popup_name
        self._kb_other_popups = kb_other_popups
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

        self._kb_Keyboard.SetPasswordMode(password_mode)

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
            bool_btn_long_message=None,
            bool_btn_true_explaination=None,
            bool_btn_false_explanation=None,
            ):
        self._bool_callback = None
        self._bool_true_text = 'Yes'
        self._bool_false_text = 'No'

        self._bool_popup_name = bool_popup_name

        self._bool_btn_true = bool_btn_true
        self._bool_btn_false = bool_btn_false
        self._bool_btn_cancel = bool_btn_cancel

        self._bool_btn_message = bool_btn_message
        self._bool_btn_long_message = bool_btn_long_message
        self._bool_btn_true_explaination = bool_btn_true_explaination
        self._bool_btn_false_explanation = bool_btn_false_explanation

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
                    long_message=None,
                    true_message=None,
                    false_message=None,
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

        if long_message:
            self._bool_btn_long_message.SetText(long_message)
        else:
            self._bool_btn_long_message.SetText('')

        if true_message:
            self._bool_btn_true_explaination.SetText(true_message)
        else:
            self._bool_btn_true_explaination.SetText('')

        if false_message:
            self._bool_btn_false_explanation.SetText(false_message)
        else:
            self._bool_btn_false_explanation.SetText('')


        self._bool_btn_true.Host.ShowPopup(self._bool_popup_name)


# Non-global variables **********************************************************
class NonGlobal:
    '''
    This class could be replaced by global vars, but this class makes the management and readability better
    values will be lost upon power-cycle or re-upload
    '''

    def Set(self, name_of_value_str, value):
        setattr(self, name_of_value_str, value)

    def Get(self, name_of_value_str):
        return getattr(self, name_of_value_str)


# Hash function *****************************************************************
def hash_it(string=''):
    '''
    This function takes in a string and converts it to a unique hash.
    Note: this is a one-way conversion. The value cannot be converted from hash to the original string
    :param string:
    :return: str
    '''
    arbitrary_string = 'gs_tools_arbitrary_string'
    string += arbitrary_string
    return hashlib.sha512(bytes(string, 'utf-8')).hexdigest()

def GetRandomPassword(length=512):
    pw = ''
    for i in range(length):
        ch = random.choice(['1','2','3','4','5','6','7','8','9','0',
                            'a','b','c','d','f'])
        pw += ch
    return pw

timerDebug = False
# Timer class (safer than recursive Wait objects per PD)
class Timer:
    def __init__(self, t, func):
        '''
        This class calls self.func every t-seconds until Timer.Stop() is called.
        It has protection from the "cant start thread" error.
        :param t: float
        :param func: callable (no parameters)
        '''
        if timerDebug: print('Timer.__init__(t={}, func={})'.format(t, func))
        self._func = func
        self._t = t
        self._run = False

    def Stop(self):
        if timerDebug: print('Timer.Stop()')
        self._run = False

    def Start(self):
        if timerDebug: print('Timer.Start()')
        if self._run is False:
            self._run = True

            try:
                @Wait(0)  # Start immediately
                def loop():
                    try:
                        # print('entering loop()')
                        while self._run:
                            # print('in while self._run')
                            if self._t < 0:
                                pass
                            else:
                                time.sleep(self._t)
                            if self._run:  # The .Stop() method may have been called while this loop was sleeping
                                self._func()
                                # print('exiting loop()')
                    except Exception as e:
                        print('Error in timer func={}\n{}'.format(self._func, e))
            except Exception as e:
                if 'can\'t start new thread' in str(e):
                    print('There are too many threads right now.\nWaiting for more threads to be available.')
                time.sleep(1)
                self.Start()

    def ChangeTime(self, new_t):
        '''
        This method allows the user to change the timer speed on the fly.
        :param new_t: float
        :return:
        '''
        if timerDebug: print('Timer.ChangeTime({})'.format(new_t))

        self._t = new_t

    def Restart(self):
        # To easily replace a Wait object
        self.Start()

    def Cancel(self):
        # To easily replace a Wait object
        self.Stop()

    def __str__(self):
        return '<gs_tools.Timer>\n_func={}\nt={}'.format(self._func, self._t)


def GetDatetimeKwargs(dt):
    '''
    This converts a datetime.datetime object to a dict.
    This is useful for saving a datetime.datetime object as a json string
    :param dt: datetime.datetime
    :return: dict
    '''
    d = {'year': dt.year,
         'month': dt.month,
         'day': dt.day,
         'hour': dt.hour,
         'minute': dt.minute,
         'second': dt.second,
         'microsecond': dt.microsecond,
         }
    return d


class Schedule:
    '''
    An easy class to call a function at a particular datetime.datetime
    '''

    def __init__(self):
        self._wait = None

    def Set(self, set_dt, func, *args, **kwargs):
        # This will execute func when time == dt with args/kwargs

        if self._wait is not None:
            self._wait.Cancel()
            self._wait = None

        # Save the attributes
        self._dt = set_dt
        self._func = func
        self._args = args
        self._kwargs = kwargs

        nowDT = datetime.datetime.now()
        delta = self._dt - nowDT
        waitSeconds = delta.total_seconds()
        print('waitSeconds=', waitSeconds)

        self._wait = Wait(waitSeconds, self._callback)

    def Cancel(self):
        print('Schedule.Cancel()')
        self._wait.Cancel()

    def _callback(self):
        print('Schedule._callback, self.func={}, self.args={}, self.kwargs={},'.format(self._func, self._args,
                                                                                       self._kwargs))
        print('Processor time =', time.asctime())
        if not self._args == ():
            if not self._kwargs == {}:
                self._func(*self._args, **self._kwargs)
            else:
                self._func(*self._args)
        else:
            if not self._kwargs == {}:
                self._func(**self._kwargs)
            else:
                self._func()


def HandleConnection(*args, **kwargs):
    if UniversalConnectionHandler._defaultCH is None:
        newCH = UniversalConnectionHandler()
        UniversalConnectionHandler._defaultCH = newCH

    UniversalConnectionHandler._defaultCH.maintain(*args, **kwargs)


def ConnectionHandlerLogicalReset(interface):
    # for backwards compatibility mostly
    if interface in UniversalConnectionHandler._defaultCH._send_counters:
        UniversalConnectionHandler._defaultCH._send_counters[interface] = 0
    pass


def RemoveConnectionHandlers(interface):
    print('RemoveConnectionHandlers\n interface={}'.format(interface))
    interface.Connected = None
    interface.Disconnected = None
    if interface in _connection_status:
        _connection_status.pop(interface)
    print('_connection_status=', _connection_status)


def AddConnectionCallback(interface, callback):
    interface.Connected = callback
    interface.Disconnected = callback


statusButtons = {}


def AddStatusButton(interface, button, GREEN=GREEN, RED=RED):
    if UniversalConnectionHandler._defaultCH is None:
        newCH = UniversalConnectionHandler()
        UniversalConnectionHandler._defaultCH = newCH

    if interface not in statusButtons:
        statusButtons[interface] = []

    if button not in statusButtons[interface]:
        statusButtons[interface].append(button)

    @event(interface, ['Connected', 'Disconnected'])
    def interfaceConnectionEvent(interface, state):
        for btn in statusButtons[interface]:
            if state in ['Connected', 'Online']:
                btn.SetState(GREEN)
                btn.SetText('Connected')
            elif state in ['Disconnected', 'Offline']:
                btn.SetState(RED)
                btn.SetText('Disconnected')
            else:
                btn.SetState(WHITE)
                btn.SetText('Error 16')

debugUCH = False

class UniversalConnectionHandler:
    _defaultCH = None

    def __init__(self, filename='connection_handler.log'):
        '''
        :param filename: str() name of file to write connection status to
        '''
        self._interfaces = []
        self._connection_status = {
            # interface: 'Connected',
        }
        self._connected_callback = None  # callable
        self._disconnected_callback = None

        self._timers = {
            # interface: Timer_obj,
        }
        self._connection_retry_freqs = {
            # interface: float() #number of seconds between retrys
        }
        self._connection_timeouts = {
            # interface: float() #number of seconds to timeout trying to connect
        }
        self._send_counters = {
            # interface: int() #number of times data has been sent without receiving a response
        }
        self._disconnect_limits = {
            # interface: int() #number of times to miss a response before triggering disconnected status
        }
        self._rx_handlers = {
            # interface: function #function must take 2 params, "interface" object and "data" bytestring
        }
        self._connected_handlers = {
            # interface: function
        }
        self._disconnected_handlers = {
            # interface: function
        }
        self._user_connected_handlers = {
            # interface: function
        }
        self._user_disconnected_handlers = {
            # interface: function
        }
        self._send_methods = {
            # interface: function
        }
        self._send_and_wait_methods = {
            # interface: function
        }

        self._server_listen_status = {
            # interface: 'Listening' or 'Not Listening' or other
        }

        self._server_client_rx_timestamps = {
            # EthernetServerInterfaceEx1: {ClientObject1A: timestamp1,
            # ClientObject1B: timestamp2,
            # },
            # EthernetServerInterfaceEx2: {ClientObject2A: timestamp3,
            # ClientObject2B: timestamp4,
            # },
        }

        self._keep_alive_query_cmds = {
            # interface: 'string',
        }

        self._keep_alive_query_quals = {
            # interface: dict(),
        }
        self._poll_freqs = {
            # interface: float(),
        }

        self._filename = filename
        if not File.Exists(self._filename):
            File(self._filename, mode='wt').close()  # Create a blank file if it doesnt exist already

    def maintain(self,
                 interface,
                 keep_alive_query_cmd=None, # Can be a module command like 'Power', or a raw string like 'q'
                 keep_alive_query_qual=None, #For extron modules. Ex: {'ID': '1'}
                 poll_freq=5,  # how many seconds between polls
                 disconnect_limit=5,  # how many missed queries before a 'Disconnected' event is triggered
                 timeout=5 * 60,
                 # After this many seconds, a client who has not sent any data to the server will be disconnected.
                 connection_retry_freq=5,  # how many seconds after a Disconnect event to try to do Connect
                 ):
        '''
        This method will maintain the connection to the interface.
        :param interface: extronlib.interface or extron GS module with .SubscribeStatus('ConnectionStatus')
        :param keep_alive_query: string like 'q' for extron FW query, or string like 'Power' will send interface.Update('Power')
        :param poll_freq: float - how many seconds between polls
        :param disconnect_limit: int - how many missed queries before a 'Disconnected' event is triggered
        :param timeout: int - After this many seconds, a client who has not sent any data to the server will be disconnected.
        :param connection_retry_freq: int - how many seconds after a Disconnect event to try to do Connect
        :return:
        '''
        if debugUCH: print(
            'maintain()\ninterface={}\nkeep_alive_query_cmd="{}"\nkeep_alive_query_qual={}\npoll_freq={}\ndisconnect_limit={}\ntimeout={}\nconnection_retry_freq={}'.format(
                interface, keep_alive_query_cmd, keep_alive_query_qual, poll_freq, disconnect_limit,
                timeout, connection_retry_freq))

        self._connection_timeouts[interface] = timeout
        self._connection_retry_freqs[interface] = connection_retry_freq
        self._disconnect_limits[interface] = disconnect_limit
        self._keep_alive_query_cmds[interface] = keep_alive_query_cmd
        self._keep_alive_query_quals[interface] = keep_alive_query_qual
        self._poll_freqs[interface] = poll_freq
        self._interfaces.append(interface)

        if isinstance(interface, extronlib.interface.EthernetClientInterface):
            self._maintain_serial_or_ethernetclient(interface)

        elif isinstance(interface, extronlib.interface.SerialInterface):
            self._maintain_serial_or_ethernetclient(interface)

        elif isinstance(interface, extronlib.interface.EthernetServerInterfaceEx):
            if interface.Protocol == 'TCP':
                self._maintain_serverEx_TCP(interface)
            else:
                raise Exception(
                    'This UniversalConnectionHandler class does not support EthernetServerInterfaceEx with Protocol="UDP".\nConsider using EthernetServerInterface with Protocol="UDP" (non-EX).')

        elif isinstance(interface, extronlib.interface.EthernetServerInterface):

            if interface.Protocol == 'TCP':
                raise Exception(
                    'This ConnectionHandler class does not support EthernetServerInterface with Protocol="TCP".\nConsider using EthernetServerInterfaceEx with Protocol="TCP".')
            elif interface.Protocol == 'UDP':
                # The extronlib.interface.EthernetServerInterfacee with Protocol="UDP" actually works pretty good by itself. No need to do anything special :-)
                while True:
                    result = interface.StartListen()
                    if debugUCH: print(result)
                    if result == 'Listening':
                        break
                    else:
                        time.sleep(1)

        else:  # Assuming a extronlib.device class
            if hasattr(interface, 'Online'):
                #print('interface={}'.format(interface))
                newHandler = self._get_controlscript_connection_callback(interface)
                #print('interface=', interface)
                #print('newHandler=', newHandler)
                interface.Online = newHandler
            if hasattr(interface, 'Offline'):
                interface.Offline = self._get_controlscript_connection_callback(interface)

    def _maintain_serverEx_TCP(self, parent):
        if debugUCH:print('_maintain_serverEx_TCP parent.Connected=', parent.Connected)
        if debugUCH:print('_maintain_serverEx_TCP parent.Disconnected=', parent.Disconnected)

        # save old handlers
        if parent not in self._user_connected_handlers:
            self._user_connected_handlers[parent] = parent.Connected

        if parent not in self._user_disconnected_handlers:
            self._user_disconnected_handlers[parent] = parent.Disconnected

        if debugUCH:print('_maintain_serverEx_TCP self._user_connected_handlers=', self._user_connected_handlers)
        if debugUCH:print('_maintain_serverEx_TCP self._user_disconnected_handlers=', self._user_disconnected_handlers)

        # Create new handlers
        parent.Connected = self._get_serverEx_connection_callback(parent)
        parent.Disconnected = self._get_serverEx_connection_callback(parent)

        def get_disconnect_undead_clients_func(parent):
            def do_disconnect_undead_clients():
                self._disconnect_undead_clients(parent)

            return do_disconnect_undead_clients

        new_timer = Timer(self._connection_timeouts[parent], get_disconnect_undead_clients_func(parent))
        new_timer.Stop()

        self._timers[parent] = new_timer

        self._server_start_listening(parent)

    def _server_start_listening(self, parent):
        '''
        This method will try to StartListen on the server. If it fails, it will retry every X seconds
        :param interface: extronlib.interface.EthernetServerInterfaceEx or EthernetServerInterface
        :return:
        '''
        if parent not in self._server_listen_status:
            self._server_listen_status[parent] = 'Unknown'

        if self._server_listen_status[parent] is not 'Listening':
            try:
                result = parent.StartListen()
            except Exception as e:
                result = 'Failed to StartListen: {}'.format(e)
                if debugUCH: print('StartListen on port {} failed\n{}'.format(parent.IPPort, e))

            if debugUCH: print('StartListen result=', result)

            self._server_listen_status[parent] = result

        if self._server_listen_status[parent] is not 'Listening':
            # We tried to start listen but it failed.
            # Try again in X seconds
            def retry_start_listen():
                self._server_start_listening(parent)

            Wait(self._connection_retry_freqs[parent], retry_start_listen)

        elif self._server_listen_status[parent] is 'Listening':
            # We have successfully started the server listening
            pass

    def _maintain_serial_or_ethernetclient(self, interface):

        # Add polling
        if self._keep_alive_query_cmds[interface] is not None:
            # For example
            if hasattr(interface, 'Update{}'.format(self._keep_alive_query_cmds[interface])):

                # Delete any old polling engine timers
                if interface in self._timers:
                    self._timers[interface].Stop()
                    self._timers.pop(interface)

                # Create a new polling engine timer
                def do_poll():
                    if debugUCH: print('do_poll interface.Update("{}", {})'.format(self._keep_alive_query_cmds[interface],
                                                                      self._keep_alive_query_quals[interface]))
                    interface.Update(self._keep_alive_query_cmds[interface], self._keep_alive_query_quals[interface])

                new_timer = Timer(self._poll_freqs[interface], do_poll)
                new_timer.Stop()
                self._timers[interface] = new_timer

            else:  # assume keep_alive_query is a string like 'q' for querying extron fw

                # Delete any old polling engine timers
                if interface in self._timers:
                    self._timers[interface].Stop()
                    self._timers.pop(interface)

                # Create a new polling engine timer
                def do_poll():
                    if debugUCH: print('do_poll interface.Send({})'.format(self._keep_alive_query_cmds[interface]))
                    interface.Send(self._keep_alive_query_cmds[interface])

                new_timer = Timer(self._poll_freqs[interface], do_poll)
                self._timers[interface] = new_timer

        # Register ControlScript connection handlers
        self._assign_new_connection_handlers(interface)

        # Register module connection callback
        if hasattr(interface, 'SubscribeStatus'):
            interface.SubscribeStatus('ConnectionStatus', None, self._get_module_connection_callback(interface))
            if isinstance(interface, extronlib.interface.SerialInterface):
                self._update_connection_status_serial_or_ethernetclient(interface, 'Connected',
                                                                        'ControlScript')  # SerialInterface ports are always 'Connected' in ControlScript
        else:
            # This interface is not an Extron module. We must create our own logical connection handling
            if isinstance(interface, extronlib.interface.EthernetClientInterface) or isinstance(interface,
                                                                                                extronlib.interface.SerialInterface):
                self._add_logical_connection_handling_client(interface)
            elif isinstance(interface, extronlib.interface.EthernetServerInterfaceEx):
                self._add_logical_connection_handling_serverEx(interface)

        # At this point all connection handlers and polling engines have been set up.
        # We can now start the connection
        if hasattr(interface, 'Connect'):
            if interface.Protocol == 'TCP':
                interface.Connect(self._connection_timeouts[interface])
                # The update_connection_status method will maintain the connection from here on out.

    def _add_logical_connection_handling_client(self, interface):
        if debugUCH: print('_add_logical_connection_handling_client')

        # Initialize the send counter to 0
        if interface not in self._send_counters:
            self._send_counters[interface] = 0

        self._check_connection_handlers(interface)
        self._check_send_methods(interface)
        self._check_rx_handler_serial_or_ethernetclient(interface)

        if isinstance(interface, extronlib.interface.SerialInterface):
            # SerialInterfaces are always connected via ControlScript.
            self._update_connection_status_serial_or_ethernetclient(interface, 'Connected', 'ControlScript')

    def _check_connection_handlers(self, interface):
        if debugUCH: print('UCH._check_connection_handlers')
        # if the user made their own connection handler, make sure our connection handler is called first
        if interface not in self._connected_handlers:
            self._connected_handlers[interface] = None

        if (interface.Connected != self._connected_handlers[interface] or
                    interface.Disconnected != self._disconnected_handlers[interface]):
            self._assign_new_connection_handlers(interface)

    def _assign_new_connection_handlers(self, interface):
        if debugUCH: print('UCH._assign_new_connection_handlers')
        if interface not in self._connected_handlers:
            self._connected_handlers[interface] = None

        connection_handler = self._get_controlscript_connection_callback(
            interface)  # This line also saves the current user handlers

        self._connected_handlers[interface] = connection_handler
        self._disconnected_handlers[interface] = connection_handler

        interface.Connected = connection_handler
        interface.Disconnected = connection_handler

    def _check_send_methods(self, interface):
        '''
        This method will check the .Send and .SendAndWait methods to see if they have already been replaced with the
            appropriate new_send that will also increment the self._send_counter
        :param interface:
        :return:
        '''

        self._check_connection_handlers(interface)

        if interface not in self._send_methods:
            self._send_methods[interface] = None

        if interface not in self._send_and_wait_methods:
            self._send_and_wait_methods[interface] = None

        current_send_method = interface.Send
        if current_send_method != self._send_methods[interface]:

            # Create a new .Send method that will increment the counter each time
            def new_send(*args, **kwargs):
                if debugUCH: print('new_send args={}, kwargs={}'.format(args, kwargs))
                self._check_rx_handler_serial_or_ethernetclient(interface)
                self._check_connection_handlers(interface)

                currentState = self.get_connection_status(interface)
                if debugUCH: print('currentState=', currentState)
                if currentState is 'Connected':
                    # We dont need to increment the send counter if we know we are disconnected
                    self._send_counters[interface] += 1
                if debugUCH: print('new_send send_counter=', self._send_counters[interface])

                # Check if we have exceeded the disconnect limit
                if self._send_counters[interface] > self._disconnect_limits[interface]:
                    self._update_connection_status_serial_or_ethernetclient(interface, 'Disconnected', 'Logical')

                current_send_method(*args, **kwargs)

            interface.Send = new_send

        current_send_and_wait_method = interface.SendAndWait
        if current_send_and_wait_method != self._send_and_wait_methods[interface]:
            # Create new .SendAndWait that will increment the counter each time
            def new_send_and_wait(*args, **kwargs):
                if debugUCH: print('new_send_and_wait args={}, kwargs={}'.format(args, kwargs))
                self._check_rx_handler_serial_or_ethernetclient(interface)
                self._check_connection_handlers(interface)

                self._send_counters[interface] += 1
                if debugUCH: print('new_send_and_wait send_counter=', self._send_counters[interface])

                # Check if we have exceeded the disconnect limit
                if self._send_counters[interface] > self._disconnect_limits[interface]:
                    self._update_connection_status_serial_or_ethernetclient(interface, 'Disconnected', 'Logical')

                return current_send_and_wait_method(*args, **kwargs)

            interface.SendAndWait = new_send_and_wait

    def _check_rx_handler_serial_or_ethernetclient(self, interface):
        '''
        This method will check to see if the rx handler is resetting the send counter to 0. if not it will create a new rx handler and assign it to the interface
        :param interface:
        :return:
        '''
        if debugUCH: print('_check_rx_handler')

        if interface not in self._rx_handlers:
            self._rx_handlers[interface] = None

        current_rx = interface.ReceiveData
        if current_rx != self._rx_handlers[interface] or current_rx == None:
            # The Rx handler got overwritten somehow, make a new Rx and assign it to the interface and save it in self._rx_handlers
            def new_rx(*args, **kwargs):
                if debugUCH: print('new_rx args={}, kwargs={}'.format(args, kwargs))
                self._send_counters[interface] = 0

                if isinstance(interface, extronlib.interface.EthernetClientInterface):
                    if interface.Protocol == 'UDP':
                        self._update_connection_status_serial_or_ethernetclient(interface, 'Connected', 'Logical')

                elif isinstance(interface, extronlib.interface.SerialInterface):
                    self._update_connection_status_serial_or_ethernetclient(interface, 'Connected', 'Logical')

                if callable(current_rx):
                    current_rx(*args, **kwargs)

            self._rx_handlers[interface] = new_rx
            interface.ReceiveData = new_rx
        else:
            # The current rx handler is doing its job. Moving on!
            pass

    def _add_logical_connection_handling_serverEx(self, interface):
        pass

    def _get_module_connection_callback(self, interface):
        # generate a new function that includes the interface and the 'kind' of connection
        def module_connection_callback(command, value, qualifier):
            if debugUCH: print('module_connection_callback(command={}, value={}, qualifier={}'.format(command, value, qualifier))
            self._update_connection_status_serial_or_ethernetclient(interface, value, 'Module')

        return module_connection_callback

    def _get_controlscript_connection_callback(self, interface):
        # generate a new function that includes the 'kind' of connection

        # init some values
        if interface not in self._connected_handlers:
            self._connected_handlers[interface] = None

        if interface not in self._disconnected_handlers:
            self._disconnected_handlers[interface] = None

        if interface not in self._user_connected_handlers:
            self._user_connected_handlers[interface] = None

        if interface not in self._user_disconnected_handlers:
            self._user_disconnected_handlers[interface] = None

        # Get handler

        # save user Connected handler
        if isinstance(interface, extronlib.device.UIDevice) or isinstance(interface, extronlib.device.ProcessorDevice):
            callback = getattr(interface, 'Online')
        else:
            callback = getattr(interface, 'Connected')

        if callback != self._connected_handlers[interface]:
            # The connection handler was prob overridden in main.py. Reassign it
            self._user_connected_handlers[interface] = callback
        else:
            self._user_connected_handlers[interface] = None

        # save user Disconnected handler
        if isinstance(interface, extronlib.device.UIDevice) or isinstance(interface, extronlib.device.ProcessorDevice):
            callback = getattr(interface, 'Offline')
        else:
            callback = getattr(interface, 'Disconnected')

        if callback != self._disconnected_handlers[interface]:
            # The connection handler was prob overridden in main.py. Reassign it
            self._user_disconnected_handlers[interface] = callback
        else:
            self._user_disconnected_handlers[interface] = None

        # Create the new handler
        if (isinstance(interface, extronlib.device.ProcessorDevice) or
                isinstance(interface, extronlib.device.UIDevice)):

            def controlscript_connection_callback(intf, state):
                # Call the UCH connection handler if applicable
                if callable(self._connected_callback):
                    self._connected_callback(intf, state)

                # Call the main.py Connection handler if applicable
                if state in ['Connected', 'Online']:
                    if callable(self._user_connected_handlers[intf]):
                        self._user_connected_handlers[intf](intf, state)

                elif state in ['Disconnected', 'Offline']:
                    if callable(self._user_disconnected_handlers[intf]):
                        self._user_disconnected_handlers[intf](intf, state)

                self._log_connection_to_file(intf, state, kind='ControlScript')


        elif (isinstance(interface, extronlib.interface.SerialInterface) or
                  isinstance(interface, extronlib.interface.EthernetClientInterface)):

            def controlscript_connection_callback(intf, state):

                # Call the main.py Connection handler if applicable
                if state in ['Connected', 'Online']:
                    if callable(self._user_connected_handlers[intf]):
                        self._user_connected_handlers[intf](intf, state)

                elif state in ['Disconnected', 'Offline']:
                    if callable(self._user_disconnected_handlers[intf]):
                        self._user_disconnected_handlers[intf](intf, state)

                self._update_connection_status_serial_or_ethernetclient(intf, state, 'ControlScript')

        return controlscript_connection_callback

    def block(self, interface):
        # this will stop this interface from communicating
        if isinstance(interface, extronlib.interface.SerialInterface):
            interface.ReceiveData = None

        elif isinstance(interface, extronlib.interface.EthernetClientInterface):
            interface.ReceiveData = None
            interface.Connected = None
            interface.Disconnected = None

            if interface.Protocol == 'TCP':
                interface.Disconnect()

        elif isinstance(interface, extronlib.interface.EthernetServerInterface):
            interface.ReceiveData = None
            interface.Connected = None
            interface.Disconnected = None

            if interface.Protocol == 'TCP':
                interface.Disconnect()

            interface.StopListen()

        elif isinstance(interface, extronlib.interface.EthernetServerInterfaceEx):
            interface.ReceiveData = None
            interface.Connected = None
            interface.Disconnected = None

            if interface.Protocol == 'TCP':
                for client in interface.Clients:
                    client.Disconnect()

            interface.StopListen()

        elif isinstance(interface, extronlib.device.UIDevice) or isinstance(interface,
                                                                            extronlib.device.ProcessorDevice):
            interface.Online = None
            interface.Offline = None

        self._interfaces.remove(interface)

    def get_connection_status(self, interface):
        # return 'Connected' or 'Disconnected'
        # Returns None if this interface is not being handled by this UCH
        return self._connection_status.get(interface, None)

    def _get_serverEx_connection_callback(self, parent):
        def controlscript_connection_callback(client, state):
            print('controlscript_connection_callback(client={}, state={})'.format(client, state))
            print('self._user_connected_handlers=', self._user_connected_handlers)
            print('self._user_disconnected_handlers=', self._user_disconnected_handlers)

            if state == 'Connected':
                if parent in self._user_connected_handlers:
                    if callable(self._user_connected_handlers[parent]):
                        self._user_connected_handlers[parent](client, state)

            elif state == 'Disconnected':
                if parent in self._user_disconnected_handlers:
                    if callable(self._user_disconnected_handlers[parent]):
                        self._user_disconnected_handlers[parent](client, state)

            self._update_connection_status_server(parent, client, state, 'ControlScript')

        return controlscript_connection_callback

    def _update_connection_status_server(self, parent, client, state, kind=None):
        '''
        This method will save the connection status and trigger any events that may be associated
        :param parent: EthernetServerInterfaceEx object
        :param client: ClientObject
        :param state: 'Connected' or 'Disconnected'
        :param kind: 'ControlScript' or 'Logical'
        :return:
        '''

        if state == 'Connected':
            client.Parent = parent  # Add this attribute to the client object for later reference

            if parent not in self._server_client_rx_timestamps:
                self._server_client_rx_timestamps[parent] = {}

            self._server_client_rx_timestamps[parent][
                client] = time.monotonic()  # init the value to the time the connection started
            self._check_rx_handler_serverEx(client)

            if callable(self._connected_callback):
                self._connected_callback(client, state)

        elif state == 'Disconnected':
            self._remove_client_data(client)  # remove dead sockets to prevent memory leak

            if callable(self._disconnected_callback):
                self._disconnected_callback(client, state)

        self._update_serverEx_timer(parent)

        self._log_connection_to_file(client, state, kind)

    def _check_rx_handler_serverEx(self, client):
        '''
        Every time data is recieved from the client, set the timestamp
        :param client:
        :return:
        '''
        parent = client.Parent

        if parent not in self._rx_handlers:
            self._rx_handlers[parent] = None

        old_rx = parent.ReceiveData
        if self._rx_handlers[parent] != old_rx or (old_rx == None):
            # we need to override the rx handler with a new handler that will also add the timestamp
            def new_rx(client, data):
                time_now = time.monotonic()
                if debugUCH: print('new_rx\ntime_now={}\nclient={}'.format(time_now, client))
                self._server_client_rx_timestamps[parent][client] = time_now
                self._update_serverEx_timer(parent)
                if callable(old_rx):
                    old_rx(client, data)

            parent.ReceiveData = new_rx
            self._rx_handlers[parent] = new_rx

    def _update_serverEx_timer(self, parent):
        '''
        This method will check all the time stamps and set the timer so that it will check again when the oldest client
            is near the X minute timeout mark.
        :param parent:
        :return:
        '''
        if len(parent.Clients) > 0:
            oldest_timestamp = None
            for client in parent.Clients:
                if client not in self._server_client_rx_timestamps[parent]:
                    self._server_client_rx_timestamps[parent][client] = time.monotonic()

                client_timestamp = self._server_client_rx_timestamps[parent][client]

                if (oldest_timestamp is None) or client_timestamp < oldest_timestamp:
                    oldest_timestamp = client_timestamp

                if debugUCH: print('client={}\nclient_timestamp={}\noldest_timestamp={}'.format(client, client_timestamp,
                                                                                   oldest_timestamp))

            # We now have the oldest timestamp, thus we know when we should check the client again
            seconds_until_timer_check = self._connection_timeouts[parent] - (time.monotonic() - oldest_timestamp)
            self._timers[parent].ChangeTime(seconds_until_timer_check)
            self._timers[parent].Start()

            # Lets say the parent timeout is 5 minutes.
            # If the oldest connected client has not communicated for 4min 55sec, then seconds_until_timer_check = 5 seconds
            # The timer will check the clients again in 5 seconds.
            # Assuming the oldest client still has no communication, it will be disconnected at the 5 minute mark exactly

        else:  # there are no clients connected
            self._timers[parent].Stop()

    def _disconnect_undead_clients(self, parent):
        for client in parent.Clients:
            client_timestamp = self._server_client_rx_timestamps[parent][client]
            if time.monotonic() - client_timestamp > self._connection_timeouts[parent]:
                if client in parent.Clients:
                    client.Send('Disconnecting due to inactivity for {} seconds.\r\nBye.\r\n'.format(
                        self._connection_timeouts[parent]))
                    client.Disconnect()
                self._remove_client_data(client)

    def _remove_client_data(self, client):
        # remove dead sockets to prevent memory leak
        self._server_client_rx_timestamps.pop(client, None)

    def _log_connection_to_file(self, interface, state, kind):
        # Write new status to a file
        with File(self._filename, mode='at') as file:
            write_str = '{}\n    {}:{}\n'.format(time.asctime(), 'type', type(interface))

            for att in [
                'IPAddress',
                'IPPort',
                'DeviceAlias',
                'Port',
                'Host',
                'ServicePort',
                'Protocol',
            ]:
                if hasattr(interface, att):
                    write_str += '    {}:{}\n'.format(att, getattr(interface, att))

                    if att == 'Host':
                        write_str += '    {}:{}\n'.format('Host.DeviceAlias', getattr(interface, att).DeviceAlias)

            write_str += '    {}:{}\n'.format('ConnectionStatus', state)
            write_str += '    {}:{}\n'.format('Kind', kind)

            file.write(write_str)
            file.close()

    def _update_connection_status_serial_or_ethernetclient(self, interface, state, kind=None):
        '''
        This method will save the connection status and trigger any events that may be associated
        :param interface:
        :param state: str
        :param kind: str() 'ControlScript' or 'Module' or any other value that may be applicable
        :return:
        '''
        if debugUCH: print('_update_connection_status\ninterface={}\nstate={}\nkind={}'.format(interface, state, kind))
        if interface not in self._connection_status:
            self._connection_status[interface] = 'Unknown'

        if state in ['Connected', 'Online']:
            self._send_counters[interface] = 0

        if state != self._connection_status[interface]:
            # The state has changed. Do something with that change

            if debugUCH: print('Connection status has changed for interface={} from "{}" to "{}"'.format(interface,
                                                                                            self._connection_status[
                                                                                                interface], state))
            if callable(self._connected_callback):
                self._connected_callback(interface, state)

            self._log_connection_to_file(interface, state, kind)

            # Do the user's callback function
            if state in ['Connected', 'Online']:
                if interface in self._user_connected_handlers:
                    if callable(self._user_connected_handlers[interface]):
                        self._user_connected_handlers[interface](interface, state)
            elif state in ['Disconnected', 'Offline']:
                if interface in self._user_disconnected_handlers:
                    if callable(self._user_disconnected_handlers[interface]):
                        self._user_disconnected_handlers[interface](interface, state)

        # save the state for later
        self._connection_status[interface] = state

        # if the interface is disconnected, try to reconnect
        if state == 'Disconnected':
            self._send_counters[interface] = 0

            if debugUCH: print('Trying to Re-connect to interface={}'.format(interface))
            if hasattr(interface, 'Connect'):
                if interface.Protocol == 'TCP':
                    Wait(self._connection_retry_freqs[interface], interface.Connect)

        # Start/Stop the polling timer if it exists
        if interface in self._timers:
            if state in ['Connected', 'Online']:
                self._timers[interface].Start()

            elif state in ['Disconnected', 'Offline']:
                if isinstance(interface, extronlib.interface.SerialInterface):
                    # SerialInterface has no Disconnect() method so the polling engine is the only thing that can detect a re-connect.
                    # Keep the timer going.
                    pass
                elif isinstance(interface, extronlib.interface.EthernetClientInterface):
                    if interface.Protocol == 'UDP':
                        # UDP EthernetClientInterface has no Disconnect() method so the polling engine is the only thing that can detect a re-connect.
                        # Keep the timer going.
                        pass
                    elif interface.Protocol == 'TCP':
                        self._timers[interface].Stop()
                        # Stop the timer and wait for a 'Connected' Event

    def __str__(self):
        s = '''{}\n\n***** Interfaces being handled *****\n\n'''.format(self)

        for interface in self._interfaces:
            s += self._interface_to_str(interface)

    def __repr__(self):
        return str(self)

    def _interface_to_str(self, interface):
        write_str = '{}\n'.format(self)

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
            write_str += '    {}:{}'.format('Connection Status', self._connection_status[interface])

        return write_str

    @property
    def Connected(self):
        '''
        There will be a single callback that will pass two params, the interface and the state
        :return:
        '''
        return self._connected_callback

    @Connected.setter
    def Connected(self, callback):
        self._connected_callback = callback

    @property
    def Disconnected(self):
        '''
        There will be a single callback that will pass two params, the interface and the state
        :return:
        '''
        return self._disconnected_callback

    @Disconnected.setter
    def Disconnected(self, callback):
        self._disconnected_callback = callback

class DirectoryNavigationClass:
    def __init__(self,
             lblCurrentDirectory=None,
             btnScrollUp=None,
             btnScrollDown=None,
             lvlScrollFeedback=None,
             lblScrollText=None,
             btnNavUp=None,
             limitStringLen=25,
             lblMessage=None,
            ):

        self._lblMessage = lblMessage
        self._limitStringLen = limitStringLen
        self._btnNavUp = btnNavUp
        self._lblCurrentDirectory = lblCurrentDirectory

        self._table = ScrollingTable()
        self._table.set_table_header_order(['entry', 'folderIcon'])
        if btnScrollUp is not None:
            self._table.register_scroll_up_button(btnScrollUp)
            btnScrollUp._repeatTime = 0.1
            btnScrollUp._holdTime = 0.2
            @event(btnScrollUp, ['Pressed', 'Repeated'])
            def btnScrollUpEvent(button, state):
                print('btnScrollUpEvent', state)
                self._table.scroll_up()

        if btnScrollDown is not None:
            self._table.register_scroll_down_button(btnScrollDown)
            btnScrollDown._repeatTime = 0.1
            btnScrollDown._holdTime = 0.2
            @event(btnScrollDown, ['Pressed', 'Repeated'])
            def btnScrollDownEvent(button, state):
                self._table.scroll_down()

        if btnNavUp is not None:
            @event(btnNavUp, 'Released')
            def btnNavUpEvent(button, state):
                self.NavigateUp()

        if lvlScrollFeedback is not None:
            self._table.register_scroll_updown_level(lvlScrollFeedback)

        if lblScrollText is not None:
            self._table.register_scroll_updown_label(lblScrollText)

        self._data = {
            #[
            #'/rootfile1',
            #'/rootfile2',
            #'/rootFolder3/file3a',
            #'/rootFolder3/file3b',
            #'/rootFolder3/folder3c/file3c1',
            #'/rootFolder3/folder3c/file3c2',
            #]
        }
        self._currentDirectory = '/'

        self._waitUpdateTable = Wait(0.1, self._UpdateTable)
        self._waitUpdateTable.Cancel()

        self._table.CellTapped = self._CellTapped
        self._fileSelectedCallback = None

        self._table.CellHeld = self._CellHeld
        self._fileHeldCallback = None

        self._allowChangeDirectory = True
        self._allowMakeNewFile = True
        self._allowMakeNewFolder = True
        self._showCurrentDirectory = True
        self._allowDelete = True

        self._directoryLock = '/' #dont allow the user to go higher than this dir
        self._showFiles = True

    def SetShowFiles(self, state):
        self._showFiles = state
        self._UpdateTable()

    def SetCurrentDirTextLen(self, length):
        length = int(length)
        self._limitStringLen = length

    def SetDirectoryLock(self, dir):
        self._directoryLock = dir
        self.SetCurrentDirectory(dir)

    def SetCurrentDirectory(self, dir):
        self._currentDirectory = dir
        self._UpdateTable()

    def RegisterRow(self, rowNumber, btnIcon, btnSelection):
        if btnIcon._holdTime is None:
            btnIcon._holdTime = 1
        self._table.register_row_buttons(rowNumber, btnSelection, btnIcon)

    def NavigateUp(self):
        if self._currentDirectory != '/':
            dropDir = self._currentDirectory.split('/')[-2] + '/'
            self._currentDirectory = self._currentDirectory.replace(dropDir, '')
            self._waitUpdateTable.Restart()

    def UpdateData(self, newData=None):
        print('UpdateData(newData={})'.format(newData))
        if newData == None:
            newData = File.ListDirWithSub()
        self._data = newData
        self._UpdateTable()

    def _CurrentDirIsValid(self):
        if not self._currentDirectory.endswith('/'):
            return False

        for item in self._data:
            if self._currentDirectory in item:
                return True

        return False

    def _UpdateTable(self):
        print('DirectoryNavigationClass._UpdateTable()')
        try:
            #Verify the self._currentDirectory is valid
            print('_UpdateTable self._currentDirectory=', self._currentDirectory)
            print('_UpdateTable self._directoryLock=', self._directoryLock)
            if self._directoryLock not in self._currentDirectory:
                self._currentDirectory = self._directoryLock

            if not self._CurrentDirIsValid():
                self._currentDirectory = self._directoryLock

            print('_UpdateTable self._allowChangeDirectory=', self._allowChangeDirectory)
            print('_UpdateTable self._btnNavUp.Visible=', self._btnNavUp.Visible)
            print('_UpdateTable self._btnNavUp=', self._btnNavUp)

            if self._allowChangeDirectory is True:
                if self._currentDirectory == self._directoryLock:
                    if self._btnNavUp.Visible is True:
                        print('self._btnNavUp.SetVisible(False)')
                        self._btnNavUp.SetVisible(False)
                else:
                    if self._btnNavUp.Visible is False:
                        print('self._btnNavUp.SetVisible(True)')
                        self._btnNavUp.SetVisible(True)
            else:
                if self._btnNavUp.Visible is True:
                    print('else self._btnNavUp.SetVisible(False)')
                    self._btnNavUp.SetVisible(False)

            print('_UpdateTable self._lblCurrentDirectory=', self._lblCurrentDirectory)
            print('_UpdateTable self._showCurrentDirectory=', self._showCurrentDirectory)
            if self._showCurrentDirectory is True:
                if self._lblCurrentDirectory.Visible is False:
                    print('self._lblCurrentDirectory.SetVisible(True)')
                    self._lblCurrentDirectory.SetVisible(True)
            else:
                if self._lblCurrentDirectory.Visible is True:
                    print('self._lblCurrentDirectory.SetVisible(False)')
                    self._lblCurrentDirectory.SetVisible(False)

            #Update the table with data
            self._table.freeze(True)

            print('_UpdateTable self._data=', self._data)
            if self._data is not None:
                #Add missing data
                currentData = []
                for item in self._data:
                    print('item=', item)
                    #Determine if the item is a folder or file
                    if item.startswith(self._currentDirectory): #only deal with items in the current directory
                        print('item.startswith(self._currentDirectory)')
                        if self.IsInCurrentDirectory(item):
                            print('self.IsInCurrentDirectory(item)')
                            itemMinusCurrent = item[len(self._currentDirectory):]
                            if itemMinusCurrent is not '':
                                print('itemMinusCurrent is not ""')

                                if self.IsFile(item):
                                    folderIcon = ' '
                                    if not self._showFiles:
                                        continue

                                elif self.IsDirectory(item):
                                    folderIcon = '\xb1'
                                    itemMinusCurrent = itemMinusCurrent[:-1] #chop off the extra '/' at the end of directories

                                else:
                                    folderIcon = '?'

                                data = {'entry': str(itemMinusCurrent), 'folderIcon': folderIcon,}
                                if not self._table.has_row(data):
                                    self._table.add_new_row_data(data)
                                currentData.append(data)

                #remove leftover data
                print('_UpdateTable currentData=', currentData)
                print('_UpdateTable self._table.get_row_data()', self._table.get_row_data())
                for row in self._table.get_row_data():
                    if row not in currentData:
                        self._table.delete_row(row)

                #Sort with the folders at the top
                self._table.sort_by_column_list([1,0], reverse=True)

                self._table.freeze(False)


            #Update the current directory label
            if self._lblCurrentDirectory is not None:
                if self._data is not None:
                    self._lblCurrentDirectory.SetText(self._currentDirectory, limitLen=self._limitStringLen, elipses=True, justify='Right')
                else:
                    self._lblCurrentDirectory.SetText('<No Data>')

        except Exception as e:
            print('Exeption DirectoryNavigationClass._UpdateTable\n', e)
            print('item=', item)

    def IsFile(self, filepath):
        print('IsFile(filepath={})'.format(filepath))
        name = filepath.split('/')[-1]
        if name == '':
            print('IsFile return False')
            return False

        for item in self._data:
            if name in item:
                if name == item.split('/')[-1]:
                    print('IsFile return True')
                    return True

        print('IsFile return False')
        return False

    def IsDirectory(self, path):
        print('IsDirectory(path={})'.format(path))
        #path may end in '/' or may not
        #examples path='TEST1026', path='TEST1026/', path='image.png'(return False)
        for item in self._data:
            if item.endswith('/'):
                #item is a directory
                if item.endswith(path):
                    print('IsDirectory return True')
                    return True
                else:
                    name = path.split('/')[-1]
                    if name == item.split('/')[-2]:
                        #'/Farm_Network_Profiles/TEST1026/'.split('/') = ['', 'Farm_Network_Profiles', 'TEST1026', '']
                        print('IsDirectory return True')
                        return True

        print('IsDirectory return False')
        return False

    def IsInCurrentDirectory(self, filepath):
        #Return true if the item is in the current directory
        #Return false if it is in a super/sub directory
        print('IsInCurrentDirectory filepath=', filepath)

        if filepath.startswith(self._currentDirectory):
            pathMinusCurrent = filepath[len(self._currentDirectory):]
            print('IsInCurrentDirectory pathMinusCurrent=', pathMinusCurrent)
            print('self.IsDirectory({})='.format(filepath), self.IsDirectory(filepath))
            print('self.IsFile({})='.format(filepath), self.IsFile(filepath))

            if self.IsDirectory(filepath):
                print('IsInCurrentDirectory IsDirectory')
                print("len(pathMinusCurrent.split('/'))=", len(pathMinusCurrent.split('/')))
                if len(pathMinusCurrent.split('/')) <= 2:
                    return True
                else:
                    return False
            elif self.IsFile(filepath):
                print('IsInCurrentDirectory IsFile')
                print("len(pathMinusCurrent.split('/'))=", len(pathMinusCurrent.split('/')))
                if len(pathMinusCurrent.split('/')) == 1:
                    return True
                else:
                    return False

        return False

    def GetType(self, name):
        if self.IsFile(name):
            return 'File'
        elif self.IsDirectory(name):
            return 'Directory'

    def ChangeDirectory(self, newDir):
        if not newDir.endswith('/'):
            newDir += '/'

        self._currentDirectory = newDir

    def _CellTapped(self, table, cell):
        print('DirectoryNavigationClass._CellTapped(table={}, cell={})\nself._fileSelectedCallback={}'.format(table, cell, self._fileSelectedCallback))
        row = cell.get_row()
        value = self._table.get_cell_value(row, 0)
        path = self._currentDirectory + value
        if value == '':
            return

        print('value=', value)
        print('path=', path)
        if self.IsDirectory(path):
            self.ChangeDirectory(path + '/')
            self._waitUpdateTable.Restart()

        elif self.IsFile(path):
            if callable(self._fileSelectedCallback):
                self._fileSelectedCallback(self, self._currentDirectory + value)

    def _CellHeld(self, table, cell):
        #This is used for providing the user with more options like: Deleting a file/folder, Creating a new file/folder...
        print('DirectoryNavigationClass._CellHeld(table={}, cell={})\nself._fileHeldCallback={}'.format(table, cell, self._fileHeldCallback))
        value = cell.get_value()
        path = self._currentDirectory + value
        #path might be a filepath or directory
        if callable(self._fileHeldCallback):
            self._fileHeldCallback(self, path)

    def GetDir(self):
        return self._currentDirectory

    @property
    def FileSelected(self):
        return self._fileSelectedCallback

    @FileSelected.setter
    def FileSelected(self, func):
        #func should be a function that accetps this dir nav object itself and the selected value
        self._fileSelectedCallback = func

    @property
    def FileHeld(self):
        return self._fileHeldCallback

    @FileHeld.setter
    def FileHeld(self, func):
        #func should be a function that accetps this dir nav object itself and the selected value
         self._fileHeldCallback = func

    def UpdateMessage(self, msg):
        if self._lblMessage is not None:
            self._lblMessage.SetText(msg)


    def AllowChangeDirectory(self, state):
        self._allowChangeDirectory = state
        self._UpdateTable()

    def GetAllowChangeDirectory(self):
        return self._allowChangeDirectory

    def AllowMakeNewFile(self, state=None):
        if state == None:
            return self._allowMakeNewFile
        else:
            self._allowMakeNewFile = state
            self._UpdateTable()

    def AllowMakeNewFolder(self, state=None):
        if state == None:
            return self._allowMakeNewFolder
        else:
            self._allowMakeNewFolder = state
            self._UpdateTable()

    def AllowDelete(self, state=None):
        if state == None:
            return self._allowDelete
        else:
            self._allowDelete = state
            self._UpdateTable()

    def ShowCurrentDirectory(self, state=None):
        if state == None:
            return self._showCurrentDirectory
        else:
            self._showCurrentDirectory = state
            self._UpdateTable()


def SortListDictByKey(aList, sortKey, reverse=False):
    '''
    aList = list of dicts
    sortKeys = list key from dict. the dicts will be sorted in this order
    reverse =  Used to sort a-z(False) or z-a(True)
    returns a new list with the items(dicts) sorted by key

    Example
    aList = [{'Value', '1'}, {'Value', '3'}, {'Value', '2'}...]
    newList = SortListOfDictsByKey(aList, 'Value')
    print(newList)
    >>[{'Value', '1'}, {'Value', '2'}, {'Value', '3'}...]

    newList = SortListOfDictsByKey(aList, 'Value', 'decending')
    print(newList)
    >>[{'Value', '3'}, {'Value', '2'}, {'Value', '1'}...]

    '''

    if not isinstance(reverse, bool):
        raise Exception('Reverse parameter must be type bool')

    return sorted(aList, key=lambda d: str(d[sortKey]), reverse=reverse)


def SortListOfDictsByKeys(aList, sortKeys=None, reverse=False):
    print('SortListOfDictsByKeys(aList={}, sortKeys={}, reverse={})'.format(aList, sortKeys, reverse))
    '''
    aList = list of dicts
    sortKeys = list of keys to sort by
    reverse = bool to sort a-z(True) or z-a(False)
    returns a new list of dicts

    Example:
    #a list filled with dicts that are not in any particular order
    theList = [
        {'valueB': 1, 'valueC': 2, 'valueA': 1} ,
        {'valueB': 0, 'valueC': 1, 'valueA': 0} ,
        {'valueB': 2, 'valueC': 9, 'valueA': 0} ,
        {'valueB': 2, 'valueC': 1, 'valueA': 2} ,
        {'valueB': 1, 'valueC': 1, 'valueA': 2} ,
        {'valueB': 1, 'valueC': 2, 'valueA': 0} ,
        {'valueB': 0, 'valueC': 2, 'valueA': 2} ,
        {'valueB': 0, 'valueC': 7, 'valueA': 1} ,
        {'valueB': 2, 'valueC': 5, 'valueA': 1} ,
        ]

    newList = SortListOfDictsByKeys(theList, ['valueA', 'valueC'])
    print(newList)
    >>>
    [
        {'valueB': 0, 'valueC': 1, 'valueA': 0} ,
        {'valueB': 1, 'valueC': 2, 'valueA': 0} ,
        {'valueB': 2, 'valueC': 9, 'valueA': 0} ,
        {'valueB': 1, 'valueC': 2, 'valueA': 1} ,
        {'valueB': 2, 'valueC': 5, 'valueA': 1} ,
        {'valueB': 0, 'valueC': 7, 'valueA': 1} ,
        {'valueB': 2, 'valueC': 1, 'valueA': 2} ,
        {'valueB': 1, 'valueC': 1, 'valueA': 2} ,
        {'valueB': 0, 'valueC': 2, 'valueA': 2} ,
    ]

    Notice the dicts are organized by valueA, when valueA is the same, then they are sorted by valueC

    '''
    if len(aList) == 0:
        return aList

    if sortKeys is None:
        sortKeys = []

    missingKeys = []
    for d in aList:
        for key in d:
            if key not in sortKeys and key not in missingKeys:
                missingKeys.append(key)

    sortKeys.extend(missingKeys)

    aList = aList.copy() #dont want to hurt the users data

    newList = []

    #break list into smaller list
    subList = {
        #'sortKey': [{...}], #all the dict that have the sortKey are in now accessible thru subList['sortKey']
        }

    for d in aList:
        for sortKey in sortKeys:
            if sortKey in d:
                if sortKey not in subList:
                    subList[sortKey] = []

                subList[sortKey].append(d)

    #now all the dicts have been split by sortKey, there are prob duplicates

    #we must now sort the sub list
    for sortKey, l in subList.copy().items():
        l = SortListDictByKey(l, sortKey, reverse)
        subList[sortKey] = l

    #now all the sublist are sorted by their respective keys


    def contains(d, subD):
        #print('contains d={}, subD={}'.format(d, subD))
        containsAllKeys = True
        for key in subD:
            if key not in d:
                containsAllKeys = False
                return False

        if containsAllKeys:
            for key in subD:
                if d[key] != subD[key]:
                    return False

        return True

    def getDictWith(l2, subD):
        #l = list of dicts
        #subD = dict
        #returns a list of dicts from within l that contain subD
        #print('getDictWith l={}, subD={}'.format(listB, subD))
        result = []

        for d in l2:
            if contains(d, subD):
                result.append(d)
        return result

    def getAllValuesOfKey(listOfDicts, key):
        values = []
        for d in listOfDicts:
            if d[key] not in values:
                values.append(d[key])

        return values

    for key in subList:
        print('subList[{}] = {}'.format(key, subList[key]))


    #assemble the subList into a single list with the final order
    newList = []

    for thisKey in sortKeys:
        thisList = subList[thisKey]
        thisIndex = sortKeys.index(thisKey)
        try:
            nextIndex = thisIndex + 1
            nextKey = sortKeys[nextIndex]
            nextList = subList[nextKey]

            print('\n thisKey={}, thisList={}'.format(thisKey, thisList))
            print('nextKey={}, nextList={}'.format(nextKey, nextList))


            for thisValue in getAllValuesOfKey(thisList, thisKey):
                for nextValue in getAllValuesOfKey(nextList, nextKey):
                    dictsWithThisValueAndNextValue = getDictWith(aList, {thisKey:thisValue, nextKey:nextValue})
                    for d in dictsWithThisValueAndNextValue:
                        if d not in newList:
                            newList.append(d)

        except Exception as e:
            #print('e=', e)
            #probably on the last index
            for d in thisList:
                if d not in newList:
                    newList.append(d)
                    pass

    return newList

def _string_to_bytes(text):
    return list(ord(c) for c in text)

def _bytes_to_string(binary):
    return "".join(chr(b) for b in binary)

def StartVTLPServer(hostIPAddress, hostIPPort=8080):
    print('StartVTLPServer')
    tlpServer = EthernetServerInterfaceEx(hostIPPort)

    regexGUID = re.compile('var\/nortxe\/gve\/web\/vtlp\/(.*?)\/layout\.json')



    @event(tlpServer, 'Connected')
    def tlpServerConnectionEvent(client, state):
        #get the tlp links
        allTLPInfo = []
        for tlp in UIDevice._allUIDevices:
            layout = tlp._layoutFile
            match = regexGUID.search(layout)
            if match:
                guid = match.group(1)
                link = 'https://{}/web/vtlp/{}/vtlp.html'.format(hostIPAddress, guid)
            allTLPInfo.append((tlp.DeviceAlias, tlp.IPAddress, link))

        print('allTLPInfo=', allTLPInfo)

        #create the table that will be put in the html
        table = '''<table>
                        <tr>
                            <th>Alias</th>
                            <th>IP Address</th>
                            <th>Link</th>
                        </tr>\r'''
        for link in allTLPInfo:
            table += '''<tr>
                            <td>{}:</td>
                            <td>{}</td>
                            <td><a href={}>{}</a></td>
                        </tr>\r'''.format(link[0], link[1], link[2], link[2])
        table += '</table>\r'

        #create the html
        html = WebPage='''\
HTTP/1.1 200 OK
<!DOCTYPE html>
    <html>
        <title>Extron Control</title>
        <body>
            <h1>Welcome to Extron Control</h1>
            <br>
            Select a link below
            <br><br>
            {}
        </body>
</html>
'''.format(table)

        #send html to client and disconnect(disconnect lets the client knowo the page is done loading)
        client.Send(html)
        client.Disconnect()

    tlpServer.StartListen()

#Processor port map ************************************************************

PROCESSOR_CAPABILITIES = {
    #'Part Number': {'Serial Ports': 8, 'IR/S Ports': 8, 'Digital Inputs...
}
PROCESSOR_CAPABILITIES['60-1418-01'] = { # IPCP Pro 550
    'Serial Ports': 8,
    'IR/S Ports': 8,
    'Digital I/Os': 0,
    'FLEX I/Os': 4,
    'Relays': 8,
    'Power Ports': 4,
    'eBus': True,
    }
PROCESSOR_CAPABILITIES['60-1413-01'] = { # IPL Pro S3
    'Serial Ports': 3,
    'IR/S Ports': 0,
    'Digital I/Os': 0,
    'FLEX I/Os': 0,
    'Relays': 0,
    'Power Ports': 0,
    'eBus': False,
    }
PROCESSOR_CAPABILITIES['60-1416-01'] = { # IPL Pro CR88
    'Serial Ports': 0,
    'IR/S Ports': 0,
    'Digital I/Os': 0,
    'FLEX I/Os': 0,
    'Relays': 8,
    'Power Ports': 0,
    'eBus': False,
    'Contact': 8,
    }

PROCESSOR_CAPABILITIES['60-1429-01'] = { # IPCP Pro 250
    'Serial Ports': 2,
    'IR/S Ports': 1,
    'Digital I/Os': 4,
    'FLEX I/Os': 0,
    'Relays': 2,
    'Power Ports': 0,
    'eBus': True,
    'Contact': 0,
    }

PROCESSOR_CAPABILITIES['60-1417-01'] = { # IPCP Pro 350
    'Serial Ports': 3,
    'IR/S Ports': 2,
    'Digital I/Os': 4,
    'FLEX I/Os': 0,
    'Relays': 4,
    'Power Ports': 0,
    'eBus': True,
    'Contact': 0,
    }

def DeleteInterface(interface):
    '''
    Some interfaces are not actually deleted because GS does not allow this.
    However, it does set the interface aside and if someone wishes to reinstantiate it again, they can.
    '''
    if isinstance(interface, extronlib.interface.EthernetServerInterface):
        interface.Connected = None
        interface.Disconnected = None
        interface.ReceiveData = None
        EthernetServerInterfaceEx.clear_port_in_use(interface.IPPort)

    elif isinstance(interface, extronlib.interface.SerialInterface):
        interface.Connected = None
        interface.Disconnected = None
        interface.ReceiveData = None
        ProcessorDevice._make_port_available(interface.Port)

    elif isinstance(interface, extronlib.interface.RelayInterface):
        ProcessorDevice._make_port_available(interface.Port)


def IsInterfaceAvailable(proc=None, ignoreKwargs=None, newKwargs=None):
    '''
    This function is meant to determine ahead of time if an interface is available on a processor.
    Perhaps the programmer is going to delete an interface and replace it with another interface.
    The programmer knows that they will not be able to create the new interface until the old interface is deleted,
    but they want to be sure that if they delete the old interface, they will be able to create the new interface without any errors.
    Otherwise my programmer friend will delete the old interface, try to create the new interface, but the new interface will fail.
    Now my friend has no way to recover the old interface. And thats no fun.

    It is possible that the new interface and old interface may share some attributes.
    The "ignoreKwargs" parameter is used to ignore attributes that are present in both the old and new interfaces.

    Example:
    interface1 = SerialInterface(proc, 'COM1')

    if not IsInterfaceAvailable(proc=proc, 'COM1'):
        DeleteInterface(interface1) #if this line is commented out, the instantiation of interface2 will fail

    interface2 = SerialInterface(proc, 'COM1')


    return list of str indicating any errors, or True if port is available
    '''
    errors = []

    if 'IPPort' in newKwargs and 'IPPort' not in ignoreKwargs:
        if 'IPAddress' in newKwargs:
            # We are checking a ethernet client
            pass #clients are always available
        else:
            # We are checking an ethernet server
            ipport = newKwargs['IPPort']
            if EthernetServerInterface.port_in_use(ipport):
                errors.append('The IPPort {} is already in use.'.format(ipport))

    elif 'Port' in newKwargs and 'Port' not in ignoreKwargs:
        port = newKwargs['Port']
        if 'RLY' in port:
            # We are checking a RelayInterface
            if ProcessorDevice.port_in_use(port):
                errors.append('The Relay Port {} is already in use.'.format(port))

        elif 'COM' in port:
            # We are checking a SerialInterface
            if ProcessorDevice.port_in_use(port):
                errors.append('The Serial Port {} is already in use.'.format(port))


    if len(errors) == 0:
        return True
    else:
        return errors




print('End  GST')




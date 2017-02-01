'''
Grant G Miller
Aug 23, 2016
gmiller@extron.com
800-633-9876 x6032

This module was created to accommodate the following scenario:
A divisible room system has two sides 'A' and 'B'.

The two systems A/B can operate independently.

The user can then 'combine' the rooms and now the TLP in A/B will 'mirror'.
That is, they will show the same page/popups/text/button states at all times.
The user can touch a button on either panel and the same action will happen.

The user can then 'uncombine' the rooms to return them to individual operation.

VERSION HISTORY ****************************************************************

v2.1.10 - Dec 19, 2016 - Bug fix when comparing button to a non-button object.

v2.1.9 - Oct 28, 2016 - When using 3 panels but only mirroring 2 panels, this module was still partially mirroring the 3rd panel. This has been fixed.

v2.1.8 - Sept 9, 2016 - Fixed typos

v2.1.7 - Sept 8, 2016 - Changed the way event handlers are called in mirror mode. This allows the programmer to be more flexible in their coding of event handlers.

v2.1.6 - Sept 8, 2016 - Added support for MESet when in mirror mode.

v2.1.5 - Sept 8, 2016 - Fixed example code.

v2.1.4 - Combine() is now a bit faster. Still kinds slow though.

v2.1.3 - Corrected error message "NoneType is not callable"

Example main.py: ***************************************************************

from extronlib import event, Version
from extronlib.device import ProcessorDevice, UIDevice
from extronlib.interface import (ContactInterface, DigitalIOInterface,
    EthernetClientInterface, EthernetServerInterfaceEx, FlexIOInterface,
    IRInterface, RelayInterface, SerialInterface, SWPowerInterface,
    VolumeInterface)
#from extronlib.ui import Button, Knob, Label, Level #Comment out this line and replace with line below
from mirrorTLP_v2_1_7 import Button, Knob, Label, Level
from extronlib.system import Clock, Wait, MESet

import mirrorTLP_v2_1_7 as Mirror

TLP1 = UIDevice('TLP1')
TLP2 = UIDevice('TLP2')

def SetupRoom(TLP):
    BtnModeMirror = Button(TLP, 71)
    BtnModeIndividual = Button(TLP, 72)
    MESetMode = MESet([BtnModeMirror, BtnModeIndividual])

    MESetMode.SetCurrent(BtnModeIndividual)

    @event(BtnModeMirror, 'Pressed')
    @event(BtnModeIndividual, 'Pressed')
    def BtnModePressed(button, state):
        print('Button {0} ID {1} {2}'.format(button.Name, button.ID, state))

        TLP1.ShowPopup('Please Wait')
        TLP2.ShowPopup('Please Wait')

        if button == BtnModeMirror:
            Mirror.Combine(TLP1, TLP2)

        elif button == BtnModeIndividual:
            Mirror.Uncombine(TLP1, TLP2)

        MESetMode.SetCurrent(button)

        TLP1.HidePopup('Please Wait')
        TLP2.HidePopup('Please Wait')

    BtnUp = Button(TLP, 56, repeatTime=0.1)
    BtnDown = Button(TLP, 55, repeatTime=0.1)
    Lvl = Level(TLP, 57)

    @event(BtnUp, 'Pressed')
    @event(BtnUp, 'Repeated')
    @event(BtnUp, 'Released')
    @event(BtnDown, 'Pressed')
    @event(BtnDown, 'Repeated')
    @event(BtnDown, 'Released')
    def BtnLvlPressed(button, state):

        if state in ['Pressed', 'Repeated']:
            button.SetState(1)
            if button == BtnUp:
                Lvl.Inc()

            elif button == BtnDown:
                Lvl.SetLevel(Lvl.Level -1)

        else:
            button.SetState(0)

SetupRoom(TLP1)
SetupRoom(TLP2)

END OF EXAMPLE *****************************************************************
'''
import extronlib.ui
import extronlib.device
from extronlib.system import ProgramLog
import hashlib
import time

debug = True

SavedMirrorStates = {}  # ex: {'tuple as string': UIData}

UIData = {'Buttons': {},
          'Labels': {},
          'Levels': {},
          'Knobs': {},
          'TLPs': {},
          }
'''
UIData is a dictionary that holds all of the 'mirror' and 'native' events.

Formatted as such:
UIData = {'TLPs' :
            {extronlib.device.UIDevice:
                {'Native Events': {
                    'ShowPage' : function,
                    ...
                    ...
                    'SetInput' : function,
                    },
                  'Mirror Events': {
                    'ShowPage' : function,
                    ...
                    ...
                    'SetInput' : function,
                    },
                },
            {extronlib.device.UIDevice:
                {'Native Events': {
                    'ShowPage' : function,
                    ...
                    ...
                    'SetInput' : function,
                    },
                  'Mirror Events': {
                    'ShowPage' : function,
                    ...
                    ...
                    'SetInput' : function,
                    },
                },
            }
          'Buttons' :
            {extronlib.ui.Button:
                {'Native Events':
                    {'Pressed' : function,
                     'Tapped'  : function,
                     'Held'    : function,
                     'Repeated': function,
                     'Released': function,
                     },
                 'Mirror Events':
                    {'Pressed' : function,
                     'Tapped'  : function,
                     'Held'    : function,
                     'Repeated': function,
                     'Released': function,
                     }
                 },
             extronlib.ui.Button:
                {'Native Events':
                    {'Pressed' : function,
                     'Tapped'  : function,
                     'Held'    : function,
                     'Repeated': function,
                     'Released': function,
                     },
                 'Mirror Events':
                    {'Pressed' : function,
                     'Tapped'  : function,
                     'Held'    : function,
                     'Repeated': function,
                     'Released': function,
                     }
                 },
             },
         'Labels':
            {extronlib.ui.Label:
                {'Native Events':
                    {'SetText'    : function,
                     'SetVisible' : function,
                     },
                 'Mirror Events':
                    {'SetText'    : function,
                     'SetVisible' : function,
                     },
                 },
             extronlib.ui.Label:
                {'Native Events':
                    {'SetText'    : function,
                     'SetVisible' : function,
                     ...
                     },
                 'Mirror Events':
                    {'SetText'    : function,
                     'SetVisible' : function,
                     ...
                     },
                 },
             },
         'Levels':
            {extronlib.ui.Level:
                {'Native Events':
                    {'SetLevel'    : function,
                     'SetVisible' : function,
                     ...
                     },
                 'Mirror Events':
                    {'SetLevel'    : function,
                     'SetVisible' : function,
                     ...
                     },
                 },
             extronlib.ui.Level:
                {'Native Events':
                    {'SetLevel'    : function,
                     'SetVisible' : function,
                     ...
                     },
                 'Mirror Events':
                    {'SetLevel'    : function,
                     'SetVisible' : function,
                     ...
                     },
                 },
             },
         'Knobs':
            {extronlib.ui.Knob:
                {'Native Events':
                    {'Turned'    : function,
                     },
                 'Mirror Events':
                    {'Turned'    : function,
                     },
                 },
             extronlib.ui.Knob:
                {'Native Events':
                    {'Turned'    : function,
                     },
                 'Mirror Events':
                    {'Turned'    : function,
                     },
                 },
             },

'''


class Button(extronlib.ui.Button):
    def __init__(self, *args, **kwargs):

        extronlib.ui.Button.__init__(self, *args, **kwargs)

        UIData['Buttons'][self] = {'Native Events': {},
                                   'Mirror Events': {},
                                   }

    def __eq__(self, other):
        '''
        https://docs.python.org/3/reference/datamodel.html
        '''
        # print('__eq__(self={}, other={})'.format(self,other))
        if self.__hash__() is other.__hash__():
            # print('self == other')
            return True
        else:
            if hasattr(other, 'ID'):
                if self.ID is other.ID:
                    # print('self.ID == other.ID')
                    return True
                else:
                    # print('return False')
                    return False
            else:
                return False

    def __hash__(self):
        '''
        https://docs.python.org/3/reference/datamodel.html
        '''
        UniqueString = self.Host.DeviceAlias + str(self.ID)
        HashObject = hashlib.sha1(UniqueString.encode())
        HashBytes = HashObject.digest()
        return int.from_bytes(HashBytes, 'big')


class Label(extronlib.ui.Label):
    def __init__(self, *args, **kwargs):
        UIData['Labels'][self] = {'Native Events': {},
                                  'Mirror Events': {},
                                  }

        extronlib.ui.Label.__init__(self, *args, **kwargs)


class Level(extronlib.ui.Level):
    def __init__(self, *args, **kwargs):
        UIData['Levels'][self] = {'Native Events': {},
                                  'Mirror Events': {},
                                  }
        extronlib.ui.Level.__init__(self, *args, **kwargs)


class Knob(extronlib.ui.Knob):
    def __init__(self, *args, **kwargs):
        UIData['Knobs'][self] = {'Native Events': {},
                                 'Mirror Events': {},
                                 }
        extronlib.ui.Knob.__init__(self, *args, **kwargs)


# ******************************************************************************
# Mirroring Functionality
UIDeviceSetMethods = ['ShowPage',
                      'ShowPopup',
                      'HidePopup',
                      'HideAllPopups',
                      'HidePopupGroup',
                      'SetLEDBlinking',
                      'SetLEDState',
                      'Click',
                      'PlaySound',
                      'StopSound',
                      'SetVolume',
                      'SetAutoBrightness',
                      'SetBrightness',
                      'SetMotionDecayTime',
                      'SetSleepTimer',
                      'SetDisplayTimer',
                      'SetInactivityTime',
                      'SetWakeOnMotion',
                      'Sleep',
                      'Wake',
                      'SetInput',
                      ]

UIDeviceEventMethods = ['BrightnessChanged',
                        'HDCPStatusChanged',
                        'InactivityChanged',
                        'InputPresenceChanged',
                        'LidChanged',
                        'LightChanged',
                        'MotionDetected',
                        'Offline',
                        'Online',
                        'SleepChanged',
                        ]

ButtonEventMethods = ['Pressed',
                      'Tapped',
                      'Held',
                      'Repeated',
                      'Released',
                      ]

ButtonSetMethods = ['SetBlinking',
                    'CustomBlink',
                    'SetEnable',
                    'SetState',
                    'SetText',
                    'SetVisible',
                    ]

LabelSetMethods = ['SetText',
                   'SetVisible',
                   ]

LevelSetMethods = ['Dec',
                   'Inc',
                   'SetLevel',
                   'SetRange',
                   'SetVisible',
                   ]

KnobEventMethods = ['Turned']


# Private functions *************************************************************

def _CreateMissingObjects(tlps):
    if debug:
        ProgramLog('_CreateMissingObjects(tlps={})'.format(tlps), 'info')

    global UIData
    for key in UIData:
        if key is not 'TLPs':
            ObjectName = key
            ObjectsToBeCreated = []  # Example [(Host1, ID1, repeatTime1, holdTime1),(Host2,ID2, repeatTime2, holdTime2),...]
            MasterTLP = tlps[0]

            for obj2 in UIData[ObjectName]:
                if obj2.Host == MasterTLP:
                    MasterObject = obj2

                    # Check the slave TLPs for an object with the same ID
                    for tlp in tlps[1:]:
                        SlaveObjectFound = False
                        for obj in UIData[ObjectName]:
                            if obj.Host == tlp:
                                if obj.ID == MasterObject.ID:
                                    SlaveObjectFound = True
                                    break

                        if not SlaveObjectFound:
                            if hasattr(MasterObject, '_repeatTime'):
                                RepeatTime = MasterObject._repeatTime
                            else:
                                RepeatTime = None

                            if hasattr(MasterObject, '_holdTime'):
                                HoldTime = MasterObject._holdTime
                            else:
                                HoldTime = None

                            ObjectsToBeCreated.append((tlp, MasterObject.ID, RepeatTime, HoldTime))

            for tup in ObjectsToBeCreated:

                Host, ID, RepeatTime, HoldTime = tup

                try:
                    NewObj = type(MasterObject)(Host, ID)
                except Exception as e:
                    print(e)
                    raise e

                if RepeatTime is not None:
                    NewObj._repeatTime = RepeatTime

                if HoldTime is not None:
                    NewObj._holdTime = HoldTime

                if debug:
                    ProgramLog('Created missing object type={}, Host={}, ID={}, repeatTime={}, holdTime={}'.format(
                        type(MasterObject), Host.DeviceAlias, ID, RepeatTime, HoldTime), 'info')
                    # Instantiating the object will add its data to the UIData


# Save Native Events
def _SaveNativeEvents(tlps):
    global UIData

    if debug:
        ProgramLog('_SaveNativeEvents(tlps={})'.format(tlps), 'info')

    # print('Saving Native Events')

    for tlp in tlps:
        # If the tlp is not in the TLPs dict, add it
        if tlp not in UIData['TLPs'].keys():
            UIData['TLPs'][tlp] = {'Native Events': {},
                                   'Mirror Events': {},
                                   }
    for Type in UIData:

        for obj in UIData[Type]:
            methodNames = []

            if isinstance(obj, extronlib.ui.Button):
                for item in ButtonEventMethods:
                    methodNames.append(item)
                for item in ButtonSetMethods:
                    methodNames.append(item)

            elif isinstance(obj, extronlib.device.UIDevice):
                for item in UIDeviceSetMethods:
                    methodNames.append(item)
                for item in UIDeviceEventMethods:
                    methodNames.append(item)

            elif isinstance(obj, extronlib.ui.Label):
                methodNames = LabelSetMethods

            elif isinstance(obj, extronlib.ui.Level):
                methodNames = LevelSetMethods

            elif isinstance(obj, extronlib.ui.Knob):
                methodNames = KnobEventMethods

            for methodName in methodNames:
                NativeMethod = getattr(obj, methodName)
                UIData[Type][obj]['Native Events'][methodName] = NativeMethod
                if debug:
                    ProgramLog('Saving Native:\nObject: {1}\nMethod: {0}'.format(methodName, obj, ), 'info')
    if debug:
        ProgramLog('Native Events Saved', 'info')


# Write Mirror methods
def _WriteMirrorMethods(objects, methods):
    global UIData

    if debug:
        ProgramLog('_WriteMirrorMethods(objects={}, methods={})'.format(objects, methods), 'info')

    # print('_WriteMirrorMethods(objects={}, methods={})'.format(objects, methods))

    # objects = tuple/list of objects (obj1, obj2,...)
    # methods = list of string method names ['Pressed', 'Released',...]

    # This function will take the methods from the objects[0] and
    # create new methods that will affect all objects
    # Ex. Button.SetText('text') will natively set the text only on this button,
    # After this function, a call to Button.SetText('text') will call the .SetText on all objects

    # print('Duplicating object', objects[0])

    ObjectName = ''
    obj = objects[0]
    if isinstance(obj, extronlib.ui.Button):
        ObjectName = 'Buttons'
    elif isinstance(obj, extronlib.device.UIDevice):
        ObjectName = 'TLPs'
    elif isinstance(obj, extronlib.ui.Label):
        ObjectName = 'Labels'
    elif isinstance(obj, extronlib.ui.Level):
        ObjectName = 'Levels'
    elif isinstance(obj, extronlib.ui.Knob):
        ObjectName = 'Knobs'

    # Overwrite the methods with the mirror methods
    for method in methods:

        # Assign the new methods to the obj attributes
        for obj in objects:
            if (method in ButtonEventMethods) or (method in UIDeviceEventMethods) or (method in KnobEventMethods):
                MasterObject = objects[0]

                def CreateNewEventFunc(MasterObject2, method2):
                    # print('CreateNewEventFunc(MasterObject2={}, method2={}'.format(MasterObject2, method2))
                    OldMethod = getattr(MasterObject2, method2)

                    if OldMethod is not None:
                        def NewEventFunction(obj, state):
                            # Call the master function and pass the masterObject, even when the slaves are pressed
                            OldMethod(MasterObject2, state)
                    else:
                        NewEventFunction = None

                    return NewEventFunction

                NewFunction = CreateNewEventFunc(MasterObject, method)

                # We dont need to call the .Pressed of each button.
            else:
                # No need to create the function if we arent going to use it.
                def CreateDoAllMethods():
                    # Collect the old methods (ex. obj.ShowPage)
                    OldMethods = []
                    for obj in objects:
                        OldMethod = getattr(obj, method)
                        if OldMethod is not None:
                            # No need to call an event handler if its set to None
                            OldMethods.append(OldMethod)

                            # Create a new method that will do ShowPage on all objects

                    def DoAllMethods(*args, **kwargs):
                        # ProgramLog('DoAllMethods(args={}, kwargs={}) OldMethods={}'.format(args, kwargs, OldMethods), 'info')
                        for Method in OldMethods:
                            Method(*args, **kwargs)

                    return DoAllMethods

                NewFunction = CreateDoAllMethods()
                # We DO need to call the .SetText of each button

            if NewFunction is not None:  # if you use setattr, it will register this in the FWs event list with a None object. This causes a silent error in ProgramLog of "NoneType is not callable"
                setattr(obj, method, NewFunction)  # only set if not None?

                # Save the mirror events to UIData
                UIData[ObjectName][obj]['Mirror Events'][method] = NewFunction


# Find objects with same ID
def _FindObjectsWithSameID(tlps):
    if debug:
        string = '_FindObjectsWithSameID(tlps={},)'.format(tlps)
        ProgramLog(string, 'info')

    global UIData
    # Returns a list of list
    # Each sub-list contains objects with the same type and same ID
    # The first object in the sub-list is the 'master' object.
    # That is, the master objects event handlers will be copied to the slave objects handlers. Slave's native handlers will be overwritten.
    MasterTLP = tlps[0]

    ReturnListList = []

    for Type in UIData:
        if Type is not 'TLPs':

            MirrorObjects = []
            for obj in UIData[Type]:
                MirrorObjects = []
                if obj.Host in tlps:
                    if obj.Host == MasterTLP:
                        MasterObject = obj

                        MirrorObjects = [MasterObject]

                        for obj2 in UIData[Type]:
                            if obj2.Host in tlps:
                                if obj2.Host != MasterTLP:
                                    SlaveObject = obj2
                                    if SlaveObject.ID == MasterObject.ID:
                                        MirrorObjects.append(SlaveObject)

                ReturnListList.append(MirrorObjects)

        else:  # Type == 'TLPs'
            MirrorObjects = []
            for index in range(len(tlps)):
                MirrorObjects.append(tlps[index])

            ReturnListList.append(MirrorObjects)

    if debug:
        ProgramLog('ReturnListList:', 'info')

        for lst in ReturnListList:
            ProgramLog(str(lst), 'info')
        ProgramLog(' ', 'info')

    return ReturnListList


def _printUIData():
    global UIData
    try:
        print('UIData =')
        for Type in UIData:
            print(Type)
            for obj in UIData[Type]:
                print(obj)
                for methodType in UIData[Type][obj]:
                    print(methodType)
                    for methodName in UIData[Type][obj][methodType]:
                        if methodName is not None:
                            for method in UIData[Type][obj][methodType][methodName]:
                                print('Type: {}\nObj: {}\nMethodType: {}\nMethodName: {}\nMethod: {}'.format(Type, obj,
                                                                                                             methodType,
                                                                                                             methodName,
                                                                                                             method))
    except Exception as e:
        time.sleep(0.0001)
        print(e)
        try:
            print('Type: {}'.format(Type))
            print('Obj: {}'.format(obj))
            print('MethodType: {}'.format(methodType))
            print('MethodName: {}'.format(methodName))
            print('Method: {}'.format(method))
        except:
            pass


# Public Functions **************************************************************
def Combine(*tlps):
    '''
    *tlps is a extronlib.device.UIDevice object or list of extronlib.device.UIDevice objects
    '''
    global UIData

    if debug:
        _printUIData()

    # First, check to see if we have already calculated the mirror state before.
    if False:  # str(tlps) in SavedMirrorStates:
        # This aint working.. not sure why... giving up
        print('Recalling previous mirror state')

        # Reset Object event/methods
        UIData = SavedMirrorStates[str(tlps)]
        for Type in UIData:
            # print('Type =', Type)
            try:
                for obj in UIData[Type]:
                    if obj is not None:
                        # print('    obj =', obj)
                        methodType = 'Mirror Events'
                        for methodName in UIData[Type][obj][methodType]:
                            MirrorMethod = UIData[Type][obj][methodType][methodName]
                            # print('        methodName = {}, NativeMethod = {}'.format(methodName, NativeMethod))
                            setattr(obj, methodName, MirrorMethod)
            except Exception as e:
                print(e)
                if debug:
                    time.sleep(0.0001)
                    try:
                        print('Type: {}'.format(Type))
                        print('Obj: {}'.format(obj))
                        print('MethodType: {}'.format(methodType))
                        print('MethodName: {}'.format(methodName))
                        print('Method: {}'.format(MirrorMethod))
                    except:
                        pass

        print('Mirror state recalled')

    else:
        # Generate a new mirror state
        print('Combine TLPs: {}'.format(tlps))
        # print(UIData)

        _CreateMissingObjects(tlps)
        _SaveNativeEvents(tlps)

        if debug:
            _printUIData()

        ListOfList = _FindObjectsWithSameID(tlps)

        _WriteMirrorMethods(tlps, UIDeviceSetMethods)
        _WriteMirrorMethods(tlps, UIDeviceEventMethods)

        for lst in ListOfList:
            if len(lst) > 0:
                MasterObject = lst[0]

                methodNames = []
                if isinstance(MasterObject, extronlib.ui.Button):
                    for item in ButtonEventMethods:
                        methodNames.append(item)
                    for item in ButtonSetMethods:
                        methodNames.append(item)

                elif isinstance(MasterObject, extronlib.ui.Label):
                    methodNames = LabelSetMethods

                elif isinstance(MasterObject, extronlib.ui.Level):
                    methodNames = LevelSetMethods

                elif isinstance(MasterObject, extronlib.ui.Knob):
                    methodNames = KnobEventMethods

                elif isinstance(MasterObject, extronlib.device.UIDevice):
                    # Skipt this. Already done above.
                    continue

                _WriteMirrorMethods(lst, methodNames)

        # print(UIData)

        # Save the mirror state so it can be easily recalled later
        SavedMirrorStates[str(tlps)] = UIData

    if debug:
        ProgramLog('Combine Complete', 'info')
        _printUIData()
    else:
        print('Combine Complete')


def Uncombine(*tlps):
    '''
    *tlps is a extronlib.device.UIDevice object or list of extronlib.device.UIDevice objects
    '''
    global UIData
    if debug:
        ProgramLog('Uncombine TLPs: {}'.format(tlps), 'info')
    else:
        print('Uncombine TLPs: {}'.format(tlps))
    # print(UIData)

    # Reset Object event/methods
    for Type in UIData:
        # print('Type =', Type)
        for obj in UIData[Type]:
            # print('    obj =', obj)
            for methodName in UIData[Type][obj]['Native Events']:
                NativeMethod = UIData[Type][obj]['Native Events'][methodName]
                # print('        methodName = {}, NativeMethod = {}'.format(methodName, NativeMethod))
                setattr(obj, methodName, NativeMethod)

                # Clear the mirror event
                UIData[Type][obj]['Mirror Events'][methodName] = None

    if debug:
        ProgramLog('Uncombine Complete', 'info')
    else:
        print('Uncombine Complete')
        # print(UIData)


## Begin ControlScript Import --------------------------------------------------
from extronlib import event, Version
from extronlib.device import ProcessorDevice, UIDevice
from extronlib.interface import (EthernetClientInterface,
                                 EthernetServerInterface, SerialInterface, IRInterface, RelayInterface,
                                 ContactInterface, DigitalIOInterface, FlexIOInterface, SWPowerInterface,
                                 VolumeInterface)
from extronlib.ui import Button, Knob, Label, Level
from extronlib.system import Clock, MESet, Wait


class ScrollingList():
    '''
    This class allows the programmer to easily implement a scrolling list.
    It also allows the same list to be tracked across TLPs.

    If you need multiple scrolling list, you can modify this module.
    '''

    ClassInstances = []

    def __init__(self, List=[], ScrollingMESet=None, UpButtonObject=None, DownButtonObject=None):
        '''
        List = list of items to scroll through.
        ScrollingMESet = The MEset for the TLP buttons that will display the list data
        UpButtonObject = The scrolling functionality will be be added to this button object.
            If the button object already has a Pressed handler, it will be maintained and the scrolling function will be added.
        '''
        NewList = ['- - -'] + List + ['- - -']
        self.List = NewList

        self.UpButtonObject = UpButtonObject
        self.DownButtonObject = DownButtonObject

        self.Position = 1
        self.ScrollingMESet = ScrollingMESet

        self.LastSelectedItem = None  # Contains the string value of the selected item

        self.ClassInstances.append(self)

        self.UpdateDisplay()

        OldUpHandler = UpButtonObject.Pressed

        def NewScrollUpEventHandler(button, state):
            self.ScrollUp()
            # print('OldUpHandler=', OldUpHandler)
            if OldUpHandler is not None:
                # print('Calling OldUpHandler')
                OldUpHandler(UpButtonObject, state)
                # print('OldUpHandler Called')

        UpButtonObject.Pressed = NewScrollUpEventHandler
        UpButtonObject.Repeated = NewScrollUpEventHandler
        UpButtonObject._holdTime = 0.3
        UpButtonObject._repeatTime = 0.2

        OldDownHandler = DownButtonObject.Pressed

        def NewScrollDownEventHandler(button, state):
            self.ScrollDown()
            if OldDownHandler is not None:
                OldDownHandler(DownButtonObject, state)

        DownButtonObject.Pressed = NewScrollDownEventHandler
        DownButtonObject.Repeated = NewScrollDownEventHandler
        DownButtonObject._holdTime = 0.3
        DownButtonObject._repeatTime = 0.2

    def UpdateDisplay(self):
        print('UpdateDisplay({})'.format(self))

        MEIndex = 0
        MEObjects = self.ScrollingMESet.Objects
        MEObjectFound = False

        for index in range(self.Position, self.Position + len(self.ScrollingMESet.Objects)):
            if index > len(self.List) - 1:
                break
            TheObject = MEObjects[MEIndex]
            Text = self.List[index]
            AdjustedText = '  ' + Text.replace('\n', '\n  ')
            TheObject.SetText(AdjustedText)

            if MEObjectFound == False:
                if self.List[index] == self.LastSelectedItem:
                    MEObjectFound = True
                    self.ScrollingMESet.SetCurrent(TheObject)

            MEIndex += 1

        if MEObjectFound == False:
            self.ScrollingMESet.SetCurrent(None)

        # Update other instances
        for Instance in self.ClassInstances:
            print('Instance=', Instance)
            print('Instance.LastSelectedItem={}, self.LastSelectedItem={}'.format(Instance.LastSelectedItem,
                                                                                  self.LastSelectedItem))
            if Instance.LastSelectedItem != self.LastSelectedItem:
                print('Instance.LastSelectedItem != self.LastSelectedItem')
                Instance.LastSelectedItem = self.LastSelectedItem
                Instance.UpdateDisplay()

    def GetCurrentItem(self):

        CurrentObject = self.ScrollingMESet.GetCurrent()
        if CurrentObject is None:
            return self.LastSelectedItem
        else:
            CurrentIndex = self.ScrollingMESet.Objects.index(CurrentObject)
            CurrentItem = self.List[self.Position + CurrentIndex]
            # print('CurrentItem=', CurrentItem)
            return CurrentItem

    def ScrollUp(self):
        self.LastSelectedItem = self.GetCurrentItem()

        self.Position -= 1
        if self.Position < 0:
            self.Position = 0
        self.UpdateDisplay()

    def ScrollDown(self):
        self.LastSelectedItem = self.GetCurrentItem()

        self.Position += 1
        LastPosition = len(self.List) - len(self.ScrollingMESet.Objects)
        if self.Position > LastPosition:
            self.Position = LastPosition

        self.UpdateDisplay()

    def GetItemFromRelativePosition(self, RelativePosition=None):
        AbsolutePosition = self.Position + RelativePosition
        return self.List[AbsolutePosition]

    def ResetList(self, List=[]):
        NewList = ['- - -'] + List + ['- - -']
        self.List = NewList

    def SelectItem(self, Item):
        '''
        Item = string of the item from self.List to select.
        '''
        self.LastSelectedItem = Item
        self.UpdateDisplay()

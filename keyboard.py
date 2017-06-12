
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


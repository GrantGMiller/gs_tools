'''
This module is meant to be a collection of tools to simplify common task in AV control systems.
Started: March 28, 2017 and appended to continuously
'''


import extronlib
from extronlib import event
from extronlib.device import ProcessorDevice, UIDevice
from extronlib.system import Wait, ProgramLog, File
from extronlib.interface import EthernetServerInterfaceEx

try:
    import aes_tools
except:
    pass

import json
import time
import hashlib
import datetime
import calendar
import re
import random

# Set this false to disable all print statements ********************************
debug = False
if not debug:
    #Disable print statements
    print = lambda *args, **kwargs: None


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


RemoteTraceServer = None


def RemoteTrace(IPPort=1024):
    '''
    This function return a new print function that will print to stdout and also send to any clients connected to the server defined on port IPPort
    For example:
        print = RemoteTrace()
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


# ScrollingTable ****************************************************************
ScrollingTable_debug = False



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




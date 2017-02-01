import urllib.request
import json
import base64

TIMEOUT = 5


class EthernetClass():
    def __init__(self, *args, **kwargs):

        self._opener = urllib.request.build_opener(urllib.request.HTTPSHandler())
        self._opener.add_handler(urllib.request.HTTPBasicAuthHandler())

        self.device_username = kwargs.get('deviceUsername')
        self.device_password = kwargs.get('devicePassword')

        # public to the user
        self.user_body = {}
        self.meeting_body = {}

        self.enterprise_token = ''

        self.Unidirectional = 'False'
        self.connectionCounter = 15

        # Do not change this the variables values below
        self.DefaultResponseTimeout = 0.3
        self.Subscription = {}
        self.counter = 0
        self.connectionFlag = True
        self.initializationChk = True
        self.Models = {}

        self.Commands = {
            'ConnectionStatus': {'Status': {}},
            'UserToken': {'Status': {}},
            'MeetingToken': {'Status': {}},

            'MeetingListRefresh': {'Status': {}},
            'MeetingListNavigation': {'Parameters': ['Step'], 'Status': {}},

            'MeetingListStatus': {'Parameters': ['Position'], 'Status': {}},
            'SIPNumberStatus': {'Parameters': ['Position'], 'Status': {}},

        }

        # will be a directory of Meeting Object Schemas (dictionary)
        self.meeting_directory = Directory(self.WriteStatus, 'MeetingListStatus', 10, filler={})

    @property
    def deviceUsername(self):
        return self.device_username

    @deviceUsername.setter
    def deviceUsername(self, newValue):
        self.device_username = newValue

    @property
    def devicePassword(self):
        return self.device_password

    @devicePassword.setter
    def devicePassword(self, newValue):
        self.device_password = newValue
        # self.SetUserToken()

    def SetUserToken(self, value=None, qualifier=None):
        """Gets the user token that is used for other commands.
        devicePassword and deviceUsername must be set prior. Setting a new devicePassword will trigger this method
        """

        if self.device_username is not None and self.device_password is not None:

            body = {
                'grant_type': 'password',
                'username': self.device_username,
                'password': self.device_password
            }

            url = 'https://api.bluejeans.com/oauth2/token'
            data = json.dumps(body).encode()

            res = self.__SetHelper('UserToken', value, qualifier, url, data)
            if res:
                self.user_body = json.loads(res)

        else:
            print('Please set a valid deviceUsername and devicePassword')

    def SetMeetingToken(self, value, qualifier):

        # Requires Position qualifier, which should be the position of the meeting in the MeetingListStatus that they want the token for
        meeting_body_param = self.meeting_directory.get_entry(int(qualifier['Position']))

        # ID of the meeting (ID that is shown on the website)
        meeting_numeric_id = meeting_body_param.get('numericMeetingId')
        if meeting_numeric_id:
            # Password in the qualifier is optional
            meeting_pw = qualifier.get('Password', '')

            # Request Body Schema
            body = {
                'grant_type': 'meeting_passcode',
                'meetingNumericId': meeting_numeric_id
            }

            # Add optional password. Will become moderator if correct password is provided.
            if meeting_pw != '':
                body['meetingPasscode'] = meeting_pw

            url = 'https://api.bluejeans.com/oauth2/token'
            data = json.dumps(body).encode()

            res = self.__SetHelper('MeetingToken', value, qualifier, url, data)
            if res:
                self.meeting_body = json.loads(res)
        else:
            self.meeting_body = {}

    def SetMeetingListRefresh(self, value, qualifier):
        """Update the meeting list for the current user
        """
        accessToken = self.user_body['access_token']
        user = self.user_body['scope']['user']

        # data = json.dumps({'title' : 'test2'}).encode()

        url = 'https://api.bluejeans.com/v1/user/{0}/scheduled_meeting/?access_token={1}'.format(user, accessToken)
        data = None

        res = self.__SetHelper('MeetingListRefresh', value, qualifier, url, data)
        if res:
            res = json.loads(res)
            # res should be a list of dictionaries

            # add meetings (dictionaries) to the directory
            # meeting_list = []
            # for meeting in res:
            #    meeting_list.append(meeting)
            self.meeting_directory.reset(res)

    def SetMeetingListNavigation(self, value, qualifier):
        step = int(qualifier['Step'])
        if value == 'Up':
            self.meeting_directory.scroll_up(step)
        elif value == 'Down':
            self.meeting_directory.scroll_down(step)
        else:
            print('Invalid command for MeetingListNavigation')

    def UpdateSIPNumberStatus(self, value=None, qualifier=None):
        """Update the SIP Number for a meeting. Requires Position qualifier that will correspond to the position of the meeting
        in the meeting list. The meeting body from that position will be passed into here
        """
        # Requires a Position qualifier to write to the correct position. It does not affect the query
        # It is up to the user to ensure that the latest call to SetMeetingToken has the same position # as the current call
        # to UpdateSIPNumberStatus


        # Get the current meeting_body token. This is assuming SetMeetingToken was called previously
        meeting_body_param = self.meeting_body

        # check if a meeting exists for that position
        accessToken = meeting_body_param.get('access_token')
        if accessToken is not None:
            user = self.user_body['scope']['user']
            meeting_id = meeting_body_param['scope']['meeting']['meetingNumericId']

            # Page 24
            body = {
                'endpointType': 1,
                'languageCode': 'en-us',
            }

            url = 'https://api.bluejeans.com/v1/user/{0}/live_meetings/{1}/pairing_code/SIP/?access_token={2}'.format(
                user, meeting_id, accessToken)
            data = json.dumps(body).encode()
            res = self.__UpdateHelper('SIPNumberStatus', value, qualifier, url, data)
            if res:
                res = json.loads(res)
                self.WriteStatus('SIPNumberStatus', res['uri'], qualifier)
        else:
            self.WriteStatus('SIPNumberStatus', '', qualifier)

    def __CheckResponseForErrors(self, command, res):
        return res.read().decode()

    def __SetHelper(self, command, value, qualifier, url='', data=None):
        print('Performing Set:', command, value, qualifier)
        headers = {'Content-Type': 'application/json'}

        # add authentication to the header for getting the user token
        if command == 'UserToken' and self.device_username is not None and self.device_password is not None:
            authentication = b'Basic ' + base64.b64encode(
                self.device_username.encode() + b':' + self.device_password.encode())
            headers['Authorization'] = authentication.decode()

        my_request = urllib.request.Request(url, data=data, headers=headers)

        try:
            res = self._opener.open(my_request, timeout=TIMEOUT)
        except urllib.error.HTTPError as err:
            print('{0} {1} - {2}'.format(command, err.code, err.reason))
            res = ''
        except urllib.error.URLError as err:
            print('{0} {1}'.format(command, err.reason))
            res = ''
        else:
            if res.status not in (200, 202):
                print('{0} {1} - {2}'.format(command, res.status, res.msg))
                res = ''
            else:
                res = self.__CheckResponseForErrors(command, res)
        return res

    def __UpdateHelper(self, command, value, qualifier, url='', data=None):
        print('Performing Update:', command, value, qualifier)
        headers = {'Content-Type': 'application/json'}

        my_request = urllib.request.Request(url, data=data, headers=headers)

        if self.initializationChk:
            self.OnConnected()
            self.initializationChk = False

        self.counter = self.counter + 1
        if self.counter > self.connectionCounter and self.connectionFlag:
            self.OnDisconnected()

        try:
            res = self._opener.open(my_request, timeout=TIMEOUT)
        except urllib.error.HTTPError as err:
            print('{0} {1} - {2}'.format(command, err.code, err.reason))
            res = ''
        except urllib.error.URLError as err:
            print('{0} {1}'.format(command, err.reason))
            res = ''
        else:
            if res.status not in (200, 202):
                print('{0} {1} - {2}'.format(command, res.status, res.msg))
                res = ''
            else:
                res = self.__CheckResponseForErrors(command, res)

        return res

    def OnConnected(self):
        self.connectionFlag = True
        self.WriteStatus('ConnectionStatus', 'Connected')
        self.counter = 0

    def OnDisconnected(self):
        self.WriteStatus('ConnectionStatus', 'Disconnected')
        self.connectionFlag = False

    def Set(self, command, value=None, qualifier=None):
        getattr(self, 'Set{0}'.format(command))(value, qualifier)

    def Update(self, command, qualifier=None):
        getattr(self, 'Update{0}'.format(command))(None, qualifier)

    # This method is to tie a specific command with specific parameter to a call back method
    # when it value is updated. It all setup how often the command to be query, if the command
    # have the update method.
    # interval 0 is for query once, any other integer is used as the query interval.
    # If command doesn't have the update feature then that command is only used for feedback
    def SubscribeStatus(self, command, qualifier, callback):
        Command = self.Commands.get(command)
        if Command:
            if command not in self.Subscription:
                self.Subscription[command] = {'method': {}}

            Subscribe = self.Subscription[command]
            Method = Subscribe['method']

            if qualifier:
                for Parameter in Command['Parameters']:
                    try:
                        Method = Method[qualifier[Parameter]]
                    except:
                        if Parameter in qualifier:
                            Method[qualifier[Parameter]] = {}
                            Method = Method[qualifier[Parameter]]
                        else:
                            return

            Method['callback'] = callback
            Method['qualifier'] = qualifier
        else:
            print(command, 'does not exist in the module')

    # This method is to check the command with new status have a callback method then trigger the callback
    def NewStatus(self, command, value, qualifier):
        if command in self.Subscription:
            Subscribe = self.Subscription[command]
            Method = Subscribe['method']
            Command = self.Commands[command]
            if qualifier:
                for Parameter in Command['Parameters']:
                    try:
                        Method = Method[qualifier[Parameter]]
                    except:
                        break
            if 'callback' in Method and Method['callback']:
                Method['callback'](command, value, qualifier)

                # Save new status to the command

    def WriteStatus(self, command, value, qualifier=None):
        self.counter = 0
        if self.connectionFlag == False:
            self.OnConnected()
        Command = self.Commands[command]
        Status = Command['Status']
        if qualifier:
            for Parameter in Command['Parameters']:
                try:
                    Status = Status[qualifier[Parameter]]
                except KeyError:
                    if Parameter in qualifier:
                        Status[qualifier[Parameter]] = {}
                        Status = Status[qualifier[Parameter]]
                    else:
                        return
        try:
            if Status['Live'] != value:
                Status['Live'] = value
                self.NewStatus(command, value, qualifier)
        except:
            Status['Live'] = value
            self.NewStatus(command, value, qualifier)

            # Read the value from a command.

    def ReadStatus(self, command, qualifier=None):
        Command = self.Commands[command]
        Status = Command['Status']
        if qualifier:
            for Parameter in Command['Parameters']:
                try:
                    Status = Status[qualifier[Parameter]]
                except KeyError:
                    return None
        try:
            return Status['Live']
        except:
            return None


################################################################
# BEGIN DIRECTORY CODE
################################################################

def UseAutoUpdate(func):
    def wrapper(self, *args, **kwargs):
        res = func(self, *args, **kwargs)
        if self.auto_update:
            self.update_status_function()
        return res

    return wrapper


class Directory:
    """Handles the logic of a directory scrolling up/down and writing to the correct status labels
    1.1
    """

    def __init__(self, write_status_function, write_status_name, display_count, filler=None):

        # Number of items to show
        self.display_count = int(display_count)

        # write status command name in the module
        self.write_status_function = write_status_function
        self.write_status_name = write_status_name

        # name of the qualifier specifying the entry position
        self.position_name = 'Position'

        self.entry_list = []

        self.start_index = 0

        # flag to specify if UpdateStatusFunction should be called automatically
        self.auto_update = True

        # This is the object to be used to fill out displayed positions if the list
        # runs out of elements to display. Also returned if invalid position is
        # accessed. Default is None.
        self.filler = filler

    def update_status_function(self):
        """Write to driver status
        """
        for index, entry in enumerate(self.get_displayed_entries()):
            if self.write_status_name == 'MeetingListStatus':
                # Write Title of the meeting to MeetingListStatus in the module
                temp_entry = entry[0]
                title = temp_entry.get('title', '')
                self.write_status_function(self.write_status_name, title, {self.position_name: str(index + 1)})

    @UseAutoUpdate
    def add_entry(self, entry):
        if isinstance(entry, list):
            self.entry_list.extend(entry)
        else:
            self.entry_list.append(entry)

    @UseAutoUpdate
    def reset(self, new_entries=None):
        if isinstance(new_entries, list):
            self.entry_list.clear()
            self.entry_list = []
            self.entry_list.extend(new_entries)
        elif new_entries is None:
            self.entry_list.clear()
        else:
            raise TypeError('argument must be a list')
        self.start_index = 0

    @UseAutoUpdate
    def remove_entry(self, display_position):
        """Removes the entry in the entry list
        The index of the entry to retrieve is offset by the start_index

        DisplayPosition is assumed to not be 0-based.
        """

        if self.__display_position_check(display_position):
            try:
                return self.entry_list.pop(self.start_index + display_position - 1)
            except IndexError:
                return self.filler
        else:
            return self.filler

    def get_entry(self, display_position):
        """Return the value of the entry
        The index of the entry to retrieve is offset by the start_index

        DisplayPosition is assumed to not be 0-based.
        """

        # Make sure the position is valid
        if self.__display_position_check(display_position):
            try:
                return self.entry_list[self.start_index + display_position - 1]
            except IndexError:
                return self.filler
        else:
            return self.filler

    def get_displayed_entries(self):
        """Returns an iterator of only the displayed entries.
        Each returned value is a tuple (entry object, item's position in the list)
        """
        index = self.start_index
        while index <= self.start_index + self.display_count - 1:
            if index >= len(self.entry_list):
                yield self.filler, index + 1
            else:
                yield self.entry_list[index], index + 1

            index += 1

    def __display_position_check(self, position):
        """Checks to make sure the given position is a valid position to display
        """
        return 0 < position <= self.display_count

    @UseAutoUpdate
    def scroll_up(self, step=1):
        # Make sure new start index is greater than 0
        if self.start_index - step >= 0:
            self.start_index -= step
        else:
            self.start_index = 0

    @UseAutoUpdate
    def scroll_down(self, step=1):
        # Make sure new start index doesn't go past the length of entry list
        if self.start_index + step < len(self.entry_list):
            self.start_index += step
        else:
            self.start_index = len(self.entry_list) - 1  # start_index becomes the last item in the entry list
            if self.start_index < 0:
                self.start_index = 0

    @UseAutoUpdate
    def scroll_to_top(self):
        self.start_index = 0

    @UseAutoUpdate
    def scroll_to_bottom(self):
        self.start_index = len(self.entry_list) - 1


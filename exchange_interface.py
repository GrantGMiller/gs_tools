import urllib.request, re
from base64 import b64encode, b64decode
import datetime

"""
    1/8/2017
    Developer: David S. Gonzalez
    Email: davidsanchez23@icloud.com/dgonzalez@extron.com
    v1_0_1 Add Support For impersonation account
    v1_0_2 incorporate Daylight Savings

    2017-06-06
    Added ability to get calendar attachments and save them to local file system

    2017-06-07 - Joel Lasher
    Created GetMeetingAttachment which returns the contents of a meeting attachment

    2017-06-08 - Joel Lasher
    Updated GetMeetingAttachment and added example for saving an attachment below


Example main.py

import exchange_interface
testCalendar = Exchange('outlook.office365.com', 'room@extron.com', 'password', 'Office365', "UTC-08:00")
testCalendar.UpdateCalendarData()
print(testCalendar.GetWeekData())
print(testCalendar.GetMeetingData('Tue', '3:00PM'))

Attachment = testCalendar.GetMeetingAttachment('Thu', '3:00PM')
attContent = b64decode(Attachment['Attachment1']['Content'])
attType = b64decode(Attachment['Attachment1']['ContentType'])

fType = {'video/mp4': '.mp4',
         'text/plain': '.txt',
         'text/xml': '.xml',
         # ...
         'audio/mp4': '.mp4',
         'video/mp4': '.mp4',
         }

fName = 'myfile.{}'.format(fType.get(attType))
f = open(fName, 'wb')
f.write(attContent)
f.close()

"""

def ConvertTimeStringToDatetime(string):
    print('ConvertTimeStringToDatetime\nstring=', string)
    year, month, etc = string.split('-')
    day, etc = etc.split('T')
    hour, minute, etc = etc.split(':')
    second = etc[:-1]
    dt = datetime.datetime(
        year=int(year),
        month=int(month),
        day=int(day),
        hour=int(hour),
        minute=int(minute),
        second=int(second),
        )
    return dt

def ConvertDatetimeToTimeString(dt):
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')

class _CalendarItem:
    def __init__(self, startDT, endDT, data=None):
        if data is None:
            data = {}
        #print('_CalendarItem data=', data)
        self._data = data.copy()  # dict like {'ItemId': 'jasfsd', 'Subject': 'SuperMeeting', ...}
        self._startDT = startDT
        self._endDT = endDT
        self._attachments = []

    def AddData(self, key, value):
        self._data[key] = value

    def Get(self, key):
        if key is 'Start':
            return self._startDT
        elif key is 'End':
            return self._endDT
        else:
            return self._data.get(key, None)

    def __contains__(self, dt):
        if isinstance(dt, datetime.date):
            if self._startDT.year == dt.year and \
                    self._startDT.month == dt.month and \
                    self._startDT.day == dt.day:
                return True

            elif self._endDT.year == dt.year and \
                    self._endDT.month == dt.month and \
                    self._endDT.day == dt.day:
                return True

            else:
                return False

        elif isinstance(dt, datetime.datetime):
            if dt >= self._startDT and dt <= self._endDT:
                return True
            else:
                return False

    def HasAttachment(self):
        if len(self._attachments) > 0:
            return True
        else:
            if self._data['HasAttachments'] is True:
                return True
            else:
                return False

        return False

    def __str__(self):
        return '<CalendarItem objectStart={}, End={}, Subject={}, HasAttachement={}>'.format(self.Get('Start'), self.Get('End'), self.Get('Subject'), self.HasAttachment())

    def __repr__(self):
        return str(self)

class _Attachment:
    def __init__(self, Filename, AttachmentId, parentExchange):
        self.Filename = Filename
        self.AttachmentId = AttachmentId
        self._parentExchange = parentExchange

    def GetContent(self):
        pass

    def SaveToPath(self, path):
        pass


class Exchange():


    #Exchange methods
    def __init__(self, server, username, password, service, timeZone, daylightSaving=True, impersonation=None):
        self.service = service
        self.daylightSavings = daylightSaving
        self.timeZoneOffset = self.timeZone(timeZone)
        self.httpURL = 'https://{0}/EWS/exchange.asmx'.format(server)
        self.encode = b64encode(bytes('{0}:{1}'.format(username, password), "ascii"))
        self.login = str(self.encode)[2:-1]
        self._impersonation = impersonation
        self.header = {'content-type': 'text/xml; charset=utf-8',
                       'Authorization': 'Basic {}'.format(self.login)
                       }
        self._calendarItems = []

        self._startOfWeek = None
        self._endOfWeek = None
        self._soapHeader = None

        self._folderID = None
        self._changeKey = None
        self._UpdateFolderIdAndChangeKey()

    # ----------------------------------------------------------------------------------------------------------------------
    # --------------------------------------------------EWS Services--------------------------------------------------------
    # ----------------------------------------------------------------------------------------------------------------------
    def _GetSoapHeader(self, account):
        #This should only need to be called once to create the header that will be used in the XML request from now on
        if account is None:
            xmlAccount = """<t:RequestServerVersion Version="Exchange2007_SP1" />"""
        else:
            xmlAccount = """<t:RequestServerVersion Version="Exchange2007_SP1" />
                            <t:ExchangeImpersonation>
                                <t:ConnectingSID>
                                    <t:SmtpAddress>{0}</t:SmtpAddress>
                                </t:ConnectingSID>
                            </t:ExchangeImpersonation>""".format(account)
        return xmlAccount


    def _UpdateFolderIdAndChangeKey(self):
        # Requests Service for ID of calendar folder and change key
        if self._soapHeader is None:
            self._soapHeader = self._GetSoapHeader(self._impersonation)

        if self._startOfWeek is None:
            todayDT = datetime.date.today()
            weekday = todayDT.weekday()
            startWeekDT = todayDT - datetime.timedelta(days=weekday)
            self._startOfWeek = ConvertDatetimeToTimeString(startWeekDT)

        if self._endOfWeek is None:
            todayDT = datetime.date.today()
            weekday = todayDT.weekday()
            endWeekDT = todayDT + datetime.timedelta(days=6 - weekday)
            self._endOfWeek = ConvertDatetimeToTimeString(endWeekDT)

        regExFolderInfo = re.compile(r't:FolderId Id=\"(.{1,})\" ChangeKey=\"(.{1,})\"\/')

        xmlbody = """<?xml version="1.0" encoding="utf-8"?>
                    <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                           xmlns:m="http://schemas.microsoft.com/exchange/services/2006/messages"
                           xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types"
                           xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                      <soap:Header>
                        {0}
                      </soap:Header>
                      <soap:Body>
                        <m:GetFolder>
                          <m:FolderShape>
                            <t:BaseShape>IdOnly</t:BaseShape>
                          </m:FolderShape>
                          <m:FolderIds>
                            <t:DistinguishedFolderId Id="calendar" />
                          </m:FolderIds>
                        </m:GetFolder>
                      </soap:Body>
                    </soap:Envelope>""".format(self._soapHeader)

        # Request for ID and Key
        response = self._SendHttp(xmlbody)

        if isinstance(response, str):
            matchFolderInfo = regExFolderInfo.search(response)
            # Set FolderId and ChangeKey
            if matchFolderInfo:
                self._folderID = matchFolderInfo.group(1)
                self._changeKey = matchFolderInfo.group(2)

    def UpdateCalendarData(self):
        # gets the latest data for this week from exchange and stores it

        xmlbody = """<?xml version="1.0" encoding="utf-8"?>
                    <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                           xmlns:m="http://schemas.microsoft.com/exchange/services/2006/messages"
                           xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types"
                           xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                      <soap:Header>
                        {0}
                      </soap:Header>
                      <soap:Body>
                        <m:FindItem Traversal="Shallow">
                          <m:ItemShape>
                            <t:BaseShape>IdOnly</t:BaseShape>
                            <t:AdditionalProperties>
                              <t:FieldURI FieldURI="item:Subject" />
                              <t:FieldURI FieldURI="calendar:Start" />
                              <t:FieldURI FieldURI="calendar:End" />
                              <t:FieldURI FieldURI="calendar:Organizer" />
                              <t:FieldURI FieldURI="item:HasAttachments" />
                            </t:AdditionalProperties>
                          </m:ItemShape>
                          <m:CalendarView MaxEntriesReturned="100" StartDate="{1}" EndDate="{2}" />
                          <m:ParentFolderIds>
                            <t:FolderId Id="{3}" ChangeKey="{4}" />
                          </m:ParentFolderIds>
                        </m:FindItem>
                      </soap:Body>
                    </soap:Envelope>""".format(self._soapHeader, self._startOfWeek, self._endOfWeek, self._folderID,
                                               self._changeKey)
        #print('xtmbody=', xmlbody)
        response = self._SendHttp(xmlbody)
        #print('response=', response)
        #response now holds all the calendar events between startOfWeek and endOfWeek

        regexCalendarItem = re.compile('<t:CalendarItem>.*?<\/t:CalendarItem>')

        regexItemId = re.compile('<t:ItemId Id="(.*?)" ChangeKey="(.*?)"/>') #group(1) = itemID, group(2) = changeKey #within a CalendarItem
        regexSubject = re.compile('<t:Subject>(.*?)</t:Subject>') #within a CalendarItem
        regexHasAttachments = re.compile('<t:HasAttachments>(.{4,5})</t:HasAttachments>') #within a CalendarItem
        regexOrganizer = re.compile('<t:Organizer>.*<t:Name>(.*?)</t:Name>.*</t:Organizer>') #group(1)=Name #within a CalendarItem
        regexStartTime = re.compile('<t:Start>(.*?)</t:Start>') #group(1) = start time string #within a CalendarItem
        regextEndTime = re.compile('<t:End>(.*?)</t:End>')#group(1) = end time string #within a CalendarItem

        for matchCalItem in regexCalendarItem.finditer(response):
            #go thru the resposne and find any CalendarItems.
            #parse their data and create CalendarItem objects
            #store CalendarItem objects in self

            print('\nmatchCalItem.group(0)=', matchCalItem.group(0))

            data = {}
            startDT = None
            endDT = None

            matchItemId = regexItemId.search(matchCalItem.group(0))
            data['ItemId'] = matchItemId.group(1)
            data['ChangeKey'] = matchItemId.group(2)
            data['Subject'] = regexSubject.search(matchCalItem.group(0)).group(1)
            data['OrganizerName'] = regexOrganizer.search(matchCalItem.group(0)).group(1)

            res = regexHasAttachments.search(matchCalItem.group(0)).group(1)
            if 'true' in res:
                data['HasAttachments'] = True
            elif 'false' in res:
                data['HasAttachments'] = False
            else:
                data['HasAttachments'] = 'Unknown'

            startTimeString = regexStartTime.search(matchCalItem.group(0)).group(1)
            endTimeString = regextEndTime.search(matchCalItem.group(0)).group(1)

            startDT = ConvertTimeStringToDatetime(startTimeString)
            endDT = ConvertTimeStringToDatetime(endTimeString)

            calItem = _CalendarItem(startDT, endDT, data)
            self._AddCalendarItem(calItem)

    def _AddCalendarItem(self, calItem):
        '''
        This method will add the calendar item to self._calendarItems
        Making sure it is not duplicated and replacing any old data with new data
        :param calItem:
        :return:
        '''

        #Remove any CalendarItems that have ended in the past
        nowDT = datetime.datetime.now()
        for sub_calItem in self._calendarItems.copy():
            endDT = sub_calItem.Get('End')
            if endDT < nowDT:
                self._calendarItems.remove(sub_calItem)

        #Remove any old items that have the same ItemId
        itemId = calItem.Get('ItemId')

        for sub_calItem in self._calendarItems.copy():
            if sub_calItem.Get('ItemId') == itemId:
                self._calendarItems.remove(sub_calItem)

        #Add CalItem to self
        self._calendarItems.append(calItem)


    def CreateCalendarEvent(self, subject, body, startDT=None, endDT=None):

        startTimeString = ConvertDatetimeToTimeString(startDT)
        endTimeString = ConvertDatetimeToTimeString(endDT)

        xmlBody = """<?xml version="1.0" encoding="utf-8"?>
                    <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                           xmlns:m="http://schemas.microsoft.com/exchange/services/2006/messages"
                           xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types"
                           xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                      <soap:Header>
                        {0}
                      </soap:Header>
                      <soap:Body>
                        <m:CreateItem SendMeetingInvitations="SendToNone">
                          <m:Items>
                            <t:CalendarItem>
                              <t:Subject>{1}</t:Subject>
                              <t:Body BodyType="HTML">{2}</t:Body>
                              <t:Start>{3}</t:Start>
                              <t:End>{4}</t:End>
                            </t:CalendarItem>
                          </m:Items>
                        </m:CreateItem>
                      </soap:Body>
                    </soap:Envelope>""".format(self._soapHeader, subject, body, startTimeString, endTimeString)

        self._SendHttp(xmlBody)

    def GetCalendarItemByID(self, itemId):
        for calItem in self._calendarItems:
            if calItem.Get('ItemId') == itemId:
                return calItem

    # This function updates the end time of an event. Can be modified to update other functions
    # Was built to update end time for RoomAgent GS needs only
    def ChangeEventTime(self, calItem, newStartDT=None, newEndDT=None):

        timeUpdateXML = ''

        if newStartDT is not None:
            startTimeString = ConvertDatetimeToTimeString(newStartDT)
            timeUpdateXML += '<t:Start>{}</t:Start>'.format(startTimeString)

        if newEndDT is not None:
            endTimeString = ConvertDatetimeToTimeString(newEndDT)
            timeUpdateXML += '<t:End>{}</t:End>'.format(endTimeString)


        xmlBody = """<?xml version="1.0" encoding="utf-8"?>
                    <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:m="http://schemas.microsoft.com/exchange/services/2006/messages"
                           xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                      <soap:Header>
                        {0}
                      </soap:Header>
                      <soap:Body>
                        <m:UpdateItem MessageDisposition="SaveOnly" ConflictResolution="AlwaysOverwrite" SendMeetingInvitationsOrCancellations="SendToNone">
                          <m:ItemChanges>
                            <t:ItemChange>
                              <t:ItemId Id="{1}" ChangeKey="{2}" />
                              <t:Updates>
                                <t:SetItemField>
                                  <t:FieldURI FieldURI="calendar:End" />
                                  <t:CalendarItem>
                                    <t:End>{3}</t:End>
                                  </t:CalendarItem>
                                </t:SetItemField>
                              </t:Updates>
                            </t:ItemChange>
                          </m:ItemChanges>
                        </m:UpdateItem>
                      </soap:Body>
                    </soap:Envelope> """.format(self._soapHeader, calItem.Get('ItemId'), calItem.Get('ChangeKey'), timeUpdateXML)

        self._SendHttp(xmlBody)

    def DeleteEvent(self, calItem):

        xmlBody = """<?xml version="1.0" encoding="utf-8"?>
                    <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                           xmlns:m="http://schemas.microsoft.com/exchange/services/2006/messages"
                           xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types"
                           xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                      <soap:Header>
                        {0}
                      </soap:Header>
                      <soap:Body>
                        <m:DeleteItem DeleteType="HardDelete" SendMeetingCancellations="SendToNone">
                          <m:ItemIds>
                            <t:ItemId Id="{1}" ChangeKey="{2}" />
                          </m:ItemIds>
                        </m:DeleteItem>
                      </soap:Body>
                    </soap:Envelope>""".format(self._soapHeader,  calItem.Get('ItemId'), calItem.Get('ChangeKey'))

        request = self._SendHttp(xmlBody)

    def _AttachmentHelper(self, attachmentIDs):
        # returns a list of _Attachment objects

        regExReponse = re.compile(r'<m:ResponseCode>(.+)</m:ResponseCode>')
        regExName = re.compile(r'<t:Name>(.+)</t:Name>')
        regExContentType = re.compile(r'<t:ContentType>(.+)</t:ContentType>')
        regExContent = re.compile(r'<t:Content>(.+)</t:Content>')
        attachmentObjects = []

        for i, attachmentID in enumerate(attachmentIDs):
            xmlBody = """<?xml version="1.0" encoding="utf-8"?>
                            <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                                           xmlns:m="http://schemas.microsoft.com/exchange/services/2006/messages"
                                           xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types"
                                           xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                              <soap:Header>
                                {0}
                              </soap:Header>
                              <soap:Body>
                                <m:GetAttachment>
                                  <m:AttachmentIds>
                                    <t:AttachmentId Id="{1}" />
                                  </m:AttachmentIds>
                                </m:GetAttachment>
                              </soap:Body>
                            </soap:Envelope>""".format(self._soapHeader, attachmentID)

            request = self._SendHttp(xmlBody)

            responseCode = regExReponse.search(request).group(1)
            if responseCode == 'NoError':  # Handle errors sent by the server
                itemName = regExName.search(request).group(1)
                itemContent = regExContent.search(request).group(1)
                itemContentType = regExContentType.search(request).group(1)

                newAttachementObject = _Attachment(itemName, attachmentID, self)
                attachmentObjects.append(newAttachementObject)

            else:
                print('An error occurred requesting the attachment: {}'.format(responseCode))
                return
        return attachmentObjects

    def GetAttachments(self, calItem):
        #returns a list of _Attachment objects

        itemId = calItem.Get('ItemId')
        regExAttKey = re.compile(r'AttachmentId Id=\"(.+)\"')
        xmlBody = """<?xml version="1.0" encoding="utf-8"?>
                        <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                                       xmlns:m="http://schemas.microsoft.com/exchange/services/2006/messages"
                                       xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types"
                                       xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                          <soap:Header>
                            {0}
                          </soap:Header>
                          <soap:Body>
                            <m:GetItem>
                              <m:ItemShape>
                                <t:BaseShape>IdOnly</t:BaseShape>
                                <t:AdditionalProperties>
                                  <t:FieldURI FieldURI="item:Attachments" />
                                  <t:FieldURI FieldURI="item:HasAttachments" />
                                </t:AdditionalProperties>
                              </m:ItemShape>
                              <m:ItemIds>
                                <t:ItemId Id="{1}" />
                              </m:ItemIds>
                            </m:GetItem>
                          </soap:Body>
                        </soap:Envelope>""".format(self._soapHeader, itemId)

        response = self._SendHttp(xmlBody)
        attachmentIdList = regExAttKey.findall(response)
        return self._AttachmentHelper(attachmentIdList)

    # ----------------------------------------------------------------------------------------------------------------------
    # -----------------------------------------------Time Zone Handling-----------------------------------------------------
    # ----------------------------------------------------------------------------------------------------------------------

    def timeZone(self, tzID):

        offSets = {
            "UTC-12:00": 12,
            "UTC-11:00": 11,
            "UTC-10:00": 10,
            "UTC-09:00": 9, "UTC-09:30": [9, 30],
            "UTC-08:00": 8,
            "UTC-07:00": 7,
            "UTC-06:00": 6,
            "UTC-05:00": 5,
            "UTC-04:00": 4, "UTC-04:30": [4, 30],
            "UTC-03:00": 3, "UTC-03:30": [3, 30],
            "UTC-02:00": 2,
            "UTC-01:00": 1,
            "UTC+00:00": 0,
            "UTC+01:00": -1,
            "UTC+02:00": -2,
            "UTC+03:00": -3,
            "UTC+04:00": -4, "UTC+04:30": [-4, -30],
            "UTC+05:00": -5, "UTC+05:30": [-5, -30], "UTC+05:45": [-5, -45],
            "UTC+06:00": -6,
            "UTC+07:00": -7,
            "UTC+08:00": -8,
            "UTC+09:00": -9, "UTC+09:30": [-9, -30],
            "UTC+10:00": -10, "UTC+10:30": [-10, -30],
            "UTC+11:00": -11, "UTC+11:30": [-11, -30],
            "UTC+12:00": -12, "UTC+12:45": [-12, -45],
            "UTC+13:00": -13,
            "UTC+14:00": -14
        }

        try:
            if self.daylightSavings == True:
                return datetime.timedelta(hours=offSets[tzID][0] - 1, minutes=offSets[tzID][1])
            else:
                return datetime.timedelta(hours=offSets[tzID][0], minutes=offSets[tzID][1])
        except Exception as e:
            if self.daylightSavings == True:
                return datetime.timedelta(hours=offSets[tzID] - 1)
            else:
                return datetime.timedelta(hours=offSets[tzID])

                # ----------------------------------------------------------------------------------------------------------------------
                # -------------------------------------------------HTTP Request---------------------------------------------------------
                # ----------------------------------------------------------------------------------------------------------------------

    def _SendHttp(self, body):

        body = body.encode()
        request = urllib.request.Request(self.httpURL, body, self.header, method='POST')

        try:
            out = urllib.request.urlopen(request)
            if out:
                return (out.read().decode())
        except Exception as e:
            print(e)

            # ----------------------------------------------------------------------------------------------------------------------
            # ------------------------------------------------Return Request--------------------------------------------------------
            # ----------------------------------------------------------------------------------------------------------------------

    def GetAllEvents(self):
        return self._calendarItems.copy()

    def GetMeetingData(self, dt=None):
        #dt = datetime.date or datetime.datetime
        # return a list of events that occur on datetime.date or at datetime.datetime
        if dt is None:
            dt = datetime.datetime.now()

        events = []

        for calItem in self._calendarItems.copy():
            if dt in calItem:
                events.append(calItem)

        return events

    def GetNowCalItem(self):
        #returns list of calendar items happening now

        returnCalItems = []

        nowDT = datetime.datetime.now()

        for calItem in self._calendarItems.copy():
            if nowDT in calItem:
                returnCalItems.append(calItem)

        return returnCalItems

    def GetNextCalItem(self):
        #return a list CalendarItems
        #will not return events happening now. only the nearest future events
        #if multiple events start at the same time, all CalendarItems will be returned

        nowDT = datetime.datetime.now()

        nextDT = None
        for calItem in self._calendarItems.copy():
            startDT = calItem.Get('Start')
            if startDT > nowDT: #its in the future
                if nextDT is None or startDT < nextDT: #its sooner than the previous soonest one. (Wha!?)
                    nextDT = startDT

        if nextDT is None:
            return [] #no events in the future
        else:
            returnCalItems = []
            for calItem in self._calendarItems.copy():
                if nextDT in calItem:
                    returnCalItems.append(calItem)
            return returnCalItems

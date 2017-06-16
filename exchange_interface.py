import urllib.request, re
from base64 import b64encode, b64decode
import datetime, copy

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
testCalendar.UpdateCalendar()
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


class Exchange():
    def __init__(self, server, username, password, service, timeZone, daylightSaving=True, impersonation=None):
        self.service = service
        self.daylightSavings = daylightSaving
        self.timeZoneOffset = self.timeZone(timeZone)
        self.httpURL = 'https://{0}/EWS/exchange.asmx'.format(server)
        self.encode = b64encode(bytes('{0}:{1}'.format(username, password), "ascii"))
        self.login = str(self.encode)[2:-1]
        self.header = {'content-type': 'text/xml; charset=utf-8',
                       'Authorization': 'Basic {}'.format(self.login)
                       }
        self.calendarData = {'Mon': {}, 'Tue': {}, 'Wed': {}, 'Thu': {}, 'Fri': {}, 'Sat': {}, 'Sun': {}}
        self.generateCalData()  # Populates calendarData dictionary
        self.FolderID = None
        self.ChangeKey = None
        self.startOfWeek = None
        self.endOfWeek = None
        self.soapHeader = self.setSoapHeader(impersonation)
        self.requestIdKey('calendar')  # For future Calendar select

    # ----------------------------------------------------------------------------------------------------------------------
    # --------------------------------------------Time and DB Management----------------------------------------------------
    # ----------------------------------------------------------------------------------------------------------------------

    # Calculates the dates of the week and the first day and last day of the week
    def generateWeek(self):
        day = datetime.datetime.today()
        start = day - datetime.timedelta(days=day.weekday() + 1)
        end = start + datetime.timedelta(days=6)
        workingDate = ''
        calendarDays = []
        for t in range(0, 7):
            workingDate = start + datetime.timedelta(days=t)
            calendarDays.append(workingDate.strftime('%Y-%m-%d'))

        self.calendarData['Mon']['Date'] = calendarDays[1]
        self.calendarData['Tue']['Date'] = calendarDays[2]
        self.calendarData['Wed']['Date'] = calendarDays[3]
        self.calendarData['Thu']['Date'] = calendarDays[4]
        self.calendarData['Fri']['Date'] = calendarDays[5]
        self.calendarData['Sat']['Date'] = calendarDays[6]
        self.calendarData['Sun']['Date'] = calendarDays[0]

        self.startOfWeek = start.strftime('%Y-%m-%d') + 'T00:01:00Z'
        self.endOfWeek = end.strftime('%Y-%m-%d') + 'T23:59:00Z'

    # Creates all the calendar data and Expands the dictionary
    def generateCalData(self):
        timeMinDel = datetime.timedelta(minutes=5)
        timeHouDel = datetime.timedelta(hours=12)
        times = {'Date': '', 'Time': {}}
        timetag = 'AM'

        startTime = datetime.datetime(year=2016, month=1, day=1, hour=11, minute=30)
        for i in range(0, 288):

            if i == 17:
                startTime = startTime + timeMinDel - timeHouDel
            elif i == 144:
                timetag = 'PM'
                startTime = startTime + timeMinDel
            elif i == 161:
                startTime = startTime + timeMinDel - timeHouDel
            else:
                startTime = startTime + timeMinDel

            # Gets rid of the 0 in front or not
            if str(startTime.time())[0] == '0':
                shiftCut = 1
            else:
                shiftCut = 0

            times['Time'].update({str(startTime.time())[shiftCut:5] + timetag: None})

        # Places the time inside the dates
        for n in self.calendarData:
            self.calendarData[n] = copy.deepcopy(times)

    # Internal clock system, returns current time and following times in selected time interval form of a List
    def currentTimeslotPlus(self, slot):
        timeTAG = ''
        shiftCut = 0
        timeChangeFlag = False
        initialtime = datetime.datetime.now()
        timeHouDel = datetime.timedelta(hours=12)
        timeMinDel = datetime.timedelta(minutes=slot)
        activeTimes = ['', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '',
                       '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '']

        if int(str(initialtime.time())[0:2]) >= 12:
            timeTAG = 'PM'
            if int(str(initialtime.time())[0:2]) == 12:
                initialtime = initialtime - datetime.timedelta(
                    minutes=abs(int(str(initialtime.time())[3:5]) % slot))
            else:
                initialtime = initialtime - timeHouDel - datetime.timedelta(
                    minutes=abs(int(str(initialtime.time())[3:5]) % slot))
        else:
            timeTAG = 'AM'
            if str(initialtime.time())[0:2] == '00':
                initialtime = initialtime + timeHouDel - datetime.timedelta(
                    minutes=abs(int(str(initialtime.time())[3:5]) % slot))
            else:
                initialtime = initialtime - datetime.timedelta(
                    minutes=abs(int(str(initialtime.time())[3:5]) % slot))

        if str(initialtime.time())[0] == '0' and str(initialtime.time())[1] != '0':
            shiftCut = 1
        else:
            shiftCut = 0

        activeTimes[0] = str(initialtime.time())[shiftCut:5] + timeTAG

        for n in range(1, 40):
            # Increments by designed
            initialtime = initialtime + timeMinDel

            if int(str(initialtime.time())[0:2]) > 12:
                initialtime = initialtime - timeHouDel
            elif int(str(initialtime.time())[0:2]) == 12 and activeTimes[0][
                                                             0:5] == '12:00' and timeChangeFlag != True:
                timeChangeFlag = True
            elif int(str(initialtime.time())[0:2]) == 12 and timeChangeFlag != True:
                timeChangeFlag = True
                if timeTAG == 'AM':
                    timeTAG = 'PM'
                else:
                    timeTAG = 'AM'
            elif timeChangeFlag == True and int(str(initialtime.time())[0:2]) == 11:
                timeChangeFlag = False

            if str(initialtime.time())[0] == '0' and str(initialtime.time())[1] != '0':
                shiftCut = 1
            else:
                shiftCut = 0

            activeTimes[n] = str(initialtime.time())[shiftCut:5] + timeTAG

        return activeTimes

    # ----------------------------------------------------------------------------------------------------------------------
    # --------------------------------------------------EWS Services--------------------------------------------------------
    # ----------------------------------------------------------------------------------------------------------------------
    def setSoapHeader(self, account):
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

    # Requests Service for ID of calendar folder and change key
    def requestIdKey(self, calendar):
        # Regular Expressions to Parce needed data
        regEx = re.compile(r't:FolderId Id=\"(.{1,})\" ChangeKey=\"(.{1,})\"\/')

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
                    </soap:Envelope>""".format(self.soapHeader)

        # Request for ID and Key
        request = self.httpRequest(xmlbody)

        if isinstance(request, str):
            match = regEx.search(request)
            # Set FolderId and ChangeKey
            if match:
                self.FolderID = match.group(1)
                self.ChangeKey = match.group(2)

    # Updates the CalData Dictionary with current Calendar
    def UpdateCalendar(self):
        # gets the latest data for this week from exchange and stores it internally

        # Regular Expressions for finding events
        regExItemId = re.compile(r'<t:ItemId Id=.{1,}?</t:Name>')
        # Regular Expression for parsing event data
        regExEventInfo = re.compile(
            r'<t:ItemId Id=\"(.{1,}?)\".{1,}<t:Subject>(.{1,}?)</t:Subject><t:HasAttachments>.{4,5}</t:HasAttachments><t:Start>(.{1,}?)</t:Start><t:End>(.{1,}?)</t:End>')
        # Regular expression to find Event Organizer
        regExOrg = re.compile(r'<t:Name>(.{1,}?)</t:Name>')
        # Regular expression to fing event change key
        regExCKey = re.compile(r'ChangeKey=\"(.{1,})\"/')
        regExHasAttachments = re.compile('\<t:HasAttachments\>(.{4,5})\</t:HasAttachments\>')
        timetag = ['AM', 'PM']

        self.generateWeek()

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
                    </soap:Envelope>""".format(self.soapHeader, self.startOfWeek, self.endOfWeek, self.FolderID,
                                               self.ChangeKey)
        # Http response for events

        response = self.httpRequest(xmlbody)
        print('response=', response
              )
        # Pull events out of XML
        if True: #try:
            matchesAllItems = regExItemId.findall(response)

            # Clear the calendar Data
            for days in self.calendarData:
                for times in self.calendarData[days]['Time']:
                    self.calendarData[days]['Time'][times] = None

            for matchItem in matchesAllItems:

                # Clean package to organize events into Dictionary
                timeList = []
                initialTime = None
                processTime = True
                package = {'Name': '',  # Done
                           'Event_ID': '',  # Done
                           'Event_CKey': '',
                           'Organizer': '',  # Done
                           'StartDate': '',
                           'EndDate': '',
                           'StartDay': '',
                           'EndDay': '',
                           'StartTime': '',
                           'EndTime': '',
                           'Has Attachments': False,
                           }

                # Sort Matches into Event information into different groups
                # 1:Event Subject 2:StartTime 3:Endtime
                matchEventInfo = regExEventInfo.search(matchItem)
                matchOrginization = regExOrg.search(matchItem)
                matchChangeKey = regExCKey.search(matchItem)
                matchHasAttachments = regExHasAttachments.search(matchItem)

                # PackageBuilder and Added to Dictionary
                package['Name'] = matchEventInfo.group(2)
                package['Organizer'] = matchOrginization.group(1)
                package['Event_ID'] = matchEventInfo.group(1)
                package['Event_CKey'] = matchChangeKey.group(1)
                if matchHasAttachments is not None:
                    if 'true' in matchHasAttachments.group(1):
                        package['Has Attachments'] = True
                    elif 'false' in matchHasAttachments.group(1):
                        package['Has Attachments'] = False

                workingStarttime = datetime.datetime(year=int(matchEventInfo.group(3)[0:4]),
                                                     month=int(matchEventInfo.group(3)[5:7]),
                                                     day=int(matchEventInfo.group(3)[8:10]),
                                                     hour=int(matchEventInfo.group(3)[11:13]),
                                                     minute=(int(matchEventInfo.group(3)[14:16]) - int(
                                                         matchEventInfo.group(3)[14:16]) % 30)) - self.timeZoneOffset

                workingEndtime = datetime.datetime(year=int(matchEventInfo.group(4)[0:4]),
                                                   month=int(matchEventInfo.group(4)[5:7]),
                                                   day=int(matchEventInfo.group(4)[8:10]),
                                                   hour=int(matchEventInfo.group(4)[11:13]),
                                                   minute=int(matchEventInfo.group(4)[14:16]) - int(
                                                       matchEventInfo.group(4)[14:16]) % 30) - self.timeZoneOffset

                package['StartDate'] = str(workingStarttime)[0:10]
                package['EndDate'] = str(workingEndtime)[0:10]

                try:
                    if int(str(workingStarttime)[11:13]) > 12:
                        package['StartTime'] = str(int(str(workingStarttime)[11:13]) - 12) + str(workingStarttime)[
                                                                                             13:16] + \
                                               timetag[1]
                    elif int(str(workingStarttime)[11:13]) == 12:
                        package['StartTime'] = str(workingStarttime)[11:16] + timetag[1]
                    else:
                        if str(workingStarttime)[11:13] == '00':
                            package['StartTime'] = '12' + str(workingStarttime)[13:16] + timetag[0]
                        elif str(workingStarttime)[11] == '0' and str(workingStarttime)[12] != '0':
                            package['StartTime'] = str(workingStarttime)[12:16] + timetag[0]
                        else:
                            package['StartTime'] = str(workingStarttime)[11:16] + timetag[0]
                except Exception as e:
                    r = e

                try:
                    if int(str(workingEndtime)[11:13]) > 12:
                        package['EndTime'] = str(int(str(workingEndtime)[11:13]) - 12) + str(workingEndtime)[13:16] + \
                                             timetag[1]
                    elif int(str(workingEndtime)[11:13]) == 12:
                        package['EndTime'] = str(workingEndtime)[11:16] + timetag[1]
                    else:
                        if str(workingEndtime)[11:13] == '00':
                            package['EndTime'] = '12' + str(workingEndtime)[13:16] + timetag[0]
                        elif str(workingEndtime)[11] == '0' and str(workingEndtime)[12] != '0':
                            package['EndTime'] = str(workingEndtime)[12:16] + timetag[0]
                        else:
                            package['EndTime'] = str(workingEndtime)[11:16] + timetag[0]
                except Exception as e:
                    r = e
                # Tells what day of the week


                package['StartDay'] = datetime.date(year=int(package['StartDate'][0:4]),
                                                    month=int(package['StartDate'][5:7]),
                                                    day=int(package['StartDate'][8:10])).strftime('%a')
                package['EndDay'] = datetime.date(year=int(package['EndDate'][0:4]), month=int(package['EndDate'][5:7]),
                                                  day=int(package['EndDate'][8:10])).strftime('%a')

                # Convert start time into time slots
                # Start Times
                try:
                    initialTime = datetime.datetime(2000, 1, 1, hour=int(package['StartTime'][0:1]),
                                                    minute=int(package['StartTime'][2:4]))
                    workingTag = package['StartTime'][4:6]
                except Exception as e:
                    r = e
                try:
                    initialTime = datetime.datetime(2000, 1, 1, hour=int(package['StartTime'][0:2]),
                                                    minute=int(package['StartTime'][3:5]))
                    workingTag = package['StartTime'][5:7]
                except Exception as e:
                    r = e

                timeList.append(package['StartTime'])

                if package['StartTime'] != package['EndTime']:
                    while processTime is True:

                        trimCut = 0
                        initialTime += datetime.timedelta(minutes=5)

                        if int(str(initialTime.time())[0:2]) > 12:
                            initialTime -= datetime.timedelta(hours=12)

                        if str(initialTime.time())[0:5] == '12:00':
                            if workingTag == 'AM':
                                workingTag = 'PM'
                            else:
                                workingTag = 'AM'

                        if str(initialTime.time())[0] == '0' and str(initialTime.time())[1] != '0':
                            trimCut = 1
                        else:
                            trimCut = 0

                        if str(initialTime.time())[trimCut:5] + workingTag == package['EndTime']:

                            processTime = False
                        else:
                            timeList.append(str(initialTime.time())[trimCut:5] + workingTag)

                for timeslots in timeList:  # timeList is a list of str like '6:45PM'
                    self.calendarData[package['StartDay']]['Time'][timeslots] = package

        else: #except Exception as e:
            print(e, 'Can not access Account')

    def startEndTimeCalc(self, duration, selectedTime=None, date=None):

        meetingLength = {'30': 30,
                         '1:00': 60,
                         '1:30': 90,
                         '2:00': 120,
                         '2:30': 150,
                         '3:00': 180
                         }

        addtime = datetime.timedelta(minutes=meetingLength[duration])

        if selectedTime[len(selectedTime) - 2:] == 'PM':
            if selectedTime[:2] == '12':
                timeConvert = datetime.timedelta(hours=0)
            else:
                timeConvert = datetime.timedelta(hours=12)
        else:
            if selectedTime[:2] == '12':
                timeConvert = datetime.timedelta(hours=-12)
            else:
                timeConvert = datetime.timedelta(hours=0)

        if len(selectedTime) == 6:
            minutes = selectedTime[2:-2]
        else:
            minutes = selectedTime[3:-2]

        if date == None:
            date = str(datetime.datetime.today().now())

        workingStartTime = datetime.datetime(year=int(date[0:4]), month=int(date[5:7]),
                                             day=int(date[8:10]), hour=int(selectedTime[:-5]),
                                             minute=int(minutes)) + self.timeZoneOffset + timeConvert

        workingEndTime = str(workingStartTime + addtime).replace(' ', 'T') + 'Z'
        workingStartTime = str(workingStartTime).replace(' ', 'T') + 'Z'

        return workingStartTime, workingEndTime

    # Creates Adhoc Event
    def setCreateEvent(self, subject, body, duration=None, date=None, startTime=None, endTime=None):

        if duration != None:
            workingStartTime, workingEndTime = self.startEndTimeCalc(duration, startTime, date)
        else:
            workingStartTime, nill = self.startEndTimeCalc('30', startTime, date)
            workingEndTime, nill = self.startEndTimeCalc('30', endTime, date)

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
                    </soap:Envelope>""".format(self.soapHeader, subject, body, workingStartTime, workingEndTime)

        self.httpRequest(xmlBody)

    # This function updates the end time of an event. Can be modified to update other functions
    # Was built to update end time for RoomAgent GS needs only
    def SetUpdateEventEndtime(self, itemId, itemCKey, oldEnd, duration):

        workingStartTime, workingEndTime = self.startEndTimeCalc(duration, oldEnd)

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
                    </soap:Envelope> """.format(self.soapHeader, itemId, itemCKey, workingEndTime)

        self.httpRequest(xmlBody)

    def setDeleteEvent(self, itemId, itemCkey):

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
                    </soap:Envelope>""".format(self.soapHeader, itemId, itemCkey)

        request = self.httpRequest(xmlBody)

    def _attachmentHelper(self, attachmentID):
        # Compile regex for different XML components
        regExReponse = re.compile(r'<m:ResponseCode>(.+)</m:ResponseCode>')
        regExName = re.compile(r'<t:Name>(.+)</t:Name>')
        regExContentType = re.compile(r'<t:ContentType>(.+)</t:ContentType>')
        regExContent = re.compile(r'<t:Content>(.+)</t:Content>')
        attData = {}
        # Check for multiple attachments and parse the responses, then store
        # them in a dict
        for i, attachment in enumerate(attachmentID):
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
                            </soap:Envelope>""".format(self.soapHeader, attachmentID[i])

            request = self.httpRequest(xmlBody)
            responseCode = regExReponse.search(request).group(1)
            if responseCode == 'NoError':  # Handle errors sent by the server
                itemName = regExName.search(request).group(1)
                itemContent = regExContent.search(request).group(1)
                itemContentType = regExContentType.search(request).group(1)
                attData['Attachment{}'.format(i + 1)] = {'Name': '{}'.format(itemName),
                                                         'Content-Type': '{}'.format(itemContentType),
                                                         'Content': '{}'.format(itemContent)}
            else:
                print('An error occurred requesting the attachment: {}'.format(responseCode))
                return
        return attData

    def getAttachment(self, itemID):
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
                        </soap:Envelope>""".format(self.soapHeader, itemID)

        request = self.httpRequest(xmlBody)
        print(request)
        attachmentList = regExAttKey.findall(request)
        return self._attachmentHelper(attachmentList)

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

    def httpRequest(self, body):

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

    def GetWeekData(self):
        # returns a dict like
        return self.calendarData

    def GetMeetingData(self, *args):
        # return a dict of calendar event data, or return None
        # day = str like 'Mon', 'Tue', etc
        # time = str like '5:30PM'

        if len(args) == 1: #probably a datetime.datetime object
            dt = args[0]
            if dt is None:
                return None
            day = dt.strftime('%a')
            time = dt.strftime('%I:%M%p')
        else: #assuming they are passing day, time
            day = args[0]
            time = args[1]

        return self.calendarData[day]['Time'][time]

    def HasAttachment(self, dt):
        #dt = datetime.datetime object
        eventInfo = self.GetMeetingData(dt)
        return eventInfo['Has Attachments']

    def GetMeetingAttachment(self, day, time):
        # Returns a dictionary with the meeting's attachment content,
        # content-type, and filename, if it exists.
        if 'Event_ID' in self.calendarData[day]['Time'][time]:
            return self.getAttachment(self.calendarData[day]['Time'][time]['Event_ID'])
        else:
            return None

    def GetNextEventDatetime(self):

        weekDayOrder = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat',
                        'Sun', ]  # TODO: may need to reconsider this assumption
        nowDT = datetime.datetime.now()
        startDay = nowDT.strftime('%a')
        startIndex = weekDayOrder.index(startDay)

        weekData = self.GetWeekData().copy()

        firstEventDT = None

        for dayStr in weekDayOrder[startIndex:]:
            for timeStr in weekData[dayStr]['Time']:
                event = weekData[dayStr]['Time'][timeStr]
                if event is not None:
                    eventDTstring = weekData[dayStr]['Date']
                    year, month, day = eventDTstring.split('-')
                    year = int(year)
                    month = int(month)
                    day = int(day)

                    hour, etc = timeStr.split(':')
                    hour = int(hour)
                    minute = int(etc[:2])
                    ampm = etc[-2:]

                    if ampm == 'PM' and hour is not 12:
                        hour += 12

                    eventDT = datetime.datetime(year=year, month=month, day=day, hour=hour, minute=minute)

                    if eventDT > nowDT:  # The event is in the future
                        if firstEventDT is None or eventDT < firstEventDT:
                            firstEventDT = eventDT

        return firstEventDT

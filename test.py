import exchange_interface
import exchange_credentials
from base64 import b64decode

exchange = exchange_interface.Exchange(
    server='outlook.office365.com',
    #username='z-365-confrm1.1@extron.com',
    #password='Extron1025',
    username=exchange_credentials.username,
    password=exchange_credentials.password,
    service='Office365',
    timeZone="UTC-05:00",
    daylightSaving=True,
    impersonation=None,
    )
exchange.UpdateCalendar()
print(exchange.GetWeekData())
print()

print('GetMeetingData=', exchange.GetMeetingData('Thu', '6:00PM'))
print()
Attachment = exchange.GetMeetingAttachment('Thu', '6:00PM')
attContent = b64decode(Attachment['Attachment1']['Content'])
#attType = b64decode(Attachment['Attachment1']['ContentType'])

fType = {'video/mp4': '.mp4',
         'text/plain': '.txt',
         'text/xml': '.xml',
         # ...
         'audio/mp4': '.mp4'}

fName = 'C:\\Users\\gmiller\\Desktop\\myfile.mp4'
with open(fName, 'wb') as f:
    f.write(attContent)


#print('\ncontentDict=', contentDict)

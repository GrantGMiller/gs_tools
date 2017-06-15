import exchange_interface
import exchange_credentials
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
contentDict = exchange.GetMeetingAttachment('Thu', '6:00PM')

#print('\ncontentDict=', contentDict)

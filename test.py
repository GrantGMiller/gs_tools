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
#print(exchange.GetWeekData())
print()

print(exchange.GetMeetingData('Tue', '9:00AM'))

contentDict = exchange.GetMeetingAttachment('Tue', '9:00AM')
print('\ncontentDict=', contentDict)

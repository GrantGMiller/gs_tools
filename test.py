import exchange_interface 
exchange = exchange_interface.Exchange(
    server='outlook.office365.com',
    username='z-365-confrm1.1@extron.com',
    password='Extron1025',
    service='Office365',
    timeZone="UTC-05:00",
    daylightSaving=True,
    impersonation=None,
    )
exchange.UpdateCalendar()
#print(exchange.GetWeekData())
print()

print(exchange.GetMeetingData('Fri', '10:00AM'))

contentDict = exchange.GetMeetingAttachment('Fri', '10:00AM')
print('contentDict=', contentDict)

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

eventDict = exchange.GetMeetingData('Tue', '5:30PM')
print('eventDict=', eventDict)

path = 'C:\\Users\\gmiller\\Desktop\\Grants GUIs\\GS Modules\\SMD Manager\\test.data'
exchange.GetEventAttachment(
    eventDict['ItemId'],
    eventDict['ChangeKey'],
    path,
)

import exchange_interface 
testCalendar = exchange_interface.Exchange(
    server='outlook.office365.com',
    username='z-365-confrm1.1@extron.com',
    password='Extron1025',
    service='Office365',
    timeZone="UTC-05:00",
    daylightSaving=True,
    impersonation=None,
    )
testCalendar.UpdateCalendar()
print(testCalendar.GetWeekData())
print()
print('Tue at 5PM:', testCalendar.GetMeetingData('Tue', '5:00PM'))
import exchange_interface
import exchange_credentials
from base64 import b64decode

exchange = exchange_interface.Exchange(
    server='outlook.office365.com',
    # username='z-365-confrm1.1@extron.com', #Fake room agent account
    # password='Extron1025',
    username=exchange_credentials.username,
    password=exchange_credentials.password,
    service='Office365',
    timeZone="UTC-05:00",
    daylightSaving=True,
    impersonation=None,
)

exchange.UpdateCalendar()
#print('exchange.GetWeekData()=', exchange.GetWeekData())

nextDT = exchange.GetNextEventDatetime()
print('nextDT=', nextDT)
print('exchange.GetMeetingData(nextDT)=', exchange.GetMeetingData(nextDT))
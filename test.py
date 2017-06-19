import exchange_interface
import exchange_credentials
import datetime
import time

exchange = exchange_interface.Exchange(
    server='outlook.office365.com',
    # username='z-365-confrm1.1@extron.com', #Fake room agent account
    # password='Extron1025',
    username=exchange_credentials.username,
    password=exchange_credentials.password,
    service='Office365',
)

folderPath = 'C:\\Users\\gmiller\\Desktop\\Grants GUIs\\GS Modules\\SMD Manager\\Test Files\\'

exchange.UpdateCalendar()
print('GetEventAtTime')
for calItem in exchange.GetEventAtTime(datetime.datetime(year=2017, month=6, day=19, hour=10)):
    print(calItem)
    attachments = calItem.GetAttachments()
    for attachment in attachments:
        attachment.SaveToPath('{}{}.png'.format(folderPath, int(time.time())))
#print('GetNextCalItems')
#for item in exchange.GetNextCalItems():
    #print(item)
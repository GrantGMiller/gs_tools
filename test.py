import exchange_interface
import exchange_credentials
import datetime

ex = exchange_interface.Exchange(
    server='outlook.office365.com',
    username=exchange_credentials.username,
    password=exchange_credentials.password,

)

ex.UpdateCalendar()
ex.CreateCalendarEvent('Test Subject', 'Test Body', startDT=datetime.datetime.now(), endDT=datetime.datetime.now() + datetime.timedelta(hours=1))

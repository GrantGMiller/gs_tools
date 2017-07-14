import exchange_credentials
import exchange_interface

exchange = exchange_interface.Exchange(
    username=exchange_credentials.username,
    password=exchange_credentials.password,
)

exchange.UpdateCalendar(calendar='rnc-conf-sales@extron.com')

items = exchange.GetNextCalItems()
for item in items:
    print(item._data)

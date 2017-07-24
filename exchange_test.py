import exchange_credentials
import exchange_interface

exchange = exchange_interface.Exchange(
    username=exchange_credentials.username,
    password=exchange_credentials.password,
)

exchange.UpdateCalendar(calendar=None)

items = exchange.GetNextCalItems()
for item in items:
    itemId = item.Get('ItemId')
    changeKey = item.Get('ChangeKey')

    exchange.GetItem(itemId, changeKey)
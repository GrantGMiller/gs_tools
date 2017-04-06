from gs_tools import phone_format

test = '918006339876*#'

for i in range(len(test)):
    phone_format(test[:i])

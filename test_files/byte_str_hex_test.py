from gs_tools import StringToBytes, BytesToString, BytesToInt, HexIntToChr, Unquote

# b = StringToBytes('hello world')
# print('b=', b)
#
# s = BytesToString(b)
# print('s=', s)
#
# i = BytesToInt(b)
# print('i=', i)
#
# c = HexIntToChr(22)
# print('c=', c)

print(Unquote('http%3A%2F%2Fwww.codebygrant.com%2FResume%2Findex.html'))
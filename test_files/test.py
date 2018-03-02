import json
def pprint(*args):
    print('\r\n'.join([json.dumps(item, indent=2) for item in args]))


d = {}
for i in range(3):
    d[i] = str(i)

l = [i for i in range(3)]


pprint(d, l, 'string', int(5), float(10))
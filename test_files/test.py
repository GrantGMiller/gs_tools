import json

def pprint(*args):
    print('\r\n'.join([json.dumps(item, indent=2) for item in args]))


d = {}
for i in range(10):
    d[i] = str(i)

l = [i for i in range(10)]
print('d=', d)
print('l=', l)

pprint(d, l, 'string', int(5), float(10))
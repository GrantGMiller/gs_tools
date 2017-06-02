from extronlib.interface import EthernetClientInterface

clients = []

for i in range(256):
    print('i=', i)
    NewClient = EthernetClientInterface('10.166.100.4', 3000)
    res = NewClient.Connect()
    print('{} res = {}'.format(i, res))
    NewClient.Send('Hello from {}'.format(i))
    clients.append(NewClient)

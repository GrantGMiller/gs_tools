from extronlib.interface import EthernetClientInterface
from extronlib.system import Wait
from extronlib import event
import time

client = EthernetClientInterface('10.8.27.104', 3888)

@event(client, ['Connected', 'Disconnected'])
def Connectionhandler(client, state):
    print(client, state)

@event(client, 'ReceiveData')
def RxData(client, data):
    print('client={}, data={}'.format(client, data))

client.Connect()

while True:
    client.Send('wct\r')
    time.sleep(0.9)
from extronlib import event
from extronlib.interface import EthernetServerInterfaceEx


def DirectPort(ComPort, IPPort):
    '''
    This function creates a Server that listens for connections on the IPPort.
    Any data received on the Server will be sent out the ComPort.Send
    Any data received on the ComPort will be sent out the Server.Send
    '''
    Server = EthernetServerInterfaceEx(IPPort, MaxClients=1)
    result = Server.StartListen()
    print('Server {}'.format(result))

    @event(Server, 'Connected')
    @event(Server, 'Disconnected')
    def ServerConnectionEvent(client, state):
        print('Client {}:{} {}'.format(client.IPAddress, client.ServicePort, state))

    @event(Server, 'ReceiveData')
    def ServerRxDataEvent(client, data):
        '''
        If the programmer wished to parse the data coming through the port,
            this is the place to do it.

        Example:
        if b'Important Info' in data:
            DoSomething()
        '''

        ComPort.Send(data)

    @event(ComPort, 'ReceiveData')
    def ComPortRxDataEvent(interface, data):
        for client in Server.Clients:
            client.Send(data)



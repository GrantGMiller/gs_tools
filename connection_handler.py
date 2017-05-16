from extronlib.interface import (
    SerialInterface,
    EthernetClientInterface,
    EthernetServerInterfaceEx,
    EthernetServerInterface,
)

from gs_tools import Timer

class ConnectionHandler:
    def __init__(self):
        self._interfaces = []
        self._connection_status = {
            #interface: 'Connected',
        }
        self._callback = None #callable
        self._timers = {
            #interface: Timer
        }

    def connect(self, interface, keep_alive_query=None, poll_freq=5, disconnect_limit=5):
        '''
        This method will maintain the connection to the interface.
        :param interface: extronlib.interface or extron GS module with .SubscribeStatus('ConnectionStatus')
        :param keep_alive_query: string like 'q' for extron FW query, or string like 'Power' will send interface.Update('Power')
        :param poll_freq: float - how many seconds between polls
        :param disconnect_limit: int - how many missed queries before a 'Disconnected' event is triggered
        :return:
        '''

        #Add polling
        if hasattr(interface, 'Update{}'.format(keep_alive_query)):

            #Delete any old polling engine timers
            if interface in self._timers:
                self._timers[interface].Stop()
                self._timers.pop(interface)

            #Create a new polling engine timer
            def do_poll():
                interface.Update(keep_alive_query)
            new_timer = Timer(poll_freq, do_poll)
            #TODO - the rest


        if isinstance(interface, SerialInterface):
            self._handle_connection_serial(interface)
        elif isinstance(interface, EthernetClientInterface):
            self._handle_connection_ethernet_client(interface)
        elif isinstance(interface, EthernetServerInterface):
            self._handle_connection_ethernet_server(interface)
        elif isinstance(interface, EthernetServerInterfaceEx):
            self._handle_connection_ethernet_serverEx(interface)

    def disconnect(self, interface):
        pass

    def get_connection_status(self, interface):
        if interface not in self._interfaces:
            raise Exception('This interface is not being handled by this ConnectionHandler object.\ninterface={}\nThis ConnectionHandler={}'.format(interface, self))
        else:
            return self._connection_status[interface]

    def _update_connection_status(self, interface, state):
        '''
        This method will save the connection status and trigger any events that may be associated
        :param interface:
        :param state:
        :return:
        '''
        if interface not in self._interfaces:
            self._connection_status[interface] = 'Unknown'

        if state != self._connection_status[interface]:
            #The state has changed. Do something with that change
            if callable(self._callback):
                self._callback(interface, state)

        #save the state for later
        self._connection_status[interface] = state

    def _handle_connection_serial(self, interface):
        '''
        Serial ports are always ControlScript "Connected"
        :param interface:
        :return:
        '''
        pass

    def _handle_connection_ethernet_client(self, interface):

    def _handle_connection_ethernet_server(self, interface):
        pass

    def _handle_connection_ethernet_serverEx(self, interface):
        pass

    def _add_module_connection(self, interface):
        pass

    def __str__(self):
        s = '''{}\n\n***** Interfaces being handled *****\n\n'''.format(self)

        for interface in self._interfaces:
            s += self._interface_to_str(interface)

    def _interface_to_str(self, interface):
        for att in [
            'IPAddress',
            'IPPort',
            'DeviceAlias',
            'Port',
            'Host',
            'ServicePort',
        ]:
            write_str = '{}\n'.format(self)
            if hasattr(interface, att):
                write_str += '    {}:{}\n'.format(att, getattr(interface, att))
            write_str += '    {}:{}'.format('Connection Status', self._connection_status[interface])

        return write_str

    @property
    def Connected(self):
        '''
        There will be a single callback that will pass two params, the interface and the state
        :return:
        '''
        return self._callback

    @Connected.setter
    def Connected(self, callback):
        self._callback = callback
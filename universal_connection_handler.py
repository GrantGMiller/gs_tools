import extronlib
from extronlib.system import File, Wait
import time

debug = True  # Set to false to disable all print statements in this module
if not debug:
    def _new_print(*args, **kwargs):
        pass


    print = _new_print

'''
Examples of how to use this UniversalConnectionHandler class:

Proc = ProcessorDevice('ProcessorAlias')

CH = connection_handler.UniversalConnectionHandler()

@event(CH, 'Connected')
@event(CH, 'Disconnected')
def CHevent(interface, state):
    print('CHevent {} {}'.format(interface, state))

##SerialInterface Test *******************************************************
Serial = SerialInterface(Proc, 'COM1', Baud=9600)
CH.maintain(
    Serial,
    keep_alive_query_cmd='q', # The command you want to send regularly to elicit a response from the device
    poll_freq=1, # How often to send the keep_alive_query_cmd command (in seconds)
    disconnect_limit=5, # How many queries get missed before the "Disconnected" event it triggered
    )

@event(Serial, 'ReceiveData')
def SerialRxData(interface, data):
    print('SerialRxData\ninterface={}\ndata={}'.format(interface, data))
    #Do something useful here

##EthernetClientInterface TCP Test *******************************************

TCPClient = EthernetClientInterface('10.166.200.2', 23)

CH.maintain(
    TCPClient,
    keep_alive_query_cmd='q', # The command you want to send regularly to elicit a response from the device
    poll_freq=1, # How often to send the keep_alive_query_cmd command (in seconds)
    disconnect_limit=5, # How many queries get missed before the "Disconnected" event it triggered
    )

@event(TCPClient, 'ReceiveData')
def TCPClientRxData(interface, data):
    print('TCPClientRxData\ninterface={}\ndata={}'.format(interface, data))
    #Do something useful here

##Extron EthernetClass TCP Module Test *********************************************

import extr_dsp_DMP64_v1_0_0_1 as DMP_Module
ModuleEthernet = DMP_Module.EthernetClass('10.166.200.2', 23)

CH.maintain(
    ModuleEthernet,
    keep_alive_query_cmd='OutputMute', # The module command to query regularly to elicit a response from the device
    keep_alive_query_qual={'Output': '1'}, # The module qualifier to query regularly to elicit a response from the device
    poll_freq=1, # How often to send the keep_alive_query_cmd command(in seconds)
    )

##Extron SerialClass Module Test ***********************************************

ModuleSerial = DMP_Module.SerialClass(Proc, 'COM1', Baud=9600)
CH.maintain(
    ModuleSerial,
    keep_alive_query_cmd='OutputMute', #The module command to query regularly to elicit a response from the device
    keep_alive_query_qual={'Output': '1'}, #The module qualifier to query regularly to elicit a response from the device
    poll_freq=1, # How often to send the keep_alive_query_cmd command (in seconds)
    )

##EthernetServerInterfaceEx TCP Test *******************************************

ServerEx = EthernetServerInterfaceEx(1024)
CH.maintain(
    ServerEx,
    timeout=15, # After this many seconds, a client who has not sent any data to the server will be disconnected.
    )

@event(ServerEx, 'ReceiveData')
def ServerExRxData(client, data):
    print('ServerExRxData(client={}, data={})'.format(client, data))
    #Do something useful here

##EthernetClientInterface UDP Test *******************************************

UDPClient = EthernetClientInterface('10.166.200.13', 1024, Protocol='UDP', ServicePort=1024)

CH.maintain(
    UDPClient,
    keep_alive_query_cmd='ping', # The command you want to send regularly to elicit a response from the device
    poll_freq=1, # How often to send the keep_alive_query_cmd command (in seconds)
    )

@event(UDPClient, 'ReceiveData')
def UDPClientRxData(client, data):
    print('UDPClientRxData(client.IP={}, data={})'.format(client.IPAddress, data))
    #Do something useful here

##Extron EthernetClass UDP Module Test *****************************************

import sony_camera_SRG_300_Series_v1_4_1_0 as Sony_Module #uses UDP
UDPModule = Sony_Module.EthernetClass('10.166.200.13', 1024, ServicePort=1024)

CH.maintain(
    UDPModule,
    keep_alive_query_cmd='Power',  # The module command to query regularly to elicit a response from the device
    keep_alive_query_qual={'Device ID': '1'}, # The module qualifier to query regularly to elicit a response from the device
    poll_freq=1, # How often to send the keep_alive_query_cmd command (in seconds)
    )


##EthernetServerInterface TCP Test *********************************************

ServerNonExUDP = EthernetServerInterface(1024, Protocol='UDP')
print(ServerNonExUDP.StartListen())

CH.maintain(
    ServerNonExUDP
    )

@event(ServerNonExUDP, 'ReceiveData')
def ServerNonExUDPRxData(client, data):
    print('ServerNonExUDPRxData(client={}, data={})'.format(client, data))
    #Do something useful here


'''


class UniversalConnectionHandler:
    def __init__(self, filename='connection_handler.log'):
        '''
        :param filename: str() name of file to write connection status to
        '''
        self._interfaces = []
        self._connection_status = {
            # interface: 'Connected',
        }
        self._connected_callback = None  # callable
        self._disconnected_callback = None

        self._timers = {
            # interface: Timer_obj,
        }
        self._connection_retry_freqs = {
            # interface: float() #number of seconds between retrys
        }
        self._connection_timeouts = {
            # interface: float() #number of seconds to timeout trying to connect
        }
        self._send_counters = {
            # interface: int() #number of times data has been sent without receiving a response
        }
        self._disconnect_limits = {
            # interface: int() #number of times to miss a response before triggering disconnected status
        }
        self._rx_handlers = {
            # interface: function #function must take 2 params, "interface" object and "data" bytestring
        }
        self._send_methods = {
            # interface: function
        }
        self._send_and_wait_methods = {
            # interface: function
        }

        self._server_listen_status = {
            # interface: 'Listening' or 'Not Listening' or other
        }

        self._server_client_rx_timestamps = {
            # EthernetServerInterfaceEx1: {ClientObject1A: timestamp1,
            # ClientObject1B: timestamp2,
            # },
            # EthernetServerInterfaceEx2: {ClientObject2A: timestamp3,
            # ClientObject2B: timestamp4,
            # },
        }

        self._keep_alive_query_cmds = {
            # interface: 'string',
        }

        self._keep_alive_query_quals = {
            # interface: dict(),
        }
        self._poll_freqs = {
            # interface: float(),
        }

        self._filename = filename
        if not File.Exists(self._filename):
            File(self._filename, mode='wt').close()  # Create a blank file if it doesnt exist already

    def maintain(self, interface, keep_alive_query_cmd=None, keep_alive_query_qual=None, poll_freq=5,
                 disconnect_limit=5,
                 timeout=5, connection_retry_freq=5):
        '''
        This method will maintain the connection to the interface.
        :param interface: extronlib.interface or extron GS module with .SubscribeStatus('ConnectionStatus')
        :param keep_alive_query: string like 'q' for extron FW query, or string like 'Power' will send interface.Update('Power')
        :param poll_freq: float - how many seconds between polls
        :param disconnect_limit: int - how many missed queries before a 'Disconnected' event is triggered
        :return:
        '''
        print(
            'maintain()\ninterface={}\nkeep_alive_query_cmd="{}"\nkeep_alive_query_qual={}\npoll_freq={}\ndisconnect_limit={}\ntimeout={}\nconnection_retry_freq={}'.format(
                interface, keep_alive_query_cmd, keep_alive_query_qual, poll_freq, disconnect_limit,
                timeout, connection_retry_freq))

        self._connection_timeouts[interface] = timeout
        self._connection_retry_freqs[interface] = connection_retry_freq
        self._disconnect_limits[interface] = disconnect_limit
        self._keep_alive_query_cmds[interface] = keep_alive_query_cmd
        self._keep_alive_query_quals[interface] = keep_alive_query_qual
        self._poll_freqs[interface] = poll_freq

        if isinstance(interface, extronlib.interface.EthernetClientInterface):
            self._maintain_serial_or_ethernetclient(interface)

        elif isinstance(interface, extronlib.interface.SerialInterface):
            self._maintain_serial_or_ethernetclient(interface)

        elif isinstance(interface, extronlib.interface.EthernetServerInterfaceEx):
            if interface.Protocol == 'TCP':
                self._maintain_serverEx_TCP(interface)
            else:
                raise Exception(
                    'This ConnectionHandler class does not support EthernetServerInterfaceEx with Protocol="UDP".\nConsider using EthernetServerInterface with Protocol="UDP" (non-EX).')

        elif isinstance(interface, extronlib.interface.EthernetServerInterface):

            if interface.Protocol == 'TCP':
                raise Exception(
                    'This ConnectionHandler class does not support EthernetServerInterface with Protocol="TCP".\nConsider using EthernetServerInterfaceEx with Protocol="TCP".')
            elif interface.Protocol == 'UDP':
                #The extronlib.interface.EthernetServerInterfacee with Protocol="UDP" actually works pretty good by itself. No need to do anything special :-)
                while True:
                    result = interface.StartListen()
                    print(result)
                    if result == 'Listening':
                        break
                    else:
                        time.sleep(1)

    def _maintain_serverEx_TCP(self, parent):
        parent.Connected = self._get_serverEx_connection_callback(parent)
        parent.Disconnected = self._get_serverEx_connection_callback(parent)

        def get_disconnect_undead_clients_func(parent):
            def do_disconnect_undead_clients():
                self._disconnect_undead_clients(parent)

            return do_disconnect_undead_clients

        new_timer = Timer(self._connection_timeouts[parent], get_disconnect_undead_clients_func(parent))
        new_timer.Stop()

        self._timers[parent] = new_timer

        self._server_start_listening(parent)

    def _server_start_listening(self, parent):
        '''
        This method will try to StartListen on the server. If it fails, it will retry every X seconds
        :param interface: extronlib.interface.EthernetServerInterfaceEx or EthernetServerInterface
        :return:
        '''
        if parent not in self._server_listen_status:
            self._server_listen_status[parent] = 'Unknown'

        if self._server_listen_status[parent] is not 'Listening':
            try:
                result = parent.StartListen()
            except Exception as e:
                result = 'Failed to StartListen: {}'.format(e)
                print('StartListen on port {} failed\n{}'.format(parent.IPPort, e))

            print('StartListen result=', result)

            self._server_listen_status[parent] = result

        if self._server_listen_status[parent] is not 'Listening':
            # We tried to start listen but it failed.
            # Try again in X seconds
            def retry_start_listen():
                self._server_start_listening(parent)

            Wait(self._connection_retry_freqs[parent], retry_start_listen)

        elif self._server_listen_status[parent] is 'Listening':
            # We have successfully started the server listening
            pass

    def _maintain_serial_or_ethernetclient(self, interface):

        # Add polling
        if self._keep_alive_query_cmds[interface] is not None:
            # For example
            if hasattr(interface, 'Update{}'.format(self._keep_alive_query_cmds[interface])):

                # Delete any old polling engine timers
                if interface in self._timers:
                    self._timers[interface].Stop()
                    self._timers.pop(interface)

                # Create a new polling engine timer
                def do_poll():
                    print('do_poll interface.Update("{}", {})'.format(self._keep_alive_query_cmds[interface],
                                                                      self._keep_alive_query_quals[interface]))
                    interface.Update(self._keep_alive_query_cmds[interface], self._keep_alive_query_quals[interface])

                new_timer = Timer(self._poll_freqs[interface], do_poll)
                new_timer.Stop()
                self._timers[interface] = new_timer

            else:  # assume keep_alive_query is a string like 'q' for querying extron fw

                # Delete any old polling engine timers
                if interface in self._timers:
                    self._timers[interface].Stop()
                    self._timers.pop(interface)

                # Create a new polling engine timer
                def do_poll():
                    print('do_poll interface.Send({})'.format(self._keep_alive_query_cmds[interface]))
                    interface.Send(self._keep_alive_query_cmds[interface])

                new_timer = Timer(self._poll_freqs[interface], do_poll)
                self._timers[interface] = new_timer

        # Register ControlScript connection handlers
        interface.Connected = self._get_controlscript_connection_callback(interface)
        interface.Disconnected = self._get_controlscript_connection_callback(interface)

        # Register module connection callback
        if hasattr(interface, 'SubscribeStatus'):
            interface.SubscribeStatus('ConnectionStatus', None, self._get_module_connection_callback(interface))
            if isinstance(interface, extronlib.interface.SerialInterface):
                self._update_connection_status_serial_or_ethernetclient(interface, 'Connected',
                                                                        'ControlScript')  # SerialInterface ports are always 'Connected' in ControlScript
        else:
            # This interface is not an Extron module. We must create our own logical connection handling
            if isinstance(interface, extronlib.interface.EthernetClientInterface) or isinstance(interface,
                                                                                                extronlib.interface.SerialInterface):
                self._add_logical_connection_handling_client(interface)
            elif isinstance(interface, extronlib.interface.EthernetServerInterfaceEx):
                self._add_logical_connection_handling_serverEx(interface)

        # At this point all connection handlers and polling engines have been set up.
        # We can now start the connection
        if hasattr(interface, 'Connect'):
            if interface.Protocol == 'TCP':
                interface.Connect(self._connection_timeouts[interface])
                # The update_connection_status method will maintain the connection from here on out.

    def _add_logical_connection_handling_client(self, interface):
        print('_add_logical_connection_handling_client')

        # Initialize the send counter to 0
        if interface not in self._send_counters:
            self._send_counters[interface] = 0

        self._check_send_methods(interface)
        self._check_rx_handler_serial_or_ethernetclient(interface)

        if isinstance(interface, extronlib.interface.SerialInterface):
            # SerialInterfaces are always connected via ControlScript.
            self._update_connection_status_serial_or_ethernetclient(interface, 'Connected', 'ControlScript')

    def _check_send_methods(self, interface):
        '''
        This method will check the .Send and .SendAndWait methods to see if they have already been replaced with the
            appropriate new_send that will also increment the self._send_counter
        :param interface:
        :return:
        '''
        if interface not in self._send_methods:
            self._send_methods[interface] = None

        if interface not in self._send_and_wait_methods:
            self._send_and_wait_methods[interface] = None

        current_send_method = interface.Send
        if current_send_method != self._send_methods[interface]:

            # Create a new .Send method that will increment the counter each time
            def new_send(*args, **kwargs):
                print('new_send args={}, kwargs={}'.format(args, kwargs))
                self._check_rx_handler_serial_or_ethernetclient(interface)

                self._send_counters[interface] += 1
                print('new_send send_counter=', self._send_counters[interface])

                # Check if we have exceeded the disconnect limit
                if self._send_counters[interface] > self._disconnect_limits[interface]:
                    self._update_connection_status_serial_or_ethernetclient(interface, 'Disconnected', 'Logical')

                current_send_method(*args, **kwargs)

            interface.Send = new_send

        current_send_and_wait_method = interface.SendAndWait
        if current_send_and_wait_method != self._send_and_wait_methods[interface]:
            # Create new .SendAndWait that will increment the counter each time
            def new_send_and_wait(*args, **kwargs):
                print('new_send_and_wait args={}, kwargs={}'.format(args, kwargs))
                self._check_rx_handler_serial_or_ethernetclient(interface)

                self._send_counters[interface] += 1
                print('new_send_and_wait send_counter=', self._send_counters[interface])

                # Check if we have exceeded the disconnect limit
                if self._send_counters[interface] > self._disconnect_limits[interface]:
                    self._update_connection_status_serial_or_ethernetclient(interface, 'Disconnected', 'Logical')

                return current_send_and_wait_method(*args, **kwargs)

            interface.SendAndWait = new_send_and_wait

    def _check_rx_handler_serial_or_ethernetclient(self, interface):
        '''
        This method will check to see if the rx handler is resetting the send counter to 0. if not it will create a new rx handler and assign it to the interface
        :param interface:
        :return:
        '''
        print('_check_rx_handler')
        if interface not in self._rx_handlers:
            self._rx_handlers[interface] = None

        current_rx = interface.ReceiveData
        if current_rx != self._rx_handlers[interface] or current_rx == None:
            # The Rx handler got overwritten somehow, make a new Rx and assign it to the interface and save it in self._rx_handlers
            def new_rx(*args, **kwargs):
                print('new_rx args={}, kwargs={}'.format(args, kwargs))
                self._send_counters[interface] = 0

                if isinstance(interface, extronlib.interface.EthernetClientInterface):
                    if interface.Protocol == 'UDP':
                        self._update_connection_status_serial_or_ethernetclient(interface, 'Connected', 'Logical')

                elif isinstance(interface, extronlib.interface.SerialInterface):
                    self._update_connection_status_serial_or_ethernetclient(interface, 'Connected', 'Logical')


                if callable(current_rx):
                    current_rx(*args, **kwargs)

            self._rx_handlers[interface] = new_rx
            interface.ReceiveData = new_rx
        else:
            # The current rx handler is doing its job. Moving on!
            pass

    def _add_logical_connection_handling_serverEx(self, interface):
        pass

    def _get_module_connection_callback(self, interface):
        # generate a new function that includes the interface and the 'kind' of connection
        def module_connection_callback(command, value, qualifier):
            print('module_connection_callback(command={}, value={}, qualifier={}'.format(command, value, qualifier))
            self._update_connection_status_serial_or_ethernetclient(interface, value, 'Module')

        return module_connection_callback

    def _get_controlscript_connection_callback(self, interface):
        # generate a new function that includes the 'kind' of connection
        def controlscript_connection_callback(interface, state):
            self._update_connection_status_serial_or_ethernetclient(interface, state, 'ControlScript')

        return controlscript_connection_callback

    def block(self, interface):
        # this will stop this interface from communicating
        if isinstance(interface, extronlib.interface.SerialInterface):
            interface.ReceiveData = None

        elif isinstance(interface, extronlib.interface.EthernetClientInterface):
            interface.ReceiveData = None
            interface.Connected = None
            interface.Disconnected = None

            if interface.Protocol == 'TCP':
                interface.Disconnect()

        elif isinstance(interface, extronlib.interface.EthernetServerInterface):
            interface.ReceiveData = None
            interface.Connected = None
            interface.Disconnected = None

            if interface.Protocol == 'TCP':
                interface.Disconnect()

            interface.StopListen()

        elif isinstance(interface, extronlib.interface.EthernetServerInterfaceEx):
            interface.ReceiveData = None
            interface.Connected = None
            interface.Disconnected = None

            if interface.Protocol == 'TCP':
                for client in interface.Clients:
                    client.Disconnect()

            interface.StopListen()


    def get_connection_status(self, interface):
        if interface not in self._interfaces:
            raise Exception(
                'This interface is not being handled by this ConnectionHandler object.\ninterface={}\nThis ConnectionHandler={}'.format(
                    interface, self))
        else:
            return self._connection_status[interface]

    def _get_serverEx_connection_callback(self, parent):
        def controlscript_connection_callback(client, state):
            self._update_connection_status_server(parent, client, state, 'ControlScript')

        return controlscript_connection_callback

    def _update_connection_status_server(self, parent, client, state, kind=None):
        '''
        This method will save the connection status and trigger any events that may be associated
        :param parent: EthernetServerInterfaceEx object
        :param client: ClientObject
        :param state: 'Connected' or 'Disconnected'
        :param kind: 'ControlScript' or 'Logical'
        :return:
        '''

        if state == 'Connected':
            client.Parent = parent  # Add this attribute to the client object for later reference

            if parent not in self._server_client_rx_timestamps:
                self._server_client_rx_timestamps[parent] = {}

            self._server_client_rx_timestamps[parent][
                client] = time.monotonic()  # init the value to the time the connection started
            self._check_rx_handler_serverEx(client)

            if callable(self._connected_callback):
                self._connected_callback(client, state)

        elif state == 'Disconnected':
            self._remove_client_data(client)  # remove dead sockets to prevent memory leak

            if callable(self._disconnected_callback):
                self._disconnected_callback(client, state)

        self._update_serverEx_timer(parent)

        self._log_connection_to_file(client, state, kind)

    def _check_rx_handler_serverEx(self, client):
        '''
        Every time data is recieved from the client, set the timestamp
        :param client:
        :return:
        '''
        parent = client.Parent

        if parent not in self._rx_handlers:
            self._rx_handlers[parent] = None

        old_rx = parent.ReceiveData
        if self._rx_handlers[parent] != old_rx or (old_rx == None):
            # we need to override the rx handler with a new handler that will also add the timestamp
            def new_rx(client, data):
                time_now = time.monotonic()
                print('new_rx\ntime_now={}\nclient={}'.format(time_now, client))
                self._server_client_rx_timestamps[parent][client] = time_now
                self._update_serverEx_timer(parent)
                old_rx(client, data)

            parent.ReceiveData = new_rx
            self._rx_handlers[parent] = new_rx

    def _update_serverEx_timer(self, parent):
        '''
        This method will check all the time stamps and set the timer so that it will check again when the oldest client
            is near the X minute timeout mark.
        :param parent:
        :return:
        '''
        if len(parent.Clients) > 0:
            oldest_timestamp = None
            for client in parent.Clients:
                if client not in self._server_client_rx_timestamps[parent]:
                    self._server_client_rx_timestamps[parent][client] = time.monotonic()

                client_timestamp = self._server_client_rx_timestamps[parent][client]

                if (oldest_timestamp is None) or client_timestamp < oldest_timestamp:
                    oldest_timestamp = client_timestamp

                print('client={}\nclient_timestamp={}\noldest_timestamp={}'.format(client, client_timestamp,
                                                                                   oldest_timestamp))

            # We now have the oldest timestamp, thus we know when we should check the client again
            seconds_until_timer_check = self._connection_timeouts[parent] - (time.monotonic() - oldest_timestamp)
            self._timers[parent].ChangeTime(seconds_until_timer_check)
            self._timers[parent].Start()

            # Lets say the parent timeout is 5 minutes.
            # If the oldest connected client has not communicated for 4min 55sec, then seconds_until_timer_check = 5 seconds
            # The timer will check the clients again in 5 seconds.
            # Assuming the oldest client still has no communication, it will be disconnected at the 5 minute mark exactly

        else:  # there are no clients connected
            self._timers[parent].Stop()

    def _disconnect_undead_clients(self, parent):
        for client in parent.Clients:
            client_timestamp = self._server_client_rx_timestamps[parent][client]
            if time.monotonic() - client_timestamp > self._connection_timeouts[parent]:
                if client in parent.Clients:
                    client.Send('Disconnecting due to inactivity for {} seconds.\r\nBye.\r\n'.format(
                        self._connection_timeouts[parent]))
                    client.Disconnect()
                self._remove_client_data(client)

    def _remove_client_data(self, client):
        # remove dead sockets to prevent memory leak
        self._server_client_rx_timestamps.pop(client, None)

    def _log_connection_to_file(self, interface, state, kind):
        # Write new status to a file
        with File(self._filename, mode='at') as file:
            write_str = '{}\n    {}:{}\n'.format(time.asctime(), 'type', type(interface))

            for att in [
                'IPAddress',
                'IPPort',
                'DeviceAlias',
                'Port',
                'Host',
                'ServicePort',
                'Protocol',
            ]:
                if hasattr(interface, att):
                    write_str += '    {}:{}\n'.format(att, getattr(interface, att))

                    if att == 'Host':
                        write_str += '    {}:{}\n'.format('Host.DeviceAlias', getattr(interface, att).DeviceAlias)


            write_str += '    {}:{}\n'.format('ConnectionStatus', state)
            write_str += '    {}:{}\n'.format('Kind', kind)

            file.write(write_str)

    def _update_connection_status_serial_or_ethernetclient(self, interface, state, kind=None):
        '''
        This method will save the connection status and trigger any events that may be associated
        :param interface:
        :param state:
        :param kind: str() 'ControlScript' or 'Module' or any other value that may be applicable
        :return:
        '''
        print('_update_connection_status\ninterface={}\nstate={}\nkind={}'.format(interface, state, kind))
        if interface not in self._connection_status:
            self._connection_status[interface] = 'Unknown'

        if state == 'Connected':
            self._send_counters[interface] = 0

        if state != self._connection_status[interface]:
            # The state has changed. Do something with that change

            print('Connection status has changed for interface={} from "{}" to "{}"'.format(interface,
                                                                                            self._connection_status[
                                                                                                interface], state))
            if callable(self._connected_callback):
                self._connected_callback(interface, state)

            self._log_connection_to_file(interface, state, kind)

        # save the state for later
        self._connection_status[interface] = state

        # if the interface is disconnected, try to reconnect
        if state == 'Disconnected':
            print('Trying to Re-connect to interface={}'.format(interface))
            if hasattr(interface, 'Connect'):
                Wait(self._connection_retry_freqs[interface], interface.Connect)

        # Start/Stop the polling timer if it exists
        if interface in self._timers:
            if state == 'Connected':
                self._timers[interface].Start()

            elif state == 'Disconnected':
                if isinstance(interface, extronlib.interface.SerialInterface):
                    # SerialInterface has no Disconnect() method so the polling engine is the only thing that can detect a re-connect.
                    # Keep the timer going.
                    pass
                elif isinstance(interface, extronlib.interface.EthernetClientInterface):
                    if interface.Protocol == 'UDP':
                        # Same for UDP EthernetClientInterface
                        # Keep the timer going.
                        pass
                    elif interface.Protocol == 'TCP':
                        self._timers[interface].Stop()
                        # Stop the timer and wait for a 'Connected' Event

    def __str__(self):
        s = '''{}\n\n***** Interfaces being handled *****\n\n'''.format(self)

        for interface in self._interfaces:
            s += self._interface_to_str(interface)

    def _interface_to_str(self, interface):
        write_str = '{}\n'.format(self)

        for att in [
            'IPAddress',
            'IPPort',
            'DeviceAlias',
            'Port',
            'Host',
            'ServicePort',
        ]:
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
        return self._connected_callback

    @Connected.setter
    def Connected(self, callback):
        self._connected_callback = callback

    @property
    def Disconnected(self):
        '''
        There will be a single callback that will pass two params, the interface and the state
        :return:
        '''
        return self._disconnected_callback

    @Disconnected.setter
    def Disconnected(self, callback):
        if __name__ == '__main__':
            self._disconnected_callback = callback


class Timer:
    def __init__(self, t, func):
        '''
        This class calls self.func every t-seconds until Timer.Stop() is called.
        :param t: float
        :param func: callable (no parameters)
        '''
        print('Timer.__init__(t={}, func={})'.format(t, func))
        self._func = func
        self._t = t
        self._run = False

    def Stop(self):
        print('Timer.Stop()')
        self._run = False

    def Start(self):
        print('Timer.Start()')
        if self._run is False:
            self._run = True

            try:
                @Wait(0.0001)  # Start immediately
                def loop():
                    try:
                        # print('entering loop()')
                        while self._run:
                            # print('in while self._run')
                            if self._t < 0:
                                pass
                            else:
                                time.sleep(self._t)
                            self._func()
                            # print('exiting loop()')
                    except Exception as e:
                        print('Error in timer func={}\n{}'.format(self._func, e))
            except Exception as e:
                if 'can\'t start new thread' in str(e):
                    print('There are too many threads right now.\nWaiting for more threads to be available.')
                time.sleep(1)
                self.Start()

    def ChangeTime(self, new_t):
        '''
        This method allows the user to change the timer speed on the fly.
        :param new_t:
        :return:
        '''
        print('Timer.ChangeTime({})'.format(new_t))
        was_running = self._run

        self.Stop()
        self._t = new_t

        if was_running:
            self.Start()

    def Restart(self):
        # To easily replace a Wait object
        self.Start()

    def Cancel(self):
        # To easily replace a Wait object
        self.Stop()

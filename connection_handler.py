import extronlib
from extronlib.system import File, Wait
import time

debug = True #Set to false to disable all print statements in this module
if not debug:
    def _new_print(*args, **kwargs):
        pass
    print = _new_print

class ConnectionHandler:
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
            #interface: function
        }
        self._send_and_wait_methods = {
            #interface: function
        }

        self._filename = filename
        if not File.Exists(self._filename):
            File(self._filename, mode='wt').close()  # Create a blank file if it doesnt exist already

    def maintain(self, interface, keep_alive_query_cmd=None, keep_alive_query_qal=None, poll_freq=5, disconnect_limit=5,
                 timeout=5, connection_retry_freq=5):
        '''
        This method will maintain the connection to the interface.
        :param interface: extronlib.interface or extron GS module with .SubscribeStatus('ConnectionStatus')
        :param keep_alive_query: string like 'q' for extron FW query, or string like 'Power' will send interface.Update('Power')
        :param poll_freq: float - how many seconds between polls
        :param disconnect_limit: int - how many missed queries before a 'Disconnected' event is triggered
        :return:
        '''
        print('maintain()\ninterface={}\nkeep_alive_query_cmd={}\nkeep_alive_query_qal={}\npoll_freq={}\ndisconnect_limit={}\ntimeout={}\nconnection_retry_freq={}'.format(
            interface, keep_alive_query_cmd, keep_alive_query_qal, poll_freq, disconnect_limit,
            timeout, connection_retry_freq))

        self._connection_timeouts[interface] = timeout
        self._connection_retry_freqs[interface] = connection_retry_freq
        self._disconnect_limits[interface] = disconnect_limit
        # Add polling
        if keep_alive_query_cmd is not None:
            # For example
            if hasattr(interface, 'Update{}'.format(keep_alive_query_cmd)):

                # Delete any old polling engine timers
                if interface in self._timers:
                    self._timers[interface].Stop()
                    self._timers.pop(interface)

                # Create a new polling engine timer
                def do_poll():
                    print('do_poll')
                    interface.Update(keep_alive_query_cmd, keep_alive_query_qal)

                new_timer = Timer(poll_freq, do_poll)
                new_timer.Stop()
                self._timers[interface] = new_timer

            else:  # assume keep_alive_query is a string like 'q' for querying extron fw

                # Delete any old polling engine timers
                if interface in self._timers:
                    self._timers[interface].Stop()
                    self._timers.pop(interface)

                # Create a new polling engine timer
                def do_poll():
                    print('do_poll')
                    interface.Send(keep_alive_query_cmd)

                new_timer = Timer(poll_freq, do_poll)
                self._timers[interface] = new_timer

        # Register ControlScript connection handlers
        interface.Connected = self._get_controlscript_connection_callback(interface)
        interface.Disconnected = self._get_controlscript_connection_callback(interface)

        # Register module connection callback
        if hasattr(interface, 'SubscribeStatus'):
            interface.SubscribeStatus('ConnectionStatus', None, self._get_module_connection_callback(interface))
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
            interface.Connect(self._connection_timeouts[interface])
        #The update_connection_status method will maintain the connection from here on out.



    def _add_logical_connection_handling_client(self, interface):
        print('_add_logical_connection_handling_client')

        # Initialize the send counter to 0
        if interface not in self._send_counters:
            self._send_counters[interface] = 0

        self._check_send_methods(interface)
        self._check_rx_handler(interface)

        if isinstance(interface, extronlib.interface.SerialInterface):
            #SerialInterfaces are always connected via ControlScript.
            self._update_connection_status(interface, 'Connected', 'ControlScript')

    def _check_send_methods(self, interface):
        if interface not in self._send_methods:
            self._send_methods[interface] = None

        if interface not in self._send_and_wait_methods:
            self._send_and_wait_methods[interface] = None

        current_send_method = interface.Send
        if current_send_method != self._send_methods[interface]:

            # Create a new .Send method that will increment the counter each time
            def new_send(*args, **kwargs):
                print('new_send args={}, kwargs={}'.format(args, kwargs))
                self._check_rx_handler(interface)

                self._send_counters[interface] += 1
                print('new_send send_counter=', self._send_counters[interface])

                # Check if we have exceeded the disconnect limit
                if self._send_counters[interface] > self._disconnect_limits[interface]:
                    self._update_connection_status(interface, 'Disconnected', 'Logical')

                current_send_method(*args, **kwargs)

            interface.Send = new_send

        current_send_and_wait_method = interface.SendAndWait
        if current_send_and_wait_method != self._send_and_wait_methods[interface]:
            # Create new .SendAndWait that will increment the counter each time
            def new_send_and_wait(*args, **kwargs):
                print('new_send_and_wait args={}, kwargs={}'.format(args, kwargs))
                self._check_rx_handler(interface)

                self._send_counters[interface] += 1
                print('new_send_and_wait send_counter=', self._send_counters[interface])

                # Check if we have exceeded the disconnect limit
                if self._send_counters[interface] > self._disconnect_limits[interface]:
                    self._update_connection_status(interface, 'Disconnected', 'Logical')

                return current_send_and_wait_method(*args, **kwargs)
            interface.SendAndWait = new_send_and_wait

    def _check_rx_handler(self, interface):
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
            self._update_connection_status(interface, value, 'Module')

        return module_connection_callback

    def _get_controlscript_connection_callback(self, interface):
        # generate a new function that includes the 'kind' of connection
        def controlscript_connection_callback(interface, state):
            self._update_connection_status(interface, state, 'ControlScript')

        return controlscript_connection_callback

    def block(self, interface):
        # this will stop this interface from communicating
        pass

    def get_connection_status(self, interface):
        if interface not in self._interfaces:
            raise Exception(
                'This interface is not being handled by this ConnectionHandler object.\ninterface={}\nThis ConnectionHandler={}'.format(
                    interface, self))
        else:
            return self._connection_status[interface]

    def _update_connection_status(self, interface, state, kind=None):
        '''
        This method will save the connection status and trigger any events that may be associated
        :param interface:
        :param state:
        :param kind: str() 'ControlScript' or 'Module' or any other value that may be applicable
        :return:
        '''
        print('_update_connection_status\ninterface={}\nstate={}\nkind={}'.format(interface, state, kind))
        if interface not in self._interfaces:
            self._connection_status[interface] = 'Unknown'

        if state == 'Connected':
            self._send_counters[interface] = 0

        if state != self._connection_status[interface]:
            # The state has changed. Do something with that change
            if callable(self._connected_callback):
                self._connected_callback(interface, state)

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
                ]:
                    if hasattr(interface, att):
                        write_str += '    {}:{}\n'.format(att, getattr(interface, att))

                write_str += '    {}:{}\n'.format('ConnectionStatus', state)

                file.write(write_str)

        # save the state for later
        self._connection_status[interface] = state

        #if the interface is disconnected, try to reconnect
        if state == 'Disconnected':
            print('Trying to Re-connect to interface={}'.format(interface))
            Wait(self._connection_retry_freqs[interface], interface.Connect)

        #Start/Stop the polling timer if it exists
        if interface in self._timers:
            if state == 'Connected':
                self._timers[interface].Start()

            elif state == 'Disconnected':
                self._timers[interface].Stop()

    def _add_module_connection(self, interface):
        pass

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

            @Wait(0.0001)  # Start immediately
            def loop():
                try:
                    #print('entering loop()')
                    while self._run:
                        #print('in while self._run')
                        time.sleep(self._t)
                        self._func()
                    #print('exiting loop()')
                except Exception as e:
                    print('Error in timer func={}\n{}'.format(self._func, e))

    def Restart(self):
        #To easily replace a Wait object
        self.Start()

    def Cancel(self):
        #To easily replace a Wait object
        self.Stop()

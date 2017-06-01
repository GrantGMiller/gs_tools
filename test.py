from gs_tools import (
    EthernetServerInterfaceEx,
    SerialInterface,
    EthernetClientInterface,
    Ping,
    Wait,
    AddConnectionCallback,
    HandleConnection,
    ConnectionHandlerLogicalReset,
    RemoveConnectionHandlers,
    File,
    ProgramLog,
    ProcessorDevice,
    event,
    get_parent,
    Timer,
)
import extronlib
import time
import json

# Set this false to disable all print statements ********************************
debug = False
if not debug:
    def newPrint(*args, **kwargs):
        pass


    print = newPrint

debugRxData = False


# *******************************************************************************

class DeviceFarm(EthernetServerInterfaceEx):
    def __init__(self, *args, **kwargs):
        self._init_complete = False

        self._do_save_Wait = Wait(1, self._do_save)
        self._do_save_Wait.Cancel()

        self._loading_callbacks = []  # hold callback functions to show/hide the "please wait" page

        super().__init__(*args, **kwargs)
        self._connection_status = {  # interface: 'Dis/connected',
        }
        self._connection_timestamps = {  # clientObject: time.monotonic()
        }
        self._SERVER_TIMEOUT = 5 * 60  # 5 minutes
        self._disconnect_undead_sockets_Timer = Timer(60,
                                                      self._disconnect_undead_sockets)  # check every X seconds to see if we should disconnect any clients

        self._handle_connection_to_devices = []  # device_interfaces in this list should have their connection handled by the farm

        self.ReceiveData = self._control_rx_data
        self.Connected = self._control_connection_handler
        self.Disconnected = self._control_connection_handler

        # self.StartListen()  # control interface

        self._devices = {  # 'name': interface(EthernetClientInterface or SerialInterface)
        }

        self._rooms = {  # 'name': EthernetServerInterfaceEx or SerialInterface
        }

        self._pairs = {  # RoomInterface: DeviceInterface
        }

        self._INTERFACE_LIMIT = 25  # Max number of devices and rooms combined

        self._farm_change_callback = None
        self._matrix_interface = None
        self._matrix_name = None

        # Matrix device
        self._matrix_info = {}
        self._matrix_info['InputA'] = {  # interface: input_str,
        }
        self._matrix_info['InputB'] = {  # interface: input_str,
        }
        self._matrix_info['OutputA'] = {  # interface: input_str,
        }
        self._matrix_info['OutputB'] = {  # interface: input_str,
        }

        # Preset Devices
        self._preset_interfaces = {  # 'name': interface
        }
        self._preset_info = {  # 'Preset Interface Name': {'room_name': {'device_name': int(preset_num),
            #                                                              'device_name2': int(preset_num2),},
            #                                                'room_name2': {'device_name3': int(preset_num3),
            #                                                               'device_name4': int(preset_num4),}
        }

        # Log reservations for later examination - do this before self._load
        self._Reservation_Log = Logger('farm_reservation.log')
        self._Reservation_Log.SystemRebooted()

        # Log connection status changes
        self._Connection_Log = Logger('device_connection_status.log')
        self._Connection_Log.SystemRebooted()

        self._load()

        # The generator will ping one device per second to synchronously detect if a device falls offline
        self._device_name_generator = self._get_new_device_name_generator()
        self._device_name_generator_Wait = Wait(1, self._ping_a_device)

        self._init_complete = True

        self._update_matrix_ties()
        self._do_all_preset_recall()

    def _handle_connection(self, device_interface):
        print('DeviceFarm._handle_connection\n device_interface={}'.format(device_interface))
        if device_interface not in self._handle_connection_to_devices:
            self._handle_connection_to_devices.append(device_interface)

            AddConnectionCallback(device_interface, self._write_connection_status)
            HandleConnection(device_interface)

    def _restore_endpoint_connection_handler(self, interface):
        print('DeviceFarm._restore_endpoint_connection_handler\n interface={}'.format(interface))
        RemoveConnectionHandlers(interface)

        if interface in self._handle_connection_to_devices:
            self._handle_connection_to_devices.remove(interface)

            interface.ReceiveData = self._endpoint_rx_data
            interface.Connected = self._endpoint_connection_handler
            interface.Disconnected = self._endpoint_connection_handler

    def _get_new_device_name_generator(self):
        def the_generator():
            while True:
                # print('the_generator while True')
                # print('self._devices=', self._devices)

                if len(self._devices) == 0:
                    # print('if len(self._devices) == 0:')
                    yield None
                else:
                    # print('else')
                    for device_name in self._devices.copy():
                        # print('for device_name=', device_name)
                        yield device_name

        return the_generator()

    def _ping_a_device(self):
        try:
            # print('self._device_name_generator=', self._device_name_generator)
            device_name = next(self._device_name_generator)

            connection_status = self.get_connection_status(device_name)
            interface = self.get_interface_by_name(device_name)

            self._write_connection_status(interface, connection_status)
            # ('_ping_a_device {} {}'.format(device_name, connection_status))

        except Exception as e:
            print('Exception in DeviceFarm._ping_a_device\n', e)

        self._device_name_generator_Wait.Restart()

    def _base_add_device(self, name, interface):
        self._show_loading_page()

        interface.ReceiveData = self._endpoint_rx_data
        interface.Connected = self._endpoint_connection_handler
        interface.Disconnected = self._endpoint_connection_handler

        self._devices[name] = interface

        if isinstance(interface, SerialInterface):
            self._write_connection_status(interface, 'Connected')  # SerialInterfaces are always "Connected"
        else:
            self._write_connection_status(interface, 'Disconnected')

        self._device_name_generator = self._get_new_device_name_generator()

        self.pair(name, '')

        self._save()

        self._hide_loading_page()

    def add_ethernet_device(self, name, *args, **kwargs):  # instantiate like a EthernetClientInterface
        '''
        name > str()
        args/kwargs > same args/kwargs you would use to instantiate an extronlib.interface.EthernetClientInterface
        '''
        if self._interfaces_above_limit():
            raise Exception(
                'The device farm interface limit has been reached.\nA maximum of {} rooms/devices are allowed.'.format(
                    self._INTERFACE_LIMIT))

        if len(name) <= 0:
            raise Exception('The name must be a str of len >= 1')
        elif self._name_exists(name):
            raise Exception('The name "{}" is already used for another room/device'.format(name))

        newClient = EthernetClientInterface(*args, **kwargs)
        self._base_add_device(name, newClient)

    def add_serial_device(self, name, *args, **kwargs):
        '''
        name > str()
        args/kwargs > same args/kwargs you would use to instantiate an extronlib.interface.SerialInterface
        '''
        print('DeviceFarm.add_serial_device\n name={}\n args={}\n kwargs={}'.format(name, args, kwargs))
        if self._interfaces_above_limit():
            raise Exception(
                'The device farm interface limit has been reached.\nA maximum of {} rooms/devices are allowed.'.format(
                    self._INTERFACE_LIMIT))

        if len(name) <= 0:
            raise Exception('The name must be a str of len >= 1')
        elif self._name_exists(name):
            raise Exception('The name "{}" is already used for another room/device'.format(name))

        newSerial = SerialInterface(*args, **kwargs)
        self._base_add_device(name, newSerial)

    def _base_add_room(self, name, interface):
        '''
        name > str()
        args/kwargs > same args/kwargs you would use to instantiate an extronlib.interface.EthernetServerInterfaceEx
        '''
        self._show_loading_page()

        interface.ReceiveData = self._endpoint_rx_data
        interface.Connected = self._endpoint_connection_handler
        interface.Disconnected = self._endpoint_connection_handler

        self._rooms[name] = interface

        if isinstance(interface, extronlib.interface.SerialInterface):
            self._write_connection_status(interface, 'Connected')  # Physical ports are always physically connected
        else:
            self._write_connection_status(interface, 'Disconnected')

        self.pair(name, '')  # Pair with nothing just to init all the needed attributes

        self._save()

        self._hide_loading_page()

    def add_ethernet_room(self, name, *args, **kwargs):
        '''
        name > str()
        args/kwargs > same args/kwargs you would use to instantiate an extronlib.interface.EthernetServerInterfaceEx
        '''
        if self._interfaces_above_limit():
            raise Exception(
                'The device farm interface limit has been reached.\nA maximum of {} rooms/devices are allowed.'.format(
                    self._INTERFACE_LIMIT))

        if len(name) <= 0:
            raise Exception('The name must be a str of len >= 1')

        elif self._name_exists(name):
            raise Exception('The name "{}" is already used for another room/device'.format(name))

        print('DeviceFarm.add_ethernet_room(\n name={} \n*args={} \n**kwargs={}'.format(name, args, kwargs))
        room_server = EthernetServerInterfaceEx(*args, **kwargs)
        print('room_server=', room_server)
        # room_server.StartListen()

        self._base_add_room(name, room_server)

    def add_serial_room(self, name, *args, **kwargs):
        '''
        name > str()
        args/kwargs > same args/kwargs you would use to instantiate an extronlib.interface.EthernetServerInterfaceEx
        '''
        if self._interfaces_above_limit():
            raise Exception(
                'The device farm interface limit has been reached.\nA maximum of {} rooms/devices are allowed.'.format(
                    self._INTERFACE_LIMIT))

        if len(name) <= 0:
            raise Exception('The name must be a str of len >= 1')
        elif self._name_exists(name):
            raise Exception('The name "{}" is already being used for another room/device'.format(name))

        print('DeviceFarm.add_serial_room(name={} \n*args={} \n**kwargs={}'.format(name, args, kwargs))
        roomServer = SerialInterface(*args, **kwargs)

        self._base_add_room(name, roomServer)

    def _get_paired_interface(self, interface):
        '''
        interface > extronlib.interface.*
        returns the device/room that is paired with interface.
        if no pair exists, return None
        '''
        if debugRxData: print('DeviceFarm._get_paired_interface\n interface={}'.format(interface))
        for k, v in self._pairs.copy().items():
            # print('pair_room={}\npair_device={}'.format(k, v))
            pass

        # If this is a ClientObject, grab the parent
        if isinstance(interface, extronlib.interface.EthernetServerInterfaceEx.ClientObject):
            interface = get_parent(interface)

        for room_interface in self._pairs.copy():
            device_interface = self._pairs.copy()[room_interface]

            if interface == room_interface:
                return device_interface

            elif interface == device_interface:
                return room_interface

    def _endpoint_rx_data(self, interface, data):
        '''
        interface > extronlib.interface.EthernetServerInterfaceEx.ClientObject or
                    extronlib.interface.EthernetClientInterface, or SerialInterface
        data > bytes()

        This method will route the data between the device and the room its paired with.
        '''
        ConnectionHandlerLogicalReset(interface)

        if isinstance(interface, extronlib.interface.EthernetServerInterfaceEx.ClientObject):
            self._connection_timestamps[interface] = time.monotonic()

        paired_interface = self._get_paired_interface(interface)
        if debugRxData: print(
            '_endpoint_rx_data()\ninterface={}\n data={}\n paired_interface={}'.format(interface, data,
                                                                                       paired_interface))

        # Send the data to the paired_interface
        if paired_interface:
            if isinstance(paired_interface, extronlib.interface.EthernetServerInterfaceEx):
                for client in paired_interface.Clients:
                    client.Send(data)
            else:
                paired_interface.Send(data)

    def _write_connection_status(self, interface, new_connection_status):
        '''
        This method should save the connection state and trigger any connection events
        '''
        # print('_write_connection_status\n interface={}, new_connection_status={}'.format(interface, new_connection_status))
        # Convert ClientObject to ServerEx if needed
        if isinstance(interface, extronlib.interface.EthernetServerInterfaceEx.ClientObject):
            interface = get_parent(interface)

        # Determine the room_name and device_name
        name = self.get_name_by_interface(interface)
        # print('_write_connection_status name=', name)
        if name in self._rooms:
            room_name = name
            device_name = None
        elif name in self._devices:
            room_name = None
            device_name = name
        else:
            room_name = None
            device_name = None

        # Determnine the old connection status
        if interface in self._connection_status:
            old_connection_status = self._connection_status[interface]
        else:
            old_connection_status = 'Unknown'

        # If status changed, do the callback
        if old_connection_status != new_connection_status:
            print(
                'DeviceFarm._write_connection_status\ninterface={}, state={}'.format(interface, new_connection_status))

            event_info = {}

            if interface == self._matrix_interface:
                event_info['Event Type'] = 'Matrix Connection Status'

            else:
                event_info['Event Type'] = 'Connection Status'

            event_info['Value'] = new_connection_status
            event_info['Room Name'] = room_name  # str with len>=1 or None
            event_info['Device Name'] = device_name  # str with len>=1 or None

            if interface in self._preset_interfaces.values():
                event_info['Preset Interface Name'] = self.get_name_by_interface(interface)

            self._send_event(event_info)

            # log the connection status change
            interface_name = self.get_name_by_interface(interface)

            if interface_name is None:
                interface_name = interface.IPAddress

            self._Connection_Log.ConnectionStatus(interface_name, new_connection_status)

        self._connection_status[interface] = new_connection_status

    def _disconnect_undead_sockets(self):
        try:
            print('DeviceFarm._disconnect_undead_sockets()')
            # if no data has been received from the socket for > X seconds, disconnect the socket.
            for client in self._connection_timestamps.copy():
                client_last_time = self._connection_timestamps[client]
                now_time = time.monotonic()

                print('time since last comm with client {}\n {} seconds'.format(client, now_time - client_last_time))

                if (now_time - client_last_time) > self._SERVER_TIMEOUT:
                    print(
                        'Disconnecting client {}:{} due to inactivity for more than {} seconds'.format(client.IPAddress,
                                                                                                       client.ServicePort,
                                                                                                       self._SERVER_TIMEOUT))
                    self._connection_timestamps.pop(client, None)
                    client.Disconnect()
        except Exception as e:
            print('Exception in DeviceFarm._disconnect_undead_sockets\n {}'.format(e))

    def _endpoint_connection_handler(self, interface, state):
        '''
        When a room connects to the Farm, the Farm should then connect to the paired device.
        When a room disconnects from the Farm, the Farm should then disconnect from the paired device.
        When a device disconnects from the Farm, the Farm should also disconnect the paired room.

        This is most usefull when connecting to devices that require a telnet handshake upon connecting.
            For example, the Cisco SX80.
            This allows the room to handle the telnet handshake and not the farm.
        '''
        print('_endpoint_connection_handler()\ninterface={}\nstate={}'.format(interface, state))

        # Save the connection state for later
        if isinstance(interface, extronlib.interface.EthernetServerInterfaceEx.ClientObject):
            parent = get_parent(interface)
            if len(parent.Clients) > 0:
                self._write_connection_status(interface, 'Connected')
            else:
                self._write_connection_status(interface, 'Disconnected')

        elif isinstance(interface, extronlib.interface.EthernetClientInterface):
            self._write_connection_status(interface, state)

        # Perform the appropriate action on the paried interface
        paired_interface = self._get_paired_interface(interface)
        if paired_interface:

            if isinstance(interface, extronlib.interface.EthernetServerInterfaceEx.ClientObject):
                # Dis/connect the paired interface
                if state == 'Connected':
                    if hasattr(paired_interface, 'Connect'):
                        paired_interface.Connect()
                elif state == 'Disconnect':
                    paired_interface.Disconnect()
                    self._connection_timestamps.pop(interface, None)

            elif isinstance(interface, extronlib.interface.EthernetServerInterfaceEx):
                # paired_interface is a EthernetServerInterfaceEx
                for client in paired_interface.Clients:
                    if state == 'Connected':
                        pass  # Cant force the client to connect
                    elif state == 'Disconnected':
                        client.Disconnect()

        # timestamp connection
        if isinstance(interface, extronlib.interface.EthernetServerInterfaceEx.ClientObject):
            if interface not in self._connection_timestamps:
                self._connection_timestamps[interface] = time.monotonic()

        # If this interface is a preset interface. Recall all the presets
        if state == 'Connected' and interface in self._preset_interfaces.values():
            self._do_all_preset_recall()

    def get_name_by_interface(self, interface):
        if isinstance(interface, extronlib.interface.EthernetServerInterfaceEx.ClientObject):
            interface = get_parent(interface)

        for device_name in self._devices:
            i = self._devices[device_name]
            if interface == i:
                return device_name

        for room_name in self._rooms:
            i = self._rooms[room_name]
            if interface == i:
                return room_name

        for preset_interface_name in self._preset_interfaces:
            i = self._preset_interfaces[preset_interface_name]
            if interface == i:
                return preset_interface_name

        if interface == self._matrix_interface:
            return self._matrix_name

        return None

    def get_interface_by_name(self, name):
        for n in self._devices:
            if name == n:
                return self._devices[n]

        for n in self._rooms:
            if name == n:
                return self._rooms[n]

        for n in self._preset_interfaces:
            if name == n:
                return self._preset_interfaces[n]

        if name == self._matrix_name:
            return self._matrix_interface

        return None

    def pair(self, name1, name2):
        '''
        Will allow communication between rooms and devices
        To "unpair" something call Farm.pair('RoomOrDeviceName', None)
        '''
        print('DeviceFarm.pair(name1={}, name2={}'.format(name1, name2))

        self._show_loading_page()

        # prevent bad data
        if not isinstance(name1, str):
            raise Exception(
                'name1 must be type str \nPassed params name1={}, name2={}'.format(name1, name2))

        if not isinstance(name2, str) and name2 is not None:
            raise Exception('name2 must be type str\nPassed params name1={}, name2={}'.format(name1, name2))

        # Determine which name is the room/device
        if name1 in self._rooms:
            room_name = name1
        elif name2 in self._rooms:
            room_name = name2
        else:
            room_name = None

        if name1 in self._devices:
            device_name = name1
        elif name2 in self._devices:
            device_name = name2
        else:
            device_name = None

        print('pair device_name=', device_name)
        print('pair room_name=', room_name)

        # Determine the associated interfaces
        room_interface = self.get_interface_by_name(room_name)
        device_interface = self.get_interface_by_name(device_name)

        # Disconnect any current pairs associated this room
        if room_interface in self._pairs:
            paired_interface = self._pairs[room_interface]

            if paired_interface is not None:
                # No longer handle connection if applicable
                self._restore_endpoint_connection_handler(paired_interface)

                # Send notification that device is no longer paired
                self._send_event({
                    'Event Type': 'Pair Update',
                    'Value': 'Available',
                    'Room Name': None,  # str with len>=1 or None
                    'Device Name': self.get_name_by_interface(paired_interface),  # str with len>=1 or None
                })

                # Disconnect device communication
                if hasattr(paired_interface, 'Disconnect'):
                    paired_interface.Disconnect()

        if hasattr(room_interface, 'Disconnect'):
            if isinstance(room_interface, EthernetServerInterfaceEx):
                for client in room_interface.Clients:
                    client.Disconnect()
            else:
                room_interface.Disconnect()

        # Disconnect any pairs associated with the device
        if device_interface in self._pairs.values():
            paired_interface = self._get_paired_interface(device_interface)

            # Send notification that device is no longer paired
            self._send_event({
                'Event Type': 'Pair Update',
                'Value': 'Available',
                'Room Name': self.get_name_by_interface(paired_interface),  # str with len>=1 or None
                'Device Name': None,  # str with len>=1 or None
            })

            # Disconnect device communication
            if hasattr(paired_interface, 'Disconnect'):
                if isinstance(paired_interface, EthernetServerInterfaceEx):
                    for client in paired_interface.Clients:
                        client.Disconnect()
                else:
                    paired_interface.Disconnect()

            # Remove the pair
            for r_interface in self._pairs.copy():
                d_interface = self._pairs[r_interface]
                if d_interface == device_interface:
                    self._pairs[r_interface] = None

        # Make and Save the new pair
        if room_interface:
            self._pairs[room_interface] = device_interface

        # if the new pair is a serial room and an IP device, the farm will handle the IP connection to the device
        if isinstance(room_interface, SerialInterface) and isinstance(device_interface, EthernetClientInterface):
            self._handle_connection(device_interface)

        print('self._pairs=', self._pairs)

        # Update callback
        self._send_event({
            'Event Type': 'Pair Update',
            'Value': 'Paired',
            'Room Name': room_name,  # str with len>=1 or None
            'Device Name': device_name,  # str with len>=1 or None
        })

        # If a room has no pair, StopListening for connections
        if isinstance(room_interface, EthernetServerInterfaceEx):
            paired_interface = self._get_paired_interface(room_interface)
            if paired_interface is None:
                room_interface.StopListen()
                for client in room_interface.Clients:
                    client.Disconnect()
            else:
                room_interface.StartListen()

        self._Reservation_Log.NewReservation(room_name, device_name)

        self._save()

        self._hide_loading_page()

        self._update_matrix_ties()

        self._do_preset_recall(room_name, device_name)

    def _control_connection_handler(self, client, state):
        pass

    def _control_rx_data(self, client, data):
        '''
        This will allow a user to control the codec Farm remotely. Say from another GS program, Dataviewer, etc.
        TODO: define API
        '''
        print('_control_rx_data()\ninterface={}\ndata={}'.format(interface, data))

    def get_device_names(self):
        # return list of device name strings - sorted alphabetically
        keys = self._devices.keys()
        keys = list(keys)
        keys.sort()
        print('DeviceFarm.get_device_names() return', keys)
        return keys

    def get_room_names(self):
        # return list of device name strings - sorted alphabetically
        keys = self._rooms.keys()
        keys = list(keys)
        keys.sort()
        print('DeviceFarm.get_rooms_names() return', keys)
        return keys

    def get_connection_status(self, name):
        interface = self.get_interface_by_name(name)
        if isinstance(interface, extronlib.interface.EthernetClientInterface):
            try:
                success, fails, time = Ping(interface.IPAddress, count=1)
                if success > 0:
                    return 'Connected'
                else:
                    return 'Disconnected'

            except ValueError as e:
                return 'Disconnected'

        elif isinstance(interface, extronlib.interface.SerialInterface):
            return 'Connected'

        elif isinstance(interface, extronlib.interface.EthernetServerInterfaceEx):
            if len(interface.Clients) > 0:
                return 'Connected'
            else:
                return 'Disconnected'

    @property
    def farm_change(self):
        return self._farm_change_callback

    @farm_change.setter
    def farm_change(self, func):
        '''
        func should be callable and receive two params
        param 1 is a DeviceFarm object
        param 2 is a dict like this:
        {'Event Type': 'Connection Status' or 'Pair Update',
         'Value': 'Connected' or 'Disconnected' or other applicable value
         'Room Name': 'room1' or None,
         'Device Name': 'device1' or None,
         }
        '''
        print('DeviceFarm @farm_change.setter')
        self._farm_change_callback = func
        self.get_full_update()

    def get_paired_name(self, name1):
        interface1 = self.get_interface_by_name(name1)
        interface2 = self._get_paired_interface(interface1)
        if interface2:
            name2 = self.get_name_by_interface(interface2)
            return name2
        else:
            return None

    def get_available_device_names(self):
        print('DeviceFarm.get_available_device_names')
        available_devices = []
        # print('self._pairs=', self._pairs)
        for device_name in self._devices:
            # print('for device_name=', device_name)
            device_interface = self._devices[device_name]
            # print('for device_interface=', device_interface)

            if device_interface not in self._pairs.values():
                available_devices.append(device_name)

        available_devices.sort()
        print('available_devices=', available_devices)
        return available_devices

    def get_available_room_names(self):
        print('DeviceFarm.get_available_room_names')
        available_rooms = []
        for room_name in self._rooms:
            room_interface = self._rooms[room_name]
            if room_interface in self._pairs:
                paired_device = self._pairs[room_interface]
                if paired_device is None:
                    available_rooms.append(room_name)
            else:
                # room_interface not in self._pairs
                available_rooms.append(room_name)

        print('available_rooms=', available_rooms)
        return available_rooms

    def get_full_update(self):
        print('DeviceFarm.get_full_update')
        if self._farm_change_callback:
            # Send updates for room/device connection status
            for interface in self._connection_status:
                # print('DeviceFarm.get_full_update for interface=', interface)
                if interface in self._rooms.values():
                    self._send_event({
                        'Event Type': 'Connection Status',
                        'Value': self._connection_status[interface],
                        'Room Name': self.get_name_by_interface(interface),
                        'Device Name': None,
                    })

                elif interface in self._devices.values():
                    self._send_event({
                        'Event Type': 'Connection Status',
                        'Value': self._connection_status[interface],
                        'Room Name': None,
                        'Device Name': self.get_name_by_interface(interface),
                    })

                elif interface in self._preset_interfaces.values():
                    self._send_event({
                        'Event Type': 'Connection Status',
                        'Value': self._connection_status[interface],
                        'Room Name': None,
                        'Device Name': None,
                        'Preset Interface Name': self.get_name_by_interface(interface),
                    })

            # Send updates for current pairs
            for room_name in self._rooms:
                room_interface = self._rooms[room_name]

                if room_interface in self._pairs:
                    device_interface = self._pairs[room_interface]
                    device_name = self.get_name_by_interface(device_interface)
                    self._send_event({
                        'Event Type': 'Pair Update',
                        'Value': 'Paired',
                        'Room Name': room_name,  # str with len>=1 or None
                        'Device Name': device_name,  # str with len>=1 or None
                    })


                else:
                    # room_interface is not in self._pairs
                    # Thus is does not have a pair
                    self._send_event({
                        'Event Type': 'Pair Update',
                        'Value': 'Paired',
                        'Room Name': room_name,  # str with len>=1 or None
                        'Device Name': None,  # str with len>=1 or None
                    })

        # Send matrix update
        if self._matrix_interface is not None:
            state = self._connection_status.get(self._matrix_interface)
            if state == None:
                state = 'Disabled'

            self._send_event({
                'Event Type': 'Matrix Connection Status',
                'Value': state,
                'Room Name': None,  # str with len>=1 or None
                'Device Name': None,  # str with len>=1 or None
            })

    def _name_exists(self, name):
        # return True if name is already used for a room/device
        if name in self._rooms:
            return True
        elif name in self._devices:
            return True
        elif name in self._preset_interfaces:
            return True
        else:
            return False

    def delete_interface(self, interface):
        print('DeviceFarm.delete_interface(interface={})'.format(interface))

        name = self.get_name_by_interface(interface)
        print('name=', name)

        # unpair anything that was associated to this interface
        if name is not None:
            self.pair(name, '')

        # Send notification of the deleted device
        if name in self._rooms:
            room_name = name
        else:
            room_name = None

        if name in self._devices:
            device_name = name
        else:
            device_name = None

        self._send_event({
            'Event Type': 'Interface Deleted',
            'Value': 'Deleted',
            'Room Name': room_name,  # str with len>=1 or None
            'Device Name': device_name,  # str with len>=1 or None
        })

        # Remove all references to this interface
        def dict_pop(d):
            res = d.pop(name, None)
            if res:
                print('removed {} from {}'.format(name, d))

        for d in [self._rooms, self._pairs, self._devices]:
            dict_pop(d)

        for room_interface in self._pairs.copy():
            device_interface = self._pairs[room_interface]
            if device_interface == interface:
                self._pairs[room_interface] = None

        self._connection_status.pop(interface, None)

        # If this was a SerialInterface, make the port available for re-instantiation
        if isinstance(interface, SerialInterface):
            interface.Host._make_port_available(interface.Host, interface.Port)

        # If this was an EthernetServerInterfaceEx, make the port available for re-instantiation
        if isinstance(interface, EthernetServerInterfaceEx):
            EthernetServerInterfaceEx.clear_port_in_use(interface.IPPort)

    def _interfaces_above_limit(self):
        number_of_interfaces = (len(self._rooms) + len(self._devices))
        print('DeviceFarm._interfaces_above_limit()')
        if number_of_interfaces >= self._INTERFACE_LIMIT:
            print('DeviceFarm._interfaces_above_limit\n number_of_interfaces={}\n return True'.format(
                number_of_interfaces))
            return True
        else:
            print('DeviceFarm._interfaces_above_limit\n number_of_interfaces={}\n return False'.format(
                number_of_interfaces))
            return False

    def _save(self):
        print('DeviceFarm._save()\n self._init_complete={}'.format(self._init_complete))
        self._do_save_Wait.Restart()

    def _do_save(self):
        print('DeviceFarm._do_save()\n self._init_complete={}'.format(self._init_complete))
        try:
            if self._init_complete:
                save_dict = {}

                # Grab the room interfaces
                print('save room data')
                save_dict['rooms'] = {}
                for room_name in self._rooms.copy():
                    room_interface = self._rooms[room_name]
                    room_dict = dict(room_interface)
                    save_dict['rooms'][room_name] = room_dict

                # Grab the device interfaces
                print('save device data')
                save_dict['devices'] = {}
                for device_name in self._devices.copy():
                    device_interface = self._devices[device_name]
                    device_dict = dict(device_interface)
                    save_dict['devices'][device_name] = device_dict

                # Grab the pairs
                print('save pairs data')
                save_dict['pairs'] = {}
                for room_interface in self._pairs.copy():
                    room_name = self.get_name_by_interface(room_interface)

                    device_interface = self._pairs[room_interface]
                    device_name = self.get_name_by_interface(device_interface)

                    save_dict['pairs'][room_name] = device_name

                # Grab matrix name/connection info
                print('save matrix data')
                if self._matrix_interface is not None:
                    save_dict['matrix_connection'] = dict(self._matrix_interface)
                    save_dict['matrix_connection']['Name'] = self._matrix_name
                else:
                    save_dict['matrix_connection'] = None

                # Grab matrix input/output info
                matrix_io_temp = {}
                # print('be-for')
                for key in self._matrix_info:
                    # print('key=', key)
                    if key not in matrix_io_temp:
                        matrix_io_temp[key] = {}

                    for interface, number in self._matrix_info[key].items():
                        # print('interface={}\n number={}'.format(interface, number))
                        interface_name = self.get_name_by_interface(interface)
                        matrix_io_temp[key][interface_name] = number

                print('matrix_io_temp=', matrix_io_temp)
                save_dict['matrix_io'] = matrix_io_temp

                # Grab preset data
                save_dict['preset_info'] = self._preset_info.copy()

                preset_interfaces = {}
                for interface_name in self._preset_interfaces:
                    interface = self._preset_interfaces[interface_name]
                    preset_interfaces[interface_name] = dict(interface)
                save_dict['preset_interfaces'] = preset_interfaces

                # Make json string
                print('save_dict=', save_dict)
                try:
                    save_json = json.dumps(save_dict)
                except Exception as e:
                    print('ERROR converting json\n{}'.format(e))

                # Write json to file
                with File('farm_data.json', mode='wt') as file:
                    file.write(save_json)

        except Exception as e:
            print('DeviceFarm._save\nError:{}'.format(e))
            raise e

        print('save complete')

    def _load(self):
        print('DeviceFarm._load()')
        try:
            if File.Exists('farm_data.json'):
                with File('farm_data.json', mode='rt') as file:
                    data_json = file.read()
                    data = json.loads(data_json)

                    print('loading room data')
                    for room_name in data['rooms']:
                        try:
                            room_dict = data['rooms'][room_name]

                            if 'EthernetServerInterfaceEx' in room_dict['Type']:
                                IPPort = room_dict['IPPort']
                                Protocol = room_dict['Protocol']
                                Interface = room_dict['Interface']
                                MaxClients = room_dict['MaxClients']

                                try:
                                    self.add_ethernet_room(room_name, IPPort, Protocol, Interface, MaxClients)
                                except Exception as e:
                                    ProgramLog('Error loading ethernet room\n' + str(e), 'error')

                            elif 'SerialInterface' in room_dict['Type']:
                                HostAlias = room_dict['Host.DeviceAlias']
                                Host = ProcessorDevice(HostAlias)
                                print('load SerialInterface Host=', Host)
                                Port = room_dict['Port']
                                Baud = room_dict['Baud']
                                Data = room_dict['Data']
                                Parity = room_dict['Parity']
                                Stop = room_dict['Stop']
                                FlowControl = room_dict['FlowControl']
                                CharDelay = room_dict['CharDelay']
                                Mode = room_dict['Mode']

                                try:
                                    self.add_serial_room(room_name, Host=Host, Port=Port, Baud=Baud, Data=Data,
                                                         Parity=Parity, Stop=Stop, FlowControl=FlowControl,
                                                         CharDelay=CharDelay, Mode=Mode)
                                except Exception as e:
                                    ProgramLog('Error loading serial room\n' + str(e), 'error')

                        except Exception as e:
                            ProgramLog(str(e), 'warning')

                    print('loading devices data')
                    for device_name in data['devices']:
                        try:

                            device_dict = data['devices'][device_name]

                            if 'EthernetClientInterface' in device_dict['Type']:
                                Hostname = device_dict['Hostname']
                                IPPort = device_dict['IPPort']
                                Protocol = device_dict['Protocol']
                                ServicePort = device_dict['ServicePort']
                                Credentials = device_dict['Credentials']

                                try:
                                    self.add_ethernet_device(device_name, Hostname, IPPort, Protocol, ServicePort,
                                                             Credentials)
                                except Exception as e:
                                    ProgramLog('Error loading ethernet device\n' + str(e), 'error')

                            elif 'SerialInterface' in device_dict['Type']:
                                HostAlias = device_dict['Host.DeviceAlias']
                                Host = ProcessorDevice(HostAlias)
                                Port = device_dict['Port']
                                Baud = device_dict['Baud']
                                Data = device_dict['Data']
                                Parity = device_dict['Parity']
                                Stop = device_dict['Stop']
                                FlowControl = device_dict['FlowControl']
                                CharDelay = device_dict['CharDelay']
                                Mode = device_dict['Mode']

                                try:
                                    self.add_serial_device(device_name, Host=Host, Port=Port, Baud=Baud, Data=Data,
                                                           Parity=Parity, Stop=Stop, FlowControl=FlowControl,
                                                           CharDelay=CharDelay, Mode=Mode)
                                except Exception as e:
                                    ProgramLog('Error loading serial device\n' + str(e), 'error')

                        except Exception as e:
                            print(str(e), 'warning')

                    print('loading pairs data')
                    for room_name in data['pairs']:
                        try:
                            device_name = data['pairs'][room_name]

                            self.pair(room_name, device_name)
                        except Exception as e:
                            ProgramLog(str(e), 'warning')

                    print('loading matrix data')
                    matrix_dict = data.get('matrix_connection')
                    if matrix_dict is not None:
                        print('matrix_dict=', matrix_dict)
                        matrix_name = matrix_dict['Name']

                        if 'SerialInterface' in matrix_dict['Type']:
                            HostAlias = matrix_dict['Host.DeviceAlias']
                            Host = ProcessorDevice(HostAlias)
                            Port = matrix_dict['Port']
                            Baud = matrix_dict['Baud']
                            Data = matrix_dict['Data']
                            Parity = matrix_dict['Parity']
                            Stop = matrix_dict['Stop']
                            FlowControl = matrix_dict['FlowControl']
                            CharDelay = matrix_dict['CharDelay']
                            Mode = matrix_dict['Mode']

                            try:
                                self.add_serial_matrix(matrix_name, Host=Host, Port=Port, Baud=Baud, Data=Data,
                                                       Parity=Parity, Stop=Stop, FlowControl=FlowControl,
                                                       CharDelay=CharDelay, Mode=Mode)
                            except Exception as e:
                                ProgramLog('Error loading serial matrix\n' + str(e), 'error')

                        elif 'EthernetClientInterface' in matrix_dict['Type']:
                            Hostname = matrix_dict['Hostname']
                            IPPort = matrix_dict['IPPort']
                            Protocol = matrix_dict['Protocol']
                            ServicePort = matrix_dict['ServicePort']
                            Credentials = matrix_dict['Credentials']

                            try:
                                self.add_ethernet_matrix(matrix_name, Hostname, IPPort, Protocol, ServicePort,
                                                         Credentials)
                            except Exception as e:
                                ProgramLog('Error loading ethernet matrix\n' + str(e), 'error')

                    print('loading matrix_info')
                    print('pre self._matrix_info=', self._matrix_info)
                    matrix_info = data.get('matrix_io')
                    if matrix_info is not None:
                        for key in matrix_info:
                            for interface_name, number in matrix_info[key].items():
                                interface = self.get_interface_by_name(interface_name)
                                self._matrix_info[key][interface] = number
                    print('post load self._matrix_info=', self._matrix_info)

                    print('loading preset interfaces')
                    preset_interfaces = data.get('preset_interfaces')
                    if preset_interfaces:
                        print('preset_interfaces=', preset_interfaces)
                        for interface_name in preset_interfaces:
                            interface_params = preset_interfaces[interface_name]
                            if 'EthernetClientInterface' in interface_params['Type']:
                                Hostname = interface_params['Hostname']
                                IPPort = interface_params['IPPort']
                                Protocol = interface_params['Protocol']
                                ServicePort = interface_params['ServicePort']
                                Credentials = interface_params['Credentials']

                                self.add_ethernet_preset_device(
                                    interface_name,
                                    Hostname,
                                    IPPort,
                                    Protocol,
                                    ServicePort,
                                    Credentials,
                                )
                            elif 'SerialInterface' in interface_params['Type']:
                                HostAlias = interface_params['Host.DeviceAlias']
                                Host = ProcessorDevice(HostAlias)
                                Port = interface_params['Port']
                                Baud = interface_params['Baud']
                                Data = interface_params['Data']
                                Parity = interface_params['Parity']
                                Stop = interface_params['Stop']
                                FlowControl = interface_params['FlowControl']
                                CharDelay = interface_params['CharDelay']
                                Mode = interface_params['Mode']

                                self.add_serial_preset_device(
                                    interface_name,
                                    Host=Host,
                                    Port=Port,
                                    Baud=Baud,
                                    Data=Data,
                                    Parity=Parity,
                                    Stop=Stop,
                                    FlowControl=FlowControl,
                                    CharDelay=CharDelay,
                                    Mode=Mode
                                )

                    print('loading preset info')
                    preset_info = data.get('preset_info')
                    if preset_info:
                        print('preset_info=', preset_info)
                        for preset_interface_name in preset_info:
                            for room_name in preset_info[preset_interface_name]:
                                for device_name in preset_info[preset_interface_name][room_name]:
                                    preset_number = preset_info[preset_interface_name][room_name][device_name]
                                    self.set_new_preset(room_name, device_name, preset_interface_name, preset_number)


        except Exception as e:
            ProgramLog('DeviceFarm._load failed\n{}\n'.format(e))

    def register_loading_callback(self, func):
        print('****\n DeviceFarm.register_loading_callback({})'.format(func))
        # func should accept 1 parameter
        # str > either 'Show' or 'Hide'
        self._loading_callbacks.append(func)

    def _show_loading_page(self):
        print('DeviceFarm._show_loading_page()')
        for func in self._loading_callbacks:
            func('Show')

    def _hide_loading_page(self):
        print('DeviceFarm._hide_loading_page()')
        for func in self._loading_callbacks:
            func('Hide')

    def _send_event(self, event_info):
        print('DeviceFarm._send_event(event_info={})'.format(event_info))
        '''event_info = somethine like this {'Event Type': 'Connection Status',
                                              'Value': new_connection_status,
                                              'Room Name': room_name, #str with len>=1 or None
                                              'Device Name': device_name, #str with len>=1 or None
                                              'Preset Interface Name': #str with len>=1 or None
                                              }
        '''

        if 'Preset Interface Name' not in event_info:
            event_info['Preset Interface Name'] = None

        if self._init_complete:
            if self._farm_change_callback:
                self._farm_change_callback(self, event_info)

    def _base_add_matrix(self, name, matrix_interface):

        self._matrix_name = name

        if self._matrix_interface is not None:
            self.delete_matrix_interface()  # There can only be one. <highlander>

        def matrix_connection_callback(interface, state):
            print('DeviceFarm.matrix_connection_callback(\n interface={}\n state={}'.format(interface, state))
            # When connected, make appropriate ties. If the matrix gets power cycled, then ties will be restored.
            if state == 'Disconnected':
                if hasattr(interface, 'StopKeepAlive'):
                    interface.StopKeepAlive()
            elif state == 'Connected':
                Wait(5, self._update_matrix_ties)

            self._write_connection_status(interface, state)

        HandleConnection(matrix_interface)
        AddConnectionCallback(matrix_interface, matrix_connection_callback)

        @event(matrix_interface, 'ReceiveData')
        def matrix_interfaceRxDataEvent(interface, data):
            if debugRxData: print('matrix_interfaceRxDataEvent\n interface={}\n data={}'.format(interface, data))

            if b'Extron Electronics' in data:
                if hasattr(interface, 'StartKeepAlive'):
                    interface.StartKeepAlive(3, 'q')

            ConnectionHandlerLogicalReset(interface)

        self._matrix_interface = matrix_interface

        self._update_matrix_ties()

        self._save()

    def add_serial_matrix(self, name, *args, **kwargs):

        if self._matrix_interface is not None:
            self.delete_matrix_interface()

        matrix_interface = SerialInterface(*args, **kwargs)
        self._base_add_matrix(name, matrix_interface)

    def add_ethernet_matrix(self, name, *args, **kwargs):

        if self._matrix_interface is not None:
            self.delete_matrix_interface()

        matrix_interface = EthernetClientInterface(*args, **kwargs)
        self._base_add_matrix(name, matrix_interface)

    def delete_matrix_interface(self):
        self._matrix_name = None

        if self._matrix_interface is not None:
            RemoveConnectionHandlers(self._matrix_interface)

            if hasattr(self._matrix_interface, 'Disconnect'):
                self._matrix_interface.Disconnect()

            if isinstance(self._matrix_interface, SerialInterface):
                Host = self._matrix_interface.Host
                Port = self._matrix_interface.Port

                ProcessorDevice._make_port_available(Host, Port)

        self._send_event({
            'Event Type': 'Matrix Connection Status',
            'Value': 'Disabled',
            'Room Name': None,  # str with len>=1 or None
            'Device Name': None,  # str with len>=1 or None
        })

        self._connection_status.pop(self._matrix_interface, None)

        self._matrix_interface = None

        self._save()

    def _update_matrix_ties(self):
        if self._init_complete:
            if self._connection_status.get(self._matrix_interface) == 'Connected':
                if self._matrix_interface:
                    send_string = 'w+q'  # Qik tie command. Queues up tie commands

                    for room_interface in self._pairs:
                        device_interface = self._pairs[room_interface]

                        # Get room inputs/outputs
                        room_inputA = self._matrix_info['InputA'].get(room_interface, '0')
                        room_inputB = self._matrix_info['InputB'].get(room_interface, '0')

                        room_outputA = self._matrix_info['OutputA'].get(room_interface, '0')
                        room_outputB = self._matrix_info['OutputB'].get(room_interface, '0')

                        # Get device inputs/outputs
                        device_inputA = self._matrix_info['InputA'].get(device_interface,
                                                                        '0')  # if not found return '0'
                        device_inputB = self._matrix_info['InputB'].get(device_interface, '0')

                        device_outputA = self._matrix_info['OutputA'].get(device_interface, '0')
                        device_outputB = self._matrix_info['OutputB'].get(device_interface, '0')

                        send_string += '{}*{}!'.format(room_inputA, device_outputA)
                        send_string += '{}*{}!'.format(room_inputB, device_outputB)
                        send_string += '{}*{}!'.format(device_inputA, room_outputA)
                        send_string += '{}*{}!'.format(device_inputB, room_outputB)

                    send_string += '\r'

                    self._matrix_interface.Send(send_string)  # Executes all queued ties instantly

    def get_matrix_interface(self):
        return self._matrix_interface

    def get_matrix_name(self):
        return self._matrix_name

    def register_matrix_info(self, interface_name, key, input_num):
        print('DeviceFarm.register_matrix_info(interface_name={}, key={}, input_num={})'.format(interface_name, key,
                                                                                                input_num))
        # key should equal 'InputA', 'InputB', 'OutputA', 'OutputB'
        if key not in ['InputA', 'InputB', 'OutputA', 'OutputB']:
            raise Exception("key must be one of these ['InputA', 'InputB', 'OutputA', 'OutputB']")

        interface = self.get_interface_by_name(interface_name)

        self._matrix_info[key][interface] = input_num

        print('self._matrix_info=', self._matrix_info)

        self._save()

    def get_matrix_info(self, interface_name, key):
        print('DeviceFarm.get_matrix_info(interface_name={}, key={})'.format(interface_name, key))
        interface = self.get_interface_by_name(interface_name)
        input_num = self._matrix_info[key].get(interface)

        if input_num is None:
            return '0'
        else:
            return input_num

    # Preset Device methods *****************************************************

    def _base_add_preset_device(self, name, interface):
        print('DeviceFarm._base_add_preset_device(name={}, interface={})'.format(name, interface))

        self._preset_interfaces[name] = interface

        # Init the connection status
        if isinstance(interface, SerialInterface):
            self._write_connection_status(interface, 'Connected')  # SerialInterfaces are always "Connected"
        else:
            self._write_connection_status(interface, 'Disconnected')

        # Setup connection handling
        def preset_connection_callback(interface, state):
            print('preset_connection_callback(\ninterface={}\nstate={}'.format(interface, state))
            if state == 'Disconnected':
                if hasattr(interface, 'StopKeepAlive'):
                    interface.StopKeepAlive()
            elif state == 'Connected':
                Wait(5, self._do_all_preset_recall)

            self._write_connection_status(interface, state)

        HandleConnection(interface)
        AddConnectionCallback(interface, preset_connection_callback)

        @event(interface, 'ReceiveData')
        def preset_device_rx_data_event(interface, data):
            if debugRxData: print('preset_device_rx_data_event(\ninterface={}\ndata={}'.format(interface, data))
            if b'Extron Electronics' in data:
                if hasattr(interface, 'StartKeepAlive'):
                    interface.StartKeepAlive(3, 'q')

            ConnectionHandlerLogicalReset(interface)

        self._save()

    def add_ethernet_preset_device(self, name, *args, **kwargs):
        print('DeviceFarm.add_ethernet_preset_device(name={}, args={}, kwargs={})'.format(name, args, kwargs))

        if not self._name_exists(name):
            interface = EthernetClientInterface(*args, **kwargs)
            self._base_add_preset_device(name, interface)
        else:
            raise Exception('The name "{}" already exists.\n\nPlease enter a different name'.format(name))

    def add_serial_preset_device(self, name, *args, **kwargs):
        print('DeviceFarm.add_serial_preset_device(name={}, args={}, kwargs={})'.format(name, args, kwargs))

        if not self._name_exists(name):
            interface = SerialInterface(*args, **kwargs)
            self._base_add_preset_device(name, interface)
        else:
            raise Exception('The name "{}" already exists.\n\nPlease enter a different name'.format(name))

    def delete_preset_interface(self, interface):
        print('DeviceFarm.delete_preset_device_interface(interface={})'.format(interface))

        interface_name = self.get_name_by_interface(interface)
        print('delete name=', interface_name)

        RemoveConnectionHandlers(interface)

        # remove the interface from self._preset_interfaces
        for preset_interface_name in self._preset_interfaces.copy():
            i = self._preset_interfaces[preset_interface_name]
            if i == interface:
                self._preset_interfaces.pop(preset_interface_name, None)

        # Make the serial port availabe for another purpose
        if isinstance(interface, SerialInterface):
            ProcessorDevice._make_port_available(interface.Host, interface.Port)

        # remove any presets from self._preset_info
        for preset_interface_name in self._preset_info.copy():
            if preset_interface_name == interface_name:
                self._preset_info.pop(preset_interface_name, None)

        self._send_event({
            'Event Type': 'Interface Deleted',
            'Value': 'Deleted',
            'Room Name': None,  # str with len>=1 or None
            'Device Name': None,  # str with len>=1 or None
            'Preset Interface Name': interface_name,
        })

        self._save()

    def get_preset_interface_names(self, name):
        print('DeviceFarm.get_preset_device_interface(name={})'.format(name))
        # return interface names
        r = list(self._preset_interfaces.keys())
        print('return {}'.format(r))
        return r

    def get_preset_info(self):
        '''
        returns a dict like this

        {'Preset Interface Name': {'room_name':  {'device_name': int(preset_num),
                                                  'device_name2': int(preset_num2),},
                                   'room_name2': {'device_name3': int(preset_num3),
                                                  'device_name4': int(preset_num4),}
        }
        '''
        return self._preset_info.copy()

    def get_presets_for_interface(self, interface):
        interface_name = self.get_name_by_interface(interface)
        return self._preset_info.copy().get(interface_name)

    def get_preset_interface_names(self):
        return list(self._preset_interfaces.keys())

    def set_new_preset(self, room_name, device_name, preset_interface_name, preset_number):
        if preset_interface_name not in self._preset_info:
            self._preset_info[preset_interface_name] = {}

        if room_name not in self._preset_info[preset_interface_name]:
            self._preset_info[preset_interface_name][room_name] = {}

        self._preset_info[preset_interface_name][room_name][device_name] = preset_number

        self._send_event({
            'Event Type': 'Preset Change',
            'Value': preset_number,
            'Room Name': room_name,  # str with len>=1 or None
            'Device Name': device_name,  # str with len>=1 or None
            'Preset Interface Name': preset_interface_name,
        })

        self._save()

    def _do_all_preset_recall(self):
        for room_interface in self._pairs:
            device_interface = self._pairs[room_interface]

            room_name = self.get_name_by_interface(room_interface)
            device_name = self.get_name_by_interface(device_interface)

            self._do_preset_recall(room_name, device_name)

            time.sleep(1)  # Extron DMPs need 1 sec delay between preset recall commands

    def _do_preset_recall(self, room_name, device_name):
        '''
        This method will check the current pairs and send preset-recall commands if certain pairs are made according to self._preset_info
        '''
        print('DeviceFarm._do_preset_recall(room_name={}, device_name={})'.format(room_name, device_name))

        if room_name == None:
            room_name = '<No Room>'

        if device_name == None:
            device_name = '<No Device>'

        for preset_interface_name in self._preset_info:
            print('preset_interface_name=', preset_interface_name)
            print('self._preset_info[preset_interface_name]=', self._preset_info[preset_interface_name])
            for p_room_name in self._preset_info[preset_interface_name]:
                print('p_room_name=', p_room_name)
                for p_device_name in self._preset_info[preset_interface_name][p_room_name]:
                    print('p_device_name=', p_device_name)

                    if p_room_name == room_name:
                        if p_device_name == device_name:
                            preset_number = self._preset_info[preset_interface_name][p_room_name][p_device_name]
                            print('preset_number=', preset_number)

                            interface = self.get_interface_by_name(preset_interface_name)
                            print(
                                'Recalling Preset\nInterface Name: {}\nPreset Number: {}'.format(preset_interface_name,
                                                                                                 preset_number))
                            interface.Send('\r{}.\r'.format(preset_number))

            if debug:
                time.sleep(0.0001)  # to make sure trace messages get printed in order

    def delete_preset(self, room_name, device_name, preset_interface_name):
        preset_info = self._preset_info.copy()

        for p_preset_interface_name in preset_info.copy():
            for p_room_name in preset_info[p_preset_interface_name].copy():
                for p_device_name in preset_info[p_preset_interface_name][p_room_name].copy():

                    if p_preset_interface_name == preset_interface_name:
                        if p_room_name == room_name:
                            if p_device_name == device_name:
                                self._preset_info[p_preset_interface_name][p_room_name].pop(p_device_name, None)

        self._save()

    def GetInterfaceKind(self, interface):
        # Return 'Room', 'Device', 'Matrix', 'Preset'
        if interface in self._rooms.values():
            return 'Room'

        elif interface in self._devices.values():
            return 'Device'

        elif (interface == self._matrix_interface and
                      interface is not None):
            return 'Matrix'
        elif interface in _preset_interfaces:
            return 'Preset'

        else:
            return None


# Class to help with logging data ***********************************************
class Logger:
    def __init__(self, filename=None):
        if filename is None:
            filename = 'reservation.log'

        self.filename = filename

        if not File.Exists(self.filename):
            File(self.filename, mode='wt').close()  # create a blank file

    def NewReservation(self, room_name, device_name):
        with File(self.filename, mode='at') as file:
            data = {'Event': 'New Reservation',
                    'Time': time.asctime(),
                    'Room Name': room_name,
                    'Device Name': device_name,
                    }
            data_json = json.dumps(data)
            file.write(data_json + '\r\n')

    def SystemRebooted(self):
        with File(self.filename, mode='at') as file:
            data = {'Event': 'System Rebooted',
                    'Time': time.asctime(),
                    }
            data_json = json.dumps(data)
            file.write(data_json + '\r\n')

    def ConnectionStatus(self, interface_name, status):
        with File(self.filename, mode='at') as file:
            data = {'Event': 'Connection Status',
                    'Time': time.asctime(),
                    'Interface Name': interface_name,
                    'Status': status,
                    }
            data_json = json.dumps(data)
            file.write(data_json + '\r\n')


from gs_tools import (
    EthernetServerInterfaceEx,
    SerialInterface,
    EthernetClientInterface,
    Ping,
    Wait,
    AddConnectionCallback,
    HandleConnection,
    ConnectionHandlerLogicalReset,
    RemoveConnectionHandlers,
    File,
    ProgramLog,
    ProcessorDevice,
    event,
    get_parent,
    Timer,
)
import extronlib
import time
import json

# Set this false to disable all print statements ********************************
debug = False
if not debug:
    def newPrint(*args, **kwargs):
        pass


    print = newPrint

debugRxData = False


# *******************************************************************************

class DeviceFarm(EthernetServerInterfaceEx):
    def __init__(self, *args, **kwargs):
        self._init_complete = False

        self._do_save_Wait = Wait(1, self._do_save)
        self._do_save_Wait.Cancel()

        self._loading_callbacks = []  # hold callback functions to show/hide the "please wait" page

        super().__init__(*args, **kwargs)
        self._connection_status = {  # interface: 'Dis/connected',
        }
        self._connection_timestamps = {  # clientObject: time.monotonic()
        }
        self._SERVER_TIMEOUT = 5 * 60  # 5 minutes
        self._disconnect_undead_sockets_Timer = Timer(60,
                                                      self._disconnect_undead_sockets)  # check every X seconds to see if we should disconnect any clients

        self._handle_connection_to_devices = []  # device_interfaces in this list should have their connection handled by the farm

        self.ReceiveData = self._control_rx_data
        self.Connected = self._control_connection_handler
        self.Disconnected = self._control_connection_handler

        # self.StartListen()  # control interface

        self._devices = {  # 'name': interface(EthernetClientInterface or SerialInterface)
        }

        self._rooms = {  # 'name': EthernetServerInterfaceEx or SerialInterface
        }

        self._pairs = {  # RoomInterface: DeviceInterface
        }

        self._INTERFACE_LIMIT = 25  # Max number of devices and rooms combined

        self._farm_change_callback = None
        self._matrix_interface = None
        self._matrix_name = None

        # Matrix device
        self._matrix_info = {}
        self._matrix_info['InputA'] = {  # interface: input_str,
        }
        self._matrix_info['InputB'] = {  # interface: input_str,
        }
        self._matrix_info['OutputA'] = {  # interface: input_str,
        }
        self._matrix_info['OutputB'] = {  # interface: input_str,
        }

        # Preset Devices
        self._preset_interfaces = {  # 'name': interface
        }
        self._preset_info = {  # 'Preset Interface Name': {'room_name': {'device_name': int(preset_num),
            #                                                              'device_name2': int(preset_num2),},
            #                                                'room_name2': {'device_name3': int(preset_num3),
            #                                                               'device_name4': int(preset_num4),}
        }

        # Log reservations for later examination - do this before self._load
        self._Reservation_Log = Logger('farm_reservation.log')
        self._Reservation_Log.SystemRebooted()

        # Log connection status changes
        self._Connection_Log = Logger('device_connection_status.log')
        self._Connection_Log.SystemRebooted()

        self._load()

        # The generator will ping one device per second to synchronously detect if a device falls offline
        self._device_name_generator = self._get_new_device_name_generator()
        self._device_name_generator_Wait = Wait(1, self._ping_a_device)

        self._init_complete = True

        self._update_matrix_ties()
        self._do_all_preset_recall()

    def _handle_connection(self, device_interface):
        print('DeviceFarm._handle_connection\n device_interface={}'.format(device_interface))
        if device_interface not in self._handle_connection_to_devices:
            self._handle_connection_to_devices.append(device_interface)

            AddConnectionCallback(device_interface, self._write_connection_status)
            HandleConnection(device_interface)

    def _restore_endpoint_connection_handler(self, interface):
        print('DeviceFarm._restore_endpoint_connection_handler\n interface={}'.format(interface))
        RemoveConnectionHandlers(interface)

        if interface in self._handle_connection_to_devices:
            self._handle_connection_to_devices.remove(interface)

            interface.ReceiveData = self._endpoint_rx_data
            interface.Connected = self._endpoint_connection_handler
            interface.Disconnected = self._endpoint_connection_handler

    def _get_new_device_name_generator(self):
        def the_generator():
            while True:
                # print('the_generator while True')
                # print('self._devices=', self._devices)

                if len(self._devices) == 0:
                    # print('if len(self._devices) == 0:')
                    yield None
                else:
                    # print('else')
                    for device_name in self._devices.copy():
                        # print('for device_name=', device_name)
                        yield device_name

        return the_generator()

    def _ping_a_device(self):
        try:
            # print('self._device_name_generator=', self._device_name_generator)
            device_name = next(self._device_name_generator)

            connection_status = self.get_connection_status(device_name)
            interface = self.get_interface_by_name(device_name)

            self._write_connection_status(interface, connection_status)
            # ('_ping_a_device {} {}'.format(device_name, connection_status))

        except Exception as e:
            print('Exception in DeviceFarm._ping_a_device\n', e)

        self._device_name_generator_Wait.Restart()

    def _base_add_device(self, name, interface):
        self._show_loading_page()

        interface.ReceiveData = self._endpoint_rx_data
        interface.Connected = self._endpoint_connection_handler
        interface.Disconnected = self._endpoint_connection_handler

        self._devices[name] = interface

        if isinstance(interface, SerialInterface):
            self._write_connection_status(interface, 'Connected')  # SerialInterfaces are always "Connected"
        else:
            self._write_connection_status(interface, 'Disconnected')

        self._device_name_generator = self._get_new_device_name_generator()

        self.pair(name, '')

        self._save()

        self._hide_loading_page()

    def add_ethernet_device(self, name, *args, **kwargs):  # instantiate like a EthernetClientInterface
        '''
        name > str()
        args/kwargs > same args/kwargs you would use to instantiate an extronlib.interface.EthernetClientInterface
        '''
        if self._interfaces_above_limit():
            raise Exception(
                'The device farm interface limit has been reached.\nA maximum of {} rooms/devices are allowed.'.format(
                    self._INTERFACE_LIMIT))

        if len(name) <= 0:
            raise Exception('The name must be a str of len >= 1')
        elif self._name_exists(name):
            raise Exception('The name "{}" is already used for another room/device'.format(name))

        newClient = EthernetClientInterface(*args, **kwargs)
        self._base_add_device(name, newClient)

    def add_serial_device(self, name, *args, **kwargs):
        '''
        name > str()
        args/kwargs > same args/kwargs you would use to instantiate an extronlib.interface.SerialInterface
        '''
        print('DeviceFarm.add_serial_device\n name={}\n args={}\n kwargs={}'.format(name, args, kwargs))
        if self._interfaces_above_limit():
            raise Exception(
                'The device farm interface limit has been reached.\nA maximum of {} rooms/devices are allowed.'.format(
                    self._INTERFACE_LIMIT))

        if len(name) <= 0:
            raise Exception('The name must be a str of len >= 1')
        elif self._name_exists(name):
            raise Exception('The name "{}" is already used for another room/device'.format(name))

        newSerial = SerialInterface(*args, **kwargs)
        self._base_add_device(name, newSerial)

    def _base_add_room(self, name, interface):
        '''
        name > str()
        args/kwargs > same args/kwargs you would use to instantiate an extronlib.interface.EthernetServerInterfaceEx
        '''
        self._show_loading_page()

        interface.ReceiveData = self._endpoint_rx_data
        interface.Connected = self._endpoint_connection_handler
        interface.Disconnected = self._endpoint_connection_handler

        self._rooms[name] = interface

        if isinstance(interface, extronlib.interface.SerialInterface):
            self._write_connection_status(interface, 'Connected')  # Physical ports are always physically connected
        else:
            self._write_connection_status(interface, 'Disconnected')

        self.pair(name, '')  # Pair with nothing just to init all the needed attributes

        self._save()

        self._hide_loading_page()

    def add_ethernet_room(self, name, *args, **kwargs):
        '''
        name > str()
        args/kwargs > same args/kwargs you would use to instantiate an extronlib.interface.EthernetServerInterfaceEx
        '''
        if self._interfaces_above_limit():
            raise Exception(
                'The device farm interface limit has been reached.\nA maximum of {} rooms/devices are allowed.'.format(
                    self._INTERFACE_LIMIT))

        if len(name) <= 0:
            raise Exception('The name must be a str of len >= 1')

        elif self._name_exists(name):
            raise Exception('The name "{}" is already used for another room/device'.format(name))

        print('DeviceFarm.add_ethernet_room(\n name={} \n*args={} \n**kwargs={}'.format(name, args, kwargs))
        room_server = EthernetServerInterfaceEx(*args, **kwargs)
        print('room_server=', room_server)
        # room_server.StartListen()

        self._base_add_room(name, room_server)

    def add_serial_room(self, name, *args, **kwargs):
        '''
        name > str()
        args/kwargs > same args/kwargs you would use to instantiate an extronlib.interface.EthernetServerInterfaceEx
        '''
        if self._interfaces_above_limit():
            raise Exception(
                'The device farm interface limit has been reached.\nA maximum of {} rooms/devices are allowed.'.format(
                    self._INTERFACE_LIMIT))

        if len(name) <= 0:
            raise Exception('The name must be a str of len >= 1')
        elif self._name_exists(name):
            raise Exception('The name "{}" is already being used for another room/device'.format(name))

        print('DeviceFarm.add_serial_room(name={} \n*args={} \n**kwargs={}'.format(name, args, kwargs))
        roomServer = SerialInterface(*args, **kwargs)

        self._base_add_room(name, roomServer)

    def _get_paired_interface(self, interface):
        '''
        interface > extronlib.interface.*
        returns the device/room that is paired with interface.
        if no pair exists, return None
        '''
        if debugRxData: print('DeviceFarm._get_paired_interface\n interface={}'.format(interface))
        for k, v in self._pairs.copy().items():
            # print('pair_room={}\npair_device={}'.format(k, v))
            pass

        # If this is a ClientObject, grab the parent
        if isinstance(interface, extronlib.interface.EthernetServerInterfaceEx.ClientObject):
            interface = get_parent(interface)

        for room_interface in self._pairs.copy():
            device_interface = self._pairs.copy()[room_interface]

            if interface == room_interface:
                return device_interface

            elif interface == device_interface:
                return room_interface

    def _endpoint_rx_data(self, interface, data):
        '''
        interface > extronlib.interface.EthernetServerInterfaceEx.ClientObject or
                    extronlib.interface.EthernetClientInterface, or SerialInterface
        data > bytes()

        This method will route the data between the device and the room its paired with.
        '''
        ConnectionHandlerLogicalReset(interface)

        if isinstance(interface, extronlib.interface.EthernetServerInterfaceEx.ClientObject):
            self._connection_timestamps[interface] = time.monotonic()

        paired_interface = self._get_paired_interface(interface)
        if debugRxData: print(
            '_endpoint_rx_data()\ninterface={}\n data={}\n paired_interface={}'.format(interface, data,
                                                                                       paired_interface))

        # Send the data to the paired_interface
        if paired_interface:
            if isinstance(paired_interface, extronlib.interface.EthernetServerInterfaceEx):
                for client in paired_interface.Clients:
                    client.Send(data)
            else:
                paired_interface.Send(data)

    def _write_connection_status(self, interface, new_connection_status):
        '''
        This method should save the connection state and trigger any connection events
        '''
        # print('_write_connection_status\n interface={}, new_connection_status={}'.format(interface, new_connection_status))
        # Convert ClientObject to ServerEx if needed
        if isinstance(interface, extronlib.interface.EthernetServerInterfaceEx.ClientObject):
            interface = get_parent(interface)

        # Determine the room_name and device_name
        name = self.get_name_by_interface(interface)
        # print('_write_connection_status name=', name)
        if name in self._rooms:
            room_name = name
            device_name = None
        elif name in self._devices:
            room_name = None
            device_name = name
        else:
            room_name = None
            device_name = None

        # Determnine the old connection status
        if interface in self._connection_status:
            old_connection_status = self._connection_status[interface]
        else:
            old_connection_status = 'Unknown'

        # If status changed, do the callback
        if old_connection_status != new_connection_status:
            print(
                'DeviceFarm._write_connection_status\ninterface={}, state={}'.format(interface, new_connection_status))

            event_info = {}

            if interface == self._matrix_interface:
                event_info['Event Type'] = 'Matrix Connection Status'

            else:
                event_info['Event Type'] = 'Connection Status'

            event_info['Value'] = new_connection_status
            event_info['Room Name'] = room_name  # str with len>=1 or None
            event_info['Device Name'] = device_name  # str with len>=1 or None

            if interface in self._preset_interfaces.values():
                event_info['Preset Interface Name'] = self.get_name_by_interface(interface)

            self._send_event(event_info)

            # log the connection status change
            interface_name = self.get_name_by_interface(interface)

            if interface_name is None:
                interface_name = interface.IPAddress

            self._Connection_Log.ConnectionStatus(interface_name, new_connection_status)

        self._connection_status[interface] = new_connection_status

    def _disconnect_undead_sockets(self):
        try:
            print('DeviceFarm._disconnect_undead_sockets()')
            # if no data has been received from the socket for > X seconds, disconnect the socket.
            for client in self._connection_timestamps.copy():
                client_last_time = self._connection_timestamps[client]
                now_time = time.monotonic()

                print('time since last comm with client {}\n {} seconds'.format(client, now_time - client_last_time))

                if (now_time - client_last_time) > self._SERVER_TIMEOUT:
                    print(
                        'Disconnecting client {}:{} due to inactivity for more than {} seconds'.format(client.IPAddress,
                                                                                                       client.ServicePort,
                                                                                                       self._SERVER_TIMEOUT))
                    self._connection_timestamps.pop(client, None)
                    client.Disconnect()
        except Exception as e:
            print('Exception in DeviceFarm._disconnect_undead_sockets\n {}'.format(e))

    def _endpoint_connection_handler(self, interface, state):
        '''
        When a room connects to the Farm, the Farm should then connect to the paired device.
        When a room disconnects from the Farm, the Farm should then disconnect from the paired device.
        When a device disconnects from the Farm, the Farm should also disconnect the paired room.

        This is most usefull when connecting to devices that require a telnet handshake upon connecting.
            For example, the Cisco SX80.
            This allows the room to handle the telnet handshake and not the farm.
        '''
        print('_endpoint_connection_handler()\ninterface={}\nstate={}'.format(interface, state))

        # Save the connection state for later
        if isinstance(interface, extronlib.interface.EthernetServerInterfaceEx.ClientObject):
            parent = get_parent(interface)
            if len(parent.Clients) > 0:
                self._write_connection_status(interface, 'Connected')
            else:
                self._write_connection_status(interface, 'Disconnected')

        elif isinstance(interface, extronlib.interface.EthernetClientInterface):
            self._write_connection_status(interface, state)

        # Perform the appropriate action on the paried interface
        paired_interface = self._get_paired_interface(interface)
        if paired_interface:

            if isinstance(interface, extronlib.interface.EthernetServerInterfaceEx.ClientObject):
                # Dis/connect the paired interface
                if state == 'Connected':
                    if hasattr(paired_interface, 'Connect'):
                        paired_interface.Connect()
                elif state == 'Disconnect':
                    paired_interface.Disconnect()
                    self._connection_timestamps.pop(interface, None)

            elif isinstance(interface, extronlib.interface.EthernetServerInterfaceEx):
                # paired_interface is a EthernetServerInterfaceEx
                for client in paired_interface.Clients:
                    if state == 'Connected':
                        pass  # Cant force the client to connect
                    elif state == 'Disconnected':
                        client.Disconnect()

        # timestamp connection
        if isinstance(interface, extronlib.interface.EthernetServerInterfaceEx.ClientObject):
            if interface not in self._connection_timestamps:
                self._connection_timestamps[interface] = time.monotonic()

        # If this interface is a preset interface. Recall all the presets
        if state == 'Connected' and interface in self._preset_interfaces.values():
            self._do_all_preset_recall()

    def get_name_by_interface(self, interface):
        if isinstance(interface, extronlib.interface.EthernetServerInterfaceEx.ClientObject):
            interface = get_parent(interface)

        for device_name in self._devices:
            i = self._devices[device_name]
            if interface == i:
                return device_name

        for room_name in self._rooms:
            i = self._rooms[room_name]
            if interface == i:
                return room_name

        for preset_interface_name in self._preset_interfaces:
            i = self._preset_interfaces[preset_interface_name]
            if interface == i:
                return preset_interface_name

        if interface == self._matrix_interface:
            return self._matrix_name

        return None

    def get_interface_by_name(self, name):
        for n in self._devices:
            if name == n:
                return self._devices[n]

        for n in self._rooms:
            if name == n:
                return self._rooms[n]

        for n in self._preset_interfaces:
            if name == n:
                return self._preset_interfaces[n]

        if name == self._matrix_name:
            return self._matrix_interface

        return None

    def pair(self, name1, name2):
        '''
        Will allow communication between rooms and devices
        To "unpair" something call Farm.pair('RoomOrDeviceName', None)
        '''
        print('DeviceFarm.pair(name1={}, name2={}'.format(name1, name2))

        self._show_loading_page()

        # prevent bad data
        if not isinstance(name1, str):
            raise Exception(
                'name1 must be type str \nPassed params name1={}, name2={}'.format(name1, name2))

        if not isinstance(name2, str) and name2 is not None:
            raise Exception('name2 must be type str\nPassed params name1={}, name2={}'.format(name1, name2))

        # Determine which name is the room/device
        if name1 in self._rooms:
            room_name = name1
        elif name2 in self._rooms:
            room_name = name2
        else:
            room_name = None

        if name1 in self._devices:
            device_name = name1
        elif name2 in self._devices:
            device_name = name2
        else:
            device_name = None

        print('pair device_name=', device_name)
        print('pair room_name=', room_name)

        # Determine the associated interfaces
        room_interface = self.get_interface_by_name(room_name)
        device_interface = self.get_interface_by_name(device_name)

        # Disconnect any current pairs associated this room
        if room_interface in self._pairs:
            paired_interface = self._pairs[room_interface]

            if paired_interface is not None:
                # No longer handle connection if applicable
                self._restore_endpoint_connection_handler(paired_interface)

                # Send notification that device is no longer paired
                self._send_event({
                    'Event Type': 'Pair Update',
                    'Value': 'Available',
                    'Room Name': None,  # str with len>=1 or None
                    'Device Name': self.get_name_by_interface(paired_interface),  # str with len>=1 or None
                })

                # Disconnect device communication
                if hasattr(paired_interface, 'Disconnect'):
                    paired_interface.Disconnect()

        if hasattr(room_interface, 'Disconnect'):
            if isinstance(room_interface, EthernetServerInterfaceEx):
                for client in room_interface.Clients:
                    client.Disconnect()
            else:
                room_interface.Disconnect()

        # Disconnect any pairs associated with the device
        if device_interface in self._pairs.values():
            paired_interface = self._get_paired_interface(device_interface)

            # Send notification that device is no longer paired
            self._send_event({
                'Event Type': 'Pair Update',
                'Value': 'Available',
                'Room Name': self.get_name_by_interface(paired_interface),  # str with len>=1 or None
                'Device Name': None,  # str with len>=1 or None
            })

            # Disconnect device communication
            if hasattr(paired_interface, 'Disconnect'):
                if isinstance(paired_interface, EthernetServerInterfaceEx):
                    for client in paired_interface.Clients:
                        client.Disconnect()
                else:
                    paired_interface.Disconnect()

            # Remove the pair
            for r_interface in self._pairs.copy():
                d_interface = self._pairs[r_interface]
                if d_interface == device_interface:
                    self._pairs[r_interface] = None

        # Make and Save the new pair
        if room_interface:
            self._pairs[room_interface] = device_interface

        # if the new pair is a serial room and an IP device, the farm will handle the IP connection to the device
        if isinstance(room_interface, SerialInterface) and isinstance(device_interface, EthernetClientInterface):
            self._handle_connection(device_interface)

        print('self._pairs=', self._pairs)

        # Update callback
        self._send_event({
            'Event Type': 'Pair Update',
            'Value': 'Paired',
            'Room Name': room_name,  # str with len>=1 or None
            'Device Name': device_name,  # str with len>=1 or None
        })

        # If a room has no pair, StopListening for connections
        if isinstance(room_interface, EthernetServerInterfaceEx):
            paired_interface = self._get_paired_interface(room_interface)
            if paired_interface is None:
                room_interface.StopListen()
                for client in room_interface.Clients:
                    client.Disconnect()
            else:
                room_interface.StartListen()

        self._Reservation_Log.NewReservation(room_name, device_name)

        self._save()

        self._hide_loading_page()

        self._update_matrix_ties()

        self._do_preset_recall(room_name, device_name)

    def _control_connection_handler(self, client, state):
        pass

    def _control_rx_data(self, client, data):
        '''
        This will allow a user to control the codec Farm remotely. Say from another GS program, Dataviewer, etc.
        TODO: define API
        '''
        print('_control_rx_data()\ninterface={}\ndata={}'.format(interface, data))

    def get_device_names(self):
        # return list of device name strings - sorted alphabetically
        keys = self._devices.keys()
        keys = list(keys)
        keys.sort()
        print('DeviceFarm.get_device_names() return', keys)
        return keys

    def get_room_names(self):
        # return list of device name strings - sorted alphabetically
        keys = self._rooms.keys()
        keys = list(keys)
        keys.sort()
        print('DeviceFarm.get_rooms_names() return', keys)
        return keys

    def get_connection_status(self, name):
        interface = self.get_interface_by_name(name)
        if isinstance(interface, extronlib.interface.EthernetClientInterface):
            try:
                success, fails, time = Ping(interface.IPAddress, count=1)
                if success > 0:
                    return 'Connected'
                else:
                    return 'Disconnected'

            except ValueError as e:
                return 'Disconnected'

        elif isinstance(interface, extronlib.interface.SerialInterface):
            return 'Connected'

        elif isinstance(interface, extronlib.interface.EthernetServerInterfaceEx):
            if len(interface.Clients) > 0:
                return 'Connected'
            else:
                return 'Disconnected'

    @property
    def farm_change(self):
        return self._farm_change_callback

    @farm_change.setter
    def farm_change(self, func):
        '''
        func should be callable and receive two params
        param 1 is a DeviceFarm object
        param 2 is a dict like this:
        {'Event Type': 'Connection Status' or 'Pair Update',
         'Value': 'Connected' or 'Disconnected' or other applicable value
         'Room Name': 'room1' or None,
         'Device Name': 'device1' or None,
         }
        '''
        print('DeviceFarm @farm_change.setter')
        self._farm_change_callback = func
        self.get_full_update()

    def get_paired_name(self, name1):
        interface1 = self.get_interface_by_name(name1)
        interface2 = self._get_paired_interface(interface1)
        if interface2:
            name2 = self.get_name_by_interface(interface2)
            return name2
        else:
            return ''

    def get_available_device_names(self):
        print('DeviceFarm.get_available_device_names')
        available_devices = []
        # print('self._pairs=', self._pairs)
        for device_name in self._devices:
            # print('for device_name=', device_name)
            device_interface = self._devices[device_name]
            # print('for device_interface=', device_interface)

            if device_interface not in self._pairs.values():
                available_devices.append(device_name)

        available_devices.sort()
        print('available_devices=', available_devices)
        return available_devices

    def get_available_room_names(self):
        print('DeviceFarm.get_available_room_names')
        available_rooms = []
        for room_name in self._rooms:
            room_interface = self._rooms[room_name]
            if room_interface in self._pairs:
                paired_device = self._pairs[room_interface]
                if paired_device is None:
                    available_rooms.append(room_name)
            else:
                # room_interface not in self._pairs
                available_rooms.append(room_name)

        print('available_rooms=', available_rooms)
        return available_rooms

    def get_full_update(self):
        print('DeviceFarm.get_full_update')
        if self._farm_change_callback:
            # Send updates for room/device connection status
            for interface in self._connection_status:
                # print('DeviceFarm.get_full_update for interface=', interface)
                if interface in self._rooms.values():
                    self._send_event({
                        'Event Type': 'Connection Status',
                        'Value': self._connection_status[interface],
                        'Room Name': self.get_name_by_interface(interface),
                        'Device Name': None,
                    })

                elif interface in self._devices.values():
                    self._send_event({
                        'Event Type': 'Connection Status',
                        'Value': self._connection_status[interface],
                        'Room Name': None,
                        'Device Name': self.get_name_by_interface(interface),
                    })

                elif interface in self._preset_interfaces.values():
                    self._send_event({
                        'Event Type': 'Connection Status',
                        'Value': self._connection_status[interface],
                        'Room Name': None,
                        'Device Name': None,
                        'Preset Interface Name': self.get_name_by_interface(interface),
                    })

            # Send updates for current pairs
            for room_name in self._rooms:
                room_interface = self._rooms[room_name]

                if room_interface in self._pairs:
                    device_interface = self._pairs[room_interface]
                    device_name = self.get_name_by_interface(device_interface)
                    self._send_event({
                        'Event Type': 'Pair Update',
                        'Value': 'Paired',
                        'Room Name': room_name,  # str with len>=1 or None
                        'Device Name': device_name,  # str with len>=1 or None
                    })


                else:
                    # room_interface is not in self._pairs
                    # Thus is does not have a pair
                    self._send_event({
                        'Event Type': 'Pair Update',
                        'Value': 'Paired',
                        'Room Name': room_name,  # str with len>=1 or None
                        'Device Name': None,  # str with len>=1 or None
                    })

        # Send matrix update
        if self._matrix_interface is not None:
            state = self._connection_status.get(self._matrix_interface)
            if state == None:
                state = 'Disabled'

            self._send_event({
                'Event Type': 'Matrix Connection Status',
                'Value': state,
                'Room Name': None,  # str with len>=1 or None
                'Device Name': None,  # str with len>=1 or None
            })

    def _name_exists(self, name):
        # return True if name is already used for a room/device
        if name in self._rooms:
            return True
        elif name in self._devices:
            return True
        elif name in self._preset_interfaces:
            return True
        else:
            return False

    def delete_interface(self, interface):
        print('DeviceFarm.delete_interface(interface={})'.format(interface))

        name = self.get_name_by_interface(interface)
        print('name=', name)

        # unpair anything that was associated to this interface
        if name is not None:
            self.pair(name, '')

        # Send notification of the deleted device
        if name in self._rooms:
            room_name = name
        else:
            room_name = None

        if name in self._devices:
            device_name = name
        else:
            device_name = None

        self._send_event({
            'Event Type': 'Interface Deleted',
            'Value': 'Deleted',
            'Room Name': room_name,  # str with len>=1 or None
            'Device Name': device_name,  # str with len>=1 or None
        })

        # Remove all references to this interface
        def dict_pop(d):
            res = d.pop(name, None)
            if res:
                print('removed {} from {}'.format(name, d))

        for d in [self._rooms, self._pairs, self._devices]:
            dict_pop(d)

        for room_interface in self._pairs.copy():
            device_interface = self._pairs[room_interface]
            if device_interface == interface:
                self._pairs[room_interface] = None

        self._connection_status.pop(interface, None)

        # If this was a SerialInterface, make the port available for re-instantiation
        if isinstance(interface, SerialInterface):
            interface.Host._make_port_available(interface.Host, interface.Port)

        # If this was an EthernetServerInterfaceEx, make the port available for re-instantiation
        if isinstance(interface, EthernetServerInterfaceEx):
            EthernetServerInterfaceEx.clear_port_in_use(interface.IPPort)

    def _interfaces_above_limit(self):
        number_of_interfaces = (len(self._rooms) + len(self._devices))
        print('DeviceFarm._interfaces_above_limit()')
        if number_of_interfaces >= self._INTERFACE_LIMIT:
            print('DeviceFarm._interfaces_above_limit\n number_of_interfaces={}\n return True'.format(
                number_of_interfaces))
            return True
        else:
            print('DeviceFarm._interfaces_above_limit\n number_of_interfaces={}\n return False'.format(
                number_of_interfaces))
            return False

    def _save(self):
        print('DeviceFarm._save()\n self._init_complete={}'.format(self._init_complete))
        self._do_save_Wait.Restart()

    def _do_save(self):
        print('DeviceFarm._do_save()\n self._init_complete={}'.format(self._init_complete))
        try:
            if self._init_complete:
                save_dict = {}

                # Grab the room interfaces
                print('save room data')
                save_dict['rooms'] = {}
                for room_name in self._rooms.copy():
                    room_interface = self._rooms[room_name]
                    room_dict = dict(room_interface)
                    save_dict['rooms'][room_name] = room_dict

                # Grab the device interfaces
                print('save device data')
                save_dict['devices'] = {}
                for device_name in self._devices.copy():
                    device_interface = self._devices[device_name]
                    device_dict = dict(device_interface)
                    save_dict['devices'][device_name] = device_dict

                # Grab the pairs
                print('save pairs data')
                save_dict['pairs'] = {}
                for room_interface in self._pairs.copy():
                    room_name = self.get_name_by_interface(room_interface)

                    device_interface = self._pairs[room_interface]
                    device_name = self.get_name_by_interface(device_interface)

                    save_dict['pairs'][room_name] = device_name

                # Grab matrix name/connection info
                print('save matrix data')
                if self._matrix_interface is not None:
                    save_dict['matrix_connection'] = dict(self._matrix_interface)
                    save_dict['matrix_connection']['Name'] = self._matrix_name
                else:
                    save_dict['matrix_connection'] = None

                # Grab matrix input/output info
                matrix_io_temp = {}
                # print('be-for')
                for key in self._matrix_info:
                    # print('key=', key)
                    if key not in matrix_io_temp:
                        matrix_io_temp[key] = {}

                    for interface, number in self._matrix_info[key].items():
                        # print('interface={}\n number={}'.format(interface, number))
                        interface_name = self.get_name_by_interface(interface)
                        matrix_io_temp[key][interface_name] = number

                print('matrix_io_temp=', matrix_io_temp)
                save_dict['matrix_io'] = matrix_io_temp

                # Grab preset data
                save_dict['preset_info'] = self._preset_info.copy()

                preset_interfaces = {}
                for interface_name in self._preset_interfaces:
                    interface = self._preset_interfaces[interface_name]
                    preset_interfaces[interface_name] = dict(interface)
                save_dict['preset_interfaces'] = preset_interfaces

                # Make json string
                print('save_dict=', save_dict)
                try:
                    save_json = json.dumps(save_dict)
                except Exception as e:
                    print('ERROR converting json\n{}'.format(e))

                # Write json to file
                with File('farm_data.json', mode='wt') as file:
                    file.write(save_json)

        except Exception as e:
            print('DeviceFarm._save\nError:{}'.format(e))
            raise e

        print('save complete')

    def _load(self):
        print('DeviceFarm._load()')
        try:
            if File.Exists('farm_data.json'):
                with File('farm_data.json', mode='rt') as file:
                    data_json = file.read()
                    data = json.loads(data_json)

                    print('loading room data')
                    for room_name in data['rooms']:
                        try:
                            room_dict = data['rooms'][room_name]

                            if 'EthernetServerInterfaceEx' in room_dict['Type']:
                                IPPort = room_dict['IPPort']
                                Protocol = room_dict['Protocol']
                                Interface = room_dict['Interface']
                                MaxClients = room_dict['MaxClients']

                                try:
                                    self.add_ethernet_room(room_name, IPPort, Protocol, Interface, MaxClients)
                                except Exception as e:
                                    ProgramLog('Error loading ethernet room\n' + str(e), 'error')

                            elif 'SerialInterface' in room_dict['Type']:
                                HostAlias = room_dict['Host.DeviceAlias']
                                Host = ProcessorDevice(HostAlias)
                                print('load SerialInterface Host=', Host)
                                Port = room_dict['Port']
                                Baud = room_dict['Baud']
                                Data = room_dict['Data']
                                Parity = room_dict['Parity']
                                Stop = room_dict['Stop']
                                FlowControl = room_dict['FlowControl']
                                CharDelay = room_dict['CharDelay']
                                Mode = room_dict['Mode']

                                try:
                                    self.add_serial_room(room_name, Host=Host, Port=Port, Baud=Baud, Data=Data,
                                                         Parity=Parity, Stop=Stop, FlowControl=FlowControl,
                                                         CharDelay=CharDelay, Mode=Mode)
                                except Exception as e:
                                    ProgramLog('Error loading serial room\n' + str(e), 'error')

                        except Exception as e:
                            ProgramLog(str(e), 'warning')

                    print('loading devices data')
                    for device_name in data['devices']:
                        try:

                            device_dict = data['devices'][device_name]

                            if 'EthernetClientInterface' in device_dict['Type']:
                                Hostname = device_dict['Hostname']
                                IPPort = device_dict['IPPort']
                                Protocol = device_dict['Protocol']
                                ServicePort = device_dict['ServicePort']
                                Credentials = device_dict['Credentials']

                                try:
                                    self.add_ethernet_device(device_name, Hostname, IPPort, Protocol, ServicePort,
                                                             Credentials)
                                except Exception as e:
                                    ProgramLog('Error loading ethernet device\n' + str(e), 'error')

                            elif 'SerialInterface' in device_dict['Type']:
                                HostAlias = device_dict['Host.DeviceAlias']
                                Host = ProcessorDevice(HostAlias)
                                Port = device_dict['Port']
                                Baud = device_dict['Baud']
                                Data = device_dict['Data']
                                Parity = device_dict['Parity']
                                Stop = device_dict['Stop']
                                FlowControl = device_dict['FlowControl']
                                CharDelay = device_dict['CharDelay']
                                Mode = device_dict['Mode']

                                try:
                                    self.add_serial_device(device_name, Host=Host, Port=Port, Baud=Baud, Data=Data,
                                                           Parity=Parity, Stop=Stop, FlowControl=FlowControl,
                                                           CharDelay=CharDelay, Mode=Mode)
                                except Exception as e:
                                    ProgramLog('Error loading serial device\n' + str(e), 'error')

                        except Exception as e:
                            print(str(e), 'warning')

                    print('loading pairs data')
                    for room_name in data['pairs']:
                        try:
                            device_name = data['pairs'][room_name]

                            self.pair(room_name, device_name)
                        except Exception as e:
                            ProgramLog(str(e), 'warning')

                    print('loading matrix data')
                    matrix_dict = data.get('matrix_connection')
                    if matrix_dict is not None:
                        print('matrix_dict=', matrix_dict)
                        matrix_name = matrix_dict['Name']

                        if 'SerialInterface' in matrix_dict['Type']:
                            HostAlias = matrix_dict['Host.DeviceAlias']
                            Host = ProcessorDevice(HostAlias)
                            Port = matrix_dict['Port']
                            Baud = matrix_dict['Baud']
                            Data = matrix_dict['Data']
                            Parity = matrix_dict['Parity']
                            Stop = matrix_dict['Stop']
                            FlowControl = matrix_dict['FlowControl']
                            CharDelay = matrix_dict['CharDelay']
                            Mode = matrix_dict['Mode']

                            try:
                                self.add_serial_matrix(matrix_name, Host=Host, Port=Port, Baud=Baud, Data=Data,
                                                       Parity=Parity, Stop=Stop, FlowControl=FlowControl,
                                                       CharDelay=CharDelay, Mode=Mode)
                            except Exception as e:
                                ProgramLog('Error loading serial matrix\n' + str(e), 'error')

                        elif 'EthernetClientInterface' in matrix_dict['Type']:
                            Hostname = matrix_dict['Hostname']
                            IPPort = matrix_dict['IPPort']
                            Protocol = matrix_dict['Protocol']
                            ServicePort = matrix_dict['ServicePort']
                            Credentials = matrix_dict['Credentials']

                            try:
                                self.add_ethernet_matrix(matrix_name, Hostname, IPPort, Protocol, ServicePort,
                                                         Credentials)
                            except Exception as e:
                                ProgramLog('Error loading ethernet matrix\n' + str(e), 'error')

                    print('loading matrix_info')
                    print('pre self._matrix_info=', self._matrix_info)
                    matrix_info = data.get('matrix_io')
                    if matrix_info is not None:
                        for key in matrix_info:
                            for interface_name, number in matrix_info[key].items():
                                interface = self.get_interface_by_name(interface_name)
                                self._matrix_info[key][interface] = number
                    print('post load self._matrix_info=', self._matrix_info)

                    print('loading preset interfaces')
                    preset_interfaces = data.get('preset_interfaces')
                    if preset_interfaces:
                        print('preset_interfaces=', preset_interfaces)
                        for interface_name in preset_interfaces:
                            interface_params = preset_interfaces[interface_name]
                            if 'EthernetClientInterface' in interface_params['Type']:
                                Hostname = interface_params['Hostname']
                                IPPort = interface_params['IPPort']
                                Protocol = interface_params['Protocol']
                                ServicePort = interface_params['ServicePort']
                                Credentials = interface_params['Credentials']

                                self.add_ethernet_preset_device(
                                    interface_name,
                                    Hostname,
                                    IPPort,
                                    Protocol,
                                    ServicePort,
                                    Credentials,
                                )
                            elif 'SerialInterface' in interface_params['Type']:
                                HostAlias = interface_params['Host.DeviceAlias']
                                Host = ProcessorDevice(HostAlias)
                                Port = interface_params['Port']
                                Baud = interface_params['Baud']
                                Data = interface_params['Data']
                                Parity = interface_params['Parity']
                                Stop = interface_params['Stop']
                                FlowControl = interface_params['FlowControl']
                                CharDelay = interface_params['CharDelay']
                                Mode = interface_params['Mode']

                                self.add_serial_preset_device(
                                    interface_name,
                                    Host=Host,
                                    Port=Port,
                                    Baud=Baud,
                                    Data=Data,
                                    Parity=Parity,
                                    Stop=Stop,
                                    FlowControl=FlowControl,
                                    CharDelay=CharDelay,
                                    Mode=Mode
                                )

                    print('loading preset info')
                    preset_info = data.get('preset_info')
                    if preset_info:
                        print('preset_info=', preset_info)
                        for preset_interface_name in preset_info:
                            for room_name in preset_info[preset_interface_name]:
                                for device_name in preset_info[preset_interface_name][room_name]:
                                    preset_number = preset_info[preset_interface_name][room_name][device_name]
                                    self.set_new_preset(room_name, device_name, preset_interface_name, preset_number)


        except Exception as e:
            ProgramLog('DeviceFarm._load failed\n{}\n'.format(e))

    def register_loading_callback(self, func):
        print('****\n DeviceFarm.register_loading_callback({})'.format(func))
        # func should accept 1 parameter
        # str > either 'Show' or 'Hide'
        self._loading_callbacks.append(func)

    def _show_loading_page(self):
        print('DeviceFarm._show_loading_page()')
        for func in self._loading_callbacks:
            func('Show')

    def _hide_loading_page(self):
        print('DeviceFarm._hide_loading_page()')
        for func in self._loading_callbacks:
            func('Hide')

    def _send_event(self, event_info):
        print('DeviceFarm._send_event(event_info={})'.format(event_info))
        '''event_info = somethine like this {'Event Type': 'Connection Status',
                                              'Value': new_connection_status,
                                              'Room Name': room_name, #str with len>=1 or None
                                              'Device Name': device_name, #str with len>=1 or None
                                              'Preset Interface Name': #str with len>=1 or None
                                              }
        '''

        if 'Preset Interface Name' not in event_info:
            event_info['Preset Interface Name'] = None

        if self._init_complete:
            if self._farm_change_callback:
                self._farm_change_callback(self, event_info)

    def _base_add_matrix(self, name, matrix_interface):

        self._matrix_name = name

        if self._matrix_interface is not None:
            self.delete_matrix_interface()  # There can only be one. <highlander>

        def matrix_connection_callback(interface, state):
            print('DeviceFarm.matrix_connection_callback(\n interface={}\n state={}'.format(interface, state))
            # When connected, make appropriate ties. If the matrix gets power cycled, then ties will be restored.
            if state == 'Disconnected':
                if hasattr(interface, 'StopKeepAlive'):
                    interface.StopKeepAlive()
            elif state == 'Connected':
                Wait(5, self._update_matrix_ties)

            self._write_connection_status(interface, state)

        HandleConnection(matrix_interface)
        AddConnectionCallback(matrix_interface, matrix_connection_callback)

        @event(matrix_interface, 'ReceiveData')
        def matrix_interfaceRxDataEvent(interface, data):
            if debugRxData: print('matrix_interfaceRxDataEvent\n interface={}\n data={}'.format(interface, data))

            if b'Extron Electronics' in data:
                if hasattr(interface, 'StartKeepAlive'):
                    interface.StartKeepAlive(3, 'q')

            ConnectionHandlerLogicalReset(interface)

        self._matrix_interface = matrix_interface

        self._update_matrix_ties()

        self._save()

    def add_serial_matrix(self, name, *args, **kwargs):

        if self._matrix_interface is not None:
            self.delete_matrix_interface()

        matrix_interface = SerialInterface(*args, **kwargs)
        self._base_add_matrix(name, matrix_interface)

    def add_ethernet_matrix(self, name, *args, **kwargs):

        if self._matrix_interface is not None:
            self.delete_matrix_interface()

        matrix_interface = EthernetClientInterface(*args, **kwargs)
        self._base_add_matrix(name, matrix_interface)

    def delete_matrix_interface(self):
        self._matrix_name = None

        if self._matrix_interface is not None:
            RemoveConnectionHandlers(self._matrix_interface)

            if hasattr(self._matrix_interface, 'Disconnect'):
                self._matrix_interface.Disconnect()

            if isinstance(self._matrix_interface, SerialInterface):
                Host = self._matrix_interface.Host
                Port = self._matrix_interface.Port

                ProcessorDevice._make_port_available(Host, Port)

        self._send_event({
            'Event Type': 'Matrix Connection Status',
            'Value': 'Disabled',
            'Room Name': None,  # str with len>=1 or None
            'Device Name': None,  # str with len>=1 or None
        })

        self._connection_status.pop(self._matrix_interface, None)

        self._matrix_interface = None

        self._save()

    def _update_matrix_ties(self):
        if self._init_complete:
            if self._connection_status.get(self._matrix_interface) == 'Connected':
                if self._matrix_interface:
                    send_string = 'w+q'  # Qik tie command. Queues up tie commands

                    for room_interface in self._pairs:
                        device_interface = self._pairs[room_interface]

                        # Get room inputs/outputs
                        room_inputA = self._matrix_info['InputA'].get(room_interface, '0')
                        room_inputB = self._matrix_info['InputB'].get(room_interface, '0')

                        room_outputA = self._matrix_info['OutputA'].get(room_interface, '0')
                        room_outputB = self._matrix_info['OutputB'].get(room_interface, '0')

                        # Get device inputs/outputs
                        device_inputA = self._matrix_info['InputA'].get(device_interface,
                                                                        '0')  # if not found return '0'
                        device_inputB = self._matrix_info['InputB'].get(device_interface, '0')

                        device_outputA = self._matrix_info['OutputA'].get(device_interface, '0')
                        device_outputB = self._matrix_info['OutputB'].get(device_interface, '0')

                        send_string += '{}*{}!'.format(room_inputA, device_outputA)
                        send_string += '{}*{}!'.format(room_inputB, device_outputB)
                        send_string += '{}*{}!'.format(device_inputA, room_outputA)
                        send_string += '{}*{}!'.format(device_inputB, room_outputB)

                    send_string += '\r'

                    self._matrix_interface.Send(send_string)  # Executes all queued ties instantly

    def get_matrix_interface(self):
        return self._matrix_interface

    def get_matrix_name(self):
        return self._matrix_name

    def register_matrix_info(self, interface_name, key, input_num):
        print('DeviceFarm.register_matrix_info(interface_name={}, key={}, input_num={})'.format(interface_name, key,
                                                                                                input_num))
        # key should equal 'InputA', 'InputB', 'OutputA', 'OutputB'
        if key not in ['InputA', 'InputB', 'OutputA', 'OutputB']:
            raise Exception("key must be one of these ['InputA', 'InputB', 'OutputA', 'OutputB']")

        interface = self.get_interface_by_name(interface_name)

        self._matrix_info[key][interface] = input_num

        print('self._matrix_info=', self._matrix_info)

        self._save()

    def get_matrix_info(self, interface_name, key):
        print('DeviceFarm.get_matrix_info(interface_name={}, key={})'.format(interface_name, key))
        interface = self.get_interface_by_name(interface_name)
        input_num = self._matrix_info[key].get(interface)

        if input_num is None:
            return '0'
        else:
            return input_num

    # Preset Device methods *****************************************************

    def _base_add_preset_device(self, name, interface):
        print('DeviceFarm._base_add_preset_device(name={}, interface={})'.format(name, interface))

        self._preset_interfaces[name] = interface

        # Init the connection status
        if isinstance(interface, SerialInterface):
            self._write_connection_status(interface, 'Connected')  # SerialInterfaces are always "Connected"
        else:
            self._write_connection_status(interface, 'Disconnected')

        # Setup connection handling
        def preset_connection_callback(interface, state):
            print('preset_connection_callback(\ninterface={}\nstate={}'.format(interface, state))
            if state == 'Disconnected':
                if hasattr(interface, 'StopKeepAlive'):
                    interface.StopKeepAlive()
            elif state == 'Connected':
                Wait(5, self._do_all_preset_recall)

            self._write_connection_status(interface, state)

        HandleConnection(interface)
        AddConnectionCallback(interface, preset_connection_callback)

        @event(interface, 'ReceiveData')
        def preset_device_rx_data_event(interface, data):
            if debugRxData: print('preset_device_rx_data_event(\ninterface={}\ndata={}'.format(interface, data))
            if b'Extron Electronics' in data:
                if hasattr(interface, 'StartKeepAlive'):
                    interface.StartKeepAlive(3, 'q')

            ConnectionHandlerLogicalReset(interface)

        self._save()

    def add_ethernet_preset_device(self, name, *args, **kwargs):
        print('DeviceFarm.add_ethernet_preset_device(name={}, args={}, kwargs={})'.format(name, args, kwargs))

        if not self._name_exists(name):
            interface = EthernetClientInterface(*args, **kwargs)
            self._base_add_preset_device(name, interface)
        else:
            raise Exception('The name "{}" already exists.\n\nPlease enter a different name'.format(name))

    def add_serial_preset_device(self, name, *args, **kwargs):
        print('DeviceFarm.add_serial_preset_device(name={}, args={}, kwargs={})'.format(name, args, kwargs))

        if not self._name_exists(name):
            interface = SerialInterface(*args, **kwargs)
            self._base_add_preset_device(name, interface)
        else:
            raise Exception('The name "{}" already exists.\n\nPlease enter a different name'.format(name))

    def delete_preset_interface(self, interface):
        print('DeviceFarm.delete_preset_device_interface(interface={})'.format(interface))

        interface_name = self.get_name_by_interface(interface)
        print('delete name=', interface_name)

        RemoveConnectionHandlers(interface)

        # remove the interface from self._preset_interfaces
        for preset_interface_name in self._preset_interfaces.copy():
            i = self._preset_interfaces[preset_interface_name]
            if i == interface:
                self._preset_interfaces.pop(preset_interface_name, None)

        # Make the serial port availabe for another purpose
        if isinstance(interface, SerialInterface):
            ProcessorDevice._make_port_available(interface.Host, interface.Port)

        # remove any presets from self._preset_info
        for preset_interface_name in self._preset_info.copy():
            if preset_interface_name == interface_name:
                self._preset_info.pop(preset_interface_name, None)

        self._send_event({
            'Event Type': 'Interface Deleted',
            'Value': 'Deleted',
            'Room Name': None,  # str with len>=1 or None
            'Device Name': None,  # str with len>=1 or None
            'Preset Interface Name': interface_name,
        })

        self._save()

    def get_preset_interface_names(self, name):
        print('DeviceFarm.get_preset_device_interface(name={})'.format(name))
        # return interface names
        r = list(self._preset_interfaces.keys())
        print('return {}'.format(r))
        return r

    def get_preset_info(self):
        '''
        returns a dict like this

        {'Preset Interface Name': {'room_name':  {'device_name': int(preset_num),
                                                  'device_name2': int(preset_num2),},
                                   'room_name2': {'device_name3': int(preset_num3),
                                                  'device_name4': int(preset_num4),}
        }
        '''
        return self._preset_info.copy()

    def get_presets_for_interface(self, interface):
        interface_name = self.get_name_by_interface(interface)
        return self._preset_info.copy().get(interface_name)

    def get_preset_interface_names(self):
        return list(self._preset_interfaces.keys())

    def set_new_preset(self, room_name, device_name, preset_interface_name, preset_number):
        if preset_interface_name not in self._preset_info:
            self._preset_info[preset_interface_name] = {}

        if room_name not in self._preset_info[preset_interface_name]:
            self._preset_info[preset_interface_name][room_name] = {}

        self._preset_info[preset_interface_name][room_name][device_name] = preset_number

        self._send_event({
            'Event Type': 'Preset Change',
            'Value': preset_number,
            'Room Name': room_name,  # str with len>=1 or None
            'Device Name': device_name,  # str with len>=1 or None
            'Preset Interface Name': preset_interface_name,
        })

        self._save()

    def _do_all_preset_recall(self):
        for room_interface in self._pairs:
            device_interface = self._pairs[room_interface]

            room_name = self.get_name_by_interface(room_interface)
            device_name = self.get_name_by_interface(device_interface)

            self._do_preset_recall(room_name, device_name)

            time.sleep(1)  # Extron DMPs need 1 sec delay between preset recall commands

    def _do_preset_recall(self, room_name, device_name):
        '''
        This method will check the current pairs and send preset-recall commands if certain pairs are made according to self._preset_info
        '''
        print('DeviceFarm._do_preset_recall(room_name={}, device_name={})'.format(room_name, device_name))

        if room_name == None:
            room_name = '<No Room>'

        if device_name == None:
            device_name = '<No Device>'

        for preset_interface_name in self._preset_info:
            print('preset_interface_name=', preset_interface_name)
            print('self._preset_info[preset_interface_name]=', self._preset_info[preset_interface_name])
            for p_room_name in self._preset_info[preset_interface_name]:
                print('p_room_name=', p_room_name)
                for p_device_name in self._preset_info[preset_interface_name][p_room_name]:
                    print('p_device_name=', p_device_name)

                    if p_room_name == room_name:
                        if p_device_name == device_name:
                            preset_number = self._preset_info[preset_interface_name][p_room_name][p_device_name]
                            print('preset_number=', preset_number)

                            interface = self.get_interface_by_name(preset_interface_name)
                            print(
                                'Recalling Preset\nInterface Name: {}\nPreset Number: {}'.format(preset_interface_name,
                                                                                                 preset_number))
                            interface.Send('\r{}.\r'.format(preset_number))

            if debug:
                time.sleep(0.0001)  # to make sure trace messages get printed in order

    def delete_preset(self, room_name, device_name, preset_interface_name):
        preset_info = self._preset_info.copy()

        for p_preset_interface_name in preset_info.copy():
            for p_room_name in preset_info[p_preset_interface_name].copy():
                for p_device_name in preset_info[p_preset_interface_name][p_room_name].copy():

                    if p_preset_interface_name == preset_interface_name:
                        if p_room_name == room_name:
                            if p_device_name == device_name:
                                self._preset_info[p_preset_interface_name][p_room_name].pop(p_device_name, None)

        self._save()

    def GetInterfaceKind(self, interface):
        # Return 'Room', 'Device', 'Matrix', 'Preset'
        if interface in self._rooms.values():
            return 'Room'

        elif interface in self._devices.values():
            return 'Device'

        elif (interface == self._matrix_interface and
                      interface is not None):
            return 'Matrix'
        elif interface in _preset_interfaces:
            return 'Preset'

        else:
            return None


# Class to help with logging data ***********************************************
class Logger:
    def __init__(self, filename=None):
        if filename is None:
            filename = 'reservation.log'

        self.filename = filename

        if not File.Exists(self.filename):
            File(self.filename, mode='wt').close()  # create a blank file

    def NewReservation(self, room_name, device_name):
        with File(self.filename, mode='at') as file:
            data = {'Event': 'New Reservation',
                    'Time': time.asctime(),
                    'Room Name': room_name,
                    'Device Name': device_name,
                    }
            data_json = json.dumps(data)
            file.write(data_json + '\r\n')

    def SystemRebooted(self):
        with File(self.filename, mode='at') as file:
            data = {'Event': 'System Rebooted',
                    'Time': time.asctime(),
                    }
            data_json = json.dumps(data)
            file.write(data_json + '\r\n')

    def ConnectionStatus(self, interface_name, status):
        with File(self.filename, mode='at') as file:
            data = {'Event': 'Connection Status',
                    'Time': time.asctime(),
                    'Interface Name': interface_name,
                    'Status': status,
                    }
            data_json = json.dumps(data)
            file.write(data_json + '\r\n')

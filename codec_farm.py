'''
Grant G Miler
Gmiller@extron.com
800-633-9876 x6032
April 13, 2016

Version 2.0.0 - better?

Version 1.1.0 - 09-06-2016
Updated Servers to EthernetServerInterfaceEx to improve Connected/Disconnect handling.

Version 1.0.0

'''

debug = True
if debug:
    def print(*args):  # override the print function to write to program log instead
        string = ''
        for arg in args:
            string += ' ' + str(arg)
        ProgramLog(string, 'info')

## Begin ControlScript Import --------------------------------------------------
from extronlib import event
from extronlib.interface import EthernetClientInterface, EthernetServerInterfaceEx
from extronlib.system import File, ProgramLog, Wait
import json


class CodecFarm():
    '''
    This class acts as a middle-man. It has the ability to bridge connections between devices.

    Example:
    There is a central room with 5 Video Conference Codecs.
    There are 10 conference rooms.

    Since not all the rooms need to use VTC simultaneously, this system allows
    the rooms to share the VTC with up to 5 rooms using VTCs simultaneously.

    This module runs several TCP servers. The rooms will connect to these servers.
    Each room on a separate TCP Port.

    This module also runs several TCP clients that connect this controller to the VTCs.

    This module simply passes communication between the appropriate server/client pairs.
    It does not manipulate the data at all.

    Note: Since this module only passes info from server to client and vice versa,
    this module can be used as a "Reservation System" for any kind of device, not just VTCs.
    Ideas: BYOD (Sharelink/Apple TV), Videowall/Multi-Window Processors, Video Recorders, etc
    '''

    def __init__(self):
        '''
        Data Structure:
        self.Rooms = {'Room Name': EthernetServerInterfaceExObject}
        self.Codecs = {'Codec Name': EthernetClientInterfaceObject}
        self.Pairs = {EthernetServerInterfaceExObject: EthernetClientInterfaceObject}
        self._MatrixData = {'RoomName': {'MatrixInL': '1',
                                        'MatrixInR': '2',
                                        'MatrixOutL': '3',
                                        'MatrixOutR': '4',
                                        },
                            'CodecName': {'MatrixInL': '1',
                                        'MatrixInR': '2',
                                        'MatrixOutL': '3',
                                        'MatrixOutR': '4',
                                        },
                          }
        '''
        self.Rooms = {}
        self.Codecs = {}
        self.Pairs = {}
        self._MatrixData = {}

        self._Callback = None
        self._ConnectionHandlerObj = None
        self._MatrixObj = None

        self._LoadData()

    def AddCodec(self, CodecName, IPofCodec, MatrixInputLeft='0', MatrixInputRight='0', MatrixOutputShare='0',
                 MatrixOutputCamera='0', Port=23):
        '''
        This method creates a new EthernetClientInterface and connects to the device.
        '''
        print('AddCodec({})'.format(CodecName))
        if CodecName in self.Codecs:
            print('CodecName {} already exists'.format(CodecName))
            # Update self.MatrixData
            self._MatrixData[CodecName] = {'MatrixInL': MatrixInputLeft,
                                           'MatrixInR': MatrixInputRight,
                                           'MatrixOutL': MatrixOutputShare,
                                           'MatrixOutR': MatrixOutputCamera,
                                           }
            self._SaveData()
            return

        # Update self.MatrixData
        self._MatrixData[CodecName] = {'MatrixInL': MatrixInputLeft,
                                       'MatrixInR': MatrixInputRight,
                                       'MatrixOutL': MatrixOutputShare,
                                       'MatrixOutR': MatrixOutputCamera,
                                       }
        self._SaveData()
        # print(CodecName,' Matrix: ', self._MatrixData[CodecName])

        NewClient = EthernetClientInterface(IPofCodec, Port)

        self.Codecs[CodecName] = NewClient

        def CreateNewRxCodec(NewClient):
            @event(NewClient, 'ReceiveData')
            def NewClientRxData(interface, data):
                # print('{}:{} data={}'.format(interface.IPAddress, interface.IPPort, data))#for debugging
                for RoomServer in self.Pairs:
                    CodecClient = self.Pairs[RoomServer]
                    if CodecClient == NewClient:
                        if len(RoomServer.Clients) > 0:
                            RoomServer.Clients[0].Send(data)

        CreateNewRxCodec(NewClient)

        if self._ConnectionHandlerObj is not None:
            self._ConnectionHandlerObj(NewClient)
        else:
            # if no connectionhandler has been passed from main.py, use this one.
            def HandleConnection(interface):
                '''
                This will try to open a IP connection to the interface.
                It will retry every 5 seconds until it is connected.
                '''

                @event(interface, ['Connected', 'Disconnected'])
                def ConnectionHandler(interface, state):
                    # print('{}:{} {}'.format(interface.IPAddress, interface.IPPort, state))

                    if state == 'Disconnected':
                        WaitReconnect.Restart()
                    elif state == 'Connected':
                        # Telnet handshake
                        interface.Send(b'\xFF\xFB\x18\xFF\xFB\x1F\xFF\xFC\x20\xFF\xFC\x23\xFF\xFB\x27\xFF\xFA\x1F')
                        interface.Send(b'\x00\x50\x00\x19\xFF\xF0\xFF\xFA\x27\x00\xFF\xF0\xFF\xFA\x18\x00\x41\x4E')
                        interface.Send(b'\x53\x49\xFF\xF0\xFF\xFD\x03\xFF\xFB\x01\xFF\xFE\x05\xFF\xFC\x21')

                        @Wait(2)
                        def CodecLoginWait1():
                            interface.Send(b'admin\x0D\x0A')

                        @Wait(2)
                        def CodecLoginWait2():
                            interface.Send(b'\x0D\x0A')

                        WaitReconnect.Cancel()

                WaitReconnect = Wait(15, interface.Connect)
                WaitReconnect.Cancel()

                Wait(0.1, interface.Connect)

            HandleConnection(NewClient)

    def AddRoom(self, RoomName, RoomPort, MatrixOutputLeft='0', MatrixOutputRight='0', MatrixInputShare='0',
                MatrixInputCamera='0', ):
        print('AddRoom({})'.format(RoomName))
        if RoomName in self.Rooms:
            print('RoomName {} already exists'.format(RoomName))
            # Update self.MatrixData
            self._MatrixData[RoomName] = {'MatrixInL': MatrixInputShare,
                                          'MatrixInR': MatrixInputCamera,
                                          'MatrixOutL': MatrixOutputLeft,
                                          'MatrixOutR': MatrixOutputRight,
                                          }
            self._SaveData()
            return

        # Update self.MatrixData
        self._MatrixData[RoomName] = {'MatrixInL': MatrixInputShare,
                                      'MatrixInR': MatrixInputCamera,
                                      'MatrixOutL': MatrixOutputLeft,
                                      'MatrixOutR': MatrixOutputRight,
                                      }

        self._SaveData()
        # print(RoomName,' Matrix: ', self._MatrixData[RoomName])
        NewServer = EthernetServerInterfaceEx(RoomPort, MaxClients=1)

        try:
            print(RoomName, NewServer.StartListen())
            self.Rooms[RoomName] = NewServer
        except Exception as e:
            # print('74 Exception:', e)
            # print('There is already a server listening on port', RoomPort)
            pass

        def CreateNewRxRoom(NewServer):
            @event(NewServer, 'ReceiveData')
            def NewServerRxData(client, data):
                # print('{}:{} data={}'.format(client.IPAddress, client.ServicePort, data)) #for debugging
                for RoomServer in self.Pairs:
                    if RoomServer == NewServer:
                        CodecClient = self.Pairs[RoomServer]
                        if CodecClient is not None:
                            try:
                                # print('Trying to send to client', CodecClient.IPAddress)
                                CodecClient.Send(data)
                            except Exception as e:
                                # print(e)
                                pass

        CreateNewRxRoom(NewServer)

    def Pair(self, RoomName=None, CodecName=None):
        print('Pair(RoomName={}, CodecName={})'.format(RoomName, CodecName))

        self.UnPair(RoomName, CodecName)

        try:
            ServerObj = self.Rooms[RoomName]
        except Exception as e:
            # print('RoomName not found')
            # print('84 Exception:', e)
            ServerObj = None

        try:
            ClientObj = self.Codecs[CodecName]
        except Exception as e:
            # print('CodecName not found')
            # print('91 Exception:', e)
            ClientObj = None

        self.Pairs[ServerObj] = ClientObj
        # print('98 self.Pairs =', self.Pairs)

        self._SaveData()

        if self._Callback is not None:
            self._Callback()

        if self._MatrixObj is not None:
            self._UpdateMatrixTies()

    def UnPair(self, RoomName=None, CodecName=None):
        print('UnPair(RoomName={}, CodecName={})'.format(RoomName, CodecName))

        # Find the server and client objects
        if RoomName is not None:
            try:
                ServerObj = self.Rooms[RoomName]
            except Exception as e:
                # print('120 Exception:', e)
                ServerObj = None

        if CodecName is not None:
            try:
                ClientObj = self.Codecs[CodecName]
            except Exception as e:
                # print('130 Exception:', e)
                ClientObj = None

        # Remove any pairs for this room
        for PairServerObj in self.Pairs:
            if PairServerObj == ServerObj:
                self.Pairs[PairServerObj] = None
        # print('146 self.Pairs =', self.Pairs)

        # Remove any pairs for this codec
        for key in self.Pairs:
            if self.Pairs[key] == ClientObj:
                self.Pairs[key] = None

        self._SaveData()

        if self._Callback is not None:
            self._Callback()

        if self._MatrixObj is not None:
            self._UpdateMatrixTies()

    def GetPairs(self):
        # print('GetPairs()')
        # print('155 self.Pairs =', self.Pairs)
        '''
        Returns a dict like this:
        {'RoomName1': 'CodecName1',
         'RoomName2' : 'CodecName2',
         }
        '''
        ReturnDict = {}

        for ServerObj in self.Pairs:
            ServerName = ''
            for RoomName in self.Rooms:
                if self.Rooms[RoomName] == ServerObj:
                    ServerName = RoomName
                    break

            ClientName = ''
            try:
                ClientObj = self.Pairs[ServerObj]
                for CodecName in self.Codecs:
                    if self.Codecs[CodecName] == ClientObj:
                        ClientName = CodecName
            except Exception as e:
                # print('178 Exception:', e)
                pass

            # print('182 ServerName={}, ClientName={}'.format(ServerName, ClientName))
            ReturnDict[ServerName] = ClientName

        # print('183 self.Pairs =', self.Pairs)
        # print('177 ReturnDict=', ReturnDict)
        return ReturnDict

    def _SaveData(self):
        RoomData = {}
        for RoomName in self.Rooms:
            RoomData[RoomName] = {'Port': self.Rooms[RoomName].IPPort}
        RoomDataJson = json.dumps(RoomData)
        File('RoomData.json', mode='wt').write(RoomDataJson)

        CodecData = {}
        for CodecName in self.Codecs:
            CodecData[CodecName] = {'Port': self.Codecs[CodecName].IPPort,
                                    'IP': self.Codecs[CodecName].IPAddress,
                                    }
        CodecDataJson = json.dumps(CodecData)
        File('CodecData.json', mode='wt').write(CodecDataJson)

        Pairs = self.GetPairs()
        # print('Pairs=', Pairs)
        if Pairs == {}:
            # print('No pairs to save')
            pass
        else:
            PairsJson = json.dumps(Pairs)
            File('Pairs.json', mode='wt').write(PairsJson)

        File('MatrixData.json', mode='wt').write(json.dumps(self._MatrixData))

    def _LoadData(self):
        print('Loading Codec Farm data from internal memory.')

        try:
            MatrixData = json.loads(File('MatrixData.json').read())
        except:
            MatrixData = {}

        if File.Exists('RoomData.json'):
            RoomData = json.loads(File('RoomData.json').read())
            for RoomName in RoomData:
                try:
                    MatrixData[RoomName]
                except:
                    MatrixData[RoomName] = {}

                for key in ['MatrixInL', 'MatrixInR', 'MatrixOutL', 'MatrixOutR']:
                    try:
                        MatrixData[RoomName][key]
                    except:
                        # If key doesnt exist fill it with 0
                        MatrixData[RoomName][key] = '0'

                self.AddRoom(RoomName,
                             RoomData[RoomName]['Port'],
                             MatrixInputShare=MatrixData[RoomName]['MatrixInL'],
                             MatrixInputCamera=MatrixData[RoomName]['MatrixInR'],
                             MatrixOutputLeft=MatrixData[RoomName]['MatrixOutL'],
                             MatrixOutputRight=MatrixData[RoomName]['MatrixOutR'],
                             )

        if File.Exists('CodecData.json'):
            CodecData = json.loads(File('CodecData.json').read())
            for CodecName in CodecData:
                IP = CodecData[CodecName]['IP']
                Port = CodecData[CodecName]['Port']

                try:
                    MatrixData[CodecName]
                except:
                    MatrixData[CodecName] = {}

                for key in ['MatrixInL', 'MatrixInR', 'MatrixOutL', 'MatrixOutR']:
                    try:
                        MatrixData[CodecName][key]
                    except:
                        MatrixData[CodecName][key] = '0'

                self.AddCodec(CodecName,
                              IP,
                              Port=Port,
                              MatrixInputLeft=MatrixData[RoomName]['MatrixInL'],
                              MatrixInputRight=MatrixData[RoomName]['MatrixInR'],
                              MatrixOutputShare=MatrixData[RoomName]['MatrixOutL'],
                              MatrixOutputCamera=MatrixData[RoomName]['MatrixOutR'],
                              )

        if File.Exists('Pairs.json'):
            PairData = json.loads(File('Pairs.json').read())
            for RoomName in PairData:
                CodecName = PairData[RoomName]
                self.Pair(RoomName, CodecName)

        if self._Callback:
            self._Callback()

    def Subscribe(self, CallbackFunction):
        self._Callback = CallbackFunction

    def SetMatrixObject(self, MatrixObject):
        '''
        MatrixObject = EthernetClientInterface object

        The user can set a MatrixObject.
        Anytime the room/codec assignments change, the appropriate
        Matrix Tie Command will be sent to the matrix.

        This assumes an Extron matrix.
        '''
        self._MatrixObj = MatrixObject

    def _UpdateMatrixTies(self):
        '''
        This method is automatically called anytime there is a change to the room/codec assignments.
        '''
        Pairs = self.GetPairs()
        print('Pairs=', Pairs)

        for RoomName in Pairs:
            if RoomName != '':
                RoomInL = self._MatrixData[RoomName]['MatrixInL']
                RoomInR = self._MatrixData[RoomName]['MatrixInR']
                RoomOutL = self._MatrixData[RoomName]['MatrixOutL']
                RoomOutR = self._MatrixData[RoomName]['MatrixOutR']

                try:
                    CodecName = Pairs[RoomName]
                except Exceptoin as e:
                    print('Exception', e)
                    raise e

                print('CodecName =', CodecName)

                if CodecName == '':
                    CodecInL = '0'
                    CodecInR = '0'
                    CodecOutL = '0'
                    CodecOutR = '0'
                else:
                    CodecInL = self._MatrixData[CodecName]['MatrixInL']
                    CodecInR = self._MatrixData[CodecName]['MatrixInR']
                    CodecOutL = self._MatrixData[CodecName]['MatrixOutL']
                    CodecOutR = self._MatrixData[CodecName]['MatrixOutR']

                # print('RoomInL =', RoomInL)
                # print('RoomInR =', RoomInR)
                # print('RoomOutL =', RoomOutL)
                # print('RoomOutR =', RoomOutR)
                # print('CodecInL =', CodecInL)
                # print('CodecInR =', CodecInR)
                # print('CodecOutL =', CodecOutL)
                # print('CodecOutR =', CodecOutR)
                self._MatrixObj.Send('{}*{}!'.format(RoomInL, CodecOutL))
                self._MatrixObj.Send('{}*{}!'.format(RoomInR, CodecOutR))
                self._MatrixObj.Send('{}*{}!'.format(CodecInL, RoomOutL))
                self._MatrixObj.Send('{}*{}!'.format(CodecInR, RoomOutR))

    def AddConnectionHandler(self, handlerObj=None):
        '''
        Used for ethernet clients.
        handlerObj should accept an interface as its first argument and add connection handling to it.
        Example:
        handlerObj(extronlib.interface.EthernetClientInterface('1.1.1.1', 23)) #Should handle automatic connect/re-connect.
        '''
        self._ConnectionHandlerObj = handlerObj




'''
This module is based off of the module extr_sp_Annotator300_v1_0_3_0.py by Extron Electronics.

This module adds a "Touch Server" that collects all of the touch commands from devices like Extron TLP Pro 1520TG/MG, Extron TLP Pro 1720TG/MG and Extron TLI Pro 101.
The server knows which IP the touch commands are coming from and sends a command to the annotator to change color when it receives commands from a different device.

Use this command to set the color for a particular UIDevice:
self.Set('AnnotationColor', 'All', {'Red': 3, 'Green': 0, 'Blue': 0', 'UI': extronlib.device.UIDevice('Alias')})

Now any time a touch command is recieved from a device with the IP Address of UIDevice.IPAddress, the color will be changed to Red.

V2.0.1 - Bug fix if touch server port is already in use.
Version 2.0.0 - Added support for self.Set('AnnotationType', 'Freehand', {'UI': TLP})

V2.0.2 - 2107-05-23
Added class UniversalConnectionHandler to manage Server connections
'''

from extronlib import event
from extronlib.interface import EthernetClientInterface, EthernetServerInterfaceEx, SerialInterface, IRInterface, RelayInterface
import re
from extronlib.system import Wait

class DeviceClass():

    def _TouchClient(self, client):

        if self.LastTouchIP is not client.IPAddress:
            self.LastTouchIP = client.IPAddress
            for UI in self.ColorMap:
                if UI.IPAddress == client.IPAddress:
                    if UI in self.ColorMap:
                        self.Set('AnnotationColor', self.ColorMap[UI]['Value'], self.ColorMap[UI])
                    if UI in self.TypeMap:
                        self.Set('AnnotationType', self.TypeMap[UI])
                    break

    def _UpdateTouchStatus(self, client, data):
        if b'ASTP' in data:
            self.TouchStatus[client.IPAddress] = 'Not Touching'
        else:
            self.TouchStatus[client.IPAddress] = 'Touching'

    def __init__(self, TouchServerPort):

        #Touch Server **********************************************************
        self.ColorMap = {
                            #UIDeviceObject : {'Red': 0, 'Green': 0, 'Blue': 0, 'Value': 'All'},
                            }
        self.TypeMap = {
                            #UIDeviceObject : 'Freehand'
                            }

        self.TouchStatus = {
                            #'1.1.1.1': 'Touching' or 'Not Touching'
                                }

        if TouchServerPort is not None:
            self.LastTouchIP = ''

            self.TouchServer = EthernetServerInterfaceEx(TouchServerPort)

            self.UCH = UniversalConnectionHandler()

            self.UCH.maintain(
                self.TouchServer,
                timeout=20, # After this many seconds, a client who has not sent any data to the server will be disconnected.
                )

            @event(self.TouchServer, 'Connected')
            @event(self.TouchServer, 'Disconnected')
            def TouchConnected(client, state):
                print('{}:{} {}'.format(client.IPAddress, client.ServicePort, state))

            @event(self.TouchServer, 'ReceiveData')
            def TouchRxData(client, data):
                #print('{}:{} Rx: {}'.format(client.IPAddress, client.ServicePort, data))

                self._UpdateTouchStatus(client, data)
                #print('self.TouchStatus=', self.TouchStatus)

                #print('self.LastTouchIP=', self.LastTouchIP)
                if client.IPAddress is not self.LastTouchIP:
                    #A new touch panel has touched
                    if self.LastTouchIP in self.TouchStatus:
                        if self.TouchStatus[self.LastTouchIP] == 'Not Touching':
                            #The last touch panel has finished their touch
                            #Allow the annotation data to pass
                            self._TouchClient(client)#changes the color if needed
                            self.Send(data) #Send touch data to the annotator
                        else:
                            #The last touch IP hasnt finished yet, ignore this touch for now
                            pass
                    else:
                        self.LastTouchIP = client.IPAddress
                else:
                    #This touch is coming from the same panel as the last touch. Forward the Touch data
                    self._TouchClient(client)#changes the color if needed
                    self.Send(data) #Send touch data to the annotator

            try:
                result = self.TouchServer.StartListen()
                print('Touch Server {} on port {}'.format(result, self.TouchServer.IPPort))
            except Exception as e:
                print('Exception in Touch Server:', e)

        #Normal module methods *************************************************
        self.Unidirectional = 'False'
        self.connectionCounter = 15

        # Do not change this the variables values below
        self.DefaultResponseTimeout = 0.3
        self._compile_list = {}
        self.Subscription = {}
        self.ReceiveData = self.__ReceiveData
        self._ReceiveBuffer = b''
        self.counter = 0
        self.connectionFlag = True
        self.initializationChk = True
        self.Models = {}

        self.Commands = {
            'ConnectionStatus': {'Status': {}},
            'ActiveLines': {'Status': {}},
            'ActivePixels': {'Status': {}},
            'AnnotationColor': {'Parameters': ['Red', 'Green', 'Blue'], 'Status': {}},
            'AnnotationDisplay': {'Status': {}},
            'AnnotationEditFunctions': {'Status': {}},
            'AnnotationObjectFill': {'Status': {}},
            'AnnotationType': {'Status': {}},
            'AspectRatio': {'Parameters': ['Input'], 'Status': {}},
            'AudioInputFormat': {'Parameters': ['Input'], 'Status': {}},
            'AudioMute': {'Status': {}},
            'AutoImage': {'Status': {}},
            'AutoSwitchMode': {'Status': {}},
            'Brightness': {'Status': {}},
            'Contrast': {'Status': {}},
            'CurrentImage': {'Status': {}},
            'CursorDisplay': {'Status': {}},
            'DetectedInputVideoFormat': {'Parameters': ['Input'], 'Status': {}},
            'DigitalOutputFormat': {'Parameters': ['Output'], 'Status': {}},
            'DropShadow': {'Status': {}},
            'EraserHighlighterSize': {'Status': {}},
            'ExecutiveMode': {'Status': {}},
            'Freeze': {'Status': {}},
            'FrontPanelCaptureButtonMode': {'Status': {}},
            'HDCPOutputMode': {'Status': {}},
            'HDCPStatus': {'Parameters': ['Port'], 'Status': {}},
            'HorizontalShift': {'Status': {}},
            'HorizontalSize': {'Status': {}},
            'HorizontalStart': {'Status': {}},
            'QuickCapture': {'Status': {}},
            'Input': {'Status': {}},
            'InputEDID': {'Parameters': ['Input'], 'Status': {}},
            'InputPresets': {'Parameters': ['Command'], 'Status': {}},
            'InputVideoFormat': {'Parameters': ['Input'], 'Status': {}},
            'LineWeight': {'Status': {}},
            'MemoryPresets': {'Parameters': ['Command'], 'Status': {}},
            'MenuDisplay': {'Status': {}},
            'MuteImage': {'Status': {}},
            'OutputScalerRate': {'Status': {}},
            'PixelPhase': {'Status': {}},
            'PowerSave': {'Status': {}},
            'RecallImageCommand': {'Parameters': ['File Name'], 'Status': {}},
            'SaveImageCommand': {'Parameters': ['File Name'], 'Status': {}},
            'ScreenSaver': {'Status': {}},
            'ScreenSaverTimeout': {'Status': {}},
            'SignalStatus': {'Parameters': ['Input'], 'Status': {}},
            'SwitchingEffect': {'Status': {}},
            'Temperature': {'Status': {}},
            'TestPattern': {'Status': {}},
            'TextSize': {'Status': {}},
            'TotalPixel': {'Status': {}},
            'USBDevice': {'Parameters': ['Device'], 'Status': {}},
            'VerticalShift': {'Status': {}},
            'VerticalSize': {'Status': {}},
            'VerticalStart': {'Status': {}},
            'VideoMute': {'Parameters': ['Output'], 'Status': {}},
            'ViewSettings': {'Status': {}},
            'WhiteboardBlackboard': {'Status': {}},
        }

        self.VerboseDisabled = True
        self.PasswdPromptCount = 0
        self.Authenticated = 'Not Needed'

        if self.Unidirectional == 'False':
            self.AddMatchString(re.compile(b'Alin([0-3]{1,2})\*([0-9]{1,4})\r\n'), self.__MatchActiveLines, None)
            self.AddMatchString(re.compile(b'Apix([0-3]{1,2})\*([0-9]{1,4})\r\n'), self.__MatchActivePixels, None)
            self.AddMatchString(re.compile(b'Ashw([0-3]{1,2})\r\n'), self.__MatchAnnotationDisplay, None)
            self.AddMatchString(re.compile(b'Fill([0-3]{1,2})\r\n'), self.__MatchAnnotationObjectFill, None)
            self.AddMatchString(re.compile(b'Draw([0-9]{1,2})\r\n'), self.__MatchAnnotationType, None)
            self.AddMatchString(re.compile(b'Acol([0-9]{1,2})\*([0-9]{2})([0-9]{2})([0-9]{2})\r\n'), self.__MatchAnnotationColor, None)
            self.AddMatchString(re.compile(b'Aspr([0-3]{1,2})\*([12])\r\n'), self.__MatchAspectRatio, None)
            self.AddMatchString(re.compile(b'AfmtI([0-3]{1,2})\*([0-2])\r\n'), self.__MatchAudioInputFormat, None)
            self.AddMatchString(re.compile(b'Amt([01])\r\n'), self.__MatchAudioMute, None)
            self.AddMatchString(re.compile(b'Ausw([0-2])\r\n'), self.__MatchAutoSwitchMode, None)
            self.AddMatchString(re.compile(b'Brit([0-3]{1,2})\*([0-9]{1,3})\r\n'), self.__MatchBrightness, None)
            self.AddMatchString(re.compile(b'Cont([0-3]{1,2})\*([0-9]{1,3})\r\n'), self.__MatchContrast, None)
            self.AddMatchString(re.compile(b'Imr[023]?\*(.*)\r\n'), self.__MatchCurrentImage, None)
            self.AddMatchString(re.compile(b'Cshw([0-3]{1,2})\r\n'), self.__MatchCursorDisplay, None)
            self.AddMatchString(re.compile(b'Shdw([01])\r\n'), self.__MatchDropShadow, None)
            self.AddMatchString(re.compile(b'Ersr([0-9]{1,2})\r\n'), self.__MatchEraserHighlighterSize, None)
            self.AddMatchString(re.compile(b'Exe([0-2])\r\n'), self.__MatchExecutiveMode, None)
            self.AddMatchString(re.compile(b'Frz([01])\r\n'), self.__MatchFreeze, None)
            self.AddMatchString(re.compile(b'Mcap([0-3])\r\n'), self.__MatchFrontPanelCaptureButtonMode, None)
            self.AddMatchString(re.compile(b'HdcpS([01])\r\n'), self.__MatchHDCPOutputMode, None)
            self.AddMatchString(re.compile(b'Hdcp([IO][0-3]{1,2})\*([0-2])\r\n'), self.__MatchHDCPStatus, None)
            self.AddMatchString(re.compile(b'Hctr([-+]?[0-9]{1,5})\r\n'), self.__MatchHorizontalShift, None)
            self.AddMatchString(re.compile(b'Hsiz([0-9]{2,5})\r\n'), self.__MatchHorizontalSize, None)
            self.AddMatchString(re.compile(b'Hsrt([0-3]{1,2})\*([0-9]{1,3})\r\n'), self.__MatchHorizontalStart, None)
            self.AddMatchString(re.compile(b'In([0-3]{1,2})\r\n'), self.__MatchInput, None)
            self.AddMatchString(re.compile(b'EdidA([0-3]{1,2})\*([0-9]{1,3})\r\n'), self.__MatchInputEDID, None)
            self.AddMatchString(re.compile(b'Ityp([0-3]{1,2})\*([0-7])\*([0-8])\r\n'), self.__MatchInputVideoFormat, None)
            self.AddMatchString(re.compile(b'Lnwt([0-9]{1,2})\r\n'), self.__MatchLineWeight, None)
            self.AddMatchString(re.compile(b'Rate([0-9]{1,3})\r\n'), self.__MatchOutputScalerRate, None)
            self.AddMatchString(re.compile(b'Phas([0-3]{1,2})\*([0-9]{1,3})\r\n'), self.__MatchPixelPhase, None)
            self.AddMatchString(re.compile(b'Psav([01])\r\n'), self.__MatchPowerSave, None)
            self.AddMatchString(re.compile(b'SsavM([12])\r\n'), self.__MatchScreenSaver, None)
            self.AddMatchString(re.compile(b'SsavT([0-9]{1,3})\r\n'), self.__MatchScreenSaverTimeout, None)
            self.AddMatchString(re.compile(b'In00 ([01])\*([01])\*([01])\r\n'), self.__MatchSignalStatus, None)
            self.AddMatchString(re.compile(b'Swef([01])\r\n'), self.__MatchSwitchingEffect, None)
            self.AddMatchString(re.compile(b'20Stat ([0-9]{1,2})\r\n'), self.__MatchTemperature, None)
            self.AddMatchString(re.compile(b'Test([0-9]{1,2})\r\n'), self.__MatchTestPattern, None)
            self.AddMatchString(re.compile(b'Txsz([0-9]{1,2})\r\n'), self.__MatchTextSize, None)
            self.AddMatchString(re.compile(b'Tpix([0-3]{1,2})\*([0-9]{1,4})\r\n'), self.__MatchTotalPixel, None)
            self.AddMatchString(re.compile(b'Adev([0-9]{1,2})\*([01])\r\n'), self.__MatchUSBDevice, None)
            self.AddMatchString(re.compile(b'Vctr([-+]?[0-9]{1,5})\r\n'), self.__MatchVerticalShift, None)
            self.AddMatchString(re.compile(b'Vsiz([0-9]{2,5})\r\n'), self.__MatchVerticalSize, None)
            self.AddMatchString(re.compile(b'Vsrt([0-3]{1,2})\*([0-9]{1,3})\r\n'), self.__MatchVerticalStart, None)
            self.AddMatchString(re.compile(b'Vmt([0-3])\*([0-2]{1,2})\r\n'), self.__MatchVideoMute, None)
            self.AddMatchString(re.compile(b'Whbd([0-2])\r\n'), self.__MatchWhiteboardBlackboard, None)

            self.AddMatchString(re.compile(b'(E\d+)\r\n'), self.__MatchError, None)
            self.AddMatchString(re.compile(b'Vrb3\r\n'), self.__MatchVerboseMode, None)

            self.AddMatchString(re.compile(b'Password:'), self.__MatchPassword, None)
            self.AddMatchString(re.compile(b'Login Administrator\r\n'), self.__MatchLoginAdmin, None)
            self.AddMatchString(re.compile(b'Login User\r\n'), self.__MatchLoginUser, None)

    def __MatchAnnotationColor(self, match, tag):
        #print('__MatchAnnotationColor')
        ColorDict = {'Red':  int(match.group(2), 2),
                     'Green': int(match.group(3), 2),
                     'Blue':  int(match.group(4), 2),
                    }

        Opacity = match.group(1).decode()
        if Opacity == '0':
            Opacity = 'All'

        #print('Opacity = {}\nColorDict = {}'.format(Opacity, ColorDict))

        self.CurrentAnnotationColor = ColorDict
        self.WriteStatus('AnnotationColor', Opacity, ColorDict)

    def SetPassword(self, value, qualifier):
        self.Send(self.devicePassword + '\r\n')

    def __MatchPassword(self, match, tag):
        self.PasswdPromptCount += 1
        if self.PasswdPromptCount > 1:
            print('Log in failed. Please supply proper Admin password')
        else:
            self.SetPassword(None, None)
        self.Authenticated = 'None'

    def __MatchLoginAdmin(self, match, tag):
        self.Authenticated = 'Admin'
        self.PasswdPromptCount = 0

    def __MatchLoginUser(self, match, tag):
        self.Authenticated = 'User'
        self.PasswdPromptCount = 0
        print('Logged in as User. May have limited functionality.')

    def __MatchVerboseMode(self, match, qualifier):
        self.VerboseDisabled = False
        self.OnConnected()

    def SetActiveLines(self, value, qualifier):
        ActiveLines = {
            'Min': 0,
            'Max': 4095
        }
        if value >= ActiveLines['Min'] and value <= ActiveLines['Max']:
            ActiveLineCommand = '\x1B{0}ALIN\r'.format(value)
            self.__SetHelper('ActiveLines', ActiveLineCommand, value, qualifier, 3)
        else:
            print('Invalid Set Command for ActiveLines')

    def UpdateActiveLines(self, value, qualifier):
        ActiveLineQueryCommand = '\x1BALIN\r'
        self.__UpdateHelper('ActiveLines', ActiveLineQueryCommand, value, qualifier)

    def __MatchActiveLines(self, match, tag):
        value = int(match.group(2).decode())
        self.WriteStatus('ActiveLines', value, None)

    def SetActivePixels(self, value, qualifier):
        ActivePixel = {
            'Min': 0,
            'Max': 4095
        }
        if value >= ActivePixel['Min'] and value <= ActivePixel['Max']:
            ActivePixelsCommand = '\x1B{0}APIX\r'.format(value)
            self.__SetHelper('ActivePixels', ActivePixelsCommand, value, qualifier, 3)
        else:
            print('Invalid Set Command for ActivePixels')

    def UpdateActivePixels(self, value, qualifier):
        ActivePixelQueryCommand = '\x1BAPIX\r'
        self.__UpdateHelper('ActivePixels', ActivePixelQueryCommand, value, qualifier)

    def __MatchActivePixels(self, match, tag):
        value = int(match.group(2).decode())
        self.WriteStatus('ActivePixels', value, None)

    def SetAnnotationColor(self, value, qualifier):
        Red = qualifier['Red']
        Green = qualifier['Green']
        Blue = qualifier['Blue']
        if value == 'All':
            Device = 0
        else:
            Device = value
        if 0 <= int(Device) <= 64 and 0 <= Red <= 3 and 0 <= Green <= 3 and 0 <= Blue <= 3:
            ColorValue = '{0:02b}{1:02b}{2:02b}'.format(Red, Green, Blue)
            AnnotationColorCmdString = '\x1B{0}*{1}ACOL\r'.format(Device, ColorValue)
            self.__SetHelper('AnnotationColor', AnnotationColorCmdString, value, qualifier)
        else:
            print('Invalid Set Command for AnnotationColor')

        if 'UI' in qualifier.keys():
            ui = qualifier['UI']

            self.ColorMap[ui] = {'Value': value,
                                 'Red'  : Red,
                                 'Green': Green,
                                 'Blue' : Blue,
                                 }

    def SetAnnotationDisplay(self, value, qualifier):
        DisplayStates = {
            'All Outputs': 0,
            'Output 1 Only': 1,
            'Output 2A and 2B Only': 2,
            'None': 3
        }
        AnnotationDisplayCommand = '\x1B{0}ASHW\r'.format(DisplayStates[value])
        self.__SetHelper('AnnotationDisplay', AnnotationDisplayCommand, value, qualifier)

    def UpdateAnnotationDisplay(self, value, qualifier):
        AnnotationDisplayQuery = '\x1BASHW\r'
        self.__UpdateHelper('AnnotationDisplay', AnnotationDisplayQuery, value, qualifier)

    def __MatchAnnotationDisplay(self, match, tag):
        AnnotationDisplay = {
            '0': 'All Outputs',
            '1': 'Output 1 Only',
            '2': 'Output 2A and 2B Only',
            '3': 'None'
        }
        value = AnnotationDisplay[str(int(match.group(1).decode()))]
        self.WriteStatus('AnnotationDisplay', value, None)

    def SetAnnotationEditFunctions(self, value, qualifier):
        AnnotationEditStates = {
            'Clear': 0,
            'Undo': 1,
            'Redo': 2
        }
        AnnotationEditCommand = '\x1B{0}EDIT\r'.format(AnnotationEditStates[value])
        self.__SetHelper('AnnotationEditFunctions', AnnotationEditCommand, value, qualifier)

    def SetAnnotationObjectFill(self, value, qualifier):
        AnnotationObjectFillStates = {
            'Off': 0,
            'On': 1
        }
        AnnotationObjectFillCommands = '\x1B{0}FILL\r'.format(AnnotationObjectFillStates[value])
        self.__SetHelper('AnnotationObjectFill', AnnotationObjectFillCommands, value, qualifier)

    def UpdateAnnotationObjectFill(self, value, qualifier):
        AnnotationObjectFillQuery = '\x1BFILL\r'
        self.__UpdateHelper('AnnotationObjectFill', AnnotationObjectFillQuery, value, qualifier)

    def __MatchAnnotationObjectFill(self, match, tag):
        AnnotationObjectFillStates = {
            '0': 'Off',
            '1': 'On'
        }
        value = AnnotationObjectFillStates[str(int(match.group(1).decode()))]
        self.WriteStatus('AnnotationObjectFill', value, None)

    def SetAnnotationType(self, value, qualifier):
        AnnotationType = {
            'Eraser': 0,
            'Pointer': 1,
            'Freehand': 2,
            'Highlighter': 3,
            'Vector Line': 4,
            'Arrow Line': 5,
            'Ellipse': 6,
            'Rectangle': 7,
            'Text Tool': 8,
            'Spotlight': 9,
            'Zoom Tool': 10,
            'Pan Tool': 11
        }
        AnnotationTypeCommand = '\x1B{0}DRAW\r'.format(AnnotationType[value])
        self.__SetHelper('AnnotationType', AnnotationTypeCommand, value, qualifier)

        if qualifier:
            if 'UI' in qualifier:
                self.TypeMap[qualifier['UI']] = value

    def UpdateAnnotationType(self, value, qualifier):
        AnnotationTypeQuery = '\x1BDRAW\r'
        self.__UpdateHelper('AnnotationType', AnnotationTypeQuery, value, qualifier)

    def __MatchAnnotationType(self, match, tag):
        AnnotationTypeStates = {
            '00': 'Eraser',
            '01': 'Pointer',
            '02': 'Freehand',
            '03': 'Highlighter',
            '04': 'Vector Line',
            '05': 'Arrow Line',
            '06': 'Ellipse',
            '07': 'Rectangle',
            '08': 'Text Tool',
            '09': 'Spotlight',
            '10': 'Zoom Tool',
            '11': 'Pan Tool'
        }

        value = AnnotationTypeStates[match.group(1).decode()]
        self.WriteStatus('AnnotationType', value, None)

    def SetAspectRatio(self, value, qualifier):
        AspectRatioValues = {
            'Fill': '1',
            'Follow': '2'
        }
        InputSelect = qualifier['Input']
        if 1 <= int(InputSelect) <= 3:
            AspectRatioCmdString = '\x1B{0}*{1}ASPR\r'.format(InputSelect, AspectRatioValues[value])
            self.__SetHelper('AspectRatio', AspectRatioCmdString, value, qualifier)
        else:
            print('Invalid Set Command for AspectRatio')

    def UpdateAspectRatio(self, value, qualifier):
        InputSelect = qualifier['Input']
        if 1 <= int(InputSelect) <= 3:
            self.__UpdateHelper('AspectRatio', '\x1B{0}ASPR\r'.format(InputSelect), value, qualifier)
        else:
            print('Invalid Update Command for AspectRatio')

    def __MatchAspectRatio(self, match, tag):
        AspectRatioNames = {
            '1': 'Fill',
            '2': 'Follow'
        }

        value = AspectRatioNames[match.group(2).decode()]
        qualifier = {'Input': str(int(match.group(1).decode()))}
        self.WriteStatus('AspectRatio', value, qualifier)

    def SetAudioInputFormat(self, value, qualifier):
        AudioInputFormatValues = {
            'None': '0',
            '2CH Digital': '1',
            'Full Digital': '2'
        }
        InputSelect = qualifier['Input']
        if 2 <= int(InputSelect) <= 3:
            self.__SetHelper('AudioInputFormat', '\x1BI{0}*{1}AFMT\r'.format(InputSelect, AudioInputFormatValues[value]), value, qualifier)
        else:
            print('Invalid Set Command for AudioInputFormat')

    def UpdateAudioInputFormat(self, value, qualifier):
        InputSelect = qualifier['Input']
        if 2 <= int(InputSelect) <= 3:
            self.__UpdateHelper('AudioInputFormat', '\x1BI{0}AFMT\r'.format(InputSelect), value, qualifier)
        else:
            print('Invalid Update Command for AudioInputFormat')

    def __MatchAudioInputFormat(self, match, tag):
        AudioInputFormatNames = {
            '0': 'None',
            '1': '2CH Digital',
            '2': 'Full Digital'
        }

        value = AudioInputFormatNames[match.group(2).decode()]
        qualifier = {'Input': str(int(match.group(1).decode()))}
        self.WriteStatus('AudioInputFormat', value, qualifier)

    def SetAudioMute(self, value, qualifier):
        AudioMuteValues = {
            'Off': '0',
            'On': '1'
        }
        self.__SetHelper('AudioMute', '{0}Z'.format(AudioMuteValues[value]), value, qualifier)

    def UpdateAudioMute(self, value, qualifier):
        self.__UpdateHelper('AudioMute', 'Z', value, qualifier)

    def __MatchAudioMute(self, match, tag):
        AudioMuteNames = {
            '0': 'Off',
            '1': 'On'
        }

        value = AudioMuteNames[match.group(1).decode()]
        self.WriteStatus('AudioMute', value, None)

    def SetAutoImage(self, value, qualifier):
        AutoImageValues = {
            'Execute': 'A',
            'Execute and Fill': '1*A',
            'Execute and Follow': '2*A'
        }
        AutoImageCommand = AutoImageValues[value]
        self.__SetHelper('AutoImage', AutoImageCommand, value, qualifier)

    def SetAutoSwitchMode(self, value, qualifier):
        AutoSwitchModeValues = {
            'Disable': '0',
            'Highest Priority': '1',
            'Lowest Priority': '2'
        }
        self.__SetHelper('AutoSwitchMode', '\x1B{0}AUSW\r'.format(AutoSwitchModeValues[value]), value, qualifier)

    def UpdateAutoSwitchMode(self, value, qualifier):
        self.__UpdateHelper('AutoSwitchMode', 'WAUSW|', value, qualifier)

    def __MatchAutoSwitchMode(self, match, tag):
        AutoSwitchModeNames = {
            '0': 'Disable',
            '1': 'Highest Priority',
            '2': 'Lowest Priority'
        }

        value = AutoSwitchModeNames[match.group(1).decode()]
        self.WriteStatus('AutoSwitchMode', value, None)

    def SetBrightness(self, value, qualifier):
        BrightnessConstraints = {
            'Min': 0,
            'Max': 127
        }
        if value >= BrightnessConstraints['Min'] and value <= BrightnessConstraints['Max']:
            BrightnessCommand = '\x1B{0}BRIT\r'.format(value)
            self.__SetHelper('Brightness', BrightnessCommand, value, qualifier, 3)
        else:
            print('Invalid Set Command for Brightness')

    def UpdateBrightness(self, value, qualifier):
        BrightnessQueryCommand = '\x1BBRIT\r'
        self.__UpdateHelper('Brightness', BrightnessQueryCommand, value, qualifier)

    def __MatchBrightness(self, match, tag):

        value = int(match.group(2))
        self.WriteStatus('Brightness', value, None)

    def SetContrast(self, value, qualifier):
        ContrastConstraints = {
            'Min': 0,
            'Max': 127
        }
        if value >= ContrastConstraints['Min'] and value <= ContrastConstraints['Max']:
            ContrastCommand = '\x1B{0}CONT\r'.format(value)
            self.__SetHelper('Contrast', ContrastCommand, value, qualifier, 3)
        else:
            print('Invalid Set Command for Contrast')

    def UpdateContrast(self, value, qualifier):
        ContrastQueryCommand = '\x1BCONT\r'
        self.__UpdateHelper('Contrast', ContrastQueryCommand, value, qualifier)

    def __MatchContrast(self, match, tag):

        value = int(match.group(2).decode())
        self.WriteStatus('Contrast', value, None)

    def UpdateCurrentImage(self, value, qualifier):
        CurrentImageQuery = '\x1BRF\r'
        self.__UpdateHelper('CurrentImage', CurrentImageQuery, value, qualifier)

    def __MatchCurrentImage(self, match, tag):

        value = match.group(1).decode()
        self.WriteStatus('CurrentImage', value, None)

    def SetCursorDisplay(self, value, qualifier):
        CursorStates = {
            'All Outputs': 0,
            'Output 1 Only': 1,
            'Output 2A and 2B Only': 2,
            'None': 3
        }
        CursorDisplayCommand = '\x1B{0}CSHW\r'.format(CursorStates[value])
        self.__SetHelper('CursorDisplay', CursorDisplayCommand, value, qualifier)

    def UpdateCursorDisplay(self, value, qualifier):
        CursorDisplayQuery = '\x1BCSHW\r'
        self.__UpdateHelper('CursorDisplay', CursorDisplayQuery, value, qualifier)

    def __MatchCursorDisplay(self, match, tag):
        CursorStates = {
            '0': 'All Outputs',
            '1': 'Output 1 Only',
            '2': 'Output 2A and 2B Only',
            '3': 'None'
        }

        value = CursorStates[str(int(match.group(1).decode()))]
        self.WriteStatus('CursorDisplay', value, None)

    def UpdateDetectedInputVideoFormat(self, value, qualifier):
        InputSelect = qualifier['Input']
        if 1 <= int(InputSelect) <= 3:
            self.__UpdateHelper('DetectedInputVideoFormat', '\x1B{0}ITYP\r'.format(InputSelect), value, qualifier)
        else:
            print('Invalid Update Command for DetectedInputVideoFormat')

    def __MatchDetectedInputVideoFormat(self, match, tag):
        pass

    def SetDigitalOutputFormat(self, value, qualifier):
        DigitalOutputFormatValues = {
            'Auto': '0',
            'DVI': '1',
            'HDMI RGB': '2',
            'HDMI RGB "LIMITED"': '3',
            'HDMI YUV 444 "FULL"': '4',
            'HDMI YUV 444 "LIMITED"': '5',
            'HDMI YUV 422 "FULL"': '6',
            'HDMI YUV 422 "LIMITED"': '7'
        }
        OutputValues = {
            'Output 1': '1',
            'Output 2A': '2',
            'Output 2B': '3'
        }
        OutputSelect = qualifier['Output']
        DigitalOutputFormatCmdString = '\x1B{0}*{1}OTYP\r'.format(OutputValues[OutputSelect], DigitalOutputFormatValues[value])
        self.__SetHelper('DigitalOutputFormat', DigitalOutputFormatCmdString, value, qualifier)

    def SetDropShadow(self, value, qualifier):
        DropShadowStates = {
            'On': 1,
            'Off': 0
        }
        DropShadowCommand = '\x1B{0}SHDW\r'.format(DropShadowStates[value])
        self.__SetHelper('DropShadow', DropShadowCommand, value, qualifier)

    def UpdateDropShadow(self, value, qualifier):
        DropShadowQuery = '\x1BSHDW\r'
        self.__UpdateHelper('DropShadow', DropShadowQuery, value, qualifier)

    def __MatchDropShadow(self, match, tag):
        DropShadowStates = {
            '0': 'Off',
            '1': 'On'
        }

        value = DropShadowStates[match.group(1).decode()]
        self.WriteStatus('DropShadow', value, None)

    def SetEraserHighlighterSize(self, value=8, qualifier=None):
        Constraints = {
            'Min': 1,
            'Max': 63
        }
        if value >= Constraints['Min'] and value <= Constraints['Max']:
            EraserHighlighterSizeCommand = '\x1B{0}ERSR\r'.format(value)
            self.__SetHelper('EraserHighlighterSize', EraserHighlighterSizeCommand, value, qualifier, 3)
        else:
            print('Invalid Set Command for EraserHighlighterSize')

    def UpdateEraserHighlighterSize(self, value, qualifier):
        EraserHighlighterSizeQuery = '\x1BERSR\r'
        self.__UpdateHelper('EraserHighlighterSize', EraserHighlighterSizeQuery, value, qualifier)

    def __MatchEraserHighlighterSize(self, match, tag):

        value = int(match.group(1).decode())
        self.WriteStatus('EraserHighlighterSize', value, None)

    def SetExecutiveMode(self, value, qualifier):
        ExecutiveModeStates = {
            'Mode 1': '1X\r',
            'Mode 2': '2X\r',
            'Disabled': '0X\r'
        }
        ExecutiveModeCommand = ExecutiveModeStates[value]
        self.__SetHelper('ExecutiveMode', ExecutiveModeCommand, value, qualifier)

    def UpdateExecutiveMode(self, value, qualifier):
        ExecutiveModeQueryCommand = 'X'
        self.__UpdateHelper('ExecutiveMode', ExecutiveModeQueryCommand, value, qualifier)

    def __MatchExecutiveMode(self, match, tag):
        ExecutiveModeStates = {
            '0': 'Disabled',
            '1': 'Mode 1',
            '2': 'Mode 2'
        }
        value = ExecutiveModeStates[match.group(1).decode()]
        self.WriteStatus('ExecutiveMode', value, None)

    def SetFreeze(self, value, qualifier):
        FreezeStates = {
            'On': '1F',
            'Off': '0F'
        }
        FreezeCommand = FreezeStates[value]
        self.__SetHelper('Freeze', FreezeCommand, value, qualifier)

    def UpdateFreeze(self, value, qualifier):
        FreezeQueryCommand = 'F'
        self.__UpdateHelper('Freeze', FreezeQueryCommand, value, qualifier)

    def __MatchFreeze(self, match, tag):
        FreezeStates = {
            '0': 'Off',
            '1': 'On'
        }

        value = FreezeStates[match.group(1).decode()]
        self.WriteStatus('Freeze', value, None)

    def SetFrontPanelCaptureButtonMode(self, value, qualifier):
        ModeValues = {
            'Internal Memory': '0',
            'Remote': '1',
            'USB Flash': '2',
            'Network Drive': '3'
        }
        CommandString = '\x1B{0}MCAP\r'.format(ModeValues[value])
        self.__SetHelper('FrontPanelCaptureButtonMode', CommandString, value, qualifier)

    def UpdateFrontPanelCaptureButtonMode(self, value, qualifier):
        FrontPanelCaptureCmdString = '\x1BMCAP\r'
        self.__UpdateHelper('FrontPanelCaptureButtonMode', FrontPanelCaptureCmdString, value, qualifier)

    def __MatchFrontPanelCaptureButtonMode(self, match, tag):
        ModeNames = {
            '0': 'Internal Memory',
            '1': 'Remote',
            '2': 'USB Flash',
            '3': 'Network Drive'
        }

        value = ModeNames[match.group(1).decode()]
        self.WriteStatus('FrontPanelCaptureButtonMode', value, None)

    def SetHDCPOutputMode(self, value, qualifier):
        HDCPOutputModeValues = {
            'Auto': '0',
            'On': '1'
        }
        HDCPOutputModeCmdString = '\x1BS{0}HDCP\r'.format(HDCPOutputModeValues[value])
        self.__SetHelper('HDCPOutputMode', HDCPOutputModeCmdString, value, qualifier)

    def UpdateHDCPOutputMode(self, value, qualifier):
        self.__UpdateHelper('HDCPOutputMode', '\x1BSHDCP\r', value, qualifier)

    def __MatchHDCPOutputMode(self, match, tag):
        HDCPOutputModeNames = {
            '0': 'Auto',
            '1': 'On'
        }

        value = HDCPOutputModeNames[match.group(1).decode()]
        self.WriteStatus('HDCPOutputMode', value, None)

    def UpdateHDCPStatus(self, value, qualifier):
        PortValues = {
            'Input 1': 'I1',
            'Input 2': 'I2',
            'Input 3': 'I3',
            'Output 1': 'O1',
            'Output 2A': 'O2',
            'Output 2B': 'O3'
        }
        PortSelect = qualifier['Port']
        self.__UpdateHelper('HDCPStatus', '\x1B{0}HDCP\r'.format(PortValues[PortSelect]), value, qualifier)

    def __MatchHDCPStatus(self, match, tag):
        HDCPStatusNames = {
            '0': 'No sink or source device detected',
            '1': 'Sink or source detected with HDCP',
            '2': 'Sink or source detected but no HDCP is present'
        }
        PortNames = {
            'I01': 'Input 1',
            'I02': 'Input 2',
            'I03': 'Input 3',
            'O1': 'Output 1',
            'O2': 'Output 2A',
            'O3': 'Output 2B'
        }

        value = HDCPStatusNames[match.group(2).decode()]
        qualifier = {'Port': PortNames[match.group(1).decode()]}
        self.WriteStatus('HDCPStatus', value, qualifier)

    def SetHorizontalShift(self, value, qualifier):
        HorizontalShift = {
            'Min': -11000,
            'Max': 11000
        }
        if value >= HorizontalShift['Min'] and value <= HorizontalShift['Max']:
            HorizontalShiftCommand = '\x1B{0}HCTR\r'.format(value)
            self.__SetHelper('HorizontalShift', HorizontalShiftCommand, value, qualifier, 3)
        else:
            print('Invalid Set Command for HorizontalShift')

    def UpdateHorizontalShift(self, value, qualifier):
        HorizontalShiftQuery = '\x1BHCTR\r'
        self.__UpdateHelper('HorizontalShift', HorizontalShiftQuery, value, qualifier)

    def __MatchHorizontalShift(self, match, tag):

        value = int(match.group(1).decode())
        self.WriteStatus('HorizontalShift', value, None)

    def SetHorizontalSize(self, value, qualifier):
        HorizontalSize = {
            'Min': 10,
            'Max': 11000
        }
        if value >= HorizontalSize['Min'] and value <= HorizontalSize['Max']:
            HorizontalSizeCommand = '\x1B{0}HSIZ\r'.format(value)
            self.__SetHelper('HorizontalSize', HorizontalSizeCommand, value, qualifier, 3)
        else:
            print('Invalid Set Command for HorizontalSize')

    def UpdateHorizontalSize(self, value, qualifier):
        HorizontalSizeQuery = '\x1BHSIZ\r'
        self.__UpdateHelper('HorizontalSize', HorizontalSizeQuery, value, qualifier)

    def __MatchHorizontalSize(self, match, tag):

        value = int(match.group(1).decode())
        self.WriteStatus('HorizontalSize', value, None)

    def SetHorizontalStart(self, value, qualifier):
        HorizontalStartConstraints = {
            'Min': 0,
            'Max': 255
        }
        if value >= HorizontalStartConstraints['Min'] and value <= HorizontalStartConstraints['Max']:
            HorizontalStartCommand = '\x1B{0}HSRT\r'.format(value)
            self.__SetHelper('HorizontalStart', HorizontalStartCommand, value, qualifier, 3)
        else:
            print('Invalid Set Command for HorizontalStart')

    def UpdateHorizontalStart(self, value, qualifier):
        HorizontalStartQuery = '\x1BHSRT\r'
        self.__UpdateHelper('HorizontalStart', HorizontalStartQuery, value, qualifier)

    def __MatchHorizontalStart(self, match, tag):

        value = int(match.group(2).decode())
        self.WriteStatus('HorizontalStart', value, None)

    def SetMuteImage(self, value, qualifier):
        MuteImageCommand = '\x1B0*0RF\r'
        self.__SetHelper('MuteImage', MuteImageCommand, value, qualifier)

    def SetQuickCapture(self, value, qualifier):
        QuickCaptureCommand = '\x1BQCAP\r'
        self.__SetHelper('QuickCapture', QuickCaptureCommand, value, qualifier)

    def SetInput(self, value, qualifier):
        if 1 <= int(value) <= 3:
            InputCommand = '{0}!'.format(value)
            self.__SetHelper('Input', InputCommand, value, qualifier)
        else:
            print('Invalid Set Command for Input')

    def UpdateInput(self, value, qualifier):
        InputQueryCommand = '!'
        self.__UpdateHelper('Input', InputQueryCommand, value, qualifier)

    def __MatchInput(self, match, tag):

        value = str(int(match.group(1).decode()))
        self.WriteStatus('Input', value, None)

    def SetInputEDID(self, value, qualifier):
        InputEDIDValues = {
            'Automatic': '0',
            'Output 1': '1',
            'Output 2A': '2',
            'Output 2B': '3',
            '640x480 (60Hz)': '10',
            '800x600 (60Hz)': '11',
            '1024x768 (60Hz)': '12',
            '1280x768 (60Hz)': '13',
            '1280x800 (60Hz)': '14',
            '1280x1024 (60Hz)': '15',
            '1360x768 (60Hz)': '16',
            '1366x768 (60Hz)': '17',
            '1440x900 (60Hz)': '18',
            '1400x1050 (60Hz)': '19',
            '1600x900 (60Hz)': '20',
            '1680x1050 (60Hz)': '21',
            '1600x1200 (60Hz)': '22',
            '1920x1200 (60Hz)': '23',
            '480p (59.94Hz)': '24',
            '480p (60Hz)': '25',
            '576p (50Hz)': '26',
            '720p (23.98Hz)': '27',
            '720p (24Hz)': '28',
            '720p (25Hz)': '29',
            '720p (29.97Hz)': '30',
            '720p (30Hz)': '31',
            '720p (50Hz)': '32',
            '720p (59.94Hz)': '33',
            '720p (60Hz)': '34',
            '1080i (50Hz)': '35',
            '1080i (59.94Hz)': '36',
            '1080i (60Hz)': '37',
            '1080p (23.98Hz)': '38',
            '1080p (24Hz)': '39',
            '1080p (25Hz)': '40',
            '1080p (29.97Hz)': '41',
            '1080p (30Hz)': '42',
            '1080p (50Hz)': '43',
            '1080p (59.94Hz)': '44',
            '1080p (60Hz)': '45',
            '2048x1080 (23.98Hz)': '46',
            '2048x1080 (24Hz)': '47',
            '2048x1080 (25Hz)': '48',
            '2048x1080 (29.97Hz)': '49',
            '2048x1080 (30Hz)': '50',
            '2048x1080 (50Hz)': '51',
            '2048x1080 (59.94Hz)': '52',
            '2048x1080 (60Hz)': '53',
            '2560x1440 (60Hz)': '81',
            '2560x1600 (60Hz)': '82',
            'Custom EDID 1': '201',
            'Custom EDID 2': '202',
            'Custom EDID 3': '203'
        }
        InputSelect = qualifier['Input']
        if 1 <= int(InputSelect) <= 3:
            InputEDIDCmdString = '\x1BA{0}*{1}EDID\r'.format(InputSelect, InputEDIDValues[value])
            self.__SetHelper('InputEDID', InputEDIDCmdString, value, qualifier)
        else:
            print('Invalid Set Command for InputEDID')

    def UpdateInputEDID(self, value, qualifier):
        InputSelect = qualifier['Input']
        if 1 <= int(InputSelect) <= 3:
            self.__UpdateHelper('InputEDID', '\x1BA{0}EDID\r'.format(InputSelect), value, qualifier)
        else:
            print('Invalid Update Command for InputEDID')

    def __MatchInputEDID(self, match, tag):
        InputEDIDNames = {
            '0': 'Automatic',
            '1': 'Output 1',
            '2': 'Output 2A',
            '3': 'Output 2B',
            '10': '640x480 (60Hz)',
            '11': '800x600 (60Hz)',
            '12': '1024x768 (60Hz)',
            '13': '1280x768 (60Hz)',
            '14': '1280x800 (60Hz)',
            '15': '1280x1024 (60Hz)',
            '16': '1360x768 (60Hz)',
            '17': '1366x768 (60Hz)',
            '18': '1440x900 (60Hz)',
            '19': '1400x1050 (60Hz)',
            '20': '1600x900 (60Hz)',
            '21': '1680x1050 (60Hz)',
            '22': '1600x1200 (60Hz)',
            '23': '1920x1200 (60Hz)',
            '24': '480p (59.94Hz)',
            '25': '480p (60Hz)',
            '26': '576p (50Hz)',
            '27': '720p (23.98Hz)',
            '28': '720p (24Hz)',
            '29': '720p (25Hz)',
            '30': '720p (29.97Hz)',
            '31': '720p (30Hz)',
            '32': '720p (50Hz)',
            '33': '720p (59.94Hz)',
            '34': '720p (60Hz)',
            '35': '1080i (50Hz)',
            '36': '1080i (59.94Hz)',
            '37': '1080i (60Hz)',
            '38': '1080p (23.98Hz)',
            '39': '1080p (24Hz)',
            '40': '1080p (25Hz)',
            '41': '1080p (29.97Hz)',
            '42': '1080p (30Hz)',
            '43': '1080p (50Hz)',
            '44': '1080p (59.94Hz)',
            '45': '1080p (60Hz)',
            '46': '2048x1080 (23.98Hz)',
            '47': '2048x1080 (24Hz)',
            '48': '2048x1080 (25Hz)',
            '49': '2048x1080 (29.97Hz)',
            '50': '2048x1080 (30Hz)',
            '51': '2048x1080 (50Hz)',
            '52': '2048x1080 (59.94Hz)',
            '53': '2048x1080 (60Hz)',
            '81': '2560x1440 (60Hz)',
            '82': '2560x1600 (60Hz)',
            '201': 'Custom EDID 1',
            '202': 'Custom EDID 2',
            '203': 'Custom EDID 3'
        }

        value = InputEDIDNames[str(int(match.group(2).decode()))]
        qualifier = {'Input': str(int(match.group(1).decode()))}
        self.WriteStatus('InputEDID', value, qualifier)

    def SetInputPresets(self, value, qualifier):
        CommandValues = {
            'Save': ',',
            'Recall': '.'
        }
        CommandSelect = qualifier['Command']
        if 1 <= int(value) <= 128:
            InputPresetCommand = '2*{0}{1}'.format(value, CommandValues[CommandSelect])
            self.__SetHelper('InputPresets', InputPresetCommand, value, qualifier)
        else:
            print('Invalid Set Command for InputPresets')

    def SetInputVideoFormat(self, value, qualifier):
        InputVideoFormatValues = {
            'Auto Detect': '0',
            'RGB': '1',
            'Auto YUV': '2',
            'RGBcvS': '3',
            'S-Video': '4',
            'Composite': '5',
            'HDMI/DVI': '6',
            'DisplayPort': '7'
        }
        InputSelect = qualifier['Input']
        if 1 <= int(InputSelect) <= 3:
            InputVideoFormatCmdString = '\x1B{0}*{1}ITYP\r'.format(InputSelect, InputVideoFormatValues[value])
            self.__SetHelper('InputVideoFormat', InputVideoFormatCmdString, value, qualifier)
        else:
            print('Invalid Set Command for InputVideoFormat')

    def UpdateInputVideoFormat(self, value, qualifier):
        InputSelect = qualifier['Input']
        if 1 <= int(InputSelect) <= 3:
            self.__UpdateHelper('InputVideoFormat', '\x1B{0}ITYP\r'.format(InputSelect), value, qualifier)
        else:
            print('Invalid Update Command for InputVideoFormat')

    def __MatchInputVideoFormat(self, match, tag):
        InputVideoFormatNames = {
            '0': 'Auto Detect',
            '1': 'RGB',
            '2': 'Auto YUV',
            '3': 'RGBcvS',
            '4': 'S-Video',
            '5': 'Composite',
            '6': 'HDMI/DVI',
            '7': 'DisplayPort'
        }
        DetectedInputVideoFormatNames = {
            '0': 'No signal present',
            '1': 'RGB',
            '2': 'Auto YUV',
            '3': 'RGBcvS',
            '4': 'S-Video',
            '5': 'Composite',
            '6': 'DVI',
            '7': 'HDMI',
            '8': 'DisplayPort'
        }

        value = InputVideoFormatNames[match.group(2).decode()]
        qualifier = {'Input': str(int(match.group(1).decode()))}
        detectedValue = DetectedInputVideoFormatNames[match.group(3).decode()]
        self.WriteStatus('InputVideoFormat', value, qualifier)
        self.WriteStatus('DetectedInputVideoFormat', detectedValue, qualifier)

    def SetLineWeight(self, value, qualifier):
        LineWeightConstraints = {
            'Min': 1,
            'Max': 63
        }
        if value >= LineWeightConstraints['Min'] and value <= LineWeightConstraints['Max']:
            LineWeightCommand = '\x1B{0}LNWT\r'.format(value)
            self.__SetHelper('LineWeight', LineWeightCommand, value, qualifier, 3)
        else:
            print('Invalid Set Command for LineWeight')

    def UpdateLineWeight(self, value, qualifier):
        LineWeightQuery = '\x1BLNWT\r'
        self.__UpdateHelper('LineWeight', LineWeightQuery, value, qualifier)

    def __MatchLineWeight(self, match, tag):

        value = int(match.group(1).decode())
        self.WriteStatus('LineWeight', value, None)

    def SetMemoryPresets(self, value, qualifier):
        CommandValues = {
            'Save': ',',
            'Recall': '.'
        }
        CommandSelect = qualifier['Command']
        if 1 <= int(value) <= 16:
            PresetCommand = '1*{0}{1}'.format(value, CommandValues[CommandSelect])
            self.__SetHelper('MemoryPresets', PresetCommand, value, qualifier)
        else:
            print('Invalid Set Command for MemoryPresets')

    def SetMenuDisplay(self, value, qualifier):
        Output = {
            'All Outputs': 0,
            'Output 1 Only': 1,
            'Output 2A and 2B Only': 2,
            'None': 3
        }
        CommandString = '\x1B{0}MSHW\r'.format(Output[value])
        self.__SetHelper('MenuDisplay', CommandString, value, qualifier)

    def SetOutputScalerRate(self, value, qualifier):
        OutputScalerRateValues = {
            '640x480 (60Hz)': '10',
            '800x600 (60Hz)': '11',
            '1024x768 (60Hz)': '12',
            '1280x768 (60Hz)': '13',
            '1280x800 (60Hz)': '14',
            '1280x1024 (60Hz)': '15',
            '1360x768 (60Hz)': '16',
            '1366x768 (60Hz)': '17',
            '1440x900 (60Hz)': '18',
            '1400x1050 (60Hz)': '19',
            '1600x900 (60Hz)': '20',
            '1680x1050 (60Hz)': '21',
            '1600x1200 (60Hz)': '22',
            '1920x1200 (60Hz)': '23',
            '480p (59.94Hz)': '24',
            '480p (60Hz)': '25',
            '576p (50Hz)': '26',
            '720p (23.98Hz)': '27',
            '720p (24Hz)': '28',
            '720p (25Hz)': '29',
            '720p (29.97Hz)': '30',
            '720p (30Hz)': '31',
            '720p (50Hz)': '32',
            '720p (59.94Hz)': '33',
            '720p (60Hz)': '34',
            '1080i (50Hz)': '35',
            '1080i (59.94Hz)': '36',
            '1080i (60Hz)': '37',
            '1080p (23.98Hz)': '38',
            '1080p (24Hz)': '39',
            '1080p (25Hz)': '40',
            '1080p (29.97Hz)': '41',
            '1080p (30Hz)': '42',
            '1080p (50Hz)': '43',
            '1080p (59.94Hz)': '44',
            '1080p (60Hz)': '45',
            '2048x1080 (23.98Hz)': '46',
            '2048x1080 (24Hz)': '47',
            '2048x1080 (25Hz)': '48',
            '2048x1080 (29.97Hz)': '49',
            '2048x1080 (30Hz)': '50',
            '2048x1080 (50Hz)': '51',
            '2048x1080 (59.94Hz)': '52',
            '2048x1080 (60Hz)': '53',
            'Custom Output Rate 1': '201',
            'Custom Output Rate 2': '202',
            'Custom Output Rate 3': '203'
        }
        OutputScalerRateCmdString = '\x1B{0}RATE\r'.format(OutputScalerRateValues[value])
        self.__SetHelper('OutputScalerRate', OutputScalerRateCmdString, value, qualifier)

    def UpdateOutputScalerRate(self, value, qualifier):
        self.__UpdateHelper('OutputScalerRate', '\x1BRATE\r', value, qualifier)

    def __MatchOutputScalerRate(self, match, tag):
        OutputScalerRateNames = {
            '10': '640x480 (60Hz)',
            '11': '800x600 (60Hz)',
            '12': '1024x768 (60Hz)',
            '13': '1280x768 (60Hz)',
            '14': '1280x800 (60Hz)',
            '15': '1280x1024 (60Hz)',
            '16': '1360x768 (60Hz)',
            '17': '1366x768 (60Hz)',
            '18': '1440x900 (60Hz)',
            '19': '1400x1050 (60Hz)',
            '20': '1600x900 (60Hz)',
            '21': '1680x1050 (60Hz)',
            '22': '1600x1200 (60Hz)',
            '23': '1920x1200 (60Hz)',
            '24': '480p (59.94Hz)',
            '25': '480p (60Hz)',
            '26': '576p (50Hz)',
            '27': '720p (23.98Hz)',
            '28': '720p (24Hz)',
            '29': '720p (25Hz)',
            '30': '720p (29.97Hz)',
            '31': '720p (30Hz)',
            '32': '720p (50Hz)',
            '33': '720p (59.94Hz)',
            '34': '720p (60Hz)',
            '35': '1080i (50Hz)',
            '36': '1080i (59.94Hz)',
            '37': '1080i (60Hz)',
            '38': '1080p (23.98Hz)',
            '39': '1080p (24Hz)',
            '40': '1080p (25Hz)',
            '41': '1080p (29.97Hz)',
            '42': '1080p (30Hz)',
            '43': '1080p (50Hz)',
            '44': '1080p (59.94Hz)',
            '45': '1080p (60Hz)',
            '46': '2048x1080 (23.98Hz)',
            '47': '2048x1080 (24Hz)',
            '48': '2048x1080 (25Hz)',
            '49': '2048x1080 (29.97Hz)',
            '50': '2048x1080 (30Hz)',
            '51': '2048x1080 (50Hz)',
            '52': '2048x1080 (59.94Hz)',
            '53': '2048x1080 (60Hz)',
            '201': 'Custom Output Rate 1',
            '202': 'Custom Output Rate 2',
            '203': 'Custom Output Rate 3'
        }
        value = OutputScalerRateNames[match.group(1).decode()]
        self.WriteStatus('OutputScalerRate', value, None)

    def SetPixelPhase(self, value, qualifier):
        PixelPhaseConstraints = {
            'Min': 0,
            'Max': 63
        }
        if value >= PixelPhaseConstraints['Min'] and value <= PixelPhaseConstraints['Max']:
            PixelPhaseCommand = '\x1B{0}PHAS\r'.format(value)
            self.__SetHelper('PixelPhase', PixelPhaseCommand, value, qualifier, 3)
        else:
            print('Invalid Set Command for PixelPhase')

    def UpdatePixelPhase(self, value, qualifier):
        PixelPhaseQuery = '\x1BPHAS\r'
        self.__UpdateHelper('PixelPhase', PixelPhaseQuery, value, qualifier)

    def __MatchPixelPhase(self, match, tag):
        value = int(match.group(2).decode())
        self.WriteStatus('PixelPhase', value, None)

    def SetPowerSave(self, value, qualifier):
        PowerSaveValues = {
            'Off': '0',
            'On': '1'
        }
        PowerSaveCmdString = '\x1B{0}PSAV\r'.format(PowerSaveValues[value])
        self.__SetHelper('PowerSave', PowerSaveCmdString, value, qualifier)

    def UpdatePowerSave(self, value, qualifier):
        self.__UpdateHelper('PowerSave', '\x1BPSAV\r', value, qualifier)

    def __MatchPowerSave(self, match, tag):
        PowerSaveNames = {
            '0': 'Off',
            '1': 'On'
        }
        value = PowerSaveNames[match.group(1).decode()]
        self.WriteStatus('PowerSave', value, None)

    def SetRecallImageCommand(self, value, qualifier):
        LocationValues = {
            'Internal Flash': '0',
            'USB Drive': '2',
            'Network': '3'
        }
        LocationSelect = LocationValues[value]
        cmdString = qualifier['File Name']
        if cmdString and 1 <= len(cmdString) <= 16:
            self.__SetHelper('RecallImageCommand', '\x1B{0}*{1}RF\r'.format(LocationSelect, cmdString), value, qualifier)
        else:
            print('Invalid Set Command for RecallImageCommand')

    def SetSaveImageCommand(self, value, qualifier):
        LocationValues = {
            'Internal Flash': '0',
            'USB Drive': '2',
            'Network': '3'
        }
        LocationSelect = LocationValues[value]
        cmdString = qualifier['File Name']
        if cmdString and 1 <= len(cmdString) <= 16:
            self.__SetHelper('SaveImageCommand', '\x1B{0}*{1}MF\r'.format(LocationSelect, cmdString), value, qualifier)
        else:
            print('Invalid Set Command for SaveImageCommand')

    def SetScreenSaver(self, value, qualifier):
        ScreenSaverValues = {
            'Black Screen': '1',
            'Blue Screen': '2'
        }
        ScreenSaverCmdString = '\x1BM{0}SSAV\r'.format(ScreenSaverValues[value])
        self.__SetHelper('ScreenSaver', ScreenSaverCmdString, value, qualifier)

    def UpdateScreenSaver(self, value, qualifier):
        self.__UpdateHelper('ScreenSaver', '\x1BMSSAV\r', value, qualifier)

    def __MatchScreenSaver(self, match, tag):
        ScreenSaverNames = {
            '1': 'Black Screen',
            '2': 'Blue Screen'
        }
        value = ScreenSaverNames[match.group(1).decode()]
        self.WriteStatus('ScreenSaver', value, None)

    def SetScreenSaverTimeout(self, value, qualifier):
        if 0 <= value <= 501:
            ScreenSaverTimeoutCmdString = '\x1BT{0}SSAV\r'.format(value)
            self.__SetHelper('ScreenSaverTimeout', ScreenSaverTimeoutCmdString, value, qualifier)
        else:
            print('Invalid Set Command for ScreenSaverTimeout')

    def UpdateScreenSaverTimeout(self, value, qualifier):
        self.__UpdateHelper('ScreenSaverTimeout', '\x1BTSSAV\r', value, qualifier)

    def __MatchScreenSaverTimeout(self, match, tag):
        value = int(match.group(1).decode())
        self.WriteStatus('ScreenSaverTimeout', value, None)

    def UpdateSignalStatus(self, value, qualifier):
        self.__UpdateHelper('SignalStatus', '\x1B0LS\r', value, qualifier)

    def __MatchSignalStatus(self, match, tag):
        SignalStatusNames = {
            '0': 'Signal Not Detected',
            '1': 'Signal Detected'
        }
        in1 = SignalStatusNames[match.group(1).decode()]
        in2 = SignalStatusNames[match.group(2).decode()]
        in3 = SignalStatusNames[match.group(3).decode()]
        self.WriteStatus('SignalStatus', in1, {'Input': '1'})
        self.WriteStatus('SignalStatus', in2, {'Input': '2'})
        self.WriteStatus('SignalStatus', in3, {'Input': '3'})

    def SetSwitchingEffect(self, value, qualifier):
        SwitchEffectStates = {
            'Cut': 0,
            'Fade': 1
        }
        SwitchCommand = '\x1B{0}SWEF\r'.format(SwitchEffectStates[value])
        self.__SetHelper('SwitchingEffect', SwitchCommand, value, qualifier)

    def UpdateSwitchingEffect(self, value, qualifier):
        SwitchEffectQuery = '\x1BSWEF\r'
        self.__UpdateHelper('SwitchingEffect', SwitchEffectQuery, value, qualifier)

    def __MatchSwitchingEffect(self, match, tag):
        SwitchEffectStates = {
            '0': 'Cut',
            '1': 'Fade'
        }
        value = SwitchEffectStates[match.group(1).decode()]
        self.WriteStatus('SwitchingEffect', value, None)

    def UpdateTemperature(self, value, qualifier):
        TemperatureQuery = '\x1B20STAT\r'
        self.__UpdateHelper('Temperature', TemperatureQuery, value, qualifier)

    def __MatchTemperature(self, match, tag):
        value = int(match.group(1).decode())
        self.WriteStatus('Temperature', value, None)

    def SetTestPattern(self, value, qualifier):
        TestPatternStates = {
            'Off': 0,
            'Crop': 1,
            'Alternating Pixels': 2,
            'Alternating Lines': 3,
            'Crosshatch': 4,
            '4x4 Crosshatch': 5,
            'Color Bars': 6,
            'Grayscale': 7,
            'Ramp': 8,
            'White Field': 9,
            '1.33 Aspect Ratio': 10,
            '1.78 Aspect Ratio': 11,
            '1.85 Aspect Ratio': 12,
            '2.35 Aspect Ratio': 13,
            'Blue Mode': 14
        }
        TestPatternCommand = '\x1B{0}TEST\r'.format(TestPatternStates[value])
        self.__SetHelper('TestPattern', TestPatternCommand, value, qualifier)

    def UpdateTestPattern(self, value, qualifier):
        TestPatternQuery = '\x1BTEST\r'
        self.__UpdateHelper('TestPattern', TestPatternQuery, value, qualifier)

    def __MatchTestPattern(self, match, tag):
        TestPatternStates = {
            '0': 'Off',
            '1': 'Crop',
            '2': 'Alternating Pixels',
            '3': 'Alternating Lines',
            '4': 'Crosshatch',
            '5': '4x4 Crosshatch',
            '6': 'Color Bars',
            '7': 'Grayscale',
            '8': 'Ramp',
            '9': 'White Field',
            '10': '1.33 Aspect Ratio',
            '11': '1.78 Aspect Ratio',
            '12': '1.85 Aspect Ratio',
            '13': '2.35 Aspect Ratio',
            '14': 'Blue Mode'
        }
        value = TestPatternStates[str(int(match.group(1).decode()))]
        self.WriteStatus('TestPattern', value, None)

    def SetTextSize(self, value, qualifier):
        TextSizeConstraints = {
            'Min': 8,
            'Max': 63
        }
        if value >= TextSizeConstraints['Min'] and value <= TextSizeConstraints['Max']:
            TextSizeCommand = '\x1B{0}TXSZ\r'.format(value)
            self.__SetHelper('TextSize', TextSizeCommand, value, qualifier, 3)
        else:
            print('Invalid Set Command for TextSize')

    def UpdateTextSize(self, value, qualifier):
        TextSizeQuery = '\x1BTXSZ\r'
        self.__UpdateHelper('TextSize', TextSizeQuery, value, qualifier)

    def __MatchTextSize(self, match, tag):
        value = int(match.group(1).decode())
        self.WriteStatus('TextSize', value, None)

    def SetTotalPixel(self, value, qualifier):
        TotalPixel = {
            'Min': 0,
            'Max': 4095
        }
        if value >= TotalPixel['Min'] and value <= TotalPixel['Max']:
            TotalPixelCommand = '\x1B{0}TPIX\r'.format(value)
            self.__SetHelper('TotalPixel', TotalPixelCommand, value, qualifier, 3)
        else:
            print('Invalid Set Command for TotalPixel')

    def UpdateTotalPixel(self, value, qualifier):
        TotalPixelQuery = '\x1BTPIX\r'
        self.__UpdateHelper('TotalPixel', TotalPixelQuery, value, qualifier)

    def __MatchTotalPixel(self, match, tag):
        value = int(match.group(2).decode())
        self.WriteStatus('TotalPixel', value, None)

    def SetUSBDevice(self, value, qualifier):
        USBDeviceValues = {
            'Disable': '0',
            'Enable': '1'
        }
        DeviceSelect = qualifier['Device']
        if DeviceSelect == 'All':
            DeviceSelect = '0'
        if 0 <= int(DeviceSelect) <= 64:
            USBDeviceCmdString = '\x1B{0}*{1}ADEV\r'.format(DeviceSelect, USBDeviceValues[value])
            self.__SetHelper('USBDevice', USBDeviceCmdString, value, qualifier)
        else:
            print('Invalid Set Command for USBDevice')

    def UpdateUSBDevice(self, value, qualifier):
        DeviceSelect = qualifier['Device']
        if DeviceSelect == 'All':
            DeviceSelect = '0'
        if 0 <= int(DeviceSelect) <= 64:
            self.__UpdateHelper('USBDevice', '\x1B{0}ADEV\r'.format(DeviceSelect), value, qualifier)
        else:
            print('Invalid Update Command for USBDevice')

    def __MatchUSBDevice(self, match, tag):
        USBDeviceNames = {
            '0': 'Disable',
            '1': 'Enable'
        }
        value = USBDeviceNames[match.group(2).decode()]
        DeviceSelect = match.group(1).decode()
        if DeviceSelect == '0':
            DeviceSelect = 'All'
        qualifier = {'Device': DeviceSelect}
        self.WriteStatus('USBDevice', value, qualifier)

    def SetVerticalShift(self, value, qualifier):
        VerticalShift = {
            'Min': -11000,
            'Max': 11000
        }
        if value >= VerticalShift['Min'] and value <= VerticalShift['Max']:
            VerticalShiftCommand = '\x1B{0}VCTR\r'.format(value)
            self.__SetHelper('VerticalShift', VerticalShiftCommand, value, qualifier, 3)
        else:
            print('Invalid Set Command for VerticalShift')

    def UpdateVerticalShift(self, value, qualifier):
        VerticalQuery = '\x1BVCTR\r'
        self.__UpdateHelper('VerticalShift', VerticalQuery, value, qualifier)

    def __MatchVerticalShift(self, match, tag):
        value = int(match.group(1).decode())
        self.WriteStatus('VerticalShift', value, None)

    def SetVerticalSize(self, value, qualifier):
        VerticalSize = {
            'Min': 10,
            'Max': 11000
        }
        if value >= VerticalSize['Min'] and value <= VerticalSize['Max']:
            VerticalSizeCommand = '\x1B{0}VSIZ\r'.format(value)
            self.__SetHelper('VerticalSize', VerticalSizeCommand, value, qualifier, 3)
        else:
            print('Invalid Set Command for VerticalSize')

    def UpdateVerticalSize(self, value, qualifier):
        VerticalSizeQuery = '\x1BVSIZ\r'
        self.__UpdateHelper('VerticalSize', VerticalSizeQuery, value, qualifier)

    def __MatchVerticalSize(self, match, tag):
        value = int(match.group(1).decode())
        self.WriteStatus('VerticalSize', value, None)

    def SetVerticalStart(self, value, qualifier):
        VerticalStartConstraints = {
            'Min': 0,
            'Max': 255
        }
        if value >= VerticalStartConstraints['Min'] and value <= VerticalStartConstraints['Max']:
            VerticalStartCommand = '\x1B{0}VSRT\r'.format(value)
            self.__SetHelper('VerticalStart', VerticalStartCommand, value, qualifier, 3)
        else:
            print('Invalid Set Command for VerticalStart')

    def UpdateVerticalStart(self, value, qualifier):
        VerticalStartQuery = '\x1BVSRT\r'
        self.__UpdateHelper('VerticalStart', VerticalStartQuery, value, qualifier)

    def __MatchVerticalStart(self, match, tag):
        value = int(match.group(2).decode())
        self.WriteStatus('VerticalStart', value, None)

    def SetVideoMute(self, value, qualifier):
        OutputValues = {
            'All Outputs': '0',
            'Output 1 Only': '1',
            'Output 2A and 2B Only': '2'
        }
        VideoMuteStates = {
            'Mute Video': '1',
            'Mute Sync and Video': '2',
            'Off': '0'
        }
        OutputSelect = qualifier['Output']
        VideoMuteCommand = '{0}*{1}B'.format(OutputValues[OutputSelect], VideoMuteStates[value])
        self.__SetHelper('VideoMute', VideoMuteCommand, value, qualifier)

    def UpdateVideoMute(self, value, qualifier):
        OutputValues = {
            'All Outputs': '0',
            'Output 1 Only': '1',
            'Output 2A and 2B Only': '2'
        }
        OutputSelect = qualifier['Output']
        VideoMuteQuery = '{0}B'.format(OutputValues[OutputSelect])
        self.__UpdateHelper('VideoMute', VideoMuteQuery, value, qualifier)

    def __MatchVideoMute(self, match, tag):
        VideoMuteStates = {
            '0': 'Off',
            '1': 'Mute Video',
            '2': 'Mute Sync and Video'
        }
        OutputNames = {
            '0': 'All Outputs',
            '1': 'Output 1 Only',
            '2': 'Output 2A and 2B Only'
        }
        value = VideoMuteStates[str(int(match.group(2).decode()))]
        qualifier = {'Output': OutputNames[match.group(1).decode()]}
        self.WriteStatus('VideoMute', value, qualifier)

    def SetViewSettings(self, value, qualifier):
        CommandString = '\x1BMSHW\r'
        self.__SetHelper('ViewSettings', CommandString, value, qualifier)

    def SetWhiteboardBlackboard(self, value, qualifier):
        ValueStateValues = {
            'Whiteboard' : '\x1B1WHBD\r',
            'Blackboard' : '\x1B2WHBD\r',
            'Off' : '\x1B0WHBD\r'
        }

        WhiteboardBlackboardCmdString = ValueStateValues[value]
        self.__SetHelper('WhiteboardBlackboard', WhiteboardBlackboardCmdString, value, qualifier)

    def UpdateWhiteboardBlackboard(self, value, qualifier):
        WhiteboardBlackboardCmdString = '\x1BWHBD\r'
        self.__UpdateHelper('WhiteboardBlackboard', WhiteboardBlackboardCmdString, value, qualifier)

    def __MatchWhiteboardBlackboard(self, match, tag):
        ValueStateValues = {
            '1' : 'Whiteboard',
            '2' : 'Blackboard',
            '0' : 'Off'
        }

        value = ValueStateValues[match.group(1).decode()]
        self.WriteStatus('WhiteboardBlackboard', value, None)

    def __SetHelper(self, command, commandstring, value, qualifier, queryDisallowTime=0):
        self.Send(commandstring)

    def __UpdateHelper(self, command, commandstring, value, qualifier):
        if self.Authenticated in ['User', 'Admin', 'Not Needed']:
            if self.Unidirectional == 'True':
                print('Inappropriate Command ', command)
            else:
                if self.initializationChk:
                    self.OnConnected()
                    self.initializationChk = False

                self.counter = self.counter + 1
                if self.counter > self.connectionCounter and self.connectionFlag:
                    self.OnDisconnected()

                if self.VerboseDisabled:
                    @Wait(1)
                    def SetVerbose():
                        self.Send('w3cv\r\n')
                        self.Send(commandstring)
                else:
                    self.Send(commandstring)
        else:
            print('Inappropriate Command ', command)

    def __MatchError(self, match, tag):
        DEVICE_ERROR_CODES = {
            'E01': "Invalid input channel number (out of range)",
            'E10': "Invalid command",
            'E11': "Invalid preset number",
            'E12': "Invalid output number/port number",
            'E13': "Invalid parameter (out of range)",
            'E14': "Command not available for this configuration",
            'E17': "Invalid command for this signal type",
            'E22': "Busy",
            'E24': "Privilege violation",
            'E25': "Device not present",
            'E26': "Maximum number of connections exceeded",
            'E27': "Invalid event number",
            'E28': "Bad filename/file not found"
        }
        value = match.group(1).decode()
        print(DEVICE_ERROR_CODES.get(value, 'Unrecognized error code: ' + match.group(0).decode()))

    def OnConnected(self):
        self.connectionFlag = True
        self.WriteStatus('ConnectionStatus', 'Connected')
        self.counter = 0

    def OnDisconnected(self):
        self.WriteStatus('ConnectionStatus', 'Disconnected')
        self.connectionFlag = False

        self.Authenticated = 'Not Needed'
        self.PasswdPromptCount = 0

        self.VerboseDisabled = True

    ######################################################
    # RECOMMENDED not to modify the code below this point
    ######################################################

    # Send  Control Commands
    def Set(self, command, value, qualifier=None):
        try:
            getattr(self, 'Set%s' % command)(value, qualifier)
        except AttributeError as e:
            print(command, 'does not support Set. Exception:', e)

    # Send Update Commands
    def Update(self, command, qualifier=None):
        try:
            getattr(self, 'Update%s' % command)(None, qualifier)
        except AttributeError:
            print(command, 'does not support Update.')

    def __ReceiveData(self, interface, data):
        # handling incoming unsolicited data
        self._ReceiveBuffer += data
        compile_list = self._compile_list
        # check incoming data if it matched any expected data from device module
        if self.CheckMatchedString() and len(self._ReceiveBuffer) > 10000:
            self._ReceiveBuffer = b''

    # Add regular expression so that it can be check on incoming data from device.
    def AddMatchString(self, regex_string, callback, arg):
        if regex_string not in self._compile_list:
            self._compile_list[regex_string] = {'callback': callback, 'para': arg}

    # Check incoming unsolicited data to see if it matched with device expectancy.
    def CheckMatchedString(self):
        for regexString in self._compile_list:
            while True:
                result = re.search(regexString, self._ReceiveBuffer)
                if result:
                    self._compile_list[regexString]['callback'](result, self._compile_list[regexString]['para'])
                    self._ReceiveBuffer = self._ReceiveBuffer.replace(result.group(0), b'')
                else:
                    break
        return True

    # This method is to tie a specific command with specific parameter to a call back method
    # when it value is updated. It all setup how often the command to be query, if the command
    # have the update method.
    # interval 0 is for query once, any other integer is used as the query interval.
    # If command doesn't have the update feature then that command is only used for feedback
    def SubscribeStatus(self, command, qualifier, callback):
        Command = self.Commands.get(command)
        if Command:
            if command not in self.Subscription:
                self.Subscription[command] = {'method': {}}

            Subscribe = self.Subscription[command]
            Method = Subscribe['method']

            if qualifier:
                for Parameter in Command['Parameters']:
                    try:
                        Method = Method[qualifier[Parameter]]
                    except:
                        if Parameter in qualifier:
                            Method[qualifier[Parameter]] = {}
                            Method = Method[qualifier[Parameter]]
                        else:
                            return

            Method['callback'] = callback
            Method['qualifier'] = qualifier
        else:
            print(command, 'does not exist in the module')

    # This method is to check the command with new status have a callback method then trigger the callback
    def NewStatus(self, command, value, qualifier):
        if command in self.Subscription:
            Subscribe = self.Subscription[command]
            Method = Subscribe['method']
            Command = self.Commands[command]
            if qualifier:
                for Parameter in Command['Parameters']:
                    try:
                        Method = Method[qualifier[Parameter]]
                    except:
                        break
            if 'callback' in Method and Method['callback']:
                Method['callback'](command, value, qualifier)

    # Save new status to the command
    def WriteStatus(self, command, value, qualifier=None):
        self.counter = 0
        if self.connectionFlag == False:
            self.OnConnected()
        Command = self.Commands[command]
        Status = Command['Status']
        if qualifier:
            for Parameter in Command['Parameters']:
                try:
                    Status = Status[qualifier[Parameter]]
                except KeyError:
                    if Parameter in qualifier:
                        Status[qualifier[Parameter]] = {}
                        Status = Status[qualifier[Parameter]]
                    else:
                        return
        try:
            if Status['Live'] != value:
                Status['Live'] = value
                self.NewStatus(command, value, qualifier)
        except:
            Status['Live'] = value
            self.NewStatus(command, value, qualifier)

    # Read the value from a command.
    def ReadStatus(self, command, qualifier=None):
        print('ReadStatus\ncommand = {}\nqualifier = {}'.format(command, qualifier))
        Command = self.Commands[command]
        print('Command=', Command)
        Status = Command['Status']
        print('Status=', Status)
        if qualifier:
            for Parameter in Command['Parameters']:
                try:
                    Status = Status[qualifier[Parameter]]
                except KeyError:
                    return None
        try:
            return Status['Live']
        except:
            return None


class SerialClass(SerialInterface, DeviceClass):

    def __init__(self, Host, Port, Baud=9600, Data=8, Parity='None', Stop=1, FlowControl='Off', CharDelay=0, Model=None, TouchServerPort=None):
        SerialInterface.__init__(self, Host, Port, Baud, Data, Parity, Stop, FlowControl, CharDelay)
        DeviceClass.__init__(self, TouchServerPort)
        # Check if Model belongs to a subclass
        if len(self.Models) > 0:
            if Model not in self.Models:
                print('Model mismatch')
            else:
                self.Models[Model]()


class EthernetClass(EthernetClientInterface, DeviceClass):

    def __init__(self, Hostname, IPPort, Protocol='TCP', ServicePort=0, Model=None, TouchServerPort=None):
        EthernetClientInterface.__init__(self, Hostname, IPPort, Protocol, ServicePort)
        DeviceClass.__init__(self, TouchServerPort)
        # Check if Model belongs to a subclass
        if len(self.Models) > 0:
            if Model not in self.Models:
                print('Model mismatch')
            else:
                self.Models[Model]()


#Connection handler class ******************************************************
import extronlib
from extronlib.system import File, Wait
import time

debug = False  # Set to false to disable all print statements in this module
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


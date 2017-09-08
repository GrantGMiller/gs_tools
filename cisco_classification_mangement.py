import extronlib

from gs_tools import (
    event,
    File,
    Wait,
    EthernetClientInterface,
)

import re
import time
import json
import datetime

debug = False
if not debug:
    print = lambda *args, **kwargs: None

SANITIZE_JSON = '''\
{
    "Relay": "RLY0",
    "IPStack": "Dual",
    "SystemUnit Name": "Sanitized",
    "DNS": "sanitized.com",
    "DNS Server": "192.168.254.1",
    "IPv4 Address": "192.168.254.254",
    "IPv4 Gateway": "192.168.254.100",
    "IPv4 SubnetMask": "255.255.0.0",
    "IPv4 Assignment": "Static"
}'''

TELNET_HANDSHAKE = b'\xFF\xFB\x18\xFF\xFB\x1F\xFF\xFC\x20\xFF\xFC\x23\xFF\xFB\x27\xFF\xFA\x1F\x00\x50\x00\x19\xFF\xF0\xFF\xFA\x27\x00\xFF\xF0\xFF\xFA\x18\x00\x41\x4E\x53\x49\xFF\xF0\xFF\xFD\x03\xFF\xFB\x01\xFF\xFE\x05\xFF\xFC\x21'


class CiscoClassificationManager:
    def __init__(self, interface, passwordPlainText=None):
        print('CiscoClassificationManager.__init__(interface={}, passwordPlainText={})'.format(interface,
                                                                                               passwordPlainText))

        self._info = {
            'DNS': {
                'query': 'xStatus Network 1 DNS Domain Name\r',
                'set': 'xConfiguration Network 1 DNS Domain Name: "{}"\r',
                'regex': re.compile('\*s Network [0-9] DNS Domain Name: "(.*?)"\r\n'),
                'last rx value': None,
            },
            'DNS Server': {
                'query': 'xStatus Network 1 DNS Server 1 Address\r',
                'set': 'xConfiguration Network 1 DNS Server 1 Address: "{}"\r',
                'regex': re.compile('\*s Network 1 DNS Server 1 Address: "(.*?)"\r\n'),
                'last rx value': None,
            },
            'IPStack': {
                'query': 'xConfiguration Network 1 IPStack\r',
                'set': 'xConfiguration Network 1 IPStack: {}\r',
                'regex': re.compile('\*c xConfiguration Network 1 IPStack: (.*?)\r\n'),
                'last rx value': None,
            },
            'IPv4 Assignment': {
                'query': 'xConfiguration Network 1 IPv4 Assignment\r',
                'set': 'xConfiguration Network 1 IPv4 Assignment: {}\r',
                'regex': re.compile('\*c xConfiguration Network 1 IPv4 Assignment: (.*?)\r\n'),
                'last rx value': None,
            },
            'IPv4 Address': {
                'query': 'xStatus Network 1 IPv4 Address\r',
                'set': 'xConfiguration Network 1 IPv4 Address: "{}"\r',
                'regex': re.compile('\*s Network 1 IPv4 Address: "(.*?)"\r\n'),
                'last rx value': None,
            },
            'IPv4 Gateway': {
                'query': 'xStatus Network 1 IPv4 Gateway\r',
                'set': 'xConfiguration Network 1 IPv4 Gateway: "{}"\r',
                'regex': re.compile('\*s Network 1 IPv4 Gateway: "(.*?)"\r\n'),
                'last rx value': None,
            },
            'IPv4 SubnetMask': {
                'query': 'xStatus Network 1 IPv4 SubnetMask\r',
                'set': 'xConfiguration Network 1 IPv4 SubnetMask: "{}"\r',
                'regex': re.compile('\*s Network 1 IPv4 SubnetMask: "(.*?)"\r\n'),
                'last rx value': None,
            },
            'SystemUnit Name': {
                'query': 'xConfiguration SystemUnit Name\r',
                'set': 'xConfiguration SystemUnit Name: "{}"\r',
                'regex': re.compile('\*c xConfiguration SystemUnit Name: "(.*?)"\r\n'),
                'last rx value': None,
            },
        }

        if passwordPlainText is None:
            self._pw = 'TANDBERG'
        else:
            self._pw = passwordPlainText

        if isinstance(interface, extronlib.interface.SerialInterface):
            self._interface = interface
        elif isinstance(interface, extronlib.interface.EthernetClientInterface):
            # Create a new interface that can work in parallel with the old interface
            self._interface = EthernetClientInterface(interface.IPAddress, interface.IPPort)

        self._buffer = ''
        self._interface_oldRx = self._interface.ReceiveData
        self._interface.ReceiveData = self.__ReceiveData

        self._maxBufferLen = None
        self._CalcMaxBufferLen()

        self._initReaderAlive = self._interface._readerAlive
        self._welcomeReceived = False

    def _CalcMaxBufferLen(self):
        maxLen = 0
        for key in self._info:
            regex = self._info[key]['regex']
            length = len(regex.pattern)
            if length > maxLen:
                maxLen = length

        self._maxBufferLen = 5 * length  # generous, but not infinite

    def _ClearInternalInfo(self):
        for key in self._info:
            self._info[key]['last rx value'] = None

    def _SendAllQueries(self):
        print('CiscoClassificationManager._SendAllQueries()')

        for key in self._info:
            print('Sending query for {}'.format(key))
            self._interface.Send(self._info[key]['query'])

    def Save(self, filePath=None, metaData=None):
        print('CiscoClassificationManager.Save(filePath={}, metaData={})'.format(filePath, metaData))
        if filePath is None:
            nowDT = datetime.datetime.now()
            filePath = 'Autosave_codec_settings_{}'.format(nowDT.strftime('%Y_%m_%d_%I_%M_%S'))

        self._ConnectAndLogin()

        self._SendAllQueries()

        # Wait X seconds for all data to come back
        startTime = time.time()
        while True:
            allDataReceived = True
            for key in self._info.copy():
                if self._info[key]['last rx value'] is None:
                    allDataReceived = False

            if allDataReceived:
                break

            if time.time() - startTime > 10:
                print('Error. Not all data was saved. filePath=', filePath)
                break

        self._WriteData(filePath, metaData)

    def _WriteData(self, filePath, metaData=None):
        # metaData is dict or None
        print('CiscoClassificationManager._WriteData(filePath={}, metaData={})'.format(filePath, metaData))

        if metaData is not None:
            data = metaData
        else:
            data = {}

        for key in self._info:
            data[key] = self._info[key]['last rx value']

        if not File.Exists('/Farm_Network_Profiles'):
            File.MakeDir('/Farm_Network_Profiles')

        with File(filePath, mode='wt') as file:
            file.write(json.dumps(data, indent=4))
            file.close()

        print('Data saved. filePath={}, data={}'.format(filePath, data))

    def _SetFakeValues(self):
        self._ConnectAndLogin()
        for key in self._info:
            self._interface.Send(self._info[key]['set'].format('1.1.1.1'))

    def Sanitize(self):
        print('CiscoClassificationManager.Sanitize')
        # self._interface.Send('xCommand SystemUnit FactoryReset Confirm: Yes\r') #Factory Reset. This will take about 3 minutes

        sanitize_filepath = '/Farm_Network_Profiles/sanitize'

        with File(sanitize_filepath, mode='wt') as file:
            file.write(SANITIZE_JSON)

        self.RestoreFromFile(sanitize_filepath)

        File.DeleteFile(sanitize_filepath)

    def Reboot(self):
        # Note: this takes about 90+ seconds
        print('CiscoClassificationManager.Reboot')
        self._interface.Send('xCommand SystemUnit Boot\r')

    def RestoreFromFile(self, filePath, saveCurrentSettingsFirst=False):
        print('CiscoClassificationManager.RestoreFromFile(filePath={}, saveCurrentSettingsFirst={})'.format(filePath,
                                                                                                            saveCurrentSettingsFirst))

        if saveCurrentSettingsFirst:
            nowDT = datetime.datetime.now()
            filename = 'Autosave_codec_settings_{}'.format(nowDT.strftime('%Y_%m_%d_%I_%M_%S'))
            self.Save(filename)

        self._ConnectAndLogin()

        with File(filePath, mode='rt') as file:
            data = json.loads(file.read())
            file.close()

        for key in data:
            if key in self._info:
                command = self._info[key]['set'].format(data[key])
                self._interface.Send(command)

        time.sleep(10)
        self.Reboot()

        print('Settings restored from file. data={}'.format(data))

    def __ReceiveData(self, interface, data):
        print('CiscoClassificationManager.__ReceiveData(interface={}, data={}'.format(interface, data))

        self._buffer += data.decode(encoding='iso-8859-1')

        # parse for classification data
        for key in self._info:
            # print('Checking for {} info'.format(key))
            # print('self._buffer     =', self._buffer)
            # print('self.regx.pattern=', self._info[key]['regex'].pattern)
            match = self._info[key]['regex'].search(self._buffer)
            if match:
                print('New {} info = "{}"'.format(key, match.group(1)))
                self._info[key]['last rx value'] = match.group(1)
                self._buffer.replace(match.group(0), '')
            else:
                # print('No {} match'.format(key))
                pass

        if '\xFF\xFD\x18\xFF\xFD\x20\xFF\xFD\x23\xFF\xFD\x27' in self._buffer:
            self._buffer = ''
            self._interface.Send(
                '\xFF\xFB\x18\xFF\xFB\x1F\xFF\xFC\x20\xFF\xFC\x23\xFF\xFB\x27\xFF\xFA\x1F\x00\x50\x00\x19\xFF\xF0\xFF\xFA\x27\x00\xFF\xF0\xFF\xFA\x18\x00\x41\x4E\x53\x49\xFF\xF0\xFF\xFD\x03\xFF\xFB\x01\xFF\xFE\x05\xFF\xFC\x21')  # Telnet handshake


        elif 'login:' in self._buffer:
            self._buffer = ''
            self._interface.Send('admin\r')


        elif 'Password:' in self._buffer:
            self._buffer = ''
            self._interface.Send(self._pw + '\r')

        elif 'Welcome' in self._buffer:
            self._welcomeReceived = True

        # clear the buffer if its full of stuff we dont care about
        if len(self._buffer) > self._maxBufferLen:
            self._buffer = ''

        if self._interface_oldRx:
            self._interface_oldRx(interface, data)

    def Del(self):
        print('CiscoClassificationManager.Del')
        self._interface.ReceiveData = self._interface_oldRx
        if isinstance(self._interface, extronlib.interface.EthernetClientInterface):
            self._interface.Disconnect()
        del self

    def GetData(self, filepath):
        try:
            with File(filepath, mode='rt') as file:
                jsonData = file.read()
                dataDict = json.loads(jsonData)
                file.close()
                return dataDict
        except Exception as e:
            print('Error: CiscoClassificationManager.GetData\n', e)

    def _ConnectAndLogin(self):
        print('CiscoClassificationManager._ConnectAndLogin()')
        if isinstance(self._interface, extronlib.interface.EthernetClientInterface):
            self._welcomeReceived = False
            res = self._interface.Connect(10)
            print('res connect=', res)
            if res == 'Connected':
                res = self._interface.SendAndWait(TELNET_HANDSHAKE, 3, deliTag='login:')
                print('res handshake=', res)
                res = self._interface.SendAndWait('admin\r', 3, deliTag='Password:')
                print('res login=', res)

                if self._pw:
                    msg = self._pw.decode() + '\r'
                else:
                    msg = '\r'
                print('msg =', msg)
                res = self._interface.SendAndWait(msg, 3, deliTag='Welcome')
                print('res pw=', res)
                if res:
                    # The login was successful
                    print('Login was successful')
                else:
                    print('Login Fail')
        else:
            print('type(self._interface)=', type(self._interface))




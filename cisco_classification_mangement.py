from gs_tools import (
    event,
    File,
)

import re
import time
import json
import datetime

debug = False
if not debug:
    print = lambda *args, **kwargs: None


class CiscoClassificationManager:
    def __init__(self, interface):
        print('CiscoClassificationManager.__init__(interface={})'.format(interface))

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

        self._interface = interface
        self._buffer = ''
        self._interface_oldRx = self._interface.ReceiveData
        self._interface.ReceiveData = self.__ReceiveData

        self._maxBufferLen = None
        self._CalcMaxBufferLen()

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

    def _GetAllInfo(self):
        for key in self._info:
            print('Sending query for {}'.format(key))
            self._interface.Send(self._info[key]['query'])

    def Save(self, filePath=None, metaData=None):
        print('CiscoClassificationManager.Save(filePath={}, metaData={})'.format(filePath, metaData))

        if filePath is None:
            nowDT = datetime.datetime.now()
            filePath = 'Autosave_codec_settings_{}.json'.format(nowDT.strftime('%Y_%m_%d_%I_%M_%S'))

        self._GetAllInfo()

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

        with File(filePath, mode='wt') as file:
            file.write(json.dumps(data))

        print('Data saved. filePath={}, data={}'.format(filePath, data))

    def Sanitize(self):
        print('CiscoClassificationManager.Sanitize')
        # self._interface.Send('xCommand SystemUnit FactoryReset Confirm: Yes\r')
        self.Reboot()

    def Reboot(self):
        # Note: this takes about 90+ seconds
        print('CiscoClassificationManager.Reboot')
        self._interface.Send('xCommand Boot\r')

    def RestoreFromFile(self, filePath, saveCurrentSettingsFirst=False):
        print('RestoreFromFile(filePath={}, saveCurrentSettingsFirst={})'.format(filePath, saveCurrentSettingsFirst))

        if saveCurrentSettingsFirst:
            nowDT = datetime.datetime.now()
            filename = 'Autosave_codec_settings_{}.json'.format(nowDT.strftime('%Y_%m_%d_%I_%M_%S'))
            self.Save(filename)

        with File(filePath, mode='rt') as file:
            data = json.loads(file.read())

        for key in data:
            if key in self._info:
                command = self._info[key]['set'].format(data[key])
                self._interface.Send(command)

        print('Settings restored from file. data={}'.format(data))

    def __ReceiveData(self, interface, data):
        print('CiscoClassificationManager.__ReceiveData(interface={}, data={}'.format(interface, data))

        self._buffer += data.decode()

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

        # clear the buffer if its full of stuff we dont care about
        if len(self._buffer) > self._maxBufferLen:
            self._buffer = ''

        if self._interface_oldRx:
            self._interface_oldRx(interface, data)

    def Del(self):
        print('CiscoClassificationManager.Del')
        self._interface.ReceiveData = self._interface_oldRx
        del self

    def GetData(self, filepath):
        try:
            with File(filepath, mode='rt') as file:
                jsonData = file.read()
                dataDict = json.loads(jsonData)
                return dataDict
        except Exception as e:
            print('Error: CiscoClassificationManager.GetData\n', e)




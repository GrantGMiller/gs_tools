'''
This module is meant to be a collection of tools to simplify common task in AV control systems.
Started: March 28, 2017 and appended to continuously
'''

import extronlib
from extronlib import event
from extronlib.device import ProcessorDevice, UIDevice
from extronlib.system import Wait, ProgramLog, File
from extronlib.interface import EthernetServerInterfaceEx

try:
    import aes_tools
except:
    pass

import json
import time
import hashlib
import datetime
import calendar
import re
import random

# Set this false to disable all print statements ********************************
debug = True
if not debug:
    # Disable print statements
    print = lambda *args, **kwargs: None


# Helpful functions *************************************************************
def ShortenText(text, MaxLength=7, LineNums=2):
    text = text.replace('Lectern', 'Lect')
    text = text.replace('Quantum', 'Qtm')
    text = text.replace('Projector', 'Proj')
    text = text.replace('Confidence', 'Conf')
    text = text.replace('Monitor', 'Mon')
    text = text.replace('Left', 'L')
    text = text.replace('Right', 'R')
    text = text.replace('Program', 'Pgm')
    text = text.replace('Annotator', 'Antr')
    text = text.replace('Preview', 'Prev')
    text = text.replace('From', 'Frm')
    text = text.replace('Display', 'Disp')
    text = text.replace('Audio', 'Aud')
    text = text.replace('Wireless', 'Wless')
    text = text.replace('Handheld', 'HH')
    text = text.replace('Display', 'Disp')
    text = text.replace('Floorbox', 'FlrBx')
    text = text.replace('Laptop', 'Lap')

    if len(text) > MaxLength:
        text = text[:MaxLength * LineNums]
        textSplit = text.split()
        if len(textSplit) > 0:
            NewText = ''
            while True:
                if len(textSplit) > 0:
                    if len(NewText) + len(' ') + len(textSplit[0]) <= MaxLength:
                        NewText += ' ' + textSplit.pop(0)
                    else:
                        break
                else:
                    break
            NewText += '\n'
            NewText += ' '.join(textSplit)
            text = NewText

    return text


def PrintProgramLog():
    """usage:
   print = PrintProgramLog()
   """

    def print(*args, sep=' ', end='\n', severity='info',
              **kwargs):  # override the print function to write to program log instead
        # Following is done to emulate behavior Python's print keyword arguments
        # (ie. you can set the arguments to None and it will do the default behavior)
        if sep is None:
            sep = ' '

        if end is None:
            end = '\n'

        string = []
        for arg in args:
            string.append(str(arg))
        ProgramLog(sep.join(string) + end, severity)

    return print


RemoteTraceServer = None


def RemoteTrace(IPPort=1024):
    '''
    This function return a new print function that will print to stdout and also send to any clients connected to the server defined on port IPPort
    For example:
        print = RemoteTrace()
    :param IPPort: int
    :return:
    '''
    global RemoteTraceServer

    # Start a new server
    if RemoteTraceServer == None:
        RemoteTraceServer = EthernetServerInterfaceEx(IPPort)

        @event(RemoteTraceServer, ['Connected', 'Disconnected'])
        def RemoteTraceServerConnectEvent(client, state):
            print('Client {}:{} {}'.format(client.IPAddress, client.ServicePort, state))

        result = RemoteTraceServer.StartListen()
        ProgramLog('RemoteTraceServer {}'.format(result), 'info')

    def NewPrint(*args):  # override the print function to write to program log instead
        string = '\r\n' + str(time.time()) + ': ' + ' '.join(str(arg) for arg in args)

        for client in RemoteTraceServer.Clients:
            client.Send(string + '\r\n')
            # ProgramLog(string, 'info')

    return NewPrint


def ToPercent(Value, Min=0, Max=100):
    '''
    This function will take the Value, Min and Max and return a percentage
    :param Value: float
    :param Min: float
    :param Max: float
    :return: float from 0.0 to 100.0
    '''
    try:
        if Value < Min:
            return 0
        elif Value > Max:
            return 100

        TotalRange = Max - Min
        # print('TotalRange=', TotalRange)

        FromMinToValue = Value - Min
        # print('FromMinToValue=', FromMinToValue)

        Percent = (FromMinToValue / TotalRange) * 100

        return Percent
    except Exception as e:
        # print(e)
        # ProgramLog('gs_tools ToPercent Erorr: {}'.format(e), 'error')
        return 0


def IncrementIP(IP):
    '''
    This function will take an IP and increment it by one.
    For example: IP='192.168.254.255' will return '192.168.255.0'
    :param IP: str like '192.168.254.254'
    :return: str like '192.168.254.255'
    '''
    IPsplit = IP.split('.')

    Oct1 = int(IPsplit[0])
    Oct2 = int(IPsplit[1])
    Oct3 = int(IPsplit[2])
    Oct4 = int(IPsplit[3])

    Oct4 += 1
    if Oct4 > 255:
        Oct4 = 0
        Oct3 += 1
        if Oct3 > 255:
            Oct3 = 0
            Oct2 += 1
            if Oct2 > 255:
                Oct2 = 0
                Oct1 += 1
                if Oct1 > 255:
                    Oct1 = 0

    return '{}.{}.{}.{}'.format(Oct1, Oct2, Oct3, Oct4)


def IsValidIPv4(ip):
    '''
    Returns True if ip is a valid IPv4 IP like '192.168.254.254'
    Example '192.168.254.254' > return True
    Example '192.168.254.300' > return False
    :param ip: str like '192.168.254.254'
    :return: bool
    '''
    ip_split = ip.split('.')
    if len(ip_split) != 4:
        return False

    for octet in ip_split:
        try:
            octet_int = int(octet)
            if not 0 <= octet_int <= 255:
                return False
        except:
            return False

    return True


def GetKeyFromValue(d, v):
    '''
    This function does a "reverse-lookup" in a dictionary.
    You give this function a value and it returns the key
    :param d: dictionary
    :param v: value within d
    :return: first key from d that has the value == v. If v is not found in v, return None
    '''
    for k in d:
        if d[k] == v:
            return k


def PhoneFormat(n):
    '''
    This function formats a string like a phone number
    Example: '8006339876' > '800-633-9876'
    :param n:
    :return:
    '''
    try:
        n = StripNonNumbers(n)
        return format(int(n[:-1]), ",").replace(",", "-") + n[-1]
    except:
        return n


def StripNonNumbers(s):
    new_s = ''
    for ch in s:
        if ch.isdigit():
            new_s += ch
    return new_s


# Non-global variables **********************************************************
class NonGlobal:
    '''
    This class could be replaced by global vars, but this class makes the management and readability better
    values will be lost upon power-cycle or re-upload
    '''

    def Set(self, name_of_value_str, value):
        setattr(self, name_of_value_str, value)

    def Get(self, name_of_value_str):
        return getattr(self, name_of_value_str)


# Hash function *****************************************************************
def HashIt(string=''):
    '''
    This function takes in a string and converts it to a unique hash.
    Note: this is a one-way conversion. The value cannot be converted from hash to the original string
    :param string:
    :return: str
    '''
    arbitrary_string = 'gs_tools_arbitrary_string'
    string += arbitrary_string
    return hashlib.sha512(bytes(string, 'utf-8')).hexdigest()


def GetRandomPassword(length=512):
    pw = ''
    for i in range(length):
        ch = random.choice(['1', '2', '3', '4', '5', '6', '7', '8', '9', '0',
                            'a', 'b', 'c', 'd', 'f'])
        pw += ch
    return pw


def GetDatetimeKwargs(dt):
    '''
    This converts a datetime.datetime object to a dict.
    This is useful for saving a datetime.datetime object as a json string
    :param dt: datetime.datetime
    :return: dict
    '''
    d = {'year': dt.year,
         'month': dt.month,
         'day': dt.day,
         'hour': dt.hour,
         'minute': dt.minute,
         'second': dt.second,
         'microsecond': dt.microsecond,
         }
    return d


def StringToBytes(text):
    return list(ord(c) for c in text)


def BytesToString(binary):
    return "".join(chr(b) for b in binary)


def BytesToInt(b):
    return int.from_bytes(b, byteorder='big')


# Processor port map ************************************************************

PROCESSOR_CAPABILITIES = {
    # 'Part Number': {'Serial Ports': 8, 'IR/S Ports': 8, 'Digital Inputs...
}
PROCESSOR_CAPABILITIES['60-1418-01'] = {  # IPCP Pro 550
    'Serial Ports': 8,
    'IR/S Ports': 8,
    'Digital I/Os': 0,
    'FLEX I/Os': 4,
    'Relays': 8,
    'Power Ports': 4,
    'eBus': True,
}

PROCESSOR_CAPABILITIES['60-1412-01'] = {  # IPL Pro S1
    'Serial Ports': 1,
    'IR/S Ports': 0,
    'Digital I/Os': 0,
    'FLEX I/Os': 0,
    'Relays': 0,
    'Power Ports': 0,
    'eBus': False,
    'Contact': 0,
}
PROCESSOR_CAPABILITIES['60-1413-01'] = {  # IPL Pro S3
    'Serial Ports': 3,
    'IR/S Ports': 0,
    'Digital I/Os': 0,
    'FLEX I/Os': 0,
    'Relays': 0,
    'Power Ports': 0,
    'eBus': False,
}
PROCESSOR_CAPABILITIES['60-1416-01'] = {  # IPL Pro CR88
    'Serial Ports': 0,
    'IR/S Ports': 0,
    'Digital I/Os': 0,
    'FLEX I/Os': 0,
    'Relays': 8,
    'Power Ports': 0,
    'eBus': False,
    'Contact': 8,
}

PROCESSOR_CAPABILITIES['60-1429-01'] = {  # IPCP Pro 250
    'Serial Ports': 2,
    'IR/S Ports': 1,
    'Digital I/Os': 4,
    'FLEX I/Os': 0,
    'Relays': 2,
    'Power Ports': 0,
    'eBus': True,
    'Contact': 0,
}

PROCESSOR_CAPABILITIES['60-1417-01'] = {  # IPCP Pro 350
    'Serial Ports': 3,
    'IR/S Ports': 2,
    'Digital I/Os': 4,
    'FLEX I/Os': 0,
    'Relays': 4,
    'Power Ports': 0,
    'eBus': True,
    'Contact': 0,
}

print('End  GST')


def ConvertDictToTupTup(d):
    # Converts a dict to a tuple of tuples.
    # This is hashable and can be used as a dict key unlike a regular dict()
    if d is None:
        return (None, None)
    else:
        return tuple(d.items())


def GetWeekOfMonth(dt):
    weeks = calendar.monthcalendar(dt.year, dt.month)
    for index, week in enumerate(weeks):
        if dt.day in week:
            return index + 1

global lastTime
lastTime = time.time()
def PrintTimeDiff(tag=None):
    global lastTime
    nowTime = time.time()
    diff = nowTime - lastTime
    if tag is not None:
        print('tag={}, TimeDiff={}'.format(tag, round(diff, 2)))
    else:
        print('TimeDiff={}'.format(round(diff, 2)))
    lastTime = nowTime

timeItLog = {
    #'Func name': float(avgTime)
}
class TimeIt:
    def __call__(self, func):
        print('TimeIt.__call__ func={}'.format(func))
        def NewFunc(*args, **kwargs):
            startTime = time.time()
            func(*args, **kwargs)
            total = time.time() - startTime
            print('TimeIt: It took {} seconds to execute {}(args={}, kwargs={})'.format(
                round(total, 2),
                func.__name__,
                args,
                kwargs,
            ))

            name = func.__name__
            if name not in timeItLog:
                timeItLog[name] = total
            else:
                lastTime = timeItLog[name]
                avgTime = (lastTime + total)/2
                timeItLog[name] = avgTime

        return NewFunc

def WriteTimeItFile():
    with File('TimeIt.log', mode='wt') as file:
        times = list(timeItLog.values())
        times.sort()
        times.reverse()
        #print('times=', times)
        sortedTimes = times #from slowest to fastest

        for t in sortedTimes:
            name = GetKeyFromValue(timeItLog, t)
            #print('name=', name)
            file.write('FunctionName="{}", ExecutionTime= {} seconds\n'.format(name, t))

def Loop(t, func):
    #Call the func every t seconds
    @Wait(0)
    def Loop():
        while True:
            time.sleep(t)
            func()

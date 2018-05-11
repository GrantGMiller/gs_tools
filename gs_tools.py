'''
This module is meant to be a collection of tools to simplify common task in AV control systems.
Started: March 28, 2017 and appended to continuously
'''

from extronlib import event
from extronlib.system import ProgramLog, File
from extronlib.interface import EthernetServerInterfaceEx

try:
    from extronlib_pro import Wait
except:
    from extronlib.system import Wait

try:
    import aes_tools
except:
    pass

import time
import hashlib
import calendar
import random
import json
import itertools
import re
import operator

# Set this false to disable all print statements ********************************
debug = False
oldPrint = print
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
        try:
            oldPrint(*args)
            string = '\r\n' + str(time.time()) + ': ' + ' '.join(str(arg) for arg in args)

            for client in RemoteTraceServer.Clients:
                client.Send(string + '\r\n')
                # ProgramLog(string, 'info')
        except Exception as e:
            ProgramLog(str(e), 'error')

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


def IsValidEmail(email):
    if len(email) > 7:
        if re.match(".+\@.+\..+", email) != None:
            return True
        return False


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
def HashIt(string='', salt='gs_tools_arbitrary_string'):
    '''
    This function takes in a string and converts it to a unique hash.
    Note: this is a one-way conversion. The value cannot be converted from hash to the original string
    :param string:
    :return: str
    '''
    salt = 'gs_tools_arbitrary_string'
    hash1 = hashlib.sha512(bytes(string, 'utf-8')).hexdigest()
    hash1 += salt
    hash2 = hashlib.sha512(bytes(hash1, 'utf-8')).hexdigest()
    return hash2


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
    # 'hello world' > [104, 101, 108, 108, 111, 32, 119, 111, 114, 108, 100]
    return bytes(list(ord(c) for c in text))


def BytesToString(binary):
    # b'hello world' > hello world
    return "".join(chr(b) for b in binary)


def BytesToInt(b):
    # b'hello world' > 126207244316550804821666916
    return int.from_bytes(b, byteorder='big')


def HexIntToChr(hexInt):
    # 22 > '\"'
    return bytes.fromhex(str(hexInt)).decode()


def Unquote(s):
    # Replaces urlencoded values like '%20' with ' '
    ret = ''
    skip = 0
    for index, ch in enumerate(s):
        if skip > 0:
            skip -= 1
            continue

        if ch == '%' and \
                index < len(s) + 2 and \
                s[index + 1] != '%' and \
                s[index - 1] != '%':
            h = s[index + 1:index + 3]
            print('h=', h)
            try:
                newCH = chr(int(h, 16))
                ret += newCH
                skip = 2
            except:
                ret += ch
        else:
            ret += ch
    return ret.replace('%%', '%')


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


def ConvertDictToTupTup(d):
    # Converts a dict to a tuple of tuples.
    # This is hashable and can be used as a dict key unlike a regular dict()
    if d is None:
        return (None, None)
    else:
        # Sort the dict to make sure two dict with different orders, but same info return the same
        sortedListOfTup = sorted(d.items(), key=operator.itemgetter(1))
        return tuple(sortedListOfTup)


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
    # 'Func name': float(avgTime)
}


class TimeIt:
    def __call__(self, func):
        print('TimeIt.__call__ func={}'.format(func))

        def NewFunc(*args, **kwargs):
            startTime = time.time()
            ret = func(*args, **kwargs)
            total = time.time() - startTime
            print('TimeIt: It took {} seconds to execute {}(args={}, kwargs={})'.format(
                round(total, 2),
                func.__name__,
                args,
                kwargs,
            ))

            name = '{}.{}'.format(func.__module__, func.__name__)
            if name not in timeItLog:
                timeItLog[name] = total
            else:
                lastTime = timeItLog[name]
                avgTime = (lastTime + total) / 2
                timeItLog[name] = avgTime

            return ret

        return NewFunc


def WriteTimeItFile():
    with File('TimeIt.log', mode='wt') as file:
        times = list(timeItLog.values())
        times.sort()
        times.reverse()
        # print('times=', times)
        sortedTimes = times  # from slowest to fastest

        longestName = None
        for name in timeItLog.keys():
            if longestName is None or len(name) > len(longestName):
                longestName = name

        for t in sortedTimes:
            name = GetKeyFromValue(timeItLog, t)
            name = name.rjust(len(longestName), ' ')
            # print('name=', name)
            file.write('FunctionName="{}", ExecutionTime= {} seconds\n'.format(name, t))


def Loop(t, func):
    # Call the func every t seconds, forever
    @Wait(0)
    def Loop():
        while True:
            time.sleep(t)
            func()


class PrintFunc:
    '''
    This will print the function and its arguments every time it is called

    This needs to go on top of the function like this
    @event(myBtn, 'Pressed')
    @PrintFunc()
    def MyBtnEvent(button, state):
        pass
    '''

    def __call__(self, func):
        # oldPrint('PrintFunc(func={})'.format(func))
        def NewFunc(*args, **kwargs):
            ret = func(*args, **kwargs)
            oldPrint('{}(args={}, kwargs={}) return {}'.format(func.__name__, args, kwargs, ret))
            return ret

        return NewFunc


def GetUTCOffset():
    offsetSeconds = time.timezone if (time.localtime().tm_isdst == 0) else time.altzone
    MY_TIME_ZONE = offsetSeconds / 60 / 60 * -1
    return MY_TIME_ZONE  # returns an int like -5 for EST


def pprint(*args):
    # Realized that from pprint import pprint works in GS too :-)
    # This one accepts multiple arguments, so u pick.
    print('\r\n'.join([json.dumps(item, indent=2) for item in args]))


def GetAllCombos(list1, list2):
    # Returns all possible combinations of these two list
    # Example GetAllCombos([1,2,3], [4,5,6])
    # >>> [(1, 4), (1, 5), (1, 6), (2, 4), (2, 5), (2, 6), (3, 4), (3, 5), (3, 6)]
    ret = []
    for x in itertools.permutations(list1, len(list2)):
        for y in zip(x, list2):
            if y not in ret:
                ret.append(y)
    ret.sort()
    return ret


def GetOpposite(side):
    return {
        'Left': 'Right',
        'Right': 'Left',
        'Up': 'Down',
        'Down': 'Up',
    }[side]


class HashableDict(dict):
    def __key(self):
        return tuple((k, self[k]) for k in sorted(self))

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        return self.__key() == other.__key()

def MoveListItem(l, item, units):
    #units is an pos/neg integer (negative it to the left)
    '''
    Exampe;
    l = ['a', 'b', 'c', 'X', 'd', 'e', 'f','g']
    MoveListItem(l, 'X', -2)
    >>> l= ['a', 'X', 'b', 'c', 'd', 'e', 'f', 'g']

    l = ['a', 'b', 'c', 'X', 'd', 'e', 'f','g']
    MoveListItem(l, 'X', -2)
    >>> l= ['a', 'b', 'c', 'd', 'e', 'X', 'f', 'g']

    '''
    l = l.copy()
    currentIndex = l.index(item)
    l.remove(item)
    l.insert(currentIndex + units, item)

    return l

def ModIndexLoop(num, min_, max_):
    '''
    Examples:
        ModIndexLoop(-10, -3, 3) >>> -3
        ModIndexLoop(-9, -3, 3) >>> -2
        ModIndexLoop(-8, -3, 3) >>> -1
        ModIndexLoop(-7, -3, 3) >>> 0
        ModIndexLoop(-6, -3, 3) >>> 1
        ModIndexLoop(-5, -3, 3) >>> 2
        ModIndexLoop(-4, -3, 3) >>> 3
        ModIndexLoop(-3, -3, 3) >>> -3
        ModIndexLoop(-2, -3, 3) >>> -2
        ModIndexLoop(-1, -3, 3) >>> -1
        ModIndexLoop(0, -3, 3) >>> 0
        ModIndexLoop(1, -3, 3) >>> 1
        ModIndexLoop(2, -3, 3) >>> 2
        ModIndexLoop(3, -3, 3) >>> 3
        ModIndexLoop(4, -3, 3) >>> -3
        ModIndexLoop(5, -3, 3) >>> -2
        ModIndexLoop(6, -3, 3) >>> -1
        ModIndexLoop(7, -3, 3) >>> 0
        ModIndexLoop(8, -3, 3) >>> 1
        ModIndexLoop(9, -3, 3) >>> 2
        ModIndexLoop(10, -3, 3) >>> 3
    '''
    #print('\nMod(num={}, min_={}, max_={})'.format(num, min_, max_))
    maxMinDiff = max_ - min_ + 1 # +1 to include min_
    #print('maxMinDiff=', maxMinDiff)

    minToNum = num - min_
    #print('minToNum=', minToNum)

    if minToNum == 0:
        return min_

    mod = minToNum % maxMinDiff
    #print('mod=', mod)

    return min_ + mod
'''
This module is meant to be a collection of tools to simplify common task in AV control systems.
Started: March 28, 2017 and appended to continuously
'''

try:
    from extronlib import event
    from extronlib.system import ProgramLog, File
    from extronlib.interface import EthernetServerInterfaceEx
except Exception as e:
    print(e)

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
import datetime
import uuid

# Set this false to disable all print statements ********************************
debug = False

oldPrint = print
if debug is False:
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
            string = '\r\n' + str(time.monotonic()) + ': ' + ' '.join(str(arg) for arg in args)

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


def StripNonHex(string):
    ret = ''
    for c in string.upper():
        if c in '0123456789ABCDEF':
            ret += c
    return ret


def MACFormat(macString):
    # macString can be any string like 'aabbccddeeff'

    macString = StripNonHex(macString)
    while len(macString) < 12:
        macString = '0' + macString

    return '-'.join([macString[i: i + 2] for i in range(0, len(macString), 2)])


def GetMac():
    from uuid import getnode as get_mac
    mac = hex(get_mac())
    return MACFormat(mac)


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


def GetUniqueMachineID():
    return HashIt(GetMac())


def GetRandomHash():
    return HashIt(GetRandomPassword())


def HashIt(string='', salt=None):
    '''
    This function takes in a string and converts it to a unique hash.
    Note: this is a one-way conversion. The value cannot be converted from hash to the original string
    :param string: string, if None a random hash will be returned
    :return: str
    '''
    if salt is None:
        salt = str(uuid.uuid1()) + str(uuid.uuid4())

    if string is None:
        # if None a random hash will be returned
        string = GetRandomPassword()

    if not isinstance(string, str):
        string = str(string)

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
PROCESSOR_CAPABILITIES['60-1413-01'] = {  # IPL Pro S3
    'Serial Ports': 3,
    'IR/S Ports': 0,
    'Digital I/Os': 0,
    'FLEX I/Os': 0,
    'Relays': 0,
    'Power Ports': 0,
    'eBus': False,
}
PROCESSOR_CAPABILITIES['60-1414-01'] = {  # IPL Pro CR88
    'Serial Ports': 6,
    'IR/S Ports': 0,
    'Digital I/Os': 0,
    'FLEX I/Os': 0,
    'Relays': 0,
    'Power Ports': 0,
    'eBus': False,
    'Contact': 0,
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
    print('448 ConvertDictToTupTup', d)
    if d is None:
        return None
    else:
        return HashableDict(d)


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
        def NewFunc(*a, **k):
            ret = func(*a, **k)
            oldPrint('{}(args={}, kwargs={}) return {}'.format(func.__name__, a, k, ret))
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
    def __new__(cls, item={}):
        # oldPrint('item=', item)
        if item is None:
            return None
        else:
            return super().__new__(cls, item)

    def __key(self):
        return tuple((k, self[k]) for k in sorted(self))

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        if isinstance(other, HashableDict):
            return self.__key() == other.__key()
        else:
            return False

    # def __setitem__(self, key, value):
    #     oldPrint('setitem', key, value)

    def __contains__(self, other):
        # return true if the self key/value pairs in exists in other
        if isinstance(other, str):
            return other in self.keys()
        else:
            for key, value in other.items():
                try:
                    if self[key] != other[key]:
                        return False
                    else:
                        continue
                except:
                    return False

            return True

    def __add__(self, other):
        # Other will take precedence if duplicate keys in self/other
        retD = self.copy()
        for key, value in other.items():
            retD[key] = value

        return HashableDict(retD)


def MoveListItem(l, item, units):
    # units is an pos/neg integer (negative it to the left)
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
    # print('\nMod(num={}, min_={}, max_={})'.format(num, min_, max_))
    maxMinDiff = max_ - min_ + 1  # +1 to include min_
    # print('maxMinDiff=', maxMinDiff)

    minToNum = num - min_
    # print('minToNum=', minToNum)

    if minToNum == 0:
        return min_

    mod = minToNum % maxMinDiff
    # print('mod=', mod)

    return min_ + mod


def DecodeLiteral(string):
    return string.decode(encoding='iso-8859-1')


def EncodeLiteral(string):
    return string.encode(encoding='iso-8859-1')


class Dummy:
    def __setattr__(self, *a, **k):
        print('Dummy __setattr__', a, k)

    def __getattr__(self, *a, **k):
        print('Dummy __setattr__', a, k)
        return self._fakeMethod

    def _fakeMethod(self, *a, **k):
        print('Dummy _fakeMethod', a, k)


def ListHasDuplicates(l):
    return len(l) != len(set(l))


def ListIsAllSame(l):
    # each element of the list is the same
    return len(set(l)) == 1


def _TupleSubtract(tup1, tup2):
    # assumes tups are same length
    # example:
    # newDT = (2018, 6, 22, 4, 17, 1, 43, 0)
    # oldDT = (2018, 6, 22, 4, 16, 33, 7, 829)
    # diff = _TupleSubtract(newDT, oldDT)
    # diff = (0, 0, 0, 0, 1, -32, 36, -829)
    ret = []
    for i in range(len(tup1)):
        ret.append(tup1[i] - tup2[i])
    return tuple(ret)


def _TupleAdd(tup1, tup2):
    ret = []
    for i in range(len(tup1)):
        ret.append(tup1[i] + tup2[i])
    return tuple(ret)


def _AdjustTimeTuple(tup):
    # example                          #7
    # tup = (0, 0, 0, 0, 1, -32, 36, -829)
    # return (0, 0, 0, 0, 0, 8, 35, 171)
    ret = list(tup)

    while ret[7] < 0:  # milis
        ret[6] -= 1
        ret[7] += 1000

    while ret[6] < 0:  # seconds
        ret[5] -= 1
        ret[6] += 60

    while ret[5] < 0:  # min
        ret[4] -= 1
        ret[5] += 60

    while ret[4] < 0:  # hour
        ret[2] -= 1
        ret[4] += 24

    while ret[2] < 0:  # days
        oldMonth = ret[1]
        ret[1] -= 1
        ret[2] += _DaysInMonth(oldMonth, ret[0])

    while ret[1] < 0:  # month
        ret[0] -= 1
        ret[1] += 12

    # ill assume year is > 0
    return tuple(ret)


def _DaysInMonth(month, year):
    return 30 if month in (9, 4, 6, 11) else 31 if month != 2 else 29 if year % 4 is 0 else 28


def _Datetime2seconds(tup):
    # months with 30 days = [9,4,6,11]
    # months with 31 days = [1,3,5,7,8,10,12]
    # feb /leap year
    daysInMonth = _DaysInMonth(tup[1], tup[0])
    seconds = 0
    seconds += tup[0] * 60 * 60 * 24 * 365  # years
    seconds += tup[1] * 60 * 60 * 24 * daysInMonth  # months
    seconds += tup[2] * 60 * 60 * 24  # days
    seconds += tup[4] * 60 * 60  # hours
    seconds += tup[5] * 60  # minutes
    seconds += tup[6]
    seconds += tup[7] / 1000
    return seconds


def _CalcDrift():
    # returns drift as float() in seconds/second
    # example drift = 1 means every real 1 second = 1 seconds in RTC (Ideal)
    # drift = 1.0833 means 1 real second = 1.0833 RTC seconds (real world measurement)

    lastNTPDT = PV().Get('LastNTPdatetime', mach.RTC().datetime())
    print()
    last2OldDT = _TupleSubtract(mach.RTC().datetime(), lastNTPDT)
    ntp.settime()
    last2NewDT = _TupleSubtract(mach.RTC().datetime(), lastNTPDT)
    driftTup = _TupleSubtract(last2NewDT, last2OldDT)
    driftSeconds = _Datetime2seconds(driftTup)
    totalSeconds = _Datetime2seconds(last2NewDT)
    if driftSeconds == 0:
        driftPerSecond = 0
    else:
        driftPerSecond = totalSeconds / driftSeconds
    return driftPerSecond


def FormatTimeAgo(dt):
    print('58 FormatTimeAgo(', dt)
    utcNowDt = datetime.datetime.now()
    delta = utcNowDt - dt
    print('61 delta=', delta)

    if delta < datetime.timedelta(days=1):
        print('less than 1 day ago')
        if delta < datetime.timedelta(hours=1):
            print('less than 1 hour ago, show "X minutes ago"')
            if delta.total_seconds() < 60:
                # print('return <1 min ago')
                ret = '< 1 min ago'
                print('70 ret=', ret)
                return ret
            else:
                minsAgo = delta.total_seconds() / 60
                minsAgo = int(minsAgo)
                ret = '{} min{} ago'.format(
                    minsAgo,
                    's' if minsAgo > 1 else '',
                )
                print('77 ret=', ret)
                return ret
        else:
            # between 1hour and 24 hours ago
            hoursAgo = delta.total_seconds() / (60 * 60)
            hoursAgo = int(hoursAgo)
            ret = '{} hour{} ago'.format(
                hoursAgo,
                's' if hoursAgo > 1 else '',
            )
            print('89 ret=', ret)
            return ret
    else:
        print('more than 1 day ago')
        daysAgo = delta.total_seconds() / (60 * 60 * 24 * 1)
        daysAgo = int(daysAgo)
        ret = '{} day{} ago'.format(
            daysAgo,
            's' if daysAgo > 1 else '',
        )
        print('99 ret=', ret)
        return ret

from extronlib.system import Clock


class ScheduleManager():
    CallbackDict = {
        # ClockObject: {
        # 'Function': functionObject,
        # 'args': args,
        # 'kwargs': kwargs
        # }
    }

    def __init__(self):
        self.Clocks = []

    def Add(self, days, times, func, *args, **kwargs):
        # day > string or list of strings like 'Monday', 'Tuesday'; 'Everyday' also accepted
        # times > string like '8:00PM' or '20:00:00'
        # func > callback function to call at time and day
        # *args > arguments to pass to callback function
        # **kwargs > keyword arguments to pass to callback function

        print('ScheduleManager.Add({},{})'.format(args, kwargs))

        # Determine the day(s)
        Days = []

        if days == 'Everyday':
            for DayKey in Clock.WEEKDAYS:  # Clock.WEEKDAYS = {'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 'Thursday': 3, 'Friday': 4, 'Saturday': 5, 'Sunday': 6}
                Days.append(DayKey)

        else: #days is prob a list already
            Days = days

        # Determine the time(s)
        Times = []
        if not isinstance(times, list):
            times = [times]

        for time in times:
            if ('AM' in time or
                        'PM' in time):

                timeSplit = time.split(':')
                hour = timeSplit[0].replace('AM', '').replace('PM', '')
                minute = timeSplit[1].replace('AM', '').replace('PM', '')
                if len(timeSplit) == 3:
                    second = timeSplit[2].replace('AM', '').replace('PM', '')
                else:
                    second = '00'

                if 'PM' in time:
                    hour = int(hour) + 12

                # format time
                if int(hour) < 10:
                    hour = '0' + str(int(hour))

                if int(minute) < 10:
                    minute = '0' + str(int(minute))

                if int(second) < 10:
                    second = '0' + str(int(second))

                time = '{}:{}:{}'.format(hour, minute, second)

            Times.append(time)

        # Create the clock
        NewClock = Clock(Times, Days, self._ClockCallback)
        NewClock.Enable()
        self.Clocks.append(NewClock)

        self.CallbackDict[NewClock] = {
            'Function': func,
            'args': args,
            'kwargs': kwargs
            }

        return NewClock

    #TODO - add a way to modify an existing schedule

    def _ClockCallback(self, clock, dt):
        func = self.CallbackDict[clock]['Function']
        args = self.CallbackDict[clock]['args']
        kwargs = self.CallbackDict[clock]['kwargs']

        if not args == ():
            if not kwargs == {}:
                func(*args, **kwargs)
            else:
                func(*args)
        else:
            if not kwargs == {}:
                func(**kwargs)
            else:
                func()


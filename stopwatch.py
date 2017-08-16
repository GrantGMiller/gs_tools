from extronlib.system import Wait

import datetime

debug = True
if not debug:
    print = lambda *a, **k: None #Disable print statements

class StopWatch:
    def __init__(self, lblFeedback):
        self._lblFeedback = lblFeedback
        self._lblFeedback.SetText('--:--:--')

        self._totalSeconds = 0
        self._startDT = None
        self._wait = None

    def Start(self):
        print('StopWatch.Start()')
        self._lblFeedback.SetText('0:00:00')
        self._wait = Wait(1, self._Increment)

    def _Increment(self):
        print('StopWatch._Increment()')
        self._totalSeconds += 1

        delta = datetime.timedelta(seconds=self._totalSeconds)
        self._lblFeedback.SetText(str(delta))

        if self._wait is not None:
            self._wait.Restart()

    def Stop(self):
        print('StopWatch.Stop()')
        if self._wait:
            self._wait.Cancel()

    def Clear(self):
        print('StopWatch.Clear()')
        if self._wait is not None:
            self._wait.Cancel()
            self._wait = None
        self._lblFeedback.SetText('--:--:--')
        self._totalSeconds = 0

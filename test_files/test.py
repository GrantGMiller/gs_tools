from gs_tools import TimeIt, WriteTimeItFile
import time

@TimeIt()
def TestFunc(arg1, arg2, keyarg1=1, keyarg2=2):
    time.sleep(1)
    print('arg1={}, arg2={}, keyarg1={}, keyarg2={}'.format(arg1, arg2, keyarg1, keyarg2))

TestFunc(3,4)
WriteTimeItFile()
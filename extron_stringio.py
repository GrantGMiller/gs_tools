'''
This module emulates the behavior of the os.StringIO python module which has
been disallowed by GS firmware.
'''
import extronlib.system


class StringIO(extronlib.system.File):
    Counter = 0

    def __init__(self, *args, **kwargs):
        self.Counter += 1
        self.TempFileName = 'grant_io_stringio_' + str(self.Counter) + '.txt'
        extronlib.system.File.__init__(self, self.TempFileName, mode='wt')

    def getvalue(self):
        self.close()
        dupFile = extronlib.system.File(self.TempFileName)
        dupText = dupFile.read()
        dupFile.close()
        dupText = str(dupText)

        # print(self.TempFileName, 'dupText=', dupText)
        self = extronlib.system.File.__init__(self, self.TempFileName, mode='at')

        return dupText


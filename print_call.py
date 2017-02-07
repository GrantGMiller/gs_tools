""" Decorator for enabling print of a function and writing a log file of when 
the function is executed.
"""
from extronlib.system import File
import time

# in the case of
# @event(btnShowShutDown, 'Pressed')
# @PrintCall.Single() # or Separate
# @event(btnShowShutDown, 'Released')
# the function name is returned as "wrapper" due to the Released decoration occurring before PrintCall decoration
# this may be solved if "event" includes wrapper.__name__ = original_function.__name__
# Ideally, PrintCall is the first decorator invoked (ie. on the bottom)

# To use in main.py:
#       import PrintCall
#
# Use as decorator
# @PrintCall.Single(True, True). Writes all logs to single file
# @PrintCall.Separate(True, True). Writes logs to separate file per function

# PrintCall class is not meant to be used directly. Use Separate or Single subclasses
class PrintCall:

    # Flag for the Single File Mode to help add only one separator line to the file
    _SeparateWrittenSingle = False
      
    def __init__(self, enablePrint=True, enableFile=True):
        self.EnablePrint = enablePrint
        self.EnableFile = enableFile
        
        self.Count = 0
        self.Filename = None # filename without the extension
        self.Extension = 'log'

        self.SeparatorWrittenSeparate = False

    def __call__(self, function):
        
        # if set to Separate File mode, then process the filename for this function
        if self._Mode == 'Separate':
            self.Filename = function.__name__
        else:
            self.Filename = 'PrintCallLogs'
            
        self.__ProcessFilename(self.Filename)

        def wrapper(*args, **kwargs):
            
            # Write to log file
            if self.EnableFile:
                
                FullFile = '{0}.{1}'.format(self.Filename, self.Extension)
                # Create the file in case the file gets removed during runtime
                if not File.Exists(FullFile):
                    self.__ProcessFilename(self.Filename)

                with File(FullFile, mode='at') as file:
                    self.Count += 1
                    if self._Mode == 'Separate':
                        if not self.SeparatorWrittenSeparate:
                            file.write('-----------------------------------------\r\n')
                            self.SeparatorWrittenSeparate = True

                        file.write('{0}. {1} - {2} {3} {4}\r\n'.format(
                            self.Count, time.asctime(), function.__name__, str(args), str(kwargs)))
                    else:
                        file.write('{0} - {1} ({2}) {3} {4}\r\n'.format(
                            time.asctime(), function.__name__, self.Count, str(args), str(kwargs)))
            else:
                self.Count += 1
            
            # Print out to console
            if self.EnablePrint:
                print('\r'.join(['Executing {0}'.format(function.__name__),
                str(args),str(kwargs),'Count: {0}'.format(self.Count)]))

            # Execute and return original function
            return function(*args, **kwargs)
        return wrapper
        
    def __ProcessFilename(self, filename):
        FullFile = '{0}.{1}'.format(filename, self.Extension)
        # Create a new file if it does not exist. Else add a separator line
        if not File.Exists(FullFile):
            with File(FullFile, mode='wt') as file:
                pass
        else:
            with File(FullFile, mode='at') as file:
                if self._Mode == 'Single' and not PrintCall._SeparateWrittenSingle:
                    file.write('-----------------------------------------\r\n')
                    PrintCall._SeparateWrittenSingle = True
        
class Separate(PrintCall):
    def __init__(self, enablePrint=True, enableFile=True):
        self._Mode = 'Separate'
        super().__init__(enablePrint, enableFile)
        
    
class Single(PrintCall):
    def __init__(self, enablePrint=True, enableFile=True):
        self._Mode = 'Single'
        super().__init__(enablePrint, enableFile)
    
    
    
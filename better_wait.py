class Wait(extronlib.system.Wait):
    """Functions that are decorated with Wait now are callable elsewhere.

    Exceptions that happen in waits wil now print the error message to TRACE as well as throwing the "Wait callback error" message in ProgramLog

    The programmer can now pass arguments to Wait callbacks
    for example:

    @Wait(2, args=('one', 'two'))
    def loop(arg1, arg2):
        print('loop(arg1={}, arg2={})'.format(arg1, arg2))
        raise Exception('loop Exception')

    **OR**

    def TestFunc(arg1, arg2):
        print('TestFunc(arg1={}, arg2={})'.format(arg1, arg2))
        raise Exception('TestFunc Exception')

    Wait(3, TestFunc, args=('three', 'four'))

    """

    def __init__(self, *args, **kwargs):
        if 'args' in kwargs:
            self._userArgs = kwargs.pop('args')
        else:
            self._userArgs = None

        if len(args) >= 2:
            if callable(args[1]):
                callback = args[1]
                newCallback = self._getNewFunc(callback)
                tempArgs = list(args)
                tempArgs[1] = newCallback
                newArgs = tuple(tempArgs)
                args = newArgs

        super().__init__(*args, **kwargs)

    def _getNewFunc(self, oldFunc):
        def newFunc():
            try:
                if self._userArgs is None:
                    oldFunc()
                else:
                    oldFunc(*self._userArgs)

            except Exception as e:
                ProgramLog('Wait Exception: {}\nException in function:{}\nargs={}'.format(e, oldFunc, self._userArgs), 'error')
                raise e

        return newFunc

    def __call__(self, callback):
        newCallback = self._getNewFunc(callback)

        super().__call__(newCallback)
        return newCallback

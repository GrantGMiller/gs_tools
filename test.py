import extronlib.ui
from extronlib.system import File

class Button(extronlib.ui.Button):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._userCallbacks = {}

    def LogEvent(self, button, state):
        with File('Event.log', mode='at') as file:
            file.write('Button {} {}'.format(button.ID, state))

    @property
    def PressedWithLog(self):
        return self._userCallbacks.get('Pressed', None)

    @PressedWithLog.setter
    def PressedWithLog(self, func):
        self._userCallbacks['Pressed'] = func

        def NewPressed(button, state):
            self.LogEvent(button, state)
            if callable(self._userCallbacks[state]):
                self._userCallbacks[state](button, state)

        self.Pressed = NewPressed

    # Do the same for held/repeated/released/tapped
    # In main.py just replace @event(btn, 'Pressed') with @event(btn, 'PressedWithLog')

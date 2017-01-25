## Begin ControlScript Import --------------------------------------------------
from extronlib import event, Version
from extronlib.device import ProcessorDevice, UIDevice
from extronlib.interface import (EthernetClientInterface,
                                 EthernetServerInterface, SerialInterface, IRInterface, RelayInterface,
                                 ContactInterface, DigitalIOInterface, FlexIOInterface, SWPowerInterface,
                                 VolumeInterface)
from extronlib.ui import Button, Knob, Label, Level
from extronlib.system import Clock, MESet, Wait

print(Version())

from file_sync_v2_0_0 import SystemSync
import time

TLP = UIDevice('TLP')

# File Sync *********************************************************************
Syncer = SystemSync()
Syncer.AddSystem('10.8.27.117')


@event(Syncer, 'NewData')
def NewDataEvent(interface, data):
    print('NewDataEvent()\ndata=', data)
    for key in data:
        if key == 'Volume':
            LvlVolume.SetLevel(data['Volume'])

        elif key == 'Mute':
            BtnVolumeMute.SetState(data['Mute'])


# GUI ***************************************************************************
BtnVolumeUp = Button(TLP, 1, repeatTime=0.1)
BtnVolumeDown = Button(TLP, 2, repeatTime=0.1)
BtnVolumeMute = Button(TLP, 3)

LvlVolume = Level(TLP, 4)


@event(BtnVolumeUp, 'Pressed')
@event(BtnVolumeUp, 'Repeated')
@event(BtnVolumeUp, 'Released')
@event(BtnVolumeDown, 'Pressed')
@event(BtnVolumeDown, 'Repeated')
@event(BtnVolumeDown, 'Released')
@event(BtnVolumeMute, 'Pressed')
@event(BtnVolumeMute, 'Released')
def BtnVolumeEvent(button, state):
    print(button.Name, button.ID, state)
    if state in ['Pressed', 'Repeated']:

        if button == BtnVolumeUp:
            LvlVolume.Inc()

        elif button == BtnVolumeDown:
            LvlVolume.Dec()

        elif button == BtnVolumeMute:
            # print('BtnVolumeMute.State=', BtnVolumeMute.State)
            # print('not BtnVolumeMute.State=', int(not BtnVolumeMute.State))
            BtnVolumeMute.SetState(int(not BtnVolumeMute.State))

    elif state == 'Released':
        if button in [BtnVolumeUp, BtnVolumeDown]:
            Syncer.Set('Volume', LvlVolume.Level)

        elif button == BtnVolumeMute:
            Syncer.Set('Mute', BtnVolumeMute.State)


print('Project Loaded')
## Begin ControlScript Import --------------------------------------------------
 from extronlib import event, Version
 from extronlib.device import ProcessorDevice, UIDevice
 from extronlib.interface import EthernetClientInterface, \
 EthernetServerInterface, SerialInterface, IRInterface, RelayInterface, \
 ContactInterface, DigitalIOInterface, FlexIOInterface, SWPowerInterface, \
 VolumeInterface
 from extronlib.ui import Button, Knob, Label, Level
 from extronlib.system import Clock, MESet, Wait

 print(Version())

 ## End ControlScript Import ----------------------------------------------------
 ##
 ## Begin User Import -----------------------------------------------------------

 ## End User Import -------------------------------------------------------------
 ##
 ## Begin Device/Processor Definition -------------------------------------------

 Processor = ProcessorDevice('IPCPPRO350')


 ## End Device/Processor Definition ---------------------------------------------
 ##
 ## Begin Device/User Interface Definition --------------------------------------

 ## End Device/User Interface Definition ----------------------------------------
 ##
 ## Begin Communication Interface Definition ------------------------------------

 IPAD_Sala_1 = UIDevice('IPAD_Sala_1')
 IPAD_Sala_2 = UIDevice('IPAD_Sala_2')
 IPAD_Sala_3 = UIDevice('IPAD_Sala_3')

 #Przyciski Sala 1
 Grafika = Label(IPAD_Sala_1, 31)

 BtnStartSala1 = Button(IPAD_Sala_1, 8000)
 BtnEndSala1 = Button(IPAD_Sala_1, 8022)
 BtnEndSala1Yes = Button(IPAD_Sala_1, 9028)
 BtnEndSala1No = Button(IPAD_Sala_1, 9029)
 #Źródło
 BtnSourceSala1 = Button(IPAD_Sala_1, 27)
 BtnSourceSala2 = Button(IPAD_Sala_1, 28)
 BtnSourceSala2 = Button(IPAD_Sala_1, 34)

 ## End Communication Interface Definition --------------------------------------

 def Initialize():
 global TomerGrafika
 TomerGrafika = 0
 print('System Start')


 ## Event Definitions -----------------------------------------------------------

 #Btn: Menu Start Sala 1
 @event(BtnStartSala1, 'Pressed')
 @event(BtnStartSala1, 'Released')
 def BtnStartSala1Event(button, state):
 if state == 'Pressed':
 button.SetState(1)
 print("Przycisk",button.Name)
 IPAD_Sala_1.ShowPopup("End1")
 @Wait(10)
 IPAD_Sala_1.HidePopup("End1")
 IPAD_Sala_1.ShowPopup("Crontrol pro")
 IPAD_Sala_1.ShowPopup("Background single room_1")
 IPAD_Sala_1.ShowPage("Main")
 else:
 button.SetState(0)

 #Btn: Menu End Sala 1

 @event(BtnEndSala1, 'Pressed')
 @event(BtnEndSala1, 'Released')
 def BtnEndSala1Event(button, state):
 if state == 'Pressed':
 button.SetState(1)
 print("Przycisk",button.Name)
 IPAD_Sala_1.ShowPopup("Confirmation")
 else:
 button.SetState(0)

 @event(BtnEndSala1Yes, 'Pressed')
 @event(BtnEndSala1Yes, 'Released')
 @event(BtnEndSala1No, 'Pressed')
 @event(BtnEndSala1No, 'Released')
 def BtnEndSala1ConfirmationEvent(button, state):
 if button is BtnEndSala1Yes:
 if state == 'Pressed':
 button.SetState(1)
 print("Przycisk",button.Name)
 IPAD_Sala_1.HideAllPopups()
 IPAD_Sala_1.ShowPage("Start")
 else:
 button.SetState(0)
 elif button is BtnEndSala1No:
 if state == 'Pressed':
 button.SetState(1)
 print("Przycisk",button.Name)
 IPAD_Sala_1.HidePopup("Confirmation")
 else:
 button.SetState(0)

 ##END Evnts Definitions-------------------------------------------------------

 Initialize()

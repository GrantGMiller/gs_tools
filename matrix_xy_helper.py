from extronlib.system import MESet, Wait
from extronlib.ui import Button
from gs_tools_ggm_v1_0_9 import (ShortenText,
                                 )


class Matrix_XY_Helper():
    '''
    This class will handle making ties, but will not
    '''

    def __init__(self, TLP):
        self.tlp = TLP

        self.interface = None
        self.MatrixInfo = None

        self.MES_Inputs = MESet([])
        self.MES_Outputs = MESet([])

        def ResetMES():
            self.MES_Inputs.SetCurrent(None)
            self.MES_Outputs.SetCurrent(None)

        self.WaitResetMES = Wait(1, ResetMES)
        self.WaitResetMES.Cancel()


    def AddMatrixInfo(self, MatrixInfo):
        self.MatrixInfo = MatrixInfo

    def AddInterface(self, interface):
        self.interface = interface

    def AddInputButtonIDs(self, InputBtnIDs):
        # InputBtnIDs should relate to the matrix input numbers.
        # The ID should be greater than 1000 and should end with the input number
        # Example: if the Matrix Input is '1', then the ID should be 1001, 2001,...., 10001, ...
        if not isinstance(InputBtnIDs, list):
            InputBtnIDs = [InputBtnIDs]

        for ID in InputBtnIDs:
            NewButton = Button(self.tlp, ID)
            self.MES_Inputs.Append(NewButton)

            if self.MatrixInfo:
                InputNum = str(NewButton.ID % 1000)

                InputName = ''
                for key in self.MatrixInfo['Input']:
                    if InputNum == self.MatrixInfo['Input'][key]:
                        InputName = ShortenText(key)

                NewButton.SetText(InputName)

        self._SetupEvents()

    def AddOutputButtonIDs(self, OutputBtnIDs):
        if not isinstance(OutputBtnIDs, list):
            OutputBtnIDs = [OutputBtnIDs]

        self.OutputBtns = []
        for ID in OutputBtnIDs:
            NewButton = Button(self.tlp, ID)
            self.MES_Outputs.Append(NewButton)

            if self.MatrixInfo:
                OutputNum = str(NewButton.ID % 1000)

                OutputName = ''
                for key in self.MatrixInfo['Output']:
                    if OutputNum == self.MatrixInfo['Output'][key]:
                        OutputName = ShortenText(key)

                NewButton.SetText(OutputName)

        self._SetupEvents()

    def _SetupEvents(self):
        if len(self.MES_Inputs.Objects) > 0:
            if len(self.MES_Outputs.Objects) > 0:

                # Create event handlers
                def InputPressEvent(button, state):
                    self.MES_Inputs.SetCurrent(button)
                    self.WaitResetMES.Cancel()

                    self._MakeTie()

                def OutputPressEvent(button, state):
                    self.MES_Outputs.SetCurrent(button)
                    self._MakeTie()

                # Assisgn event handlers to buttons
                for btn in self.MES_Inputs.Objects:
                    btn.Pressed = InputPressEvent

                for btn in self.MES_Outputs.Objects:
                    btn.Pressed = OutputPressEvent

    def _MakeTie(self):
        BtnInput = self.MES_Inputs.GetCurrent()
        BtnOutput = self.MES_Outputs.GetCurrent()

        if BtnInput is not None:
            if BtnOutput is not None:
                InputNum = str(BtnInput.ID % 1000)
                OutputNum = str(BtnOutput.ID % 1000)

                self.interface.Set('MatrixTieCommand', None, {'Input': InputNum,
                                                              'Output': OutputNum,
                                                              'Tie Type': 'Video',
                                                              })

                self.MES_Outputs.SetCurrent(None)
                self.WaitResetMES.Restart()

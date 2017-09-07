'''
Grant G. Miller
Sept 20, 2016
gmiller@extron.com
800-633-9876 x6032

This is a SMTP client that behaves similar to extronlib.system.Email

This class adds the ability to send an email with attachement.
Note: this class does not support SMTP username/password although it could be easily added.

Based on example from: http://www.codeproject.com/Articles/28806/SMTP-Client and other online resources

'''

from extronlib import event
from extronlib.interface import EthernetClientInterface
import time
from extronlib.system import File
import base64


class SMTP_Client():
    def __init__(self, smtpServer=None, port=None, username=None, password=None, sslEnabled=None):
        #TODO - account for username, password, sslEnabled
        self.IP = smtpServer
        self.IPPort = port
        self.Receivers = []
        self.Received220 = False
        self.Received250 = False
        self.FileBytes = None

        self.Interface = EthernetClientInterface(self.IP, self.IPPort)

        @event(self.Interface, 'ReceiveData')
        def PrintRxData(interface, data):
            # print('Rx:', data)
            data = data.decode()
            if '220' in data:
                # print('self.Received220 = True')
                self.Received220 = True

            if '250' in data:
                # print('self.Received250 = True')
                self.Received250 = True

                # AddTrace(self.Interface)

        self.sender = 'IPCP@extron.com'

    def Receiver(self, receiver=[], cc=False):
        #TODO - account for cc=True
        if not isinstance(receiver, list):
            receiver = [receiver]

        self.Receivers.extend(receiver)
        # print('self.Receivers =', self.Receivers)

    def Subject(self, subject):
        self.subject = subject
        self.Domain = self.sender.split('@')[1]
        # print('self.subject =', self.subject)

    def Sender(self, sender):
        self.sender = sender
        # print('self.sender =', self.sender)

    def AddAttachement(self, filename):
        self.filename = filename
        # print('self.filename =', self.filename)

        file = File(self.filename, mode='rb')
        self.FileBytes = base64.b64encode(file.read())
        # print('self.FileBytes =', self.FileBytes[-100:])

    def SendMessage(self, msg):
        self.MsgID = str(time.time()).replace('.', '')
        self.Received220 = False
        self.Msg = msg
        # print('self.Msg=', self.Msg)
        # print('type(self.Msg)=', type(self.Msg))

        result = self.Interface.Connect()
        # print('Connect() result =', result)
        if result is not 'Connected':
            raise Exception(result)

        while not self.Received220:
            time.sleep(0.001)
            # print('Waiting for 220')
            pass

        time.sleep(0.001)
        data = self.Interface.SendAndWait('EHLO\r\n'.format(self.Domain), 1, deliTag='\r\n')
        # print(data)
        data = data.decode()
        # print('EHLO data =', data)

        if '250' not in data:
            # print(data)
            raise Exception(str(data))

        time.sleep(0.001)
        data = self.Interface.SendAndWait('MAIL FROM:<{}>\r\n'.format(self.sender), 1, deliTag='\r\n')
        # print(data)
        data = data.decode()
        if '250' not in data:
            # print(data)
            raise Exception(str(data))

        time.sleep(0.001)
        SendString = 'RCPT TO:<{}>\r\n'.format(self.Receivers[0])
        # print('OUT:', SendString)
        data = self.Interface.SendAndWait(SendString, 1, deliTag='\r\n')
        # print(data)
        data = data.decode()
        if '250' not in data:
            # print(data)
            raise Exception(str(data))

        time.sleep(0.001)
        data = self.Interface.SendAndWait('DATA\r\n', 1, deliTag='\r\n')
        # print(data)
        data = data.decode()
        if '354' not in data:
            # print(data)
            raise Exception(str(data))

        TotalMessage = b'''Date ''' + time.asctime().encode() + b'''
From: <''' + self.sender.encode() + b'''>
X-Mailer: The Bat! (v3.02) Professional
Replay-to: main@''' + self.Domain.encode() + b'''
X-Priority: 3 (Normal)
To:<''' + self.Receivers[0].encode() + b'''>
Subject: ''' + self.subject.encode() + b'''
MIME Version 1.0
Content-Type: multipart/mixed; boundary="__MESSAGE__ID__''' + self.MsgID.encode() + b'''"


--__MESSAGE__ID__''' + self.MsgID.encode() + b'''
Content-type: text/plain; charset=US-ASCII
Content-Transfer-Encoding: 7bit

''' + self.Msg.encode()

        if self.FileBytes is not None:
            TotalMessage += b'''

--__MESSAGE__ID__''' + self.MsgID.encode() + b'''
Content-Type: application/x-msdownload; name="''' + self.filename.encode() + b'''"
Content-Transfer-Encoding: base64
Content-Disposition: attachment; filename="''' + self.filename.encode() + b'''"

''' + self.FileBytes

        TotalMessage += b'''

--__MESSAGE__ID__''' + self.MsgID.encode() + b'''--

\r\n.\r\n'''

        # time.sleep(5)
        Wait = False
        if Wait:
            while True:
                try:
                    data = self.Interface.SendAndWait(TotalMessage, 1, deliTag='\r\n')
                    # print(data)
                    break
                except Exception as e:
                    print(e)
                    time.sleep(0.003)
        else:

            self.Received250 = False

            # Send data in chunks.
            ChunkSize = 512
            NumberOfChunks = int(len(TotalMessage) / ChunkSize) + 1
            ##print('NumberOfChunks=', NumberOfChunks)
            for i in range(NumberOfChunks):
                ##print('Sending Chunk', i)
                StartIndex = i * ChunkSize
                EndIndex = (i + 1) * ChunkSize

                if EndIndex > len(TotalMessage):
                    Chunk = TotalMessage[StartIndex:]
                else:
                    Chunk = TotalMessage[StartIndex:EndIndex]

                try:
                    self.Interface.Send(Chunk)
                    ##print('Chunk', i, '=', Chunk)
                    time.sleep(0.01)  # make sure chunks are received in order
                    pass
                except Exception as e:
                    print(e)

        while self.Received250 == False:
            # print("Waiting for 250 Response")
            time.sleep(1)

        data = self.Interface.SendAndWait('QUIT\r\n', 1, deliTag='\r\n')
        # print('QUIT data=', data)
        self.Interface.Disconnect()
        self.FileBytes = None
        self.Received220 = False
        self.Received221 = False

        print('Email sent')

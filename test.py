from gs_tools import HandleConnection
from extronlib import EthernetServerInterfaceEx

server = EthernetServerInterfaceEx(3888)
HandleConnection(server)

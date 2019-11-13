from graf import Network
from communicator import Communicator
communicator = Communicator()
# import pydevd
# port_mapping=[36219, 46181, 43801, 43925]
#
# pydevd.settrace('localhost', port=port_mapping[communicator.rank], stdoutToServer=True, stderrToServer=True)

def mySimulator():
    sim = Network()
    sim.boot_network()
    sim.run()


mySimulator()

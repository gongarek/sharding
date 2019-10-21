from graf import Network


def mySimulator():
    sim = Network()
    sim.boot_network()
    sim.run()


mySimulator()

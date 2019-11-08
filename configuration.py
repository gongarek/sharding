class Configuration:
    def __init__(self):
        # Topology network                  # pewnie dla beacon chaina bedzie inaczej
        self.nodesPerRank = 6
        self.nodesPerBeacon = 10
        self.intervalID = 1000

        # Main chain settings
        self.nbPeers = 2
        self.nbMigrates = 2

        # Time settings
        self.simTime = 1

        # Block settings
        self.start_money = 100
        self.max_pay = 300
        self.max_stake = 4000000    # tu bedzie trzeba wyliczyc z maksymalnej kasy w transakcji w blokach i ile ich jest
        self.added_paid_every_tick = 20
        self.transactionsPerBlock = 5

from configuration import Configuration
from communicator import  Communicator
from random import sample

class Beacon:
    def __init__(self):
        self.config = Configuration()
        self.communicator = Communicator()
        self.accounts_info = []
        shard_node_ids = sample(range(self.config.intervalID, 2 * self.config.intervalID), self.config.nodesPerBeacon)
        self.create_account_info()
        self.node_ids = self.communicator.comm.bcast([i["id"] for i in self.accounts_info], root=0)
        for node in shard_node_ids:
            self.peers_of_nodes_in_shard[node] = sample((set(shard_node_ids)-{node}), self.config.nbPeers)
        plot_network(s.peers_of_nodes_in_shard, s.communicator.rank)

    def create_account_info(s):
        for rank in range(1, s.communicator.nbRanks):
            interval = range((rank+1)*s.config.intervalID, (rank+2)*s.config.intervalID)
            # if rank == (s.communicator.nbRanks-1):
            #     for notary_id in sample(interval, s.config.nodesPerNotarry):
            #         account = {"id": notary_id,
            #                    "money": s.config.start_money,
            #                    "shard": rank}
            #         s.accounts_info.append(account)
            # else:
                # for id_node in sample(interval, s.config.nodesPerRank):
                #     account = {"id": id_node,
                #                "money": s.config.start_money,
                #                "shard": rank}
                #     s.accounts_info.append(account)
            for id_node in sample(interval, s.config.nodesPerRank):
                account = {"id": id_node,
                           "money": s.config.start_money,
                           "shard": rank}
                s.accounts_info.append(account)
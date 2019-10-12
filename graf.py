from random import sample
import networkx as nx
import matplotlib.pyplot as plt
import warnings
from configuration import Configuration
from mpi import Topology


class Network:
    def __init__(self):
        self.config = Configuration()
        self.peers_shard = []

    def draw(self):
        g = nx.Graph()
        plt.figure(figsize=(15, 15))
        node_ids = []
        length_list = self.config.nodesPerRank

        for i in range(length_list):
            node_id = id(i)             # musi być przypisanie, zeby dzialalo id
            node_ids.append(node_id)

        g.add_nodes_from(node_ids)

        for node in node_ids:
            peers_node = sample((set(node_ids) - {node}), k=self.config.nbPeers)
            self.peers_shard.append(peers_node)    # lista w której są listy peerow w węźle
            for peer in peers_node:
               g.add_edge(node, peer)

        print(self.peers_shard)

        pos = nx.kamada_kawai_layout(g)
        warnings.filterwarnings("ignore")
        nx.draw(g, pos, with_labels=True, node_size=3500, node_color='y')
        warnings.resetwarnings()
        plt.show()

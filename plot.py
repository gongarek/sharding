import networkx as nx
import matplotlib.pyplot as plt
import warnings


def plot_network(peers_shard, rank):
    g = nx.Graph()
    plt.figure(figsize=(5, 5))
    # plt.axis('off')
    fig = plt.gcf()
    fig.canvas.set_window_title(f"shard {rank}")
    node_ids = list(peers_shard)
    g.add_nodes_from(node_ids)
    g.add_edges_from([[k, i] for k, v in peers_shard.items() for i in v])

    pos = nx.kamada_kawai_layout(g)
    warnings.filterwarnings("ignore")
    nx.draw(g, pos, with_labels=True, node_size=1200, node_color='y')
    warnings.resetwarnings()
    plt.show()

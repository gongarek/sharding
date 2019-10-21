from random import choice, sample, randrange
from configuration import Configuration
from communicator import Communicator
from plot import plot_network
from copy import deepcopy
from transaction import Transaction


class Network:
    def __init__(s):
        s.config = Configuration()
        s.commu = Communicator()
        s.peers_of_nodes_in_shard = {}
        s.node_ids = []
        s.shard_transactions = []
        s.accounts_info = []

    def boot_network(s):
        shard_node_ids = []
        if s.commu.rank == 0:
            shard_node_ids = sample(range(1000, 2000), s.config.nodesPerBeacon)   #POTEM SIE ZMIENI
            s.create_account_info()

        s.node_ids = s.commu.comm.bcast([i["id"] for i in s.accounts_info], root=0)
        # w node_ids są id wezłow. Najpierw są w shardzie zerowym, potem pierwszym itd.
        if s.commu.rank != 0:
            for i in range((s.commu.rank-1)*s.config.nodesPerRank, s.commu.rank*s.config.nodesPerRank):
                shard_node_ids.append(s.node_ids[i])
        for node in shard_node_ids:
            s.peers_of_nodes_in_shard[node] = sample((set(shard_node_ids)-{node}), s.config.nbPeers)
        plot_network(s.peers_of_nodes_in_shard, s.commu.rank)

    def create_account_info(s):
        for rank in range(1, s.commu.nbRanks):
            interval = range((rank+1)*s.config.intervalID, (rank+2)*s.config.intervalID)
            for id in sample(interval, s.config.nodesPerRank):
                account = {"id": id,
                           "money": s.config.start_money,
                           "shard": rank}
                s.accounts_info.append(account)

    def run(s):
        for i in range(s.config.simTime):
            s.tick()
        s.commu.comm.barrier()
        plot_network(s.peers_of_nodes_in_shard, s.commu.rank)

    def tick(s):
        if s.commu.rank == 0:
            s.choose_rotated_nodes()
        s.commu.comm.barrier()
        if s.commu.rank != 0:
            s.shuffle_nodes(s.peers_of_nodes_in_shard, s.commu.comm.recv(source=0))
        s.commu.comm.barrier()
        if s.commu.rank != 0:
            s.send_transactions_to_beacon()
        s.commu.comm.barrier()
        if s.commu.rank == 0:
            trans_after_del = s.account_balanace([s.commu.comm.recv(source=i) for i in range(1, s.commu.nbRanks)])
            # print(trans_after_del, "poeinny byc usuniete\n")
            s.resend_transaction(trans_after_del)
        s.commu.comm.barrier()

        if s.commu.rank != 0:
            trans_shard = s.commu.comm.recv(source=0)
            print(trans_shard)
            """potworzyc merkle rooty"""
            """transakcja bedzie w liscie
            i to bedzie lisc drzewa.
            w kazdym ticku bedzie jeden blok
            swoja transakcje bedzie mial wezel 
            i tam bedzie podane id bloku i kawalek, gdzie mozna go znalezc. 
            """









    def choose_rotated_nodes(s):
        old_rotated_nodes = []
        for rank in range(1, s.commu.nbRanks):
            new_rotated_nodes = sample([(index, acc['id']) for index, acc in enumerate(s.accounts_info) if acc["shard"] == rank], s.config.nbMigrates)
            if old_rotated_nodes:
                for node in old_rotated_nodes:
                    s.accounts_info[node[0]]["shard"] += 1
            old_rotated_nodes = new_rotated_nodes
            if rank == (s.commu.nbRanks - 1):
                for node in old_rotated_nodes:
                    s.accounts_info[node[0]]["shard"] = 1
            s.commu.comm.send([node[1] for node in new_rotated_nodes], dest=rank)

    def shuffle_nodes(s, peers_of_nodes_in_shard, migrant_ids):
        # usuwanie perrow poprzez rotowane wezly
        for m in migrant_ids:
            del peers_of_nodes_in_shard[m]
            for v in list(peers_of_nodes_in_shard.values()):
                for i in v:
                    if i == m:
                        v.remove(i)
        s.send_recv_migrants(migrant_ids)

    def send_recv_migrants(s, migrant_ids):
        if s.commu.rank == 1:
            s.commu.comm.send(migrant_ids, dest=2)
            s.supp_peers(s.commu.comm.recv(source=s.commu.nbRanks - 1))
        elif s.commu.rank == (s.commu.nbRanks-1):
            s.commu.comm.send(migrant_ids, dest=1)
            s.supp_peers(s.commu.comm.recv(source=s.commu.rank-1))
        else:
            s.commu.comm.send(migrant_ids, dest=s.commu.rank+1)
            s.supp_peers(s.commu.comm.recv(source=s.commu.rank - 1))

    def supp_peers(s, recv_migrant_id):
        for i in recv_migrant_id:
            s.peers_of_nodes_in_shard[i] = []
        keys = list(s.peers_of_nodes_in_shard.keys())
        for u in keys:
            while len(s.peers_of_nodes_in_shard[u]) < s.config.nbPeers:
                s.peers_of_nodes_in_shard[u].append(choice(list(set(keys) - {u} - set(s.peers_of_nodes_in_shard[u]))))

    def send_transactions_to_beacon(s):
        for i in range(s.config.transactionsPerBlock):
            sender = choice(list(s.peers_of_nodes_in_shard))
            transaction = {
                "ID": f"{s.commu.rank}x{randrange(10**50, 10**51)}",  # id transakcji -->numeru wysylajacego sharda
                "sender": sender,
                "receiver": choice(list((set(s.node_ids) - {sender}))),
                "amount": choice(range(s.config.max_pay))
            }
            s.shard_transactions.append(transaction)
        s.commu.comm.send(s.shard_transactions, dest=0)

    def account_balanace(s, transactions):
        transactions_removed = deepcopy(transactions)
        for index, shard_trans in enumerate(transactions):
            for trans in shard_trans:
                sacc = next((ind, acc) for ind, acc in enumerate(s.accounts_info) if acc["id"] == trans["sender"])
                racc = next((ind, acc) for ind, acc in enumerate(s.accounts_info) if acc["id"] == trans["receiver"])
                if trans["amount"] <= sacc[1]["money"]:
                    s.accounts_info[sacc[0]]["money"] -= trans["amount"]
                    s.accounts_info[racc[0]]["money"] += trans["amount"]
                else:
                    transactions_removed[index].remove(trans)
        transactions = transactions_removed
        return transactions

    def resend_transaction(s, transactions):
        send_transactions = deepcopy(transactions)
        for index, shard_trans in enumerate(transactions):
            for tran in shard_trans:
                shard_odbierajacy = next(acc["shard"] for acc in s.accounts_info if acc["id"] == tran["receiver"])
                if shard_odbierajacy != index + 1:
                    send_transactions[shard_odbierajacy - 1].append(tran)
        for index, shard_trans in enumerate(send_transactions):
            s.commu.comm.send(shard_trans, dest=index+1)


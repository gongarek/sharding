from random import choice, sample, randrange, random
from configuration import Configuration
from communicator import Communicator
from block import Block
from plot import plot_network
from copy import deepcopy
from time import time

from transaction import Transaction
import merkletools


class Network:
    def __init__(s):
        s.config = Configuration()
        s.commu = Communicator()
        s.peers_of_nodes_in_shard = {}
        s.node_ids = []
        s.shard_transactions = []
        s.accounts_info = []
        s.shard_blockchain = []

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
        s.block = Block(None, None, time(), None, None)
        s.block.create_tree()
        s.shard_blockchain.append(s.block)
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
        for i in range(s.config.simTime):                                       # sprawdzic piry i account info dla wiekszej ilosci simtimow
            if i % 3 == 0:                      # CO TRZECI TIK JEST JEST ROTACJA WEZLOW. CO TICK BEDA ROTOWANI NOTARIUSZE. aLE NARAZIE NOTARIUSZE NIE DZIALAJA
                if s.commu.rank == 0:
                    s.choose_rotated_nodes()
                s.commu.comm.barrier()
                if s.commu.rank != 0:
                    s.shuffle_nodes(s.peers_of_nodes_in_shard, s.commu.comm.recv(source=0))
                s.commu.comm.barrier()
            s.tick()
        s.commu.comm.barrier()
        plot_network(s.peers_of_nodes_in_shard, s.commu.rank)

    def tick(s):
        if s.commu.rank != 0:
            s.send_transactions_to_beacon()
        s.commu.comm.barrier()
        if s.commu.rank == 0:
            trans_after_del = s.account_balanace([s.commu.comm.recv(source=i) for i in range(1, s.commu.nbRanks)]) ###POTEM JAK BEDA NOTARIUSZE TO TRZEBA BEDZIE ZMIENIC TO PETLE. Zmieniane sa stany konta i usuwne sa transakcje, ktore nie maja pokrycia w pieniadzach
            # print(trans_after_del, "poeinny byc usuniete\n")
            s.resend_transaction(trans_after_del)
        s.commu.comm.barrier()
        if s.commu.rank != 0:
            true_block = s.ramification_send_bad()
        s.commu.comm.barrier()
        if s.commu.comm.rank == 0:
            s.burning_stakes_ramification()
        s.commu.comm.barrier()
        if s.commu.comm.rank != 0:
            s.walidate_all_blockchain(s.shard_blockchain, true_block)
        s.commu.comm.barrier()
        if s.commu.comm.rank == 0:
            s.burn_stake_bad_commit()
            s.remove_indebted_nodes()
        s.commu.comm.barrier()
        if s.commu.rank != 0:
            s.change_node_ids(s.commu.comm.recv(source=0))








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
                "amount": choice(range(1, s.config.max_pay))
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
        #Dodaje wszystkim po 20 poniewaz beda palone stawki przy tworzeniu zlych BLOKÓW i nie chce zeby ludzie sie wykosztowali
        for account in s.accounts_info:
            account["money"] += s.config.added_paid_every_tick
        return transactions

    def resend_transaction(s, transactions): # wysylane sa transakcje do shardow, by mogly stworzyc z nich bloki
        send_transactions = deepcopy(transactions)
        for index, shard_trans in enumerate(transactions):
            for tran in shard_trans:
                shard_odbierajacy = next(acc["shard"] for acc in s.accounts_info if acc["id"] == tran["receiver"])
                if shard_odbierajacy != index + 1:
                    send_transactions[shard_odbierajacy - 1].append(tran)
        for index, shard_trans in enumerate(send_transactions):
            s.commu.comm.send(shard_trans, dest=index+1)

    def ramification_send_bad(s): # te rozgalezienia i i tak dalej robia sie poza beacon chainem ,wiec duzo zobostrzen jest pomijanych, jak na przyklad podowjne id transakcji. POza tym te bloki nie musza miez miejsca w beaconie. bo lekkie wezly biora transakcje z shardow a nie z beacon chaina
        ramification = []
        fake_transactions = []
        fake_transaction = {}
        money_in_block = 0
        while random() > 0.5:
            for tran in range(s.config.transactionsPerBlock): #DODAJEMY BLOK ROZGALEZIONY Z ZLYMI, LOSOWYMI TRANSAKCJAMI
                fake_transaction = {
                    "ID": f"{s.commu.rank}x{randrange(10**50, 10**51)}",  # id transakcji -->numeru wysylajacego sharda
                    "sender": choice(list(s.peers_of_nodes_in_shard)),
                    "receiver": choice(list(s.peers_of_nodes_in_shard)),
                    "amount": choice(range(1, s.config.max_pay))
                }
                money_in_block += fake_transaction["amount"]
                fake_transactions.append(fake_transaction)
            staker = choice(list(s.peers_of_nodes_in_shard.keys()))
            stake = choice(list(range(money_in_block+1, s.config.max_stake+1)))
            s.block = Block(fake_transactions, s.shard_blockchain[-1].block_id, time(), staker, stake)
            s.block.create_tree()
            ramification.append(s.block)
            money_in_block = 0

        received_transactions = s.commu.comm.recv(source=0)
        for tran in received_transactions:
            money_in_block += tran['amount']
        staker = choice(list(s.peers_of_nodes_in_shard.keys()))
        stake = choice(list(range(money_in_block, s.config.max_stake + 1)))
        s.block = Block(received_transactions, s.shard_blockchain[-1].block_id, time(), staker, stake)
        s.block.create_tree()
        ramification.append(s.block)

        indexes = []
        for ind, block in enumerate(ramification):
            bl = Block(received_transactions, s.shard_blockchain[-1].block_id, time(), None, None)
            bl.create_tree()
            if block.mt.get_merkle_root() != bl.mt.get_merkle_root():
                indexes.append(ind)


        "wysylam wiadomosci o paleniu stawek, ale wydaje mi sie ze to bez sensu, bo te tworzenie galezi w sumie nie jest specjalnie, a to bardzo czesto zmniejsza kase kont i chyba nie ma co. Najwyzej usunac c jest na dole plus palenie po galeziacj, czyli usuwanie burning_stakes_ramificication"
        s.commu.comm.send((len(ramification) - 1), dest=0)  # tyle stawek bedzie palonych, bo tyle jest zlych bloków
        for block in ramification[:-1]: #ostatni blok jest spoko, wiec nie ma co palic. Zostawmy go :)
            s.commu.comm.send([block.staker, block.stake], dest=0)

        for i in indexes[::-1]:
            del ramification[i]

        """zatwierdzenie niewlasciwej transakcji"""
        hostility = random()
        proper_transaction = ramification[-1]
        print(proper_transaction)
        print(received_transactions, s.commu.rank, '\n')
        if hostility < 0.75:
            s.shard_blockchain.append(proper_transaction) #ostatnia to poprawna
            if hostility >= 0.5:
                proper_transaction.transaction = proper_transaction.transaction[:-1] # dodajemy blok bez transakcji ostatniej. Tak sobie wymyslilismy
                s.shard_blockchain.append(proper_transaction)
        else:
            staker = choice(list(s.peers_of_nodes_in_shard.keys()))
            stake = choice(list(range(money_in_block, s.config.max_stake + 1)))
            s.block = Block(received_transactions, hash("whatever"), time(), staker, stake)
            s.block.create_tree()
            s.shard_blockchain.append(s.block)
        return ramification[-1]                     # dodanie ostatniego, poprawnego bloku


    def burning_stakes_ramification(s):
        """narazie zostawimy watek notariuszy"""
        for rank in range(1, s.commu.nbRanks):
            nb_to_burn = s.commu.comm.recv(source=rank)
            if nb_to_burn > 0:
                for i in range(nb_to_burn):
                    acc_burned = s.commu.comm.recv(source=rank)
                    for ind, acc in enumerate(s.accounts_info):
                        if acc_burned[0] == acc['id']:
                            s.accounts_info[ind]['money'] -= acc_burned[1] #jak bedzie na minusie to go trzeba wywalicWYWALIC, ale po walidacji calego bloku, bo wczesniej wszystko jest w jendym

    def walidate_all_blockchain(s, blockchain, true_block):  #ALE USUWANY JEST ZAWSZE    OSTATNI, BO WCZESNIEJ ZAWSZE JEST OK. I JEST ZAWSZE ich dwa. W sensie jeden. Albo dobry albo zly
        to_send = "None"
        for index, block in enumerate(blockchain):
            if block.parent is not None:
                if block.parent != blockchain[index-1].block_id:
                    to_send = [block.staker, block.stake]
                    del s.shard_blockchain[-1]
                    s.accounts_info.append(true_block)  #dodawanie poprawnego
                """block.transakcje sa niepwlne i teraz o to chodzi, by to sprawdzicz czy ten atrybut jest ok , jesli nie to stakera bloku trzeba uwiesic za jaja itd. Trzeba to zrobic dla czwartego, ostaniego procesu rank==4 i trzeba bedzie stworzuyc nawa funkcje tylko dla niego"""
                if block.transaction





        s.commu.comm.send(to_send, dest=0) #ze niby none nie mozna wysylac . I dzieki temu bedziemy palic i usuwac

    def burn_stake_bad_commit(s):
        """narazie zostawiamy watek notariuszy"""
        # list_id = [acc['id'] for acc in s.accounts_info]
        for rank in range(1, s.commu.nbRanks):
            acc_burned = s.commu.comm.recv(source=rank)
            if acc_burned != "None":
                for index, acc in enumerate(s.accounts_info):
                    if acc_burned[0] == acc['id']:
                        s.accounts_info[index]['money'] -= acc_burned[1]


    """USUWAC WEZLY KTORE SA NA MINUSIE"""
    def remove_indebted_nodes(s):
        list_id = [acc['id'] for acc in s.accounts_info]
        change_ids = []
        for index, acc in enumerate(s.accounts_info):
            if acc['money'] < 0:
                interval = range(2000, ((s.commu.nbRanks+1) * s.config.intervalID))
                old_id = acc['id']
                new_id = choice(list(set(interval) - {acc['id']} - set(list_id)))
                s.accounts_info[index]['id'] = new_id
                s.accounts_info[index]['money'] = s.config.start_money
                change_ids.append((old_id, new_id))
                list_id[index] = new_id
        for i in range(1, s.commu.nbRanks):
            s.commu.comm.send(change_ids, dest=i)

    """receive ids to change"""
    def change_node_ids(s, change_ids):   # W SUMIE TO SLABE BO ZAMIENIA WEZLAMI ,ALE TAK NAPRAWDE POWINNO BYC USUWANKO I POTEM DOBIOR WEZLOW TAK JAK NA GORZE ROBILEM, ALE JUZ NIE CHCE MI SIE
        new_peers_of_nodes_in_shard = deepcopy(s.peers_of_nodes_in_shard)
        for key, val in new_peers_of_nodes_in_shard.items():
            for change in change_ids:
                for index, vali in enumerate(val):
                    if vali == change[0]:
                        s.peers_of_nodes_in_shard[key][index] = change[1]
                if key == change[0]:
                    s.peers_of_nodes_in_shard[change[1]] = new_peers_of_nodes_in_shard[change[0]]
        for change in change_ids:
            if change[0] in s.peers_of_nodes_in_shard.keys():
                s.peers_of_nodes_in_shard.pop(change[0])

        for change in change_ids:
            for index, node in enumerate(s.node_ids):
                if node == change[0]:
                    s.node_ids[index] = change[1]







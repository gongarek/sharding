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
        s.communicator = Communicator()
        s.peers_of_nodes_in_shard = {}
        s.node_ids = []
        s.shard_transactions = []
        s.accounts_info = []
        s.shard_blockchain = []
        s.block = Block(None, None, time(), None, None)

    def boot_network(s):
        shard_node_ids = []
        if s.communicator.rank == 0:
            shard_node_ids = sample(range(s.config.intervalID, 2*s.config.intervalID), s.config.nodesPerBeacon)
            s.create_account_info()
        s.node_ids = s.communicator.comm.bcast([i["id"] for i in s.accounts_info], root=0)
        # if s.communicator.rank == s.communicator.nbRanks-1:  # notariusze
        #     for id_notary in s.node_ids[-s.config.nodesPerNotarry:]:
        #         shard_node_ids.append(id_notary)
        #     s.block.create_tree()
        #     s.shard_blockchain.append(s.block)
        # w node_ids są id wezłow. Najpierw są w shardzie zerowym, potem pierwszym itd.

        # if (s.communicator.rank != 0) and (s.communicator.rank != (s.communicator.nbRanks-1)):
        if s.communicator.rank != 0:
            for i in range((s.communicator.rank-1)*s.config.nodesPerRank, s.communicator.rank*s.config.nodesPerRank):
                shard_node_ids.append(s.node_ids[i])
            s.block.create_tree()
            s.shard_blockchain.append(s.block)


        for node in shard_node_ids:
            s.peers_of_nodes_in_shard[node] = sample((set(shard_node_ids)-{node}), s.config.nbPeers)



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

    def run(s):
        for i in range(s.config.simTime):       # sprawdzic piry i account info dla wiekszej ilosci simtimow
            if i % 3 == 0:                      # CO TRZECI TIK JEST ROTACJA WEZLOW. CO TICK BEDA ROTOWANI NOTARIUSZE. aLE NARAZIE NOTARIUSZE NIE DZIALAJA
                if s.communicator.rank == 0:
                    s.choose_rotated_nodes()
                s.communicator.comm.barrier()
                if s.communicator.rank != 0:
                    s.shuffle_nodes(s.peers_of_nodes_in_shard, s.communicator.comm.recv(source=0))
                s.communicator.comm.barrier()
            s.tick()
        s.communicator.comm.barrier()
        plot_network(s.peers_of_nodes_in_shard, s.communicator.rank)

    def tick(s):
        if s.communicator.rank != 0:
            s.send_transactions_to_beacon()
        s.communicator.comm.barrier()
        if s.communicator.rank == 0:
            trans_after_del = s.account_balanace([s.communicator.comm.recv(source=i) for i in range(1, s.communicator.nbRanks)]) ###POTEM JAK BEDA NOTARIUSZE TO TRZEBA BEDZIE ZMIENIC TO PETLE. Zmieniane sa stany konta i usuwne sa transakcje, ktore nie maja pokrycia w pieniadzach
            # print(trans_after_del, "poeinny byc usuniete\n")
            s.resend_transaction(trans_after_del)
        s.communicator.comm.barrier()
        if s.communicator.rank != 0:
            true_block = s.ramification_send_bad()
        s.communicator.comm.barrier()
        if s.communicator.comm.rank == 0:
            s.burning_stakes_ramification()
        s.communicator.comm.barrier()
        if s.communicator.comm.rank != 0:
            s.walidate_all_blockchain(s.shard_blockchain, true_block)
        # s.communicator.comm.barrier() # tego nie trzeba robic to na spokojnie te dwa beda sobie robic swoje i nie powinny sobie przeszkadzac
        # if s.communicator.comm.rank == (s.communicator.nbRanks-1): #trzeba bedzie przejsc przez wszystko i posprawdzac czy notariusze nie swiruja w innych. A na pewno to robia
        #     s.check_data_availability(s.shard_blockchain, true_block)
        s.communicator.comm.barrier()
        if s.communicator.comm.rank == 0:
            s.burn_stake_bad_commit_availability()
            s.remove_indebted_nodes()
        s.communicator.comm.barrier()
        if s.communicator.rank != 0:
            s.change_node_ids(s.communicator.comm.recv(source=0))








    def choose_rotated_nodes(s):
        old_rotated_nodes = []
        for rank in range(1, s.communicator.nbRanks): # bez beacon chaina
            new_rotated_nodes = sample([(index, acc['id']) for index, acc in enumerate(s.accounts_info) if acc["shard"] == rank], s.config.nbMigrates)
            if old_rotated_nodes:
                for node in old_rotated_nodes:
                    s.accounts_info[node[0]]["shard"] += 1
            old_rotated_nodes = new_rotated_nodes
            if rank == (s.communicator.nbRanks - 1):
                for node in old_rotated_nodes:
                    s.accounts_info[node[0]]["shard"] = 1
            s.communicator.comm.send([node[1] for node in new_rotated_nodes], dest=rank) # wyjdzie jedna lista nodow
        # print(s.accounts_info, "TTTTTTT")

    def shuffle_nodes(s, peers_of_nodes_in_shard, migrant_ids):
        # usuwanie perrow poprzez rotowane wezly
        # print(migrant_ids, "GGGGGGGGGGG")
        for m in migrant_ids:
            del peers_of_nodes_in_shard[m]
        p_o_n = deepcopy(peers_of_nodes_in_shard)
        for peer in p_o_n.items():
            indexes = []
            for index, val, in enumerate(peer[1]):
                if val in migrant_ids:
                    indexes.append(index)
            for i in indexes[::-1]:
                del peers_of_nodes_in_shard[peer[0]][i]

        s.send_recv_migrants(migrant_ids)

    def send_recv_migrants(s, migrant_ids):
        if s.communicator.rank == 1:
            s.communicator.comm.send(migrant_ids, dest=2)
            s.supp_peers(s.communicator.comm.recv(source=s.communicator.nbRanks - 1))
        elif s.communicator.rank == (s.communicator.nbRanks-1):
            s.communicator.comm.send(migrant_ids, dest=1)
            s.supp_peers(s.communicator.comm.recv(source=s.communicator.rank-1))
        else:
            s.communicator.comm.send(migrant_ids, dest=s.communicator.rank+1)
            s.supp_peers(s.communicator.comm.recv(source=s.communicator.rank - 1))

    def supp_peers(s, recv_migrant_id):
        for i in recv_migrant_id:
            s.peers_of_nodes_in_shard[i] = []
        keys = list(s.peers_of_nodes_in_shard.keys())
        for u in keys:
            while len(s.peers_of_nodes_in_shard[u]) < s.config.nbPeers:
                s.peers_of_nodes_in_shard[u].append(choice(list(set(keys) - {u} - set(s.peers_of_nodes_in_shard[u]))))
        print(s.peers_of_nodes_in_shard, s.communicator.rank, "999")

    def send_transactions_to_beacon(s):
        for i in range(s.config.transactionsPerBlock):
            sender = choice(list(s.peers_of_nodes_in_shard))
            transaction = {
                "ID": f"{s.communicator.rank}x{randrange(10**50, 10**51)}",  # id transakcji -->numeru wysylajacego sharda
                "sender": sender,
                "receiver": choice(list((set(s.node_ids) - {sender}))),
                "amount": choice(range(1, s.config.max_pay))
            }
            s.shard_transactions.append(transaction)
        s.communicator.comm.send(s.shard_transactions, dest=0)

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
            s.communicator.comm.send(shard_trans, dest=index+1)

    def ramification_send_bad(s): # te rozgalezienia i i tak dalej robia sie poza beacon chainem ,wiec duzo zobostrzen jest pomijanych, jak na przyklad podowjne id transakcji. POza tym te bloki nie musza miez miejsca w beaconie. bo lekkie wezly biora transakcje z shardow a nie z beacon chaina
        ramification = []
        fake_transactions = []
        fake_transaction = {}
        money_in_block = 0
        while random() > 0.5:
            for tran in range(s.config.transactionsPerBlock): #DODAJEMY BLOK ROZGALEZIONY Z ZLYMI, LOSOWYMI TRANSAKCJAMI
                fake_transaction = {
                    "ID": f"{s.communicator.rank}x{randrange(10**50, 10**51)}",  # id transakcji -->numeru wysylajacego sharda
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

        received_transactions = s.communicator.comm.recv(source=0)
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
        s.communicator.comm.send((len(ramification) - 1), dest=0)  # tyle stawek bedzie palonych, bo tyle jest zlych bloków
        for block in ramification[:-1]: #ostatni blok jest spoko, wiec nie ma co palic. Zostawmy go :)
            s.communicator.comm.send([block.staker, block.stake], dest=0)

        for i in indexes[::-1]:
            del ramification[i]

        """zatwierdzenie niewlasciwej transakcji"""
        hostility = random()
        proper_transaction = ramification[-1]
        if hostility < 0.5:
            s.shard_blockchain.append(proper_transaction) #ostatnia to poprawna
        # elif ((hostility >= 0.5) and (hostility < 0.75)):
        #         proper_transaction.transaction = proper_transaction.transaction[:-1] # Usuwamy z bloku ostatnia transakcje. Tak sobie wymyslilismy
        #         s.shard_blockchain.append(proper_transaction)  # dodajemy blok bez jednej transakcji
        else:
            staker = choice(list(s.peers_of_nodes_in_shard.keys()))
            stake = choice(list(range(money_in_block, s.config.max_stake + 1)))
            s.block = Block(received_transactions, hash("whatever"), time(), staker, stake)
            s.block.create_tree()
            s.shard_blockchain.append(s.block)
        return ramification[-1]                     # dodanie ostatniego, poprawnego bloku


    def burning_stakes_ramification(s):
        """narazie zostawimy watek notariuszy"""
        for rank in range(1, s.communicator.nbRanks):
            nb_to_burn = s.communicator.comm.recv(source=rank)
            if nb_to_burn > 0:
                for i in range(nb_to_burn):
                    acc_burned = s.communicator.comm.recv(source=rank)
                    for ind, acc in enumerate(s.accounts_info):
                        if acc_burned[0] == acc['id']:
                            s.accounts_info[ind]['money'] -= acc_burned[1] #jak bedzie na minusie to go trzeba wywalicWYWALIC, ale po walidacji calego bloku, bo wczesniej wszystko jest w jendym

    def walidate_all_blockchain(s, blockchain, true_block):  #ALE USUWANY JEST ZAWSZE  OSTATNI, BO WCZESNIEJ ZAWSZE JEST OK. I JEST ZAWSZE ich dwa. W sensie jeden. Albo dobry albo zly
        to_send = "None"
        for index, block in enumerate(blockchain):
            if block.parent is not None:
                if block.parent != blockchain[index-1].block_id:
                    to_send = [block.staker, block.stake]
                    del s.shard_blockchain[index]
                    s.shard_blockchain.append(true_block)  #dodawanie poprawnego
                """block.transakcje sa niepelne i teraz o to chodzi, by to sprawdzicz czy ten atrybut jest ok , jesli nie to stakera bloku trzeba uwiesic za jaja itd. Trzeba to zrobic dla czwartego, ostaniego procesu rank==4 i trzeba bedzie stworzuyc nawa funkcje tylko dla niego"""
        s.communicator.comm.send(to_send, dest=0, tag=1) #ze niby none nie mozna wysylac . I dzieki temu bedziemy palic i usuwac

    #
    # def check_data_availability(s, blockchain, true_block): # tu bedzie sprawdzana transakcja
    #     to_send = "None"
    #     for index, block in enumerate(blockchain):
    #         transactions = block.transaction
    #         test_block = Block(transactions,  None, time(), None, None)
    #         test_block.create_tree()
    #         test_nb_leaves = test_block.mt.get_leaf_count()
    #         number_of_leaves = block.mt.get_leaf_count()
    #         if test_nb_leaves != number_of_leaves:
    #             to_send = [block.staker, block.stake]
    #             del s.shard_blockchain[index]
    #             s.shard_blockchain.append(true_block)  # dodawanie poprawnego
    #     s.communicator.comm.send(to_send, dest=0, tag="availability")
    #


    def burn_stake_bad_commit_availability(s):
        # """narazie zostawiamy watek notariuszy"""
        # # list_id = [acc['id'] for acc in s.accounts_info]
        # acc_burned = s.communicator.comm.recv(source=(s.communicator.nbRanks-1), tag="availability")
        # if acc_burned != "None":
        #     for index, acc in enumerate(s.accounts_info):
        #         if acc_burned[0] == acc['id']:
        #             s.accounts_info[index]['money'] -= acc_burned[1]

        for rank in range(1, s.communicator.nbRanks):
            acc_burned = s.communicator.comm.recv(source=rank, tag=1)
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
                interval = range(2000, ((s.communicator.nbRanks+1) * s.config.intervalID))
                old_id = acc['id']
                new_id = choice(list(set(interval) - {acc['id']} - set(list_id)))
                s.accounts_info[index]['id'] = new_id
                s.accounts_info[index]['money'] = s.config.start_money
                change_ids.append((old_id, new_id))
                list_id[index] = new_id
        for i in range(1, s.communicator.nbRanks):
            s.communicator.comm.send(change_ids, dest=i)

    """receive ids to change"""
    def change_node_ids(s, change_ids):   # W SUMIE TO SLABE BO ZAMIENIA WEZLAMI ,ALE TAK NAPRAWDE POWINNO BYC USUWANKO I POTEM DOBIOR WEZLOW TAK JAK NA GORZE ROBILEM, ALE JUZ NIE CHCE MI SIE
        print(change_ids)
        print(s.peers_of_nodes_in_shard, s.node_ids, s.communicator.rank, "wszystko czego dzis chce \n")
        new_peers_of_nodes_in_shard = deepcopy(s.peers_of_nodes_in_shard)
        for key, val in new_peers_of_nodes_in_shard.items():
            for change in change_ids:
                for index, vali in enumerate(val):
                    if vali == change[0]:
                        s.peers_of_nodes_in_shard[key][index] = change[1]
        for key in new_peers_of_nodes_in_shard:
            for change in change_ids:
                if key == change[0]:
                    s.peers_of_nodes_in_shard[change[1]] = s.peers_of_nodes_in_shard[change[0]]

        for change in change_ids:
            if change[0] in s.peers_of_nodes_in_shard.keys():
                s.peers_of_nodes_in_shard.pop(change[0])




        print(s.node_ids, s.communicator.rank, "wszystko czego dzis chce \n")
        for change in change_ids:
            for index, node in enumerate(s.node_ids):
                if node == change[0]:
                    s.node_ids[index] = change[1]
        print(s.node_ids, s.communicator.rank, "auu \n")








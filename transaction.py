from random import randrange
from communicator import Communicator


class Transaction:
    def __init__(self, rank, sender, consignor_id, receiving_id, amount):  #to id_bedzie problem
        self.commu = Communicator()
        self.trans_id = f"{rank}x{randrange(10**50, 10**51)}"
        self.consignor_id = consignor_id
        self.receiving_id = receiving_id
        self.amount = amount

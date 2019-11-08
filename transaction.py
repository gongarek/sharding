from random import randrange
from communicator import Communicator


class Transaction:
    def __init__(self, trans_id, consignor_id, receiving_id, balance):  #to id_bedzie problem
        self.commu = Communicator()
        if trans_id is None:
            self.trans_id = f"{self.commu.rank}x{randrange(10**50, 10**51)}"
        else:
            self.trans_id = trans_id
        self.consignor_id = consignor_id
        self.receiving_id = receiving_id
        self.balance = balance

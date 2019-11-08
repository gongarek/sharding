from merkletools import MerkleTools


class Block:
    def __init__(self, transaction, parent, time, staker, stake):
        self.transaction = transaction
        self.block_time = time
        self.parent = parent
        self.staker = staker
        self.stake = stake
        self.blockchain = []
        self.mt = MerkleTools(hash_type="md5")
        self.block_id = 0

    def create_tree(self):
        if self.transaction is not None:
            for tran in self.transaction:
                tran_string = ''
                for element in tran.values():
                    tran_string += (" " + str(element))
                self.mt.add_leaf(tran_string, True)
        self.mt.make_tree()
        self.block_id = hash((self.mt.get_merkle_root(), self.block_time, self.parent))

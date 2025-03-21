import sys 
sys.path.append('/Users/shash/Noctal') 

import configparser
from Blockchain.Backend.Core.block import Block
from Blockchain.Backend.Core.blockheader import BlockHeader
from Blockchain.Backend.util.util import hash256 , merkle_root, target_to_bits
from Blockchain.Backend.Core.database.database import BlockchainDB, NodeDB
from Blockchain.Backend.Core.tx import CoinbaseTx
from multiprocessing import Process, Manager
from Blockchain.Frontend.run import main
from Blockchain.Frontend.Gui.NoctalCore import mainGui
from Blockchain.Backend.Core.network.syncManager import syncManager
import time



GENESIS_HASH = '0' * 64
VERSION = 1 
INITIAL_TARGET = 0x0000FFFF00000000000000000000000000000000000000000000000000000000

class Blockchain:
    def __init__(self, utxos, MemPool):
        self.utxos = utxos
        self.MemPool = MemPool
        self.current_target = INITIAL_TARGET
        self.bits = target_to_bits(INITIAL_TARGET)


    def write_on_disk(self,block):
        blockchainDB = BlockchainDB()
        blockchainDB.write(block)
    

    def fetch_last_block(self):
        blockchainDB = BlockchainDB()
        return blockchainDB.lastBlock()


    def GenesisBlock(self):
        BlockHeight = 0
        prevBlockHash = GENESIS_HASH
        self.addBlock(BlockHeight, prevBlockHash)

    """ Start the Sync Node """
    def startSync(self):
        node = NodeDB()
        portList = node.read()
        
        for port in portList:
            if localHostPort != port:
                sync = syncManager(localHost, port)
                sync.startDownload()
                

    def store_utxos_in_cache(self):
        for tx in self.addTransactionsInBlock:
            print(f"Transaction added {tx.TxId} ")
            self.utxos[tx.TxId] = tx

    def remove_spent_Transactions(self):
        for txId_index in self.remove_spent_transactions:
            if txId_index[0].hex() in self.utxos:

                if len(self.utxos[txId_index[0].hex()].tx_outs) < 2:
                    print(f"Spent transaction removed {txId_index[0].hex()} ")
                    del self.utxos[txId_index[0].hex()]
                else:
                    prev_trans = self.utxos[txId_index[0].hex()]
                    self.utxos[txId_index[0].hex()] = prev_trans.tx_outs.pop(txId_index[1])

    
    """Read Transactions from Memory Pool"""
    def read_transactions_from_memorypool(self):
        self.Blocksize = 80 
        self.TxIds = []
        self.addTransactionsInBlock = []
        self.remove_spent_transactions = []

        for tx in MemPool:
            self.TxIds.append(bytes.fromhex(tx))
            self.addTransactionsInBlock.append(self.MemPool[tx])
            self.Blocksize += len(self.MemPool[tx].serialize())
            
            for spent in self.MemPool[tx].tx_ins:
                self.remove_spent_transactions.append([spent.prev_tx, spent.prev_index])

    
    def remove_transactions_from_memorypool(self):
        for tx in self.TxIds:
            if tx.hex() in self.MemPool:
                del self.MemPool[tx.hex()]


    def convert_to_json(self):
        self.TxJson = []

        for tx in self.addTransactionsInBlock:
            self.TxJson.append(tx.to_dict())


    def calculate_fee(self):
        self.input_amount = 0
        self.output_amount = 0

        for TxId_index in self.remove_spent_transactions:
            if TxId_index[0].hex() in self.utxos:
                self.input_amount += self.utxos[TxId_index[0].hex()].tx_outs[TxId_index[1]].amount

        for tx in self.addTransactionsInBlock:
            for tx_out in tx.tx_outs:
                self.output_amount += tx_out.amount

        self.fee = self.input_amount - self.output_amount


    def addBlock(self, BlockHeight, prevBlockHash):
        self.read_transactions_from_memorypool()
        self.calculate_fee()
        timestamp = int(time.time()) 
        coinbaseIstance = CoinbaseTx(BlockHeight)
        coinbaseTx = coinbaseIstance.CoinbaseTransaction()
        self.Blocksize += len(coinbaseTx.serialize())
    
        coinbaseTx.tx_outs[0].amount = coinbaseTx.tx_outs[0].amount + self.fee

        self.TxIds.insert(0, bytes.fromhex(coinbaseTx.id()))
        self.addTransactionsInBlock.insert(0, coinbaseTx)

        merkleRoot = merkle_root(self.TxIds)[::-1].hex()
        blockheader = BlockHeader(VERSION, prevBlockHash, merkleRoot, timestamp, self.bits) 
        blockheader.mine(self.current_target)

        self.remove_spent_Transactions()
        self.remove_transactions_from_memorypool()
        self.store_utxos_in_cache()
        self.convert_to_json()

        print(f"Block {BlockHeight} mined successfully with Nonce value of {blockheader.nonce}")
        self.write_on_disk([Block(BlockHeight, self.Blocksize, blockheader.__dict__, len(self.TxJson), self.TxJson).__dict__])

    def main(self):
        lastBlock = self.fetch_last_block()
        if lastBlock is None:
            self.GenesisBlock()

        while True:
            lastBlock = self.fetch_last_block()
            BlockHeight = lastBlock["Height"] + 1
            prevBlockHash = lastBlock['BlockHeader']['blockHash']
            self.addBlock(BlockHeight, prevBlockHash)

if __name__ == "__main__":

    config = configparser.ConfigParser()
    config.read('config.ini')
    localHost = config['DEFAULT']['host']
    localHostPort = int(config['MINER']['port'])
    webport = int(config['Webhost']['port'])

    with Manager() as manager:
        utxos = manager.dict()
        MemPool = manager.dict()
        
        gui = Process(target=mainGui, args=(utxos, MemPool, webport))
        gui.start()
        
        # If you want to  try the Noctal Explorer, disable the gui.
        #webapp = Process(target = main, args = (utxos, MemPool, webport))
        #webapp.start()

        """Start Server and Listen for miner requests"""
        sync = syncManager(localHost, localHostPort)
        starServer = Process(target = sync.SpinUpTheServer)
        starServer.start()

        blockchain = Blockchain(utxos, MemPool)
        blockchain.startSync()
        blockchain.main()

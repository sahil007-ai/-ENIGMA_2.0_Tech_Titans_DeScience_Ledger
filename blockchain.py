import os
import json
from web3 import Web3
from dotenv import load_dotenv

# --- Load Environment Variables ---
# This prevents your private keys from being exposed in your code!
load_dotenv()

RPC_URL = os.getenv("RPC_URL", "http://127.0.0.1:8545") # Default to local Ganache if not set
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS")
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")

# The ABI tells Python how to interact with your Solidity contract
CONTRACT_ABI = json.loads("""
[
    {
        "inputs": [{"internalType": "string", "name": "_sha256Hash", "type": "string"}, {"internalType": "string", "name": "_ipfsUri", "type": "string"}],
        "name": "anchorFile",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "string", "name": "_sha256Hash", "type": "string"}],
        "name": "verifyIntegrity",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function"
    }
]
""")

# Initialize Web3 Connection
w3 = Web3(Web3.HTTPProvider(RPC_URL))

# Only load the contract if we are actually connected
if w3.is_connected():
    contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=CONTRACT_ABI)
else:
    contract = None

# Provide an alias that other modules expect (`web3`) so imports are compatible
web3 = w3

def anchor_on_chain(sha256_hash, ipfs_uri):
    """Sends a transaction to the blockchain to permanently store the hash and URI."""
    if not w3.is_connected() or not contract:
        print("Warning: Blockchain not connected. Returning dummy transaction hash.")
        return "0xDummyTransactionHashForTestingOnly"

    # 1. Get dynamic network data
    nonce = w3.eth.get_transaction_count(WALLET_ADDRESS)
    chain_id = w3.eth.chain_id          # Dynamically gets 1337 for Ganache, 1 for Mainnet, etc.
    current_gas_price = w3.eth.gas_price # Dynamically gets the current network gas price

    # 2. Build the transaction
    txn = contract.functions.anchorFile(sha256_hash, ipfs_uri).build_transaction({
        'chainId': chain_id, 
        'gas': 2000000, # You could also use w3.eth.estimate_gas() here for precision
        'gasPrice': current_gas_price,
        'nonce': nonce,
    })

    # 3. Sign the transaction
    signed_txn = w3.eth.account.sign_transaction(txn, private_key=PRIVATE_KEY)

    # 4. Send the transaction
    tx_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)

    # 5. Wait for the transaction to be mined
    print(f"Transaction sent! Waiting for receipt... Tx Hash: {w3.to_hex(tx_hash)}")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    
    # Return the transaction hash as proof
    return w3.to_hex(tx_hash)

def verify_on_chain(sha256_hash):
    """Reads from the blockchain to check if the hash exists."""
    if not w3.is_connected() or not contract:
        raise ConnectionError("Failed to connect to the blockchain network.")
        
    is_authentic = contract.functions.verifyIntegrity(sha256_hash).call()
    return is_authentic
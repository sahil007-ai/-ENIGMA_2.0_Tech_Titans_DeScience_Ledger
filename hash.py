# task a file either csv or json and generate a hash for it using SHA 256. The hash should be unique for each file and should be stored in a database for future reference. The database should also store the file name, file type, and the date and time when the hash was generated. The system should also have a function to verify the integrity of the file by comparing the generated hash with the stored hash in the database. If the hashes match, it means the file has not been tampered with. If they do not match, it indicates that the file has been altered in some way. this file should return the hash value for the given file and also store it in the database along with the file name, file type, and timestamp. The database can be implemented using a IPFS database of your choice. The system should also have a function to verify the integrity of the file by comparing the generated hash with the stored hash in the database. If the hashes match, it means the file has not been tampered with. If they do not match, it indicates that the file has been altered in some way.

import hashlib
import os
import datetime
import json
import sqlite3
import requests

# IPFS Node API Endpoint (Default local node)
IPFS_API_URL = 'http://127.0.0.1:5001/api/v0/add'

# Setup local SQLite DB to keep track of IPFS CIDs
def setup_local_db():
    conn = sqlite3.connect('file_registry.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS file_records (
            file_name TEXT PRIMARY KEY,
            ipfs_cid TEXT NOT NULL
        )
    ''')
    conn.commit()
    return conn

def generate_file_hash(file_path):
    """Generates a SHA-256 hash for a given file."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"The file {file_path} does not exist.")
    
    sha256_hash = hashlib.sha256()
    # Read in chunks to handle large files efficiently
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
            
    return sha256_hash.hexdigest()

def store_file_metadata(file_path):
    """Generates hash, creates metadata, stores in IPFS, and logs CID locally."""
    conn = setup_local_db()
    cursor = conn.cursor()
    
    file_name = os.path.basename(file_path)
    file_type = os.path.splitext(file_name)[1].lower()
    
    if file_type not in ['.csv', '.json']:
        print("Warning: File type is not CSV or JSON, but proceeding anyway.")

    # 1. Generate the Hash
    file_hash = generate_file_hash(file_path)
    timestamp = datetime.datetime.now().isoformat()
    
    # 2. Create the Metadata Object
    metadata = {
        "file_name": file_name,
        "file_type": file_type,
        "timestamp": timestamp,
        "sha256_hash": file_hash
    }
    
    # 3. Store Metadata on IPFS
    try:
        files = {
            'file': ('metadata.json', json.dumps(metadata))
        }
        response = requests.post(IPFS_API_URL, files=files)
        response.raise_for_status()
        ipfs_cid = response.json()['Hash']
        
        # 4. Save mapping to local DB
        cursor.execute('''
            INSERT OR REPLACE INTO file_records (file_name, ipfs_cid)
            VALUES (?, ?)
        ''', (file_name, ipfs_cid))
        conn.commit()
        
        print(f"Success! Metadata stored on IPFS.")
        print(f"IPFS CID: {ipfs_cid}")
        print(f"Generated Hash: {file_hash}")
        
        return file_hash
        
    except requests.exceptions.RequestException as e:
        print(f"Failed to connect to IPFS node. Is it running? Error: {e}")
        return None
    finally:
        conn.close()

def verify_file_integrity(file_path):
    """Verifies the current file hash against the hash stored in IPFS."""
    conn = setup_local_db()
    cursor = conn.cursor()
    file_name = os.path.basename(file_path)
    
    # 1. Retrieve the IPFS CID for this file
    cursor.execute('SELECT ipfs_cid FROM file_records WHERE file_name = ?', (file_name,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        print(f"No record found for {file_name} in the registry.")
        return False
        
    ipfs_cid = row[0]
    
    # 2. Fetch the metadata from IPFS
    try:
        cat_url = f'http://127.0.0.1:5001/api/v0/cat?arg={ipfs_cid}'
        response = requests.post(cat_url)
        response.raise_for_status()
        stored_metadata = response.json()
        stored_hash = stored_metadata.get("sha256_hash")
        
    except requests.exceptions.RequestException as e:
        print(f"Failed to retrieve metadata from IPFS. Error: {e}")
        return False

    # 3. Generate current hash and compare
    current_hash = generate_file_hash(file_path)
    
    print(f"Stored Hash:  {stored_hash}")
    print(f"Current Hash: {current_hash}")
    
    if current_hash == stored_hash:
        print("Integrity Verified: The file has NOT been tampered with.")
        return True
    else:
        print("ALERT: File integrity compromised! The hashes do not match.")
        return False

# --- Example Usage ---
if __name__ == "__main__":
    # Create a dummy CSV file for testing
    test_file = "data.csv"
    with open(test_file, "w") as f:
        f.write("id,name,value\n1,Alice,100\n2,Bob,200")
        
    print("--- Storing File ---")
    store_file_metadata(test_file)
    
    print("\n--- Verifying Unaltered File ---")
    verify_file_integrity(test_file)
    
    print("\n--- Tampering with File ---")
    with open(test_file, "a") as f:
        f.write("\n3,Charlie,999") # Malicious actor alters the file
        
    print("\n--- Verifying Altered File ---")
    verify_file_integrity(test_file)
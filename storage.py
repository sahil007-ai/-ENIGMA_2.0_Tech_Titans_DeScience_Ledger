import hashlib
import os
import datetime
import requests
import json

# --- PINATA CLOUD CONFIGURATION ---
# Replace this with your actual Pinata JWT (Bearer Token)
PINATA_JWT = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySW5mb3JtYXRpb24iOnsiaWQiOiI5NTQ3NDBkNS03ZWJlLTRkYTMtOTczYi0wYzdjOWMzMzM2YTQiLCJlbWFpbCI6InNhaGlsc29teWFuaTAwN0BnbWFpbC5jb20iLCJlbWFpbF92ZXJpZmllZCI6dHJ1ZSwicGluX3BvbGljeSI6eyJyZWdpb25zIjpbeyJkZXNpcmVkUmVwbGljYXRpb25Db3VudCI6MSwiaWQiOiJGUkExIn0seyJkZXNpcmVkUmVwbGljYXRpb25Db3VudCI6MSwiaWQiOiJOWUMxIn1dLCJ2ZXJzaW9uIjoxfSwibWZhX2VuYWJsZWQiOmZhbHNlLCJzdGF0dXMiOiJBQ1RJVkUifSwiYXV0aGVudGljYXRpb25UeXBlIjoic2NvcGVkS2V5Iiwic2NvcGVkS2V5S2V5IjoiMjc4YzJhNjlkYTg2YzM4YTg5YjIiLCJzY29wZWRLZXlTZWNyZXQiOiJjNmYyNjg0MWQwYzhlMzgyMzlmNTUxNThiMjQ4OTUwNjY1OGRhM2YwMDljZmIwNGNmMjI4Mjg4YzE2YTViYzEwIiwiZXhwIjoxODAzNjgxNzg1fQ.eY51CSW9jMx7GZQKLfS-dz3xEMuVnAq49FfNlg2ZDto" 

PINATA_PIN_URL = "https://api.pinata.cloud/pinning/pinJSONToIPFS"
# Using a public IPFS gateway to read the files back
IPFS_GATEWAY_URL = "https://gateway.pinata.cloud/ipfs/" 

def generate_file_hash(file_path):
    """Generates a SHA-256 hash for a given file."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"The file {file_path} does not exist.")
    
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
            
    return sha256_hash.hexdigest()

def store_file_metadata(file_path):
    """
    Generates hash, creates metadata, pins it to IPFS via Pinata Cloud, 
    and returns the IPFS URL.
    """
    file_name = os.path.basename(file_path)
    file_type = os.path.splitext(file_name)[1].lower()
    
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
    
    # 3. Format the payload for Pinata
    payload = {
        "pinataContent": metadata,
        "pinataMetadata": {
            "name": f"Metadata_{file_name}" # Names the file in your Pinata dashboard
        }
    }
    
    headers = {
        "Authorization": f"Bearer {PINATA_JWT}",
        "Content-Type": "application/json"
    }
    
    # 4. Store Metadata on Pinata (IPFS)
    try:
        response = requests.post(PINATA_PIN_URL, json=payload, headers=headers)
        response.raise_for_status()
        
        # Extract the Content Identifier (CID) from Pinata's response
        ipfs_cid = response.json()['IpfsHash']
        
        # Construct the standard IPFS URL
        ipfs_url = f"ipfs://{ipfs_cid}"
        return ipfs_url
        
    except requests.exceptions.RequestException as e:
        print(f"Pinata Upload Failed. Check your JWT token and internet connection. Error: {e}")
        return None

def verify_file_integrity(file_path, ipfs_url):
    """
    Fetches the original hash from a public IPFS gateway and compares 
    it against the current file's hash.
    """
    if ipfs_url.startswith("ipfs://"):
        ipfs_cid = ipfs_url.replace("ipfs://", "")
    else:
        ipfs_cid = ipfs_url
        
    # Fetch the metadata from IPFS using a public gateway
    try:
        response = requests.get(f"{IPFS_GATEWAY_URL}{ipfs_cid}")
        response.raise_for_status()
        
        stored_metadata = response.json()
        stored_hash = stored_metadata.get("sha256_hash")
        
    except requests.exceptions.RequestException as e:
        print(f"Failed to retrieve metadata from IPFS gateway. Error: {e}")
        return False
    except json.JSONDecodeError:
        print("Data retrieved from IPFS is not valid JSON.")
        return False

    # Generate current hash and compare
    current_hash = generate_file_hash(file_path)
    
    return current_hash == stored_hash
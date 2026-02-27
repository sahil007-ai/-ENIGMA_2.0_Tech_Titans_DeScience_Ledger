# The De-Science Ledger

Lightweight web UI and services to anchor research data hashes to a blockchain, store metadata on IPFS (Pinata), and let verified oracles (universities/labs) confirm SHA/IPFS correctness.

This README explains how the project works, how to run it locally, and how the oracle verification and recent activity features operate.

**Status:** Development (Flask, local Ganache by default)

---

**Quick Overview**

- `app.py` — Flask application and routes (dashboard, auto-secure, verify, oracle auth).
- `storage.py` — Generates SHA-256 for files, pins metadata to IPFS via Pinata, and verifies metadata.
- `blockchain.py` — Web3 connection and `anchor_on_chain()` helper (returns a tx hash or dummy when offline). Exports `web3` as an alias.
- `templates/` — HTML templates for dashboard and oracle pages.
- `uploads/` — temporary storage while processing uploads.
- `file_registry.db` — SQLite DB used to store `registry` (anchored files) and `oracles`.

---

Getting started (local development)

1. Clone the repo and open the project folder.
2. Create and activate a Python virtual environment (Windows PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

3. Install dependencies (recommended packages used in this project):

```powershell
pip install flask web3 python-dotenv requests werkzeug
```

4. Copy and edit `.env` (the repo contains an example `.env`) to configure your environment. Key variables:

```
RPC_URL=http://127.0.0.1:8545      # Change to a Sepolia/Infura URL to point to Sepolia
CONTRACT_ADDRESS=0x...             # Contract address (optional during dev)
WALLET_ADDRESS=0x...               # Wallet used to sign transactions
PRIVATE_KEY=<hex>                  # Local private key used only for dev tests
FLASK_ENV=development
NETWORK_NAME="Sepolia Testnet"    # UI label only
SECRET_KEY=change-me               # Session secret for oracle logins
PINATA_JWT=<your-pinata-jwt>       # For IPFS pinning via Pinata
```

5. Start a local blockchain for testing (Ganache) or set `RPC_URL` to a Sepolia provider (Infura/Alchemy).

6. Run the app:

```powershell
python app.py
```

Open the dashboard at: http://127.0.0.1:5000/

---

How the main flow works (Auto-Secure / Anchor)

1. User uploads a file via the Dashboard > Auto-Secure form.
2. `storage.generate_file_hash()` computes the SHA-256 of the file.
3. `storage.store_file_metadata()` creates a metadata JSON and pins it to IPFS (Pinata). It returns an `ipfs://CID` URL.
4. `blockchain.anchor_on_chain(sha256, ipfs_url)` builds, signs, and sends a transaction (or returns a dummy tx hash if not connected).
5. After anchor success, the app inserts a record into the local `registry` table with `filename`, `sha256`, `ipfs_url`, `tx_hash`, and `timestamp` so it appears in Recent Chain Activity.
6. The dashboard shows Recent Chain Activity from the `registry` table.

Notes:

- If IPFS pinning fails (invalid PINATA_JWT or network issue), the anchor step is not attempted.
- The app now returns a `db_recorded` boolean in the Auto-Secure response so you can tell if the local registry persisted the entry.

---

Oracle workflow (Universities / Labs)

Purpose: let verified oracles confirm that a SHA and IPFS metadata match and are anchored.

Pages / endpoints:

- `GET/POST /oracle/register` — create an oracle account (email + password). Stored in `oracles` table with hashed password.
- `GET/POST /oracle/login` — sign in to access oracle dashboard.
- `GET /oracle/dashboard` — simple UI for oracles to submit `sha256` and `ipfs_url` for verification.
- `POST /oracle/verify` — endpoint that checks:
  - whether IPFS metadata at the given CID contains the same `sha256_hash` (calls public gateway), and
  - whether there is a local `registry` entry that contains a non-empty `tx_hash` for the SHA or IPFS URL.

Return value: JSON `{ is_valid: bool, matches_ipfs: bool, anchored: bool }`.

Important: Oracle accounts are simple username/password stored hashed with Werkzeug. For production, replace with a proper identity provider and require admin approval before allowing verification.

---

Database schema (SQLite in `file_registry.db`)

- Table `registry` (created on startup if missing):
  - `id` INTEGER PK
  - `filename` TEXT
  - `sha256` TEXT
  - `ipfs_url` TEXT
  - `tx_hash` TEXT
  - `timestamp` TEXT

- Table `oracles` (created on startup if missing):
  - `id` INTEGER PK
  - `email` TEXT UNIQUE
  - `name` TEXT
  - `org_type` TEXT
  - `password_hash` TEXT
  - `created_at` TEXT

If your table column names differ, update the SQL queries in `app.py` accordingly.

---

Switching to Sepolia (or any public network)

1. Get an RPC URL (Infura/Alchemy or your own node) for the Sepolia network.
2. Update `RPC_URL` in `.env` and restart the app.
3. If using a remote network you will need test ETH for transactions and the correct `CONTRACT_ADDRESS`/`WALLET_ADDRESS`/`PRIVATE_KEY` setup.

Example `.env` change:

```
RPC_URL=https://sepolia.infura.io/v3/YOUR_INFURA_KEY
NETWORK_NAME="Sepolia Testnet"
```

---

Troubleshooting

- If the dashboard shows `Current Block: Offline`, check `RPC_URL` and confirm `blockchain.web3.is_connected()`.
- If `db_recorded` is false after a successful anchor, check app logs for `Warning: failed to write registry record:` and make sure the process has write access to the workspace and `file_registry.db`.
- If IPFS pinning fails, verify `PINATA_JWT` and network connectivity.

Quick verification via Python REPL:

```python
from storage import generate_file_hash
from dotenv import load_dotenv
load_dotenv()
import blockchain
print('connected:', blockchain.web3.is_connected())
```

Query the registry manually (sqlite3):

```powershell
sqlite3 file_registry.db "SELECT id, filename, tx_hash, timestamp FROM registry ORDER BY timestamp DESC LIMIT 10;"
```

Security notes

- Do NOT commit real private keys (`PRIVATE_KEY`) or Pinata JWTs to source control.
- Use environment variables and restricted test keys for development.
- For production: move private-key operations to a secure signing service or hardware wallet.

Contributing

PRs welcome. If you add features that alter the DB schema, include a migration script or instructions.

License

MIT — see LICENSE file if included.

---

If you'd like, I can:

- Add an admin approval step for new oracle accounts.
- Log verification attempts to the DB.
- Wire up a tested Sepolia example using Infura and show an end-to-end anchor.

Enjoy — open issues or request specific changes and I will implement them.

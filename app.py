import os
import sqlite3
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from flask import redirect, url_for, session

# --- Import Custom Modules ---
# Import node data from our new dedicated file
from registered_nodes import get_registered_nodes, get_total_nodes_count

# Assuming these are your existing functional modules
# Note: Ensure these modules are correctly set up to use .env variables internally if needed.
try:
    from storage import store_file_metadata, verify_file_integrity, generate_file_hash
    from blockchain import anchor_on_chain, web3 # Importing web3 to get current block
except ImportError as e:
    print(f"Warning: Could not import core modules: {e}. Ensure blockchain.py and storage.py exist.")
    # Mocking for demonstration if files are missing during setup
    web3 = None

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key')

# --- Configuration ---
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'csv', 'json', 'txt'}
DATABASE_FILE = 'file_registry.db' # Pointing to your existing DB file

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB limit
NETWORK_NAME = os.getenv("NETWORK_NAME", "Unknown Network") # Fetched from .env

# Ensure the upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# --- Database Helper Functions ---
def get_db_connection():
    """Creates a connection to the existing file_registry.db"""
    # Check if DB exists first to avoid errors if running fresh
    if not os.path.exists(DATABASE_FILE):
        print(f"Warning: {DATABASE_FILE} not found. Dashboard data will be empty.")
        return None
        
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row # Allows accessing columns by name
    return conn

def ensure_oracles_table_exists():
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS oracles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            name TEXT,
            org_type TEXT,
            password_hash TEXT NOT NULL,
            created_at TEXT
        )
    ''')
    conn.commit()
    conn.close()

def create_oracle(email, name, org_type, password):
    ensure_oracles_table_exists()
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    pw_hash = generate_password_hash(password)
    cursor.execute("INSERT INTO oracles (email, name, org_type, password_hash, created_at) VALUES (?, ?, ?, ?, datetime('now'))",
                   (email, name, org_type, pw_hash))
    conn.commit()
    conn.close()

def authenticate_oracle(email, password):
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT password_hash FROM oracles WHERE email = ?', (email,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return False
    return check_password_hash(row[0], password)

def get_anchored_stats_from_db():
    """Queries the local DB for counts and recent activity."""
    conn = get_db_connection()
    if conn is None:
         return {"count": 0, "activity": []}

    try:
        cursor = conn.cursor()
        
        # 1. Get total count of anchored files
        # Assuming a table name like 'registry' or 'files'. Adjust if yours is different.
        # We count rows where a transaction hash exists (meaning it was anchored).
        cursor.execute("SELECT COUNT(*) FROM registry WHERE tx_hash IS NOT NULL")
        count_result = cursor.fetchone()
        total_anchored = count_result[0] if count_result else 0

        # 2. Get recent activity (last 5 anchored files)
        # Assuming columns: filename, tx_hash, timestamp (or created_at)
        cursor.execute("""
            SELECT filename, tx_hash, timestamp 
            FROM registry 
            WHERE tx_hash IS NOT NULL 
            ORDER BY timestamp DESC 
            LIMIT 5
        """)
        recent_rows = cursor.fetchall()
        
        activity_feed = []
        for row in recent_rows:
            # Format the data for the UI
            short_tx = f"{row['tx_hash'][:6]}...{row['tx_hash'][-4:]}"
            activity_feed.append({
                # You might want to format the timestamp string nicely here using datetime
                "text": f"File '{row['filename']}' anchored on-chain. Tx: {short_tx}",
                "time": row['timestamp'] 
            })
            
        conn.close()
        return {"count": total_anchored, "activity": activity_feed}
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if conn: conn.close()
        return {"count": 0, "activity": []}

def get_current_block_number():
    """Fetches real-time block number from the blockchain connection."""
    if web3 and web3.is_connected():
        try:
            return f"#{web3.eth.block_number:,}"
        except Exception as e:
            print(f"Error fetching block: {e}")
            return "Error"
    return "Offline"


# --- Helper Functions ---
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# --- Routes ---

@app.route('/')
def index():
    """Renders the main dashboard interface with Dynamic Data."""
    
    # 1. Gather Data from various sources
    db_stats = get_anchored_stats_from_db()
    total_nodes = get_total_nodes_count() # From registered_nodes.py
    current_block = get_current_block_number() # From real blockchain connection
    node_list = get_registered_nodes() # From registered_nodes.py

    # 2. Structure data for the template
    dashboard_data = {
        "stats": {
            "total_nodes": total_nodes,
            "data_batches": f"{db_stats['count']:,}", # comma format numbers
            "current_block": current_block,
            "network_name": NETWORK_NAME # From .env
        },
        "nodes": node_list,
        "activity": db_stats['activity']
    }
    
    return render_template('dashboard.html', **dashboard_data)


# --- Existing Transactional Routes (Kept the same as your previous code) ---

@app.route('/auto-secure', methods=['POST'])
def auto_secure_file():
    # ... (Keep your existing implementation of this function) ...
    # NOTE: Ensure your blockchain.anchor_on_chain function updates 
    # the file_registry.db with the new tx_hash so it shows up on the dashboard!
    if 'file' not in request.files:
        return jsonify({'error': 'No file part detected.'}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected.'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        try:
            # Step 1: Hash
            file_hash = generate_file_hash(filepath)
            
            # Step 2: IPFS
            ipfs_url = store_file_metadata(filepath)
            if not ipfs_url:
                return jsonify({'error': 'IPFS upload failed.'}), 500
                
            # Step 3: Blockchain Anchor
            # IMPORTANT: This function needs to return the tx_hash AND update your DB
            tx_hash = anchor_on_chain(file_hash, ipfs_url)
            
            return jsonify({
                'status': 'success',
                'message': 'File secured permanently!',
                'transaction_hash': tx_hash,
                'file_hash': file_hash,
                'ipfs_url': ipfs_url
            }), 200
            
        except Exception as e:
            return jsonify({'error': f"Processing failed: {str(e)}"}), 500
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)
    else:
        return jsonify({'error': 'Invalid file type.'}), 400

@app.route('/verify', methods=['POST'])
def verify_file():
     # ... (Keep your existing implementation) ...
     pass

@app.route('/about')
def about():
    return render_template('about.html')


# --- Oracle UI Routes (for universities / labs) ---
@app.route('/oracle/register', methods=['GET', 'POST'])
def oracle_register():
    if request.method == 'POST':
        email = request.form.get('email')
        name = request.form.get('name')
        org_type = request.form.get('org_type')
        password = request.form.get('password')
        try:
            create_oracle(email, name, org_type, password)
            return render_template('oracle_register.html', success=True)
        except Exception as e:
            return render_template('oracle_register.html', error=str(e))
    return render_template('oracle_register.html')


@app.route('/oracle/login', methods=['GET', 'POST'])
def oracle_login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        if authenticate_oracle(email, password):
            session['oracle_email'] = email
            return redirect(url_for('oracle_dashboard'))
        return render_template('oracle_login.html', error='Invalid credentials')
    return render_template('oracle_login.html')


@app.route('/oracle/logout')
def oracle_logout():
    session.pop('oracle_email', None)
    return redirect(url_for('oracle_login'))


@app.route('/oracle/dashboard')
def oracle_dashboard():
    if 'oracle_email' not in session:
        return redirect(url_for('oracle_login'))
    return render_template('oracle_dashboard.html', oracle_email=session.get('oracle_email'))


@app.route('/oracle/verify', methods=['POST'])
def oracle_verify():
    # Accepts form or JSON with 'sha256' and 'ipfs_url'
    data = request.get_json() if request.is_json else request.form
    sha = data.get('sha256') or data.get('sha')
    ipfs_url = data.get('ipfs_url') or data.get('ipfs')

    if not sha or not ipfs_url:
        return jsonify({'error': 'Missing parameters', 'is_valid': False}), 400

    # 1) Check IPFS metadata (if available) against provided sha
    try:
        from storage import IPFS_GATEWAY_URL
        import requests

        cid = ipfs_url.replace('ipfs://', '') if ipfs_url.startswith('ipfs://') else ipfs_url
        resp = requests.get(f"{IPFS_GATEWAY_URL}{cid}", timeout=10)
        resp.raise_for_status()
        meta = resp.json()
        stored_sha = meta.get('sha256_hash')
        matches_ipfs = (stored_sha == sha)
    except Exception as e:
        return jsonify({'error': f'Failed to fetch IPFS metadata: {e}', 'is_valid': False}), 500

    # 2) Optionally check local DB registry for anchored tx (best-effort)
    anchored = False
    try:
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            cur.execute('SELECT tx_hash, ipfs_url FROM registry WHERE sha256 = ? OR ipfs_url = ? LIMIT 1', (sha, ipfs_url))
            row = cur.fetchone()
            if row and row['tx_hash']:
                anchored = True
            conn.close()
    except Exception:
        anchored = False

    is_valid = matches_ipfs and anchored
    return jsonify({'is_valid': is_valid, 'matches_ipfs': matches_ipfs, 'anchored': anchored})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
import os
import json
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# --- Configuration ---
DATABASE_FILE = "medicines_data.json"
MEDICINES_DB = {}

# Load the database ONCE when the app starts
if os.path.exists(DATABASE_FILE):
    with open(DATABASE_FILE, 'r', encoding='utf-8') as f:
        MEDICINES_DB = json.load(f)
    print(f"✅ System Online: Loaded {len(MEDICINES_DB)} records.")
else:
    print("⚠️ Error: Database file not found. Run mimip.py first.")

@app.route('/')
def index():
    """Serves the frontend interface."""
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    """
    The missing link! This function receives the search request
    and looks it up in the JSON database.
    """
    data = request.get_json()
    brand_name = data.get('brand_name', '').strip().lower()

    if not brand_name:
        return jsonify({'status': 'error', 'message': 'Please enter a brand name.'}), 400

    # Backend Logic: Case-Insensitive Lookup
    found_key = None
    for key in MEDICINES_DB.keys():
        if key.lower() == brand_name:
            found_key = key
            break
    
    if not found_key:
        return jsonify({'status': 'not_found'})

    # If found, return the data
    drug_data = MEDICINES_DB[found_key]
    return jsonify({
        'status': 'success',
        'ingredient': drug_data.get('active_ingredient'),
        'data': drug_data.get('alternatives', [])
    })

if __name__ == '__main__':
    print("🚀 App running! Open: http://127.0.0.1:5001")
    app.run(port=5001, debug=True)
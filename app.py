import os
import requests
import json
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from trie import MedicineTrie  # Importing our custom search engine

# --- Setup ---
load_dotenv()
app = Flask(__name__)

# --- Configuration ---
API_KEY = os.getenv("FDA_API_KEY")
API_BASE_URL = "https://api.fda.gov/drug/label.json"

# --- THE SEARCH BRAIN (Data Structures) ---
# 1. The Trie: Used for "Type-ahead" search. It helps us find a medicine name fast.
medicine_trie = MedicineTrie()

# 2. The Group Index (Hash Map): Used to find "Siblings". 
# If you find "Advil", this list gives you "Motrin", "Ibuprofen", etc. instantly.
ingredient_index = {} 

# Flag to track if our local data loaded correctly
trie_ready = False

def load_trie_data():
    """
    This runs ONCE when the server starts. 
    It reads our 'medicines_data.json' file and organizes the data 
    into our smart data structures so searches are super fast (0.01s).
    """
    global trie_ready, ingredient_index
    try:
        print("🚀 Starting up: organizing data for fast searching...")
        
        # Open the local data file
        with open('medicines_data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            
            # Go through every medicine in our list...
            for generic_name, details in data.items():
                
                # Clean up the ingredient name (make it uppercase) so it's easy to match
                # e.g., "ibuprofen" becomes "IBUPROFEN"
                active_ing = details.get('active_ingredient', generic_name).upper()
                
                # --- STEP 1: PREPARE THE GROUP LIST ---
                # If we haven't seen this ingredient before, create a new empty list for it
                if active_ing not in ingredient_index:
                    ingredient_index[active_ing] = []
                
                # Create a neat package of data for the Generic name itself
                generic_entry = {
                    "product_name": generic_name,
                    "manufacturer": "Generic Category",
                    "active_ingredient": active_ing,
                    "source": "Local Fast Index"
                }
                
                # Add it to our "Group List" (Hash Map)
                ingredient_index[active_ing].append(generic_entry)
                
                # Teach the Search Engine (Trie) about this name
                medicine_trie.insert(generic_name, generic_entry)

                # --- STEP 2: PROCESS ALL BRAND NAMES ---
                # Now look at the brand names (like "Advil" or "Motrin") inside this generic
                alternatives = details.get('alternatives', [])
                for alt in alternatives:
                    p_name = alt.get('product_name')
                    
                    if p_name:
                        # Create a data package for the Brand Name
                        brand_entry = {
                            "product_name": p_name,
                            "manufacturer": alt.get('manufacturer', 'Unknown'),
                            "active_ingredient": active_ing,
                            "source": "Local Fast Index"
                        }
                        
                        # Add this brand to the "Group List" so it appears with its siblings
                        ingredient_index[active_ing].append(brand_entry)
                        
                        # Teach the Search Engine (Trie) about this brand name too
                        medicine_trie.insert(str(p_name), brand_entry)
                        
        trie_ready = True
        print(f"✅ Ready! I have memorized {len(ingredient_index)} different types of medicine.")
        
    except Exception as e:
        print(f"⚠️ Oops, something went wrong loading the data: {e}")
        print("System will continue running, but will rely ONLY on the slow FDA API.")
        trie_ready = False

# Run the loading function immediately
load_trie_data()


# --- FALLBACK: THE OLD ONLINE WAY (Slow but Reliable) ---

def _fetch_active_ingredient(brand_name):
    """Asks the FDA website: 'What ingredient is in this medicine?'"""
    clean_name = brand_name.replace('"', '').strip()
    params = {
        'api_key': API_KEY,
        'search': f'openfda.brand_name:"{clean_name}"',
        'limit': 1
    }
    try:
        response = requests.get(API_BASE_URL, params=params)
        response.raise_for_status() 
        data = response.json()
        if 'results' in data and data['results']:
            openfda_data = data['results'][0].get('openfda', {})
            if 'substance_name' in openfda_data:
                return ", ".join(openfda_data['substance_name'])
    except requests.exceptions.RequestException as e:
        print(f"API Error: {e}")
    return None

def _fetch_generics(active_ingredient, original_brand_name):
    """Asks the FDA website: 'Who else makes pills with this ingredient?'"""
    ingredients = [ing.strip() for ing in active_ingredient.split(',')]
    query_parts = [f'openfda.substance_name:"{ing}"' for ing in ingredients if ing]
    if not query_parts: return []

    search_query = " AND ".join(query_parts)
    params = {'api_key': API_KEY, 'search': search_query, 'limit': 50}
    
    try:
        response = requests.get(API_BASE_URL, params=params)
        if response.status_code == 404: return [] 
        response.raise_for_status()
        data = response.json()
        
        generics_found = []
        if 'results' in data:
            for item in data['results']:
                openfda_data = item.get('openfda', {})
                product_name_list = openfda_data.get('brand_name')
                if not product_name_list: continue 
                
                product_name = product_name_list[0]
                # Don't recommend the exact same brand the user just searched for
                if product_name.lower() != original_brand_name.lower():
                    generics_found.append({
                        'product_name': product_name,
                        'manufacturer': openfda_data.get('manufacturer_name', ["N/A"])[0],
                        'source': 'FDA Live API'
                    })
        return generics_found
    except requests.exceptions.RequestException:
        return []


# --- THE WEBSITE ROUTES ---

@app.route('/')
def index():
    return render_template('online.html')

@app.route('/search', methods=['POST'])
def search():
    """
    THE MAIN LOGIC:
    1. Try looking in our "Fast Memory" (Trie) first.
    2. If we find a match, find its ingredient.
    3. Use the ingredient to grab ALL similar medicines instantly.
    4. If we find NOTHING locally, go ask the FDA website (slower fallback).
    """
    data = request.get_json()
    brand_name = data.get('brand_name', '').strip()

    if not brand_name:
        return jsonify({'status': 'error', 'message': 'Please enter a brand name.'}), 400

    # --- STRATEGY 1: FAST LOCAL SEARCH ---
    if trie_ready:
        try:
            # Step A: Ask the Trie for a match
            # "Do we have anything that starts with..."
            initial_matches = medicine_trie.search_prefix(brand_name)
            
            if initial_matches:
                # Step B: Smart Expansion
                # "Okay, we found the drug. Now, let's find its FAMILY."
                best_match = initial_matches[0] 
                detected_ingredient = best_match.get('active_ingredient')
                
                # Step C: Instant Group Lookup
                # Check our Hash Map for the full list of siblings
                if detected_ingredient and detected_ingredient in ingredient_index:
                    full_list = ingredient_index[detected_ingredient]
                    
                    print(f"⚡ Fast Hit: User asked for '{brand_name}', we found '{detected_ingredient}', returning {len(full_list)} alternatives.")
                    
                    return jsonify({
                        'status': 'success',
                        'ingredient': detected_ingredient,
                        'data': full_list,
                        'search_method': 'In-Memory Trie + Hash Map',
                        'source_type': 'local'
                    })
                else:
                    # If we can't find the family, just return what the Trie found
                    return jsonify({
                        'status': 'success',
                        'ingredient': detected_ingredient or "Unknown",
                        'data': initial_matches,
                        'search_method': 'In-Memory Trie',
                        'source_type': 'local'
                    })
                    
        except Exception as e:
            print(f"Trie search error: {e}")
            # If our fast search crashes, don't panic. Just keep going to the API.

    # --- STRATEGY 2: SLOW ONLINE SEARCH (Fallback) ---
    print(f"🌐 Fast search failed. Asking FDA API for: {brand_name}")
    
    active_ingredient = _fetch_active_ingredient(brand_name)
    
    if not active_ingredient:
        return jsonify({
            'status': 'error', 
            'message': f"Sorry, I couldn't find details for '{brand_name}' in the database.",
            'source_type': 'api'
        })

    recommendations = _fetch_generics(active_ingredient, brand_name)

    if not recommendations:
        return jsonify({
            'status': 'not_found',
            'ingredient': active_ingredient,
            'message': f"Found ingredient '{active_ingredient}', but no other generic brands found.",
            'source_type': 'api'
        })
        
    return jsonify({
        'status': 'success',
        'ingredient': active_ingredient,
        'data': recommendations,
        'search_method': 'FDA Live API',
        'source_type': 'api'
    })

if __name__ == '__main__':
    debug_mode = os.getenv("FLASK_DEBUG", "False").lower() == "true"
    app.run(debug=debug_mode)
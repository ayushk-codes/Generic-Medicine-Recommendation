import os
import requests
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

# Load the secret keys from the .env file so they aren't exposed in the code
load_dotenv()

app = Flask(__name__)

# --- Config ---
# We grab the key safely from the environment now.
# Note: FDA API allows limited requests without a key, so None is okay for testing.
API_KEY = os.getenv("FDA_API_KEY")
API_BASE_URL = "https://api.fda.gov/drug/label.json"

def _fetch_active_ingredient(brand_name):
    """
    Asks the FDA database: "Hey, what's actually inside this brand name drug?"
    """
    # --- SECURITY/LOGIC FIX ---
    # We strip quotes to prevent users from breaking the search syntax (e.g. searching for 'Advil"')
    clean_name = brand_name.replace('"', '').strip()

    params = {
        'api_key': API_KEY,
        'search': f'openfda.brand_name:"{clean_name}"',
        'limit': 1
    }
    try:
        response = requests.get(API_BASE_URL, params=params)
        response.raise_for_status() # Check if the FDA server is happy
        data = response.json()
        
        if 'results' in data and data['results']:
            # We prefer 'substance_name' because it's usually cleaner data
            openfda_data = data['results'][0].get('openfda', {})
            if 'substance_name' in openfda_data:
                return ", ".join(openfda_data['substance_name'])
                
    except requests.exceptions.RequestException as e:
        print(f"Ouch, API call failed looking for {brand_name}: {e}")
        return None 
    return None

def _fetch_generics(active_ingredient, original_brand_name):
    """
    Now that we know the ingredients, we ask: "Who else makes a drug with these ingredients?"
    """
    # Clean up the ingredients list
    ingredients = [ing.strip() for ing in active_ingredient.split(',')]
    
    # Build a search query that looks like: ingredient A AND ingredient B
    query_parts = [f'openfda.substance_name:"{ing}"' for ing in ingredients]
    search_query = " AND ".join(query_parts)
    
    # Debug print just so we can see what's happening in the console
    print(f"DEBUG: Searching FDA for matches on: {search_query}") 

    params = {'api_key': API_KEY, 'search': search_query, 'limit': 50}
    
    try:
        response = requests.get(API_BASE_URL, params=params)
        
        # 404 isn't a crash, it just means "No matches found"
        if response.status_code == 404:
            return [] 
            
        response.raise_for_status()
        data = response.json()
        
        generics_found = []
        if 'results' in data:
            for item in data['results']:
                openfda_data = item.get('openfda', {})
                product_name_list = openfda_data.get('brand_name')

                if not product_name_list:
                    continue 

                product_name = product_name_list[0]
                
                # We don't want to recommend the exact same brand the user just typed in
                if product_name.lower() != original_brand_name.lower():
                    
                    # Double check: ensure ingredients match exactly
                    api_ingredients = set(ing.upper() for ing in openfda_data.get('substance_name', []))
                    local_ingredients = set(ing.upper() for ing in ingredients)

                    if api_ingredients == local_ingredients:
                        generics_found.append({
                            'product_name': product_name,
                            'manufacturer': openfda_data.get('manufacturer_name', ["N/A"])[0]
                        })
            return generics_found
            
    except requests.exceptions.RequestException as e:
        print(f"API struggled looking for generics: {e}")
        return []
    return []

@app.route('/')
def index():
    """Serves the actual webpage."""
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    """
    The JavaScript on the frontend talks to this part.
    It sends a name, we do the heavy lifting, and send back JSON.
    """
    data = request.get_json()
    brand_name = data.get('brand_name', '').strip()

    if not brand_name:
        return jsonify({'status': 'error', 'message': 'Please enter a brand name.'}), 400

    # --- SECURITY FIX ---
    # Prevent massive strings from clogging the server
    if len(brand_name) > 100:
        return jsonify({'status': 'error', 'message': 'Brand name is too long (max 100 characters).'}), 400

    # Step 1: Identify what the drug actually is
    active_ingredient = _fetch_active_ingredient(brand_name)
    
    if not active_ingredient:
        return jsonify({
            'status': 'error', 
            'message': f"Sorry, I couldn't figure out the ingredients for '{brand_name.title()}'."
        })

    # Step 2: Find the alternatives
    recommendations = _fetch_generics(active_ingredient, brand_name)

    if not recommendations:
        return jsonify({
            'status': 'not_found',
            'ingredient': active_ingredient,
            'message': f"I found that the active ingredient is '{active_ingredient}', but I couldn't find other generic brands in the database."
        })
        
    # Step 3: Success! Send the data back.
    return jsonify({
        'status': 'success',
        'ingredient': active_ingredient,
        'data': recommendations
    })

if __name__ == '__main__':
    # --- Security Fix for Production ---
    # We never want 'debug=True' on a live server (AWS/Heroku/Render).
    # We check the .env file for 'FLASK_DEBUG'. If not found, it defaults to False.
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    app.run(debug=debug_mode)
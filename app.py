import os
import requests
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

# --- Setup ---
# Load secret keys from the .env file.
load_dotenv()

app = Flask(__name__)

# --- Configuration ---
API_KEY = os.getenv("FDA_API_KEY")
API_BASE_URL = "https://api.fda.gov/drug/label.json"


def _fetch_active_ingredient(brand_name):
    """
    Step 1: Ask the FDA database: "Hey, what is actually inside this brand name drug?"
    """
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
        print(f"Error fetching ingredient for {brand_name}: {e}")
        return None 
    return None


def _fetch_generics(active_ingredient, original_brand_name):
    """
    Step 2: Ask: "Who else makes a drug with these EXACT ingredients?"
    """
    ingredients = [ing.strip() for ing in active_ingredient.split(',')]
    query_parts = [f'openfda.substance_name:"{ing}"' for ing in ingredients if ing]
    
    if not query_parts:
        return []

    search_query = " AND ".join(query_parts)
    params = {'api_key': API_KEY, 'search': search_query, 'limit': 50}
    
    try:
        response = requests.get(API_BASE_URL, params=params)
        
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
                
                if product_name.lower() != original_brand_name.lower():
                    api_ingredients = set(ing.upper() for ing in openfda_data.get('substance_name', []))
                    local_ingredients = set(ing.upper() for ing in ingredients)

                    if api_ingredients == local_ingredients:
                        generics_found.append({
                            'product_name': product_name,
                            'manufacturer': openfda_data.get('manufacturer_name', ["N/A"])[0]
                        })
            return generics_found
            
    except requests.exceptions.RequestException:
        return []
    return []


# --- Routes ---

@app.route('/')
def index():
    """Serves the main homepage."""
    # --- FIX IS HERE ---
    # We explicitly tell Flask to load the ONLINE HTML file
    return render_template('online.html')

@app.route('/search', methods=['POST'])
def search():
    """
    API Endpoint: Processes the search request.
    """
    data = request.get_json()
    brand_name = data.get('brand_name', '').strip()

    if not brand_name:
        return jsonify({'status': 'error', 'message': 'Please enter a brand name.'}), 400

    if len(brand_name) > 100:
        return jsonify({'status': 'error', 'message': 'Brand name is too long.'}), 400

    # Step 1: Identify drug
    active_ingredient = _fetch_active_ingredient(brand_name)
    
    if not active_ingredient:
        return jsonify({
            'status': 'error', 
            'message': f"Sorry, I couldn't find details for '{brand_name}' in the FDA database."
        })

    # Step 2: Find alternatives
    recommendations = _fetch_generics(active_ingredient, brand_name)

    if not recommendations:
        return jsonify({
            'status': 'not_found',
            'ingredient': active_ingredient,
            'message': f"I found the ingredient is '{active_ingredient}', but I couldn't find other generic brands."
        })
        
    return jsonify({
        'status': 'success',
        'ingredient': active_ingredient,
        'data': recommendations
    })

if __name__ == '__main__':
    debug_mode = os.getenv("FLASK_DEBUG", "False").lower() == "true"
    app.run(debug=debug_mode)
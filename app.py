import os
import requests
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

# --- Setup ---
# Load secret keys from the .env file.
# This ensures we don't accidentally push our API keys to GitHub.
load_dotenv()

app = Flask(__name__)

# --- Configuration ---
# We grab the API key safely from the environment.
# If the key is missing (None), the app will still run but might hit rate limits.
API_KEY = os.getenv("FDA_API_KEY")
API_BASE_URL = "https://api.fda.gov/drug/label.json"


def _fetch_active_ingredient(brand_name):
    """
    Step 1: Ask the FDA database: "Hey, what is actually inside this brand name drug?"
    Returns a string of ingredients (e.g., "IBUPROFEN") or None.
    """
    # Security Clean-up: 
    # Users might accidentally type quotes (e.g., 'Advil"'). We strip them to prevent
    # breaking the strict FDA search syntax.
    clean_name = brand_name.replace('"', '').strip()

    params = {
        'api_key': API_KEY,
        'search': f'openfda.brand_name:"{clean_name}"',
        'limit': 1
    }
    
    try:
        response = requests.get(API_BASE_URL, params=params)
        response.raise_for_status() # Check if the FDA server is happy (200 OK)
        data = response.json()
        
        # Check if we actually got a valid result
        if 'results' in data and data['results']:
            openfda_data = data['results'][0].get('openfda', {})
            
            # We prefer 'substance_name' because it is the cleanest field for ingredients
            if 'substance_name' in openfda_data:
                return ", ".join(openfda_data['substance_name'])
                
    except requests.exceptions.RequestException as e:
        # If the API fails, we log it (print it) and return nothing so the app doesn't crash.
        print(f"Error fetching ingredient for {brand_name}: {e}")
        return None 
    return None


def _fetch_generics(active_ingredient, original_brand_name):
    """
    Step 2: Now that we know the ingredients, we ask: 
    "Who else makes a drug with these EXACT ingredients?"
    """
    # Break down the ingredients into a clean list
    ingredients = [ing.strip() for ing in active_ingredient.split(',')]
    
    # Build a precise search query.
    # Logic: Search for (Ingredient A) AND (Ingredient B)
    query_parts = [f'openfda.substance_name:"{ing}"' for ing in ingredients if ing]
    
    if not query_parts:
        return []

    search_query = " AND ".join(query_parts)
    params = {'api_key': API_KEY, 'search': search_query, 'limit': 50}
    
    try:
        response = requests.get(API_BASE_URL, params=params)
        
        # 404 isn't a crash here; it just means "No other matches found."
        if response.status_code == 404:
            return [] 
            
        response.raise_for_status()
        data = response.json()
        
        generics_found = []
        if 'results' in data:
            for item in data['results']:
                openfda_data = item.get('openfda', {})
                product_name_list = openfda_data.get('brand_name')

                # Skip if the drug has no name (data can be messy)
                if not product_name_list: 
                    continue 

                product_name = product_name_list[0]
                
                # Filter 1: Don't recommend the exact brand the user just searched for.
                if product_name.lower() != original_brand_name.lower():
                    
                    # Filter 2: CRITICAL SAFETY CHECK 
                    # We must ensure the ingredients match EXACTLY.
                    # Example: If user searches for Tylenol (Acetaminophen), 
                    # we must NOT recommend Excedrin (Acetaminophen + Caffeine).
                    
                    # Convert both lists to SETS to ignore order (A, B == B, A)
                    api_ingredients = set(ing.upper() for ing in openfda_data.get('substance_name', []))
                    local_ingredients = set(ing.upper() for ing in ingredients)

                    if api_ingredients == local_ingredients:
                        generics_found.append({
                            'product_name': product_name,
                            'manufacturer': openfda_data.get('manufacturer_name', ["N/A"])[0]
                        })
            return generics_found
            
    except requests.exceptions.RequestException:
        # Silently fail on network errors for this step
        return []
    return []


# --- Routes ---

@app.route('/')
def index():
    """Serves the main homepage (the HTML file)."""
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    """
    API Endpoint: The frontend sends a brand name here.
    We process it and send back a JSON response.
    """
    data = request.get_json()
    brand_name = data.get('brand_name', '').strip()

    # --- Basic Validation ---
    if not brand_name:
        return jsonify({'status': 'error', 'message': 'Please enter a brand name.'}), 400

    # Prevent massive strings from clogging the server or API
    if len(brand_name) > 100:
        return jsonify({'status': 'error', 'message': 'Brand name is too long (max 100 chars).'}), 400

    # --- Step 1: Find what the drug is ---
    active_ingredient = _fetch_active_ingredient(brand_name)
    
    if not active_ingredient:
        return jsonify({
            'status': 'error', 
            'message': f"Sorry, I couldn't find details for '{brand_name}' in the FDA database."
        })

    # --- Step 2: Find alternatives ---
    recommendations = _fetch_generics(active_ingredient, brand_name)

    if not recommendations:
        return jsonify({
            'status': 'not_found',
            'ingredient': active_ingredient,
            'message': f"I found the ingredient is '{active_ingredient}', but I couldn't find other generic brands."
        })
        
    # --- Step 3: Success ---
    return jsonify({
        'status': 'success',
        'ingredient': active_ingredient,
        'data': recommendations
    })

if __name__ == '__main__':
    # --- Production vs Development ---
    # We check the environment variable. If FLASK_DEBUG is not set, we default to False.
    # This prevents the debug console (and security holes) from appearing on the live public site.
    debug_mode = os.getenv("FLASK_DEBUG", "False").lower() == "true"
    app.run(debug=debug_mode)
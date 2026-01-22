import requests
import json
import time
import os
from dotenv import load_dotenv

# --- Setup ---
# Load secrets securely. 
# This ensures your API key stays in .env and never gets pushed to Git.
load_dotenv()

# --- Configuration ---
API_KEY = os.getenv("FDA_API_KEY")
OUTPUT_FILE = "medicines_data.json"  # JSON is faster/better for apps than CSV
INPUT_FILE = "brand_names.txt"       # The list of drugs you want to support offline
API_BASE_URL = "https://api.fda.gov/drug/label.json"

def load_brand_names(filename=INPUT_FILE):
    """Reads the list of brands (e.g., Tylenol, Advil) from a text file."""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            names = [line.strip() for line in f if line.strip()]
        print(f"✅ Loaded {len(names)} brands from '{filename}'.")
        return names
    except FileNotFoundError:
        print(f"🛑 Error: Could not find '{filename}'. Please create this file with a list of drug names (one per line).")
        return []

def get_active_ingredient(brand_name, api_key):
    """
    Step 1: Asks the FDA: 'What chemicals are actually inside this brand?'
    Returns a LIST of ingredients to enable strict safety checks later.
    """
    # Sanitize input to prevent API errors
    clean_name = brand_name.replace('"', '').strip()
    
    params = {
        'api_key': api_key,
        'search': f'openfda.brand_name:"{clean_name}"',
        'limit': 1
    }
    try:
        response = requests.get(API_BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()
        
        if 'results' in data and data['results']:
            openfda = data['results'][0].get('openfda', {})
            
            # We prefer 'substance_name' because it's the standard chemical name
            if 'substance_name' in openfda:
                return openfda['substance_name'] # Returns a LIST ['Ingredient A', 'Ingredient B']
            
    except requests.exceptions.RequestException as e:
        print(f"   -> API Warning for {brand_name}: {e}")
    
    return None

def get_generics(active_ingredients_list, original_brand, api_key):
    """
    Step 2: Asks the FDA: 'Who else makes drugs with these EXACT ingredients?'
    """
    generics = []
    
    # Clean up the ingredients (remove details like 'USP' or brackets)
    clean_ingredients = [ing.split('(')[0].strip() for ing in active_ingredients_list]
    
    # Build Query: Ingredient A AND Ingredient B
    query_parts = [f'openfda.substance_name:"{ing}"' for ing in clean_ingredients]
    search_query = " AND ".join(query_parts)
    
    params = {'api_key': api_key, 'search': search_query, 'limit': 100}
    
    try:
        response = requests.get(API_BASE_URL, params=params)
        
        # 404 is normal - just means no other generics exist
        if response.status_code == 404:
            return [] 

        response.raise_for_status()
        data = response.json()
        
        if 'results' in data:
            for item in data['results']:
                openfda = item.get('openfda', {})
                product_names = openfda.get('brand_name')

                if not product_names: continue

                product_name = product_names[0]
                
                # Filter 1: Skip the brand we just searched for
                if product_name.lower() == original_brand.lower():
                    continue

                # --- CRITICAL SAFETY CHECK ---
                # We compare the SET of ingredients.
                # If we search for 'Tylenol' (Acetaminophen), we must NOT return 
                # 'Excedrin' (Acetaminophen + Caffeine). Sets ignore order, which is perfect.
                found_ingredients = set(ing.upper() for ing in openfda.get('substance_name', []))
                required_ingredients = set(ing.upper() for ing in active_ingredients_list)

                if found_ingredients == required_ingredients:
                    generics.append({
                        'product_name': product_name,
                        'manufacturer': openfda.get('manufacturer_name', ["Unknown"])[0]
                    })
            return generics
            
    except requests.exceptions.RequestException:
        return []
    return []

if __name__ == "__main__":
    if not API_KEY:
        print("🛑 Error: API Key missing from .env file.")
    else:
        brand_names = load_brand_names()
        
        if brand_names:
            print(f"\n🚀 Starting data collection for {len(brand_names)} drugs...")
            print("   (This runs securely online to build your offline database)\n")
            
            # We use a Dictionary/Map structure for fast offline lookups
            final_database = {} 
            
            for brand in brand_names:
                print(f"🔎 Processing: {brand}")
                
                # 1. Get Ingredients
                ingredients_list = get_active_ingredient(brand, API_KEY)
                
                if ingredients_list:
                    ing_str = ", ".join(ingredients_list)
                    print(f"   -> Ingredients: {ing_str}")
                    
                    # 2. Get Safe Generics
                    alternatives = get_generics(ingredients_list, brand, API_KEY)
                    print(f"   -> Found {len(alternatives)} strict matches.")
                    
                    # 3. Add to our database
                    final_database[brand] = {
                        "active_ingredient": ing_str,
                        "alternatives": alternatives
                    }
                else:
                    print(f"   -> ⚠️ Could not verify ingredients. Skipping.")
                
                # Sleep to respect FDA API limits
                time.sleep(0.5)

            # Save as JSON (Better than CSV for apps)
            if final_database:
                print(f"\n✅ Done! Saving {len(final_database)} records to '{OUTPUT_FILE}'...")
                with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                    json.dump(final_database, f, indent=4)
                print("🎉 Database created successfully! Your offline app can now use this file.")
            else:
                print("\n⏹️ No data collected.")
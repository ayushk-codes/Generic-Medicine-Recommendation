import json
import os

# --- Configuration ---
# We use the same JSON database as the offline web app
DATABASE_FILE = "medicines_data.json"

def load_database():
    """
    Loads the medicine 'dictionary' into memory.
    """
    if not os.path.exists(DATABASE_FILE):
        return None
    
    try:
        with open(DATABASE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return None

def recommend_generics(brand_name_input, db):
    """
    Looks up the brand in our dictionary.
    """
    search_term = brand_name_input.strip().lower()
    
    # 1. Find the key (Case-insensitive search)
    # We scan keys because 'tylenol' should match 'Tylenol'
    found_key = None
    for key in db.keys():
        if key.lower() == search_term:
            found_key = key
            break
            
    if not found_key:
        return "not_found"
        
    # 2. Get the data
    drug_data = db[found_key]
    alternatives = drug_data.get('alternatives', [])
    active_ingredient = drug_data.get('active_ingredient', 'Unknown')
    
    if not alternatives:
        return {"status": "no_generics", "ingredient": active_ingredient}
        
    return {
        "status": "success",
        "ingredient": active_ingredient,
        "data": alternatives
    }

# --- Main Interaction ---
if __name__ == "__main__":
    print("\n💊 Generic Medicine Recommendation System (Offline CLI)")
    
    # Load data once at startup
    database = load_database()
    
    if not database:
        print(f"🛑 Error: Could not load '{DATABASE_FILE}'.")
        print("   -> Did you run 'mimip.py' to download the data first?")
        exit()

    print(f"✅ Database loaded with {len(database)} medicines.")
    print("Type a brand name (e.g., Ibuprofen, Amoxicillin) or 'quit' to exit.")

    while True:
        user_input = input("\n🔎 Enter a brand name: ")
        
        if user_input.lower() in ['quit', 'exit']:
            print("👋 Stay healthy! Goodbye.")
            break
        
        if not user_input.strip():
            continue

        result = recommend_generics(user_input, database)
        
        if result == "not_found":
            print(f"❌ Sorry, I don't have data for '{user_input}' in the offline list.")
            
        elif result["status"] == "no_generics":
            print(f"ℹ️  Found '{user_input}' (Ingredient: {result['ingredient']}).")
            print("   However, I couldn't find any exact generic matches recorded.")
            
        elif result["status"] == "success":
            print(f"✅ Found '{user_input}' (Ingredient: {result['ingredient']}).")
            print(f"   Here are {len(result['data'])} alternatives:\n")
            
            # Print a neat header
            print(f"   {'Product Name':<30} | {'Manufacturer'}")
            print(f"   {'-'*30} | {'-'*20}")
            
            for item in result['data']:
                print(f"   {item['product_name']:<30} | {item['manufacturer']}")
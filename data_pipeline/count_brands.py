import json
import os

# --- Configuration ---
# We check the new JSON database file
DATABASE_FILE = "medicines_data.json"

print("Reading your dataset...")

if not os.path.exists(DATABASE_FILE):
    print(f"🛑 Error: Couldn't find '{DATABASE_FILE}'.")
    print("   -> Run 'mimip.py' to build the database first.")
    exit()

try:
    with open(DATABASE_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    # In our JSON structure, the keys of the dictionary ARE the brand names.
    brands = list(data.keys())
    count = len(brands)

    print(f"✅ You have data for {count} unique brand-name medicines.")
    
    if count > 0:
        print("\nHere are the names you can test with:")
        # Sort them alphabetically so it's easier to read
        for brand in sorted(brands):
            print(f"- {brand}")
    else:
        print("\n⚠️ The database file exists, but it's empty.")

except json.JSONDecodeError:
    print(f"🛑 Error: The file '{DATABASE_FILE}' seems corrupted or not valid JSON.")
except Exception as e:
    print(f"🛑 Unexpected error: {e}")
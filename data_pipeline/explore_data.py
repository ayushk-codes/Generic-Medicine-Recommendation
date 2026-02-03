import json
import os

# The file we want to check out (Now it's JSON!)
DATA_FILE = "medicines_data.json"

print(f"📊 Opening up {DATA_FILE} to see what we've got...\n")

try:
    # Load the data using standard Python JSON library
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print("✅ File loaded! Let's take a look.")

except FileNotFoundError:
    print(f"🛑 Error: I couldn't find '{DATA_FILE}'.")
    print("   Make sure you ran 'mimip.py' first to build the database!")
    exit()
except json.JSONDecodeError:
    print(f"🛑 Error: The file '{DATA_FILE}' seems broken or empty.")
    exit()

# --- 1. Health Check ---
total_drugs = len(data)
print(f"\n--- Dataset Summary ---")
print(f"Total Drugs in Database: {total_drugs}")

if total_drugs == 0:
    print("⚠️ The database is empty. Add brand names to 'brand_names.txt' and run the builder again.")
    exit()

# --- 2. What brands are inside? ---
print("\n--- Brands Collection ---")
brand_names = list(data.keys())
# Print just the first 10 so we don't spam the console
print(f"First 10 brands: {', '.join(brand_names[:10])}...")

# --- 3. Deep Dive into a Sample ---
# Let's pick the first drug and show exactly what the offline app sees
sample_brand = brand_names[0]
sample_data = data[sample_brand]

print(f"\n--- Deep Dive: '{sample_brand}' ---")
print(f"💊 Active Ingredient: {sample_data.get('active_ingredient', 'Unknown')}")
print(f"🔄 Alternatives Found: {len(sample_data.get('alternatives', []))}")

# Show a few alternatives if they exist
if sample_data.get('alternatives'):
    print("   Sample Alternatives:")
    for alt in sample_data['alternatives'][:3]: # Just show top 3
        print(f"    - {alt['product_name']} (by {alt['manufacturer']})")

# --- 4. Statistics ---
print("\n--- Quick Stats ---")
# Count how many have 0 alternatives
zeros = sum(1 for d in data.values() if not d.get('alternatives'))
print(f"Drugs with NO generics found: {zeros}")
print(f"Drugs WITH generics found:    {total_drugs - zeros}")

print("\n✅ Data looks good for the offline app!")
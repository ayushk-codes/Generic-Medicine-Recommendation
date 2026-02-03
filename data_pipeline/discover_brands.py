import requests
import os
from dotenv import load_dotenv

# Load your secrets from the .env file so they stay safe locally
load_dotenv()

# --- Config ---
# We grab the key from the environment.
API_KEY = os.getenv("FDA_API_KEY")
API_BASE_URL = "https://api.fda.gov/drug/label.json"
OUTPUT_FILE = "brand_names.txt"

# How many top brands to fetch? 
# 100 is good for testing. For a real app, you might want 500 or 1000.
NUMBER_TO_FETCH = 100

print(f"🚀 Starting up! I'm going to ask the FDA for the top {NUMBER_TO_FETCH} brand names...")

if not API_KEY:
    print("🛑 Whoops! I couldn't find your API key. Make sure it's in the .env file.")
    exit()

# We use the 'count' feature to see which names appear most often in the FDA records
params = {
    'api_key': API_KEY,
    'count': 'openfda.brand_name.exact',
    'limit': NUMBER_TO_FETCH 
}

try:
    response = requests.get(API_BASE_URL, params=params)
    response.raise_for_status()
    data = response.json()

    if 'results' in data:
        discovered_names = [item['term'] for item in data['results']]
        
        # --- Cleaning Phase ---
        # We want real brand names, not generic packaging terms like "KIT" or "TABLET".
        cleaned_names = []
        excluded_words = ['KIT', 'TRAY', 'TABLET', 'RELIEF', 'USP', 'HCL']
        
        for name in discovered_names:
            # 1. Must be longer than 2 letters
            # 2. Must not contain exclusion words (e.g. "Oxygen USP")
            if len(name) > 2 and not any(word in name.upper() for word in excluded_words):
                 cleaned_names.append(name.title()) # Clean formatting: "ADVIL" -> "Advil"
        
        print(f"✅ Awesome, I found and cleaned up {len(cleaned_names)} names.")

        # Save them to our text file
        # CRITICAL FIX: We use encoding='utf-8' so this works on Windows, Mac, and Linux equally.
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            for name in cleaned_names:
                f.write(name + "\n")
        
        print(f"🎉 Done! The list is saved in '{OUTPUT_FILE}'.")
        print("   -> Next step: Run 'mimip.py' to get the ingredients for these brands.")

except requests.exceptions.RequestException as e:
    print(f"🛑 Something went wrong connecting to the API: {e}")
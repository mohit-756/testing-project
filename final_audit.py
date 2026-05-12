import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

def get_models(api_key):
    url = f"https://generativelanguage.googleapis.com/v1/models?key={api_key}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return [m.get("name") for m in r.json().get("models", [])]
        else:
            return f"Error {r.status_code}: {r.text}"
    except Exception as e:
        return str(e)

primary = os.getenv("GEMINI_API_KEY")
secondary = os.getenv("GEMINI_API_KEY_SECONDARY")

results = {
    "primary": get_models(primary) if primary else "Missing",
    "secondary": get_models(secondary) if secondary else "Missing"
}

with open("audit_results_final.json", "w") as f:
    json.dump(results, f, indent=2)
print("Saved to audit_results_final.json")

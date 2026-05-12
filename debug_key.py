import os
from dotenv import load_dotenv

load_dotenv()

key = os.getenv("GROQ_API_KEY")
if key:
    print(f"Key found. Length: {len(key)}")
    print(f"Starts with: {key[:10]}...")
    print(f"Ends with: ...{key[-5:]}")
else:
    print("GROQ_API_KEY NOT FOUND in environment.")

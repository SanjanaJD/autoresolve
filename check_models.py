import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    print("❌ ERROR: Could not find GOOGLE_API_KEY in .env")
    exit(1)

genai.configure(api_key=api_key)

print(f"Checking models for API Key ending in ...{api_key[-4:]}")
print("==========================================")

try:
    found = False
    for m in genai.list_models():
        if "generateContent" in m.supported_generation_methods:
            print(f"✅ Found: {m.name}")
            found = True
    
    if not found:
        print("⚠️ No models found. Check your API Key permissions.")

except Exception as e:
    print(f"❌ Error listing models: {e}")
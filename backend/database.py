import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise EnvironmentError("SUPABASE_URL or SUPABASE_KEY missing from .env file!")

db: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

if __name__ == "__main__":
    print("\n=== Supabase Connection Test ===")
    print(f"URL: {SUPABASE_URL}")
    print(f"Key: {SUPABASE_KEY[:20]}...")
    try:
        result = db.table("appointments").select("id").limit(1).execute()
        print("\nSUCCESS! Connected to Supabase.")
        print(f"appointments table rows: {len(result.data)}")
    except Exception as e:
        print(f"\nFAILED: {e}")
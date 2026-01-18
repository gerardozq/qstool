import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_STORAGE_UPLOADS_BUCKET = os.getenv("SUPABASE_STORAGE_UPLOADS_BUCKET", "uploads")
SUPABASE_STORAGE_OVERLAYS_BUCKET = os.getenv("SUPABASE_STORAGE_OVERLAYS_BUCKET", "overlays")

VLM_API_URL = os.getenv("VLM_API_URL", "https://api.openai.com/v1/responses")
VLM_API_KEY = os.getenv("VLM_API_KEY", "")
VLM_MODEL = os.getenv("VLM_MODEL", "gpt-4o-mini")

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

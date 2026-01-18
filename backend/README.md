# Backend

## Local dev
- Create .env from .env.example
- Install deps: pip install -r requirements.txt
- Run API: uvicorn app.main:app --reload
- Run worker: python worker.py

## Supabase
- Run schema in supabase_schema.sql
- Create storage buckets: uploads, overlays

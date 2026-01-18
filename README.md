# QS Tool

Monorepo with:
- frontend/ (React + Vite)
- backend/ (FastAPI + worker)

## Setup overview

1) Create Supabase project and run the schema in backend/supabase_schema.sql.
2) Create storage buckets: uploads and overlays.
3) Configure environment variables using backend/.env.example and frontend/.env.example.
4) Deploy:
   - Frontend: Vercel
   - Backend API + worker: Render
   - DB + Storage: Supabase

## Deploy (Render + Vercel)

### Supabase
1) Run the SQL in backend/supabase_schema.sql.
2) Create storage buckets: uploads, overlays.
3) Copy SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY for Render env vars.

### Render (API + Worker)
1) Use render.yaml as a Blueprint.
2) Set environment variables:
   - SUPABASE_URL
   - SUPABASE_SERVICE_ROLE_KEY
   - VLM_API_URL (placeholder ok)
   - VLM_API_KEY (placeholder ok)
   - CORS_ORIGINS = your Vercel URL
3) Deploy both services (web + worker).

### Vercel (Frontend)
1) Import frontend/ as the project root.
2) Set VITE_API_URL to your Render API URL.
3) Deploy.

## VLM integration

Replace call_vlm in backend/worker.py with your hosted model API.
The expected output format is:
- label (string)
- bbox [x, y, w, h]
- confidence (float)

## Local development

Frontend:
- Install deps and run dev server.

Backend:
- Install deps and run API server.
- Run worker to process jobs.

## Docker Compose (local)

1) Create backend/.env and frontend/.env from the examples.
2) Run: docker compose up
3) Frontend: http://localhost:5173
4) API: http://localhost:8000

## VLM placeholder

The worker uses a placeholder VLM call. Replace call_vlm in backend/worker.py with your hosted VLM API integration.
Symbol inputs are uploaded as image files; their file names are used as labels.
Overlay images are not generated when using counts-only output.
When mode is full, tiles are stored in Supabase Storage under uploads/{job_id}/tiles/.

from typing import List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .config import (
    CORS_ORIGINS,
    SUPABASE_STORAGE_OVERLAYS_BUCKET,
    SUPABASE_STORAGE_UPLOADS_BUCKET,
)
from .health import router as health_router
from .supabase_client import supabase
from .types import JobDetail, JobSummary, SymbolCount


app = FastAPI(title="QS Symbol Counter")
app.include_router(health_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"] ,
    allow_headers=["*"],
)


def _job_summary(row) -> JobSummary:
    return JobSummary(
        id=row["id"],
        filename=row["filename"],
        status=row["status"],
        created_at=row["created_at"],
    )


def _job_detail(row, counts, input_url: Optional[str], overlay_url: Optional[str]) -> JobDetail:
    raw_symbols = row.get("symbols", []) or []
    symbols: List[str] = []
    for item in raw_symbols:
        if isinstance(item, dict):
            label = item.get("label")
            if label:
                symbols.append(label)
        elif isinstance(item, str):
            symbols.append(item)
    return JobDetail(
        id=row["id"],
        filename=row["filename"],
        status=row["status"],
        created_at=row["created_at"],
        symbols=symbols,
        counts=[SymbolCount(**c) for c in counts],
        mode=row.get("mode"),
        tile_rows=row.get("tile_rows"),
        tile_cols=row.get("tile_cols"),
        input_url=input_url,
        overlay_url=overlay_url,
        error_message=row.get("error_message"),
    )


@app.get("/jobs", response_model=List[JobSummary])
def list_jobs():
    result = (
        supabase.table("jobs")
        .select("id,filename,status,created_at")
        .order("created_at", desc=True)
        .limit(25)
        .execute()
    )
    return [_job_summary(row) for row in result.data]


@app.get("/jobs/{job_id}", response_model=JobDetail)
def get_job(job_id: str):
    job_result = supabase.table("jobs").select("*").eq("id", job_id).execute()
    if not job_result.data:
        raise HTTPException(status_code=404, detail="Job not found")

    job = job_result.data[0]
    counts_result = (
        supabase.table("symbols")
        .select("label,count")
        .eq("job_id", job_id)
        .order("label")
        .execute()
    )

    overlay_url = None
    if job.get("overlay_path"):
        overlay_url = (
            supabase.storage.from_(SUPABASE_STORAGE_OVERLAYS_BUCKET)
            .get_public_url(job["overlay_path"])
        )

    input_url = None
    if job.get("input_path"):
        input_url = (
            supabase.storage.from_(SUPABASE_STORAGE_UPLOADS_BUCKET)
            .get_public_url(job["input_path"])
        )

    return _job_detail(job, counts_result.data, input_url, overlay_url)


@app.post("/jobs")
async def create_job(
    file: UploadFile = File(...),
    symbol_files: Optional[List[UploadFile]] = File(None),
    mode: Optional[str] = Form("full"),
    tile_rows: Optional[int] = Form(10),
    tile_cols: Optional[int] = Form(10),
):
    symbols_payload = []
    filename = file.filename or "drawing"

    safe_rows = max(1, min(20, tile_rows or 10))
    safe_cols = max(1, min(20, tile_cols or 10))

    job_result = (
        supabase.table("jobs")
        .insert(
            {
                "filename": filename,
                "status": "uploading",
                "symbols": [],
                "mode": mode or "full",
                "tile_rows": safe_rows,
                "tile_cols": safe_cols,
            }
        )
        .execute()
    )

    job = job_result.data[0]
    job_id = job["id"]

    file_bytes = await file.read()
    storage_path = f"{job_id}/{filename}"

    try:
        supabase.storage.from_(SUPABASE_STORAGE_UPLOADS_BUCKET).upload(
            storage_path,
            file_bytes,
            {
                "content-type": file.content_type or "application/octet-stream",
            },
        )

        if symbol_files:
            for index, symbol_file in enumerate(symbol_files, start=1):
                symbol_name = symbol_file.filename or f"symbol_{index}"
                symbol_bytes = await symbol_file.read()
                symbol_path = f"{job_id}/symbols/{symbol_name}"
                supabase.storage.from_(SUPABASE_STORAGE_UPLOADS_BUCKET).upload(
                    symbol_path,
                    symbol_bytes,
                    {
                        "content-type": symbol_file.content_type or "application/octet-stream",
                    },
                )
                symbols_payload.append({"path": symbol_path})

        supabase.table("jobs").update(
            {
                "input_path": storage_path,
                "symbols": symbols_payload,
                "status": "queued",
                "mode": mode or "full",
                "tile_rows": safe_rows,
                "tile_cols": safe_cols,
            }
        ).eq("id", job_id).execute()
    except Exception as exc:
        supabase.table("jobs").update(
            {"status": "failed", "error_message": str(exc)}
        ).eq("id", job_id).execute()
        raise HTTPException(status_code=500, detail="Upload failed") from exc

    return {"id": job_id}



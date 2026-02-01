import base64
import io
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Dict, List, Tuple

import httpx
from PIL import Image, ImageDraw, ImageFont
import pypdfium2 as pdfium

from app.config import (
    SUPABASE_STORAGE_OVERLAYS_BUCKET,
    SUPABASE_STORAGE_UPLOADS_BUCKET,
    VLM_API_KEY,
    VLM_API_URL,
    VLM_MODEL,
)
from app.supabase_client import supabase


POLL_INTERVAL_SEC = 5


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def render_pdf_to_images(file_bytes: bytes) -> List[Image.Image]:
    doc = pdfium.PdfDocument(file_bytes)
    images: List[Image.Image] = []
    try:
        for page_index in range(len(doc)):
            page = doc[page_index]
            try:
                bitmap = page.render(scale=4)
                images.append(bitmap.to_pil())
            finally:
                page.close()
    finally:
        doc.close()
    return images


def _encode_image(data: bytes) -> str:
    return base64.b64encode(data).decode("utf-8")




def _extract_text_from_response(payload: dict) -> str:
    if isinstance(payload.get("output_text"), str) and payload.get("output_text"):
        return payload.get("output_text", "").strip()
    output = payload.get("output", [])
    texts: List[str] = []
    for item in output:
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"}:
                texts.append(content.get("text", ""))
    return "\n".join(texts).strip()


def _parse_counts(text: str) -> Dict[str, int]:
    if not text:
        return {}
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return {str(k): int(v) for k, v in data.items()}
        if isinstance(data, list):
            result: Dict[str, int] = {}
            for item in data:
                if isinstance(item, dict) and "label" in item and "count" in item:
                    result[str(item["label"])] = int(item["count"])
            return result
        return {}
    except (json.JSONDecodeError, ValueError, TypeError):
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                data = json.loads(text[start : end + 1])
                if isinstance(data, dict):
                    return {str(k): int(v) for k, v in data.items()}
            except (json.JSONDecodeError, ValueError, TypeError):
                return {}
        return {}


def normalize_label(label: str) -> str:
    normalized = (label or "").strip().lower().replace("_", " ")
    normalized = " ".join(normalized.split())
    return normalized


def load_image(file_bytes: bytes) -> Image.Image:
    return Image.open(io.BytesIO(file_bytes)).convert("RGB")


def split_image_grid(image: Image.Image, rows: int, cols: int) -> List[tuple[int, int, Image.Image]]:
    width, height = image.size
    tiles: List[tuple[int, int, Image.Image]] = []
    tile_w = max(1, width // cols)
    tile_h = max(1, height // rows)
    for row in range(rows):
        for col in range(cols):
            left = col * tile_w
            top = row * tile_h
            right = width if col == cols - 1 else (col + 1) * tile_w
            bottom = height if row == rows - 1 else (row + 1) * tile_h
            tiles.append((row, col, image.crop((left, top, right, bottom))))
    return tiles


def call_vlm(image_bytes: bytes, symbols: List[bytes]):
    """
    OpenAI Responses API call.
    Expected return format:
    [{"label": "door", "bbox": [x, y, w, h], "confidence": 0.92}]
    """
    if not VLM_API_KEY:
        return []

    prompt = (
        "You are an expert quantity surveyor assistant. "
        "Given a floorplan image and a list of symbol reference images, "
        "count occurrences of each symbol in the floorplan. "
        "The symbols in the floorplan could be rotated. "
        "Return ONLY JSON counts. "
        "Preferred format: {\"label1\": 3, \"label2\": 0}. "
        "Use descriptive labels inferred from the symbol images. "
        "Do NOT use generic labels like 'Symbol 1'. "
        "If you cannot see images, return an empty JSON object {}."
    )

    content = [
        {"type": "input_text", "text": prompt},
        {
            "type": "input_image",
            "image_url": f"data:image/png;base64,{_encode_image(image_bytes)}",
        },
    ]

    for index, symbol_bytes in enumerate(symbols, start=1):
        content.append({"type": "input_text", "text": f"Reference symbol #{index}"})
        content.append(
            {
                "type": "input_image",
                "image_url": f"data:image/png;base64,{_encode_image(symbol_bytes)}",
            }
        )

    headers = {
        "Authorization": f"Bearer {VLM_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": VLM_MODEL,
        "input": [{"role": "user", "content": content}],
        "temperature": 0.0,
    }

    with httpx.Client(timeout=60) as client:
        response = client.post(VLM_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

    usage = data.get("usage")
    if usage:
        print(
            "VLM token usage:",
            {
                "input_tokens": usage.get("input_tokens"),
                "output_tokens": usage.get("output_tokens"),
                "total_tokens": usage.get("total_tokens"),
            },
        )

    text = _extract_text_from_response(data)
    if text:
        print("VLM raw output:", text)
    else:
        output_preview = json.dumps(data.get("output", []), ensure_ascii=False)[:2000]
        print("VLM raw output empty. Output preview:", output_preview)
    return _parse_counts(text)


def draw_overlay(image: Image.Image, detections: List[dict]) -> Image.Image:
    overlay = image.copy()
    draw = ImageDraw.Draw(overlay)
    for det in detections:
        x, y, w, h = det["bbox"]
        label = det["label"]
        draw.rectangle([x, y, x + w, y + h], outline="#22c55e", width=3)
        draw.text((x, max(0, y - 14)), label, fill="#16a34a")
    return overlay


def process_job(job: dict):
    job_id = job["id"]
    input_path = job.get("input_path")
    if not input_path:
        raise RuntimeError("Job has no input_path")

    raw_symbols = job.get("symbols") or []
    symbol_items: List[bytes] = []
    for item in raw_symbols:
        if isinstance(item, dict) and item.get("path"):
            symbol_path = item["path"]
            symbol_bytes = supabase.storage.from_(SUPABASE_STORAGE_UPLOADS_BUCKET).download(
                symbol_path
            )
            symbol_items.append(symbol_bytes)

    file_bytes = supabase.storage.from_(SUPABASE_STORAGE_UPLOADS_BUCKET).download(input_path)

    pages: List[Image.Image] = []
    if input_path.lower().endswith(".pdf"):
        pages = render_pdf_to_images(file_bytes)
    else:
        pages = [load_image(file_bytes)]

    mode = job.get("mode", "full")
    tile_rows = max(1, min(20, int(job.get("tile_rows") or 10)))
    tile_cols = max(1, min(20, int(job.get("tile_cols") or 10)))

    merged_counts: Dict[str, int] = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        for page_index, page_image in enumerate(pages):
            tiles = (
                split_image_grid(page_image, tile_rows, tile_cols)
                if mode == "full"
                else [(0, 0, page_image)]
            )
            total_tiles = len(tiles)
            futures = []
            for tile_index, (row, col, tile) in enumerate(tiles, start=1):
                print(f"Processing tile {tile_index}/{total_tiles} (page {page_index})")
                buffer = io.BytesIO()
                tile.save(buffer, format="PNG")
                tile_bytes = buffer.getvalue()

                tile_path = f"{job_id}/tiles/page-{page_index}_r{row}_c{col}.png"
                supabase.storage.from_(SUPABASE_STORAGE_UPLOADS_BUCKET).upload(
                    tile_path,
                    tile_bytes,
                    {"content-type": "image/png"},
                )

                futures.append(executor.submit(call_vlm, tile_bytes, symbol_items))

            for future in as_completed(futures):
                page_counts = future.result()
                for label, count in page_counts.items():
                    normalized_label = normalize_label(label)
                    merged_counts[normalized_label] = merged_counts.get(normalized_label, 0) + int(count)

    supabase.table("symbols").delete().eq("job_id", job_id).execute()
    if merged_counts:
        rows = [
            {"job_id": job_id, "label": k, "count": v}
            for k, v in merged_counts.items()
        ]
        supabase.table("symbols").insert(rows).execute()

    overlay_path = None

    supabase.table("jobs").update(
        {
            "status": "done",
            "completed_at": now_iso(),
            "overlay_path": overlay_path,
        }
    ).eq("id", job_id).execute()


if __name__ == "__main__":
    print("Worker started")
    while True:
        try:
            result = (
                supabase.table("jobs")
                .select("*")
                .eq("status", "queued")
                .neq("input_path", None)
                .order("created_at")
                .limit(1)
                .execute()
            )
            if not result.data:
                time.sleep(POLL_INTERVAL_SEC)
                continue

            job = result.data[0]
            claim = (
                supabase.table("jobs")
                .update({"status": "processing", "started_at": now_iso()})
                .eq("id", job["id"])
                .eq("status", "queued")
                .execute()
            )
            if not claim.data:
                continue

            try:
                process_job(job)
            except Exception as exc:
                supabase.table("jobs").update(
                    {
                        "status": "failed",
                        "error_message": str(exc),
                        "completed_at": now_iso(),
                    }
                ).eq("id", job["id"]).execute()
        except Exception as exc:
            print(f"Worker loop error: {exc}")
            time.sleep(POLL_INTERVAL_SEC)

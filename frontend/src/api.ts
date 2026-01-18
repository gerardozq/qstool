import { AnalysisMode, JobDetail, JobSummary } from "./types";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export async function createJob(
  file: File,
  symbolFiles: File[],
  mode: AnalysisMode,
  tileRows: number,
  tileCols: number
) {
  const form = new FormData();
  form.append("file", file);
  form.append("mode", mode);
  form.append("tile_rows", String(tileRows));
  form.append("tile_cols", String(tileCols));
  if (symbolFiles.length > 0) {
    symbolFiles.forEach((symbolFile) => form.append("symbol_files", symbolFile));
  }

  const res = await fetch(`${API_BASE}/jobs`, {
    method: "POST",
    body: form
  });
  if (!res.ok) {
    throw new Error(`Upload failed (${res.status})`);
  }
  return (await res.json()) as { id: string };
}

export async function getJob(id: string) {
  const res = await fetch(`${API_BASE}/jobs/${id}`);
  if (!res.ok) {
    throw new Error(`Job fetch failed (${res.status})`);
  }
  return (await res.json()) as JobDetail;
}

export async function listJobs() {
  const res = await fetch(`${API_BASE}/jobs`);
  if (!res.ok) {
    throw new Error(`Jobs fetch failed (${res.status})`);
  }
  return (await res.json()) as JobSummary[];
}

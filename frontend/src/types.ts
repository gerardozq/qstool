export type JobStatus = "queued" | "processing" | "done" | "failed";

export type AnalysisMode = "full" | "snippet";

export type JobSummary = {
  id: string;
  filename: string;
  status: JobStatus;
  created_at: string;
};

export type SymbolCount = {
  label: string;
  count: number;
};

export type JobDetail = {
  id: string;
  filename: string;
  status: JobStatus;
  created_at: string;
  symbols: string[];
  counts: SymbolCount[];
  mode?: AnalysisMode;
  tile_rows?: number | null;
  tile_cols?: number | null;
  input_url?: string | null;
  overlay_url?: string | null;
  error_message?: string | null;
};

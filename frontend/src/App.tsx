import { useEffect, useState } from "react";
import { createJob, getJob, listJobs } from "./api";
import { AnalysisMode, JobDetail, JobSummary } from "./types";

const POLL_INTERVAL_MS = 4000;

export default function App() {
  const [file, setFile] = useState<File | null>(null);
  const [symbolFiles, setSymbolFiles] = useState<File[]>([]);
  const [mode, setMode] = useState<AnalysisMode>("full");
  const [tileRows, setTileRows] = useState(10);
  const [tileCols, setTileCols] = useState(10);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [selectedJob, setSelectedJob] = useState<JobDetail | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);


  useEffect(() => {
    let isMounted = true;

    const loadJobs = async () => {
      try {
        const data = await listJobs();
        if (isMounted) {
          setJobs(data);
        }
      } catch {
        if (isMounted) {
          setJobs((current) => current);
        }
      }
    };

    loadJobs();
    const timer = setInterval(loadJobs, POLL_INTERVAL_MS);

    return () => {
      isMounted = false;
      clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    if (!selectedJobId) return;

    let isMounted = true;

    const load = async () => {
      try {
        const data = await getJob(selectedJobId);
        if (isMounted) {
          setSelectedJob(data);
          setError(null);
        }
      } catch (err) {
        if (isMounted) {
          setError((err as Error).message);
        }
      }
    };

    load();
    const timer = setInterval(load, POLL_INTERVAL_MS);

    return () => {
      isMounted = false;
      clearInterval(timer);
    };
  }, [selectedJobId]);

  const onSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!file) {
      setError("Please select a file.");
      return;
    }

    try {
      setIsUploading(true);
      setError(null);
      const result = await createJob(file, symbolFiles, mode, tileRows, tileCols);
      setSelectedJobId(result.id);
      setSelectedJob(null);
      setIsModalOpen(true);
      const updated = await listJobs();
      setJobs(updated);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="page">
      <header className="hero">
        <div>
          <p className="eyebrow">QS Vision</p>
          <h1>Floorplan Symbol Counter</h1>
          <p className="subtitle">
            Upload a floorplan, define your symbols, and get automated counts with visual overlays.
          </p>
        </div>
      </header>

      <main className="grid">
        <section className="card">
          <h2>Upload drawing</h2>
          <form onSubmit={onSubmit} className="form">
            <label className="field">
              <span>Drawing (PDF or image)</span>
              <input
                type="file"
                accept="application/pdf,image/*"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
              />
            </label>

            <label className="field">
              <span>Symbol images</span>
              <input
                type="file"
                accept="image/*"
                multiple
                onChange={(e) => setSymbolFiles(Array.from(e.target.files ?? []))}
              />
            </label>

            <div className="field">
              <span>Drawing mode</span>
              <div className="radio-group">
                <label className="radio">
                  <input
                    type="radio"
                    name="mode"
                    value="full"
                    checked={mode === "full"}
                    onChange={() => setMode("full")}
                  />
                  Full (split into grid)
                </label>
                <label className="radio">
                  <input
                    type="radio"
                    name="mode"
                    value="snippet"
                    checked={mode === "snippet"}
                    onChange={() => setMode("snippet")}
                  />
                  Snippet (no split)
                </label>
              </div>
            </div>

            <div className="field">
              <span>Tile grid (rows x cols)</span>
              <div className="tile-grid">
                <input
                  type="number"
                  min={1}
                  max={20}
                  value={tileRows}
                  onChange={(e) => setTileRows(Number(e.target.value) || 1)}
                  disabled={mode !== "full"}
                />
                <span className="muted">x</span>
                <input
                  type="number"
                  min={1}
                  max={20}
                  value={tileCols}
                  onChange={(e) => setTileCols(Number(e.target.value) || 1)}
                  disabled={mode !== "full"}
                />
              </div>
            </div>


            <button type="submit" disabled={isUploading}>
              {isUploading ? "Uploading..." : "Start analysis"}
            </button>
          </form>
          {error && <p className="error">{error}</p>}
        </section>

        <section className="card">
          <h2>Recent jobs</h2>
          {jobs.length === 0 && <p className="muted">No recent jobs.</p>}
          <ul className="job-list">
            {jobs.map((item) => (
              <li key={item.id}>
                <button
                  className="link"
                  type="button"
                  onClick={() => {
                    setSelectedJobId(item.id);
                    setIsModalOpen(true);
                  }}
                >
                  {item.filename}
                </button>
                <span className={`status status-${item.status}`}>{item.status}</span>
              </li>
            ))}
          </ul>
        </section>
      </main>

      {isModalOpen && (
        <div className="modal-backdrop" onClick={() => setIsModalOpen(false)}>
          <div className="modal" onClick={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div>
                <p className="eyebrow">Job</p>
                <h3>{selectedJob?.filename ?? "Loading..."}</h3>
                {selectedJob && (
                  <p className={`status status-${selectedJob.status}`}>
                    {selectedJob.status}
                  </p>
                )}
              </div>
              <button className="ghost" onClick={() => setIsModalOpen(false)}>
                Close
              </button>
            </div>

            {!selectedJob && <p className="muted">Loading job details...</p>}

            {selectedJob && (
              <div className="modal-content">
                <div className="meta">
                  {selectedJob.mode && <p>Mode: {selectedJob.mode}</p>}
                  {selectedJob.tile_rows && selectedJob.tile_cols && (
                    <p>
                      Tiles: {selectedJob.tile_rows} x {selectedJob.tile_cols}
                    </p>
                  )}
                  <p>Created: {new Date(selectedJob.created_at).toLocaleString()}</p>
                </div>

                {selectedJob.status === "failed" && selectedJob.error_message && (
                  <p className="error">{selectedJob.error_message}</p>
                )}

                <div className="results">
                  <div>
                    <h4>Counts</h4>
                    {selectedJob.counts.length === 0 ? (
                      <p className="muted">No detections yet.</p>
                    ) : (
                      <table>
                        <thead>
                          <tr>
                            <th>Symbol</th>
                            <th>Count</th>
                          </tr>
                        </thead>
                        <tbody>
                          {selectedJob.counts.map((item) => (
                            <tr key={item.label}>
                              <td>{item.label}</td>
                              <td>{item.count}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </div>

                  <div>
                    <h4>Input image</h4>
                    {selectedJob.input_url ? (
                      <img
                        className="overlay"
                        src={selectedJob.input_url}
                        alt="Input drawing"
                      />
                    ) : (
                      <p className="muted">Input image not available.</p>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

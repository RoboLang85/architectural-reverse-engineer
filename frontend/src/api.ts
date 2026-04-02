const API_BASE_URL = process.env.REACT_APP_API_BASE_URL ?? '';

export interface AnalyzeRequest {
  sources: { input_type: 'local_path' | 'github_url'; value: string }[];
  documents: { file_path: string; file_type: 'pdf' | 'docx' | 'png' | 'jpg' | 'svg' }[];
}

export interface AnalyzeResponse {
  job_id: string;
}

export interface StatusResponse {
  job_id: string;
  stage: string;
}

export interface JobResults {
  results: Record<string, unknown>;
  errors: { error_type: string; message: string; details: Record<string, unknown> }[];
  artifacts: string[];
}

export async function startAnalysis(request: AnalyzeRequest): Promise<AnalyzeResponse> {
  const res = await fetch(`${API_BASE_URL}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.message || `Analysis request failed (${res.status})`);
  }
  return res.json();
}

export async function getStatus(jobId: string): Promise<StatusResponse> {
  const res = await fetch(`${API_BASE_URL}/status/${jobId}`);
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.message || `Status check failed (${res.status})`);
  }
  return res.json();
}

export async function getResults(jobId: string): Promise<JobResults> {
  const res = await fetch(`${API_BASE_URL}/results/${jobId}`);
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.message || `Results fetch failed (${res.status})`);
  }
  return res.json();
}

export function getDownloadUrl(jobId: string, artifact: string): string {
  return `${API_BASE_URL}/download/${jobId}/${artifact}`;
}

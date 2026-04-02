import React, { useState } from 'react';
import { startAnalysis, AnalyzeRequest } from '../api';

export interface AnalyzeFormProps {
  onJobStarted: (jobId: string) => void;
  onError: (message: string) => void;
}

export default function AnalyzeForm({ onJobStarted, onError }: AnalyzeFormProps) {
  const [localPath, setLocalPath] = useState('');
  const [githubUrl, setGithubUrl] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const [submitting, setSubmitting] = useState(false);

  const SUPPORTED_EXTENSIONS = ['.pdf', '.docx', '.png', '.jpg', '.jpeg', '.svg'];

  function fileTypeFromName(name: string): 'pdf' | 'docx' | 'png' | 'jpg' | 'svg' {
    const ext = name.toLowerCase().split('.').pop() || '';
    if (ext === 'jpeg') return 'jpg';
    return ext as 'pdf' | 'docx' | 'png' | 'jpg' | 'svg';
  }

  function isSupported(name: string): boolean {
    const ext = '.' + (name.toLowerCase().split('.').pop() || '');
    return SUPPORTED_EXTENSIONS.includes(ext);
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const selected = Array.from(e.target.files || []) as File[];
    const unsupported = selected.filter((f: File) => !isSupported(f.name));
    if (unsupported.length > 0) {
      onError(`Unsupported file types: ${unsupported.map((f: File) => f.name).join(', ')}. Supported: PDF, Word, PNG, JPG, SVG`);
      return;
    }
    setFiles(selected);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    const hasSource = localPath.trim() || githubUrl.trim();
    const hasFiles = files.length > 0;
    if (!hasSource && !hasFiles) {
      onError('Please provide at least one source (local path or GitHub URL) or upload a file.');
      return;
    }

    const request: AnalyzeRequest = { sources: [], documents: [] };

    if (localPath.trim()) {
      request.sources.push({ input_type: 'local_path', value: localPath.trim() });
    }
    if (githubUrl.trim()) {
      request.sources.push({ input_type: 'github_url', value: githubUrl.trim() });
    }
    for (const f of files) {
      request.documents.push({ file_path: f.name, file_type: fileTypeFromName(f.name) });
    }

    setSubmitting(true);
    try {
      const { job_id } = await startAnalysis(request);
      onJobStarted(job_id);
    } catch (err: unknown) {
      onError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} aria-label="Analyze form">
      <div>
        <label htmlFor="local-path">Local Folder Path</label>
        <input
          id="local-path"
          type="text"
          placeholder="/path/to/project"
          value={localPath}
          onChange={(e) => setLocalPath(e.target.value)}
        />
      </div>

      <div>
        <label htmlFor="github-url">GitHub URL</label>
        <input
          id="github-url"
          type="text"
          placeholder="https://github.com/owner/repo"
          value={githubUrl}
          onChange={(e) => setGithubUrl(e.target.value)}
        />
      </div>

      <div>
        <label htmlFor="file-upload">Upload Documents</label>
        <input
          id="file-upload"
          type="file"
          multiple
          accept=".pdf,.docx,.png,.jpg,.jpeg,.svg"
          onChange={handleFileChange}
        />
      </div>

      <button type="submit" disabled={submitting}>
        {submitting ? 'Analyzing…' : 'Analyze'}
      </button>
    </form>
  );
}

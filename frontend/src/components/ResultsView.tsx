import React, { useEffect, useState } from 'react';
import { getResults, getDownloadUrl, JobResults } from '../api';

export interface ResultsViewProps {
  jobId: string;
  onError: (message: string) => void;
}

export default function ResultsView({ jobId, onError }: ResultsViewProps) {
  const [results, setResults] = useState<JobResults | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function fetchResults() {
      try {
        const data = await getResults(jobId);
        if (!cancelled) {
          setResults(data);
          setLoading(false);
        }
      } catch (err: unknown) {
        if (!cancelled) {
          onError(err instanceof Error ? err.message : 'Failed to load results');
          setLoading(false);
        }
      }
    }

    fetchResults();
    return () => {
      cancelled = true;
    };
  }, [jobId, onError]);

  if (loading) return <p>Loading results…</p>;
  if (!results) return <p>No results available.</p>;

  const { results: data, errors, artifacts } = results;

  return (
    <div aria-label="Analysis results">
      {errors.length > 0 && (
        <section>
          <h3>Warnings / Errors</h3>
          <ul>
            {errors.map((e: { error_type: string; message: string }, i: number) => (
              <li key={i} role="alert">
                [{e.error_type}] {e.message}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section>
        <h3>Generated Outputs</h3>
        {Object.keys(data).length === 0 ? (
          <p>No outputs generated.</p>
        ) : (
          <ul>
            {Object.entries(data).map(([key, value]) => (
              <li key={key}>
                <strong>{key}</strong>: <pre>{typeof value === 'string' ? value : JSON.stringify(value, null, 2)}</pre>
              </li>
            ))}
          </ul>
        )}
      </section>

      {artifacts.length > 0 && (
        <section>
          <h3>Downloads</h3>
          <ul>
            {artifacts.map((name: string) => (
              <li key={name}>
                <a href={getDownloadUrl(jobId, name)} download>
                  {name}
                </a>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

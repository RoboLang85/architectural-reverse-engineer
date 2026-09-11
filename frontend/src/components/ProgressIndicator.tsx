import React, { useEffect, useState } from 'react';
import { getStatus } from '../api';

const STAGES = ['queued', 'ingesting', 'analyzing', 'generating', 'serializing', 'complete'];

export interface ProgressIndicatorProps {
  jobId: string;
  onComplete: () => void;
  onError: (message: string) => void;
  pollInterval?: number;
}

export default function ProgressIndicator({
  jobId,
  onComplete,
  onError,
  pollInterval = 2000,
}: ProgressIndicatorProps) {
  const [stage, setStage] = useState('queued');

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const status = await getStatus(jobId);
        if (cancelled) return;
        setStage(status.stage);

        if (status.stage === 'complete') {
          onComplete();
          return;
        }
        if (status.stage === 'failed') {
          onError('Analysis failed. Check results for details.');
          return;
        }
      } catch (err: unknown) {
        if (!cancelled) {
          onError(err instanceof Error ? err.message : 'Failed to check status');
        }
        return;
      }

      if (!cancelled) {
        setTimeout(poll, pollInterval);
      }
    }

    poll();
    return () => {
      cancelled = true;
    };
  }, [jobId, onComplete, onError, pollInterval]);

  const stageIndex = STAGES.indexOf(stage);

  return (
    <div aria-label="Analysis progress" role="status">
      <p>
        Stage: <strong data-testid="current-stage">{stage}</strong>
      </p>
      <ul>
        {STAGES.map((s, i) => (
          <li key={s} aria-current={s === stage ? 'step' : undefined}>
            {i < stageIndex ? '✓' : i === stageIndex ? '▶' : '○'} {s}
          </li>
        ))}
      </ul>
    </div>
  );
}

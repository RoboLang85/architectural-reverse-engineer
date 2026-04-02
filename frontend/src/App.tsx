import React, { useState, useCallback } from 'react';
import AnalyzeForm from './components/AnalyzeForm';
import ProgressIndicator from './components/ProgressIndicator';
import ResultsView from './components/ResultsView';
import ErrorDisplay from './components/ErrorDisplay';

type AppPhase = 'input' | 'progress' | 'results';

export default function App() {
  const [phase, setPhase] = useState<AppPhase>('input');
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleJobStarted = useCallback((id: string) => {
    setError(null);
    setJobId(id);
    setPhase('progress');
  }, []);

  const handleComplete = useCallback(() => {
    setPhase('results');
  }, []);

  const handleError = useCallback((msg: string) => {
    setError(msg);
  }, []);

  const handleDismissError = useCallback(() => {
    setError(null);
  }, []);

  const handleReset = useCallback(() => {
    setPhase('input');
    setJobId(null);
    setError(null);
  }, []);

  return (
    <div>
      <h1>Architectural Reverse Engineer</h1>

      <ErrorDisplay message={error} onDismiss={handleDismissError} />

      {phase === 'input' && (
        <AnalyzeForm onJobStarted={handleJobStarted} onError={handleError} />
      )}

      {phase === 'progress' && jobId && (
        <ProgressIndicator jobId={jobId} onComplete={handleComplete} onError={handleError} />
      )}

      {phase === 'results' && jobId && (
        <>
          <ResultsView jobId={jobId} onError={handleError} />
          <button onClick={handleReset}>New Analysis</button>
        </>
      )}
    </div>
  );
}

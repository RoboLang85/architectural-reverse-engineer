import React from 'react';
import { render, screen, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import ProgressIndicator from '../src/components/ProgressIndicator';

beforeEach(() => {
  jest.useFakeTimers();
  (global as any).fetch = jest.fn();
});
afterEach(() => {
  jest.useRealTimers();
  jest.restoreAllMocks();
});

describe('ProgressIndicator', () => {
  const onComplete = jest.fn();
  const onError = jest.fn();

  beforeEach(() => {
    onComplete.mockClear();
    onError.mockClear();
  });

  it('displays initial queued stage', async () => {
    (global as any).fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ job_id: 'j1', stage: 'queued' }),
    });

    render(
      <ProgressIndicator jobId="j1" onComplete={onComplete} onError={onError} pollInterval={1000} />
    );

    await waitFor(() => {
      expect(screen.getByTestId('current-stage')).toHaveTextContent('queued');
    });
  });

  it('updates stage on poll', async () => {
    let callCount = 0;
    (global as any).fetch = jest.fn().mockImplementation(() => {
      callCount++;
      const stage = callCount === 1 ? 'ingesting' : 'analyzing';
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ job_id: 'j1', stage }),
      });
    });

    render(
      <ProgressIndicator jobId="j1" onComplete={onComplete} onError={onError} pollInterval={500} />
    );

    await waitFor(() => {
      expect(screen.getByTestId('current-stage')).toHaveTextContent('ingesting');
    });

    await act(async () => {
      jest.advanceTimersByTime(600);
    });

    await waitFor(() => {
      expect(screen.getByTestId('current-stage')).toHaveTextContent('analyzing');
    });
  });

  it('calls onComplete when stage is complete', async () => {
    (global as any).fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ job_id: 'j1', stage: 'complete' }),
    });

    render(
      <ProgressIndicator jobId="j1" onComplete={onComplete} onError={onError} pollInterval={1000} />
    );

    await waitFor(() => {
      expect(onComplete).toHaveBeenCalled();
    });
  });

  it('calls onError when stage is failed', async () => {
    (global as any).fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ job_id: 'j1', stage: 'failed' }),
    });

    render(
      <ProgressIndicator jobId="j1" onComplete={onComplete} onError={onError} pollInterval={1000} />
    );

    await waitFor(() => {
      expect(onError).toHaveBeenCalledWith('Analysis failed. Check results for details.');
    });
  });

  it('calls onError when fetch fails', async () => {
    (global as any).fetch = jest.fn().mockRejectedValue(new Error('Network error'));

    render(
      <ProgressIndicator jobId="j1" onComplete={onComplete} onError={onError} pollInterval={1000} />
    );

    await waitFor(() => {
      expect(onError).toHaveBeenCalledWith('Network error');
    });
  });

  it('renders all stage labels', async () => {
    (global as any).fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ job_id: 'j1', stage: 'queued' }),
    });

    render(
      <ProgressIndicator jobId="j1" onComplete={onComplete} onError={onError} pollInterval={5000} />
    );

    await waitFor(() => {
      expect(screen.getByText(/queued/)).toBeInTheDocument();
    });

    expect(screen.getByText(/ingesting/)).toBeInTheDocument();
    expect(screen.getByText(/analyzing/)).toBeInTheDocument();
    expect(screen.getByText(/generating/)).toBeInTheDocument();
    expect(screen.getByText(/serializing/)).toBeInTheDocument();
    expect(screen.getByText(/complete/)).toBeInTheDocument();
  });
});

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import AnalyzeForm from '../src/components/AnalyzeForm';

// Mock fetch globally
beforeEach(() => {
  (global as any).fetch = jest.fn();
});
afterEach(() => {
  jest.restoreAllMocks();
});

describe('AnalyzeForm', () => {
  const onJobStarted = jest.fn();
  const onError = jest.fn();

  beforeEach(() => {
    onJobStarted.mockClear();
    onError.mockClear();
  });

  it('renders local path input', () => {
    render(<AnalyzeForm onJobStarted={onJobStarted} onError={onError} />);
    expect(screen.getByLabelText('Local Folder Path')).toBeInTheDocument();
  });

  it('renders GitHub URL input', () => {
    render(<AnalyzeForm onJobStarted={onJobStarted} onError={onError} />);
    expect(screen.getByLabelText('GitHub URL')).toBeInTheDocument();
  });

  it('renders file upload control', () => {
    render(<AnalyzeForm onJobStarted={onJobStarted} onError={onError} />);
    expect(screen.getByLabelText('Upload Documents')).toBeInTheDocument();
  });

  it('renders Analyze button', () => {
    render(<AnalyzeForm onJobStarted={onJobStarted} onError={onError} />);
    expect(screen.getByRole('button', { name: /analyze/i })).toBeInTheDocument();
  });

  it('shows error when submitting with no inputs', async () => {
    render(<AnalyzeForm onJobStarted={onJobStarted} onError={onError} />);
    fireEvent.click(screen.getByRole('button', { name: /analyze/i }));
    expect(onError).toHaveBeenCalledWith(
      'Please provide at least one source (local path or GitHub URL) or upload a file.'
    );
  });

  it('calls onJobStarted on successful submission', async () => {
    (global as any).fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ job_id: 'test-job-123' }),
    });

    render(<AnalyzeForm onJobStarted={onJobStarted} onError={onError} />);
    fireEvent.change(screen.getByLabelText('Local Folder Path'), {
      target: { value: '/my/project' },
    });
    fireEvent.click(screen.getByRole('button', { name: /analyze/i }));

    await waitFor(() => {
      expect(onJobStarted).toHaveBeenCalledWith('test-job-123');
    });
  });

  it('calls onError when API returns an error', async () => {
    (global as any).fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 400,
      json: () => Promise.resolve({ message: 'Bad request' }),
    });

    render(<AnalyzeForm onJobStarted={onJobStarted} onError={onError} />);
    fireEvent.change(screen.getByLabelText('GitHub URL'), {
      target: { value: 'https://github.com/owner/repo' },
    });
    fireEvent.click(screen.getByRole('button', { name: /analyze/i }));

    await waitFor(() => {
      expect(onError).toHaveBeenCalledWith('Bad request');
    });
  });

  it('disables button while submitting', async () => {
    let resolvePromise: (v: any) => void;
    (global as any).fetch = jest.fn().mockReturnValue(
      new Promise((resolve) => {
        resolvePromise = resolve;
      })
    );

    render(<AnalyzeForm onJobStarted={onJobStarted} onError={onError} />);
    fireEvent.change(screen.getByLabelText('Local Folder Path'), {
      target: { value: '/path' },
    });
    fireEvent.click(screen.getByRole('button', { name: /analyz/i }));

    expect(screen.getByRole('button')).toBeDisabled();
    expect(screen.getByRole('button')).toHaveTextContent('Analyzing…');

    resolvePromise!({
      ok: true,
      json: () => Promise.resolve({ job_id: 'j1' }),
    });

    await waitFor(() => {
      expect(screen.getByRole('button')).not.toBeDisabled();
    });
  });
});

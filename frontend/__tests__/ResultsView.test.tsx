import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import ResultsView from '../src/components/ResultsView';

beforeEach(() => {
  (global as any).fetch = jest.fn();
});
afterEach(() => {
  jest.restoreAllMocks();
});

describe('ResultsView', () => {
  const onError = jest.fn();

  beforeEach(() => {
    onError.mockClear();
  });

  it('shows loading state initially', () => {
    (global as any).fetch = jest.fn().mockReturnValue(new Promise(() => {}));
    render(<ResultsView jobId="j1" onError={onError} />);
    expect(screen.getByText('Loading results…')).toBeInTheDocument();
  });

  it('displays generated outputs', async () => {
    (global as any).fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          results: { dependency_graph: { nodes: ['A', 'B'] } },
          errors: [],
          artifacts: [],
        }),
    });

    render(<ResultsView jobId="j1" onError={onError} />);

    await waitFor(() => {
      expect(screen.getByText('dependency_graph')).toBeInTheDocument();
    });
  });

  it('displays download links for artifacts', async () => {
    (global as any).fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          results: {},
          errors: [],
          artifacts: ['diagram.png', 'report.json'],
        }),
    });

    render(<ResultsView jobId="j1" onError={onError} />);

    await waitFor(() => {
      expect(screen.getByText('diagram.png')).toBeInTheDocument();
      expect(screen.getByText('report.json')).toBeInTheDocument();
    });

    const links = screen.getAllByRole('link');
    expect(links).toHaveLength(2);
    expect(links[0]).toHaveAttribute('href', expect.stringContaining('/download/j1/diagram.png'));
    expect(links[1]).toHaveAttribute('href', expect.stringContaining('/download/j1/report.json'));
  });

  it('displays errors from results', async () => {
    (global as any).fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          results: {},
          errors: [{ error_type: 'ParseError', message: 'Failed to parse file.py', details: {} }],
          artifacts: [],
        }),
    });

    render(<ResultsView jobId="j1" onError={onError} />);

    await waitFor(() => {
      expect(screen.getByText(/Failed to parse file.py/)).toBeInTheDocument();
    });
  });

  it('calls onError when fetch fails', async () => {
    (global as any).fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 404,
      json: () => Promise.resolve({ message: 'Job not found' }),
    });

    render(<ResultsView jobId="j1" onError={onError} />);

    await waitFor(() => {
      expect(onError).toHaveBeenCalledWith('Job not found');
    });
  });

  it('shows no results message when data is empty', async () => {
    (global as any).fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          results: {},
          errors: [],
          artifacts: [],
        }),
    });

    render(<ResultsView jobId="j1" onError={onError} />);

    await waitFor(() => {
      expect(screen.getByText('No outputs generated.')).toBeInTheDocument();
    });
  });
});

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import ErrorDisplay from '../src/components/ErrorDisplay';

describe('ErrorDisplay', () => {
  it('renders nothing when message is null', () => {
    const { container } = render(<ErrorDisplay message={null} />);
    expect(container.firstChild).toBeNull();
  });

  it('displays the error message', () => {
    render(<ErrorDisplay message="Something went wrong" />);
    expect(screen.getByRole('alert')).toHaveTextContent('Something went wrong');
  });

  it('shows dismiss button when onDismiss is provided', () => {
    const onDismiss = jest.fn();
    render(<ErrorDisplay message="Error" onDismiss={onDismiss} />);
    expect(screen.getByLabelText('Dismiss error')).toBeInTheDocument();
  });

  it('does not show dismiss button when onDismiss is not provided', () => {
    render(<ErrorDisplay message="Error" />);
    expect(screen.queryByLabelText('Dismiss error')).not.toBeInTheDocument();
  });

  it('calls onDismiss when dismiss button is clicked', () => {
    const onDismiss = jest.fn();
    render(<ErrorDisplay message="Error" onDismiss={onDismiss} />);
    fireEvent.click(screen.getByLabelText('Dismiss error'));
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });
});

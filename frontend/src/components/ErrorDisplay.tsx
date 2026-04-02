import React from 'react';

export interface ErrorDisplayProps {
  message: string | null;
  onDismiss?: () => void;
}

export default function ErrorDisplay({ message, onDismiss }: ErrorDisplayProps) {
  if (!message) return null;

  return (
    <div role="alert" className="error-display">
      <p>{message}</p>
      {onDismiss && (
        <button onClick={onDismiss} aria-label="Dismiss error">
          ✕
        </button>
      )}
    </div>
  );
}

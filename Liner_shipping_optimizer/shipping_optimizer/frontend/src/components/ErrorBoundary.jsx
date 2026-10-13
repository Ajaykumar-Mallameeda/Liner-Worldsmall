/**
 * Error Boundary Component
 * Catches and displays React errors
 */

import React from 'react';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    // Update state so the next render will show the fallback UI
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    // You can also log the error to an error reporting service
    console.error('Error caught by boundary:', error, errorInfo);
    this.setState({
      error: error,
      errorInfo: errorInfo
    });
  }

  render() {
    if (this.state.hasError) {
      // You can render any custom fallback UI
      return (
        <div style={{ padding: '20px', backgroundColor: '#fee', border: '1px solid #fcc', borderRadius: '8px', margin: '20px' }}>
          <h2 style={{ color: '#c00' }}>Something went wrong!</h2>
          <details style={{ whiteSpace: 'pre-wrap' }}>
            <summary>Click to see error details</summary>
            <p>{this.state.error && this.state.error.toString()}</p>
            {this.state.errorInfo && <p>{this.state.errorInfo.componentStack}</p>}
          </details>
          <button
            onClick={() => this.setState({ hasError: false, error: null, errorInfo: null })}
            style={{ marginTop: '10px', padding: '8px 16px', backgroundColor: '#c00', color: 'white', border: 'none', borderRadius: '4px' }}
          >
            Try again
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
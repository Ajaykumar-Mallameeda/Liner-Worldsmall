/**
 * ViewBoundary — contains a crash to the one view that threw.
 * Keyed by tab id in MaritimeDashboard, so switching tabs mounts a fresh boundary and the
 * header, navigation and other tabs keep working. The app-level ErrorBoundary stays as the last resort.
 */

import React from 'react';

export default class ViewBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error(`View "${this.props.label}" failed:`, error, info && info.componentStack);
  }

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;
    return (
      <div className="cx-view-error" role="alert">
        <div className="cx-view-error-title">{this.props.label} could not be drawn</div>
        <p>The rest of the console still works. Pick another tab, or retry this one.</p>
        <code>{String(error && error.message ? error.message : error)}</code>
        <button type="button" className="cx-btn" onClick={() => this.setState({ error: null })}>Retry</button>
      </div>
    );
  }
}

import React from 'react';
import ReactDOM from 'react-dom/client';
import MaritimeDashboard from './views/MaritimeDashboard.jsx';
import ErrorBoundary from './components/ErrorBoundary.jsx';
import './styles/index.css';

console.log('Loading maritime dashboard...');

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ErrorBoundary>
      <MaritimeDashboard />
    </ErrorBoundary>
  </React.StrictMode>
);
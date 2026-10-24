/** Renders the toast stack (services/toastStore.js). Mounted once in the shell. */
import React from 'react';
import { dismissToast, useToasts } from '../../services/toastStore.js';

export default function Toaster() {
  const toasts = useToasts();
  return (
    <div className="toasts" role="status" aria-live="polite">
      {toasts.map((t) => (
        <div key={t.id} className={`toast is-${t.tone}`}>
          <span className="ic" aria-hidden="true">{t.tone === 'warn' ? '!' : '✓'}</span>
          <span className="tx">{t.text}</span>
          <button type="button" onClick={() => dismissToast(t.id)} aria-label="Dismiss">✕</button>
        </div>
      ))}
    </div>
  );
}

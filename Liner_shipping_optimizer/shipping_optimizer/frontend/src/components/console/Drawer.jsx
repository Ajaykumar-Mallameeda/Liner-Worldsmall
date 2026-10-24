/**
 * Drawer
 * ------
 * Phase 11 - context-preserving side panel for inspecting
 * vessels, ports, routes, agents, iterations, decisions, and
 * events. Closing the drawer returns the user to the same
 * page they were on.
 *
 * Pure presentational. Caller supplies title, eyebrow,
 * body, and onClose.
 */

import { useEffect } from 'react';

export default function Drawer({
  open,
  onClose,
  title,
  eyebrow,
  children,
  footer,
  width = 'min(440px, 92vw)',
}) {
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => {
      if (e.key === 'Escape') onClose && onClose();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <>
      <div
        className="console-drawer-backdrop"
        onClick={onClose}
        role="presentation"
        aria-hidden="true"
      />
      <aside
        className="console-drawer"
        role="dialog"
        aria-modal="true"
        aria-label={title || 'Detail'}
        style={{ width }}
      >
        <header>
          <span style={{ flex: 1 }}>
            {eyebrow && <span style={{ display: 'block', marginBottom: 2 }}>{eyebrow}</span>}
            <span className="title">{title || 'Detail'}</span>
          </span>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close drawer"
            style={{
              background: 'transparent',
              border: '1px solid var(--console-edge)',
              color: 'var(--console-text-dim)',
              padding: '4px 8px',
              borderRadius: 4,
              cursor: 'pointer',
              fontFamily: 'var(--maritime-font-data)',
              fontSize: 12,
              textTransform: 'uppercase',
              letterSpacing: '0.18em',
            }}
          >
            Close
          </button>
        </header>
        <div className="body">{children}</div>
        {footer && (
          <footer style={{
            padding: '10px 16px',
            borderTop: '1px solid var(--console-edge)',
            fontFamily: 'var(--maritime-font-data)',
            fontSize: 12,
            color: 'var(--console-text-faint)',
            letterSpacing: '0.05em',
          }}>{footer}</footer>
        )}
      </aside>
    </>
  );
}

/** Helper to render a label/value field row inside a drawer. */
export function DrawerField({ label, value, mono = true }) {
  return (
    <div className="field">
      <span className="k">{label}</span>
      <span className="v" style={mono ? undefined : { fontFamily: 'var(--maritime-font-prose)' }}>{value ?? '—'}</span>
    </div>
  );
}

/**
 * InstrumentPanel
 * ---------------
 * The structural replacement for "card". A rectangular
 * 1px-bordered module with a thin 1px underlined header strip.
 * No rounded corners, no heavy glassmorphism, no extra padding
 * inside. The panel reads as one connected instrument.
 *
 * density: compact | comfortable (default) | spacious
 * bodyPadding: tight | normal | flush (no padding — useful for tables/maps)
 *
 * Pure presentational. Honors prefers-reduced-motion.
 */

import { useEffect, useState } from 'react';

export default function InstrumentPanel({
  title,
  right,
  children,
  footer,
  density = 'comfortable',
  bodyPadding = 'normal',
  as: As = 'section',
  className = '',
  ariaLabel,
  accent = false,
  style = {},
}) {
  const [entered, setEntered] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setEntered(true), 8);
    return () => clearTimeout(t);
  }, []);

  const densCls = density === 'compact' ? 'cx-instr--compact' : '';
  const bodyCls =
    bodyPadding === 'flush' ? 'cx-instr-body--flush' :
    bodyPadding === 'tight' ? 'cx-instr-body--tight' : '';

  return (
    <As
      className={`cx-instr ${densCls} ${accent ? 'cx-instr--accent' : ''} ${className}`}
      aria-label={ariaLabel || title}
      style={{ opacity: entered ? 1 : 0, transition: 'opacity 0.18s ease', ...style }}
    >
      {(title || right) && (
        <div className="cx-instr-head">
          <span className="title">{title}</span>
          {right != null && <span className="meta">{right}</span>}
        </div>
      )}
      <div className={`cx-instr-body ${bodyCls}`}>
        {children}
      </div>
      {footer && <div className="cx-instr-foot">{footer}</div>}
    </As>
  );
}

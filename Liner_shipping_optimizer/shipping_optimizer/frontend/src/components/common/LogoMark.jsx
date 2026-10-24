/**
 * Product mark: a liner service rotation — one closed loop with three port calls, the first one filled
 * (where the rotation starts). Same drawing as the favicon and the boot splash in index.html.
 */
import React from 'react';

export default function LogoMark({ size = 18, title }) {
  return (
    <svg className="logo-mark" width={size} height={size} viewBox="0 0 24 24" role={title ? 'img' : undefined} aria-hidden={title ? undefined : 'true'} aria-label={title}>
      <path d="M5 15.5C3.3 11.6 5.6 6.4 11 5.2c5.6-1.2 9.6 2.2 8.6 6.4-.9 3.9-5.6 6.9-10.4 6.4C7.4 17.8 5.9 17.1 5 15.5Z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
      <circle cx="5" cy="15.5" r="2.6" fill="currentColor" />
      <circle cx="11" cy="5.2" r="2" fill="var(--cx-bg-2, #050b14)" stroke="currentColor" strokeWidth="1.6" />
      <circle cx="19.6" cy="11.6" r="2" fill="var(--cx-bg-2, #050b14)" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  );
}

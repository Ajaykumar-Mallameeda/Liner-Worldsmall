/**
 * exportData.js — save what is on screen: a table as CSV, a chart (SVG) as PNG. Runs in the browser only;
 * nothing is sent anywhere. File names carry the run label so exports from different runs don't collide.
 */

import { toast } from '../services/toastStore.js';

const safe = (s) => String(s || 'export').replace(/[^\w.-]+/g, '_').replace(/^_+|_+$/g, '').slice(0, 80) || 'export';

function save(blob, name) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  toast(`Saved ${name}`);
}

const cell = (v) => {
  if (v == null) return '';
  const s = typeof v === 'number' ? String(Math.round(v * 1e6) / 1e6) : String(v);
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
};

/** columns: [[header, row => value], ...] */
export function downloadCsv(name, columns, rows) {
  const lines = [columns.map(([h]) => cell(h)).join(',')];
  rows.forEach((r) => lines.push(columns.map(([, f]) => cell(f(r))).join(',')));
  save(new Blob([`﻿${lines.join('\r\n')}\r\n`], { type: 'text/csv;charset=utf-8' }), `${safe(name)}.csv`);
}

const STYLE_PROPS = ['fill', 'fill-opacity', 'stroke', 'stroke-width', 'stroke-opacity', 'stroke-dasharray', 'opacity',
  'font-family', 'font-size', 'font-weight', 'text-anchor', 'dominant-baseline', 'letter-spacing'];

/** Copy computed styles (CSS variables resolved) onto a clone, so the PNG matches the screen. */
function inlineStyles(src, dst) {
  const cs = getComputedStyle(src);
  dst.setAttribute('style', STYLE_PROPS.map((p) => `${p}:${cs.getPropertyValue(p)}`).join(';'));
  for (let i = 0; i < src.children.length; i++) inlineStyles(src.children[i], dst.children[i]);
}

export async function downloadSvgPng(svg, name, { scale = 2, title = '' } = {}) {
  if (!svg) return;
  const w = svg.width.baseVal.value || svg.getBoundingClientRect().width;
  const h = svg.height.baseVal.value || svg.getBoundingClientRect().height;
  const clone = svg.cloneNode(true);
  inlineStyles(svg, clone);
  clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
  clone.setAttribute('width', w);
  clone.setAttribute('height', h);
  const xml = new XMLSerializer().serializeToString(clone);
  const img = new Image();
  const loaded = new Promise((res, rej) => { img.onload = res; img.onerror = rej; });
  img.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(xml)}`;
  await loaded;
  const head = title ? 28 : 0;
  const pad = 12;
  const canvas = document.createElement('canvas');
  canvas.width = (w + pad * 2) * scale;
  canvas.height = (h + pad * 2 + head) * scale;
  const ctx = canvas.getContext('2d');
  ctx.scale(scale, scale);
  const root = getComputedStyle(document.documentElement);
  ctx.fillStyle = root.getPropertyValue('--cx-bg-2').trim() || '#050b14';
  ctx.fillRect(0, 0, w + pad * 2, h + pad * 2 + head);
  if (title) {
    ctx.fillStyle = root.getPropertyValue('--cx-text').trim() || '#e6edf3';
    ctx.font = '600 13px "IBM Plex Sans", system-ui, sans-serif';
    ctx.fillText(title, pad, pad + 14);
  }
  ctx.drawImage(img, pad, pad + head, w, h);
  canvas.toBlob((b) => b && save(b, `${safe(name)}.png`), 'image/png');
}

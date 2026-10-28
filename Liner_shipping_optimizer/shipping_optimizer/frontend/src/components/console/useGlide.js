/**
 * Box of the active item in a list ({ x, y, w, h } in the list's own coordinates), for a single marker that
 * glides between items. The list must be position: relative. Re-measured when the active key changes and
 * when the list resizes (icon rail, density, wrapping).
 */
import { useLayoutEffect, useState } from 'react';

export default function useGlide(listRef, activeKey) {
  const [box, setBox] = useState(null);
  useLayoutEffect(() => {
    const list = listRef.current;
    if (!list) return undefined;
    const measure = () => {
      const el = list.querySelector('[aria-current="page"], [aria-selected="true"]');
      setBox(el ? { x: el.offsetLeft, y: el.offsetTop, w: el.offsetWidth, h: el.offsetHeight, key: activeKey } : null);
    };
    measure();
    if (typeof ResizeObserver === 'undefined') return undefined;
    const ro = new ResizeObserver(measure);
    ro.observe(list);
    return () => ro.disconnect();
  }, [listRef, activeKey]);
  return box;
}

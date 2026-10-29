/** Bottom-sheet rules (design D9, components/console/BottomSheet.jsx), kept here so node tests can load them. */

export const DRAG_CLOSE_PX = 80;
export const DRAG_OPEN_PX = 60;

/** Where a drag of dy pixels (down positive) leaves a sheet at `size`: 'half' | 'full' | 'closed'. */
export function sheetAfterDrag(size, dy) {
  if (dy <= -DRAG_OPEN_PX) return 'full';
  if (dy >= DRAG_CLOSE_PX) return size === 'full' ? 'half' : 'closed';
  return size;
}

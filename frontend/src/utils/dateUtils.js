/**
 * Returns the local date string in YYYY-MM-DD format.
 * Uses the local timezone instead of UTC.
 */
export function getLocalDateString(date = new Date()) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

/**
 * Returns a new Date object offset by dayOffset in local time.
 */
export function getOffsetLocalDateString(dayOffset, baseDate = new Date()) {
  const d = new Date(baseDate);
  d.setDate(d.getDate() + dayOffset);
  return getLocalDateString(d);
}

/**
 * Formats a YYYY-MM-DD date string into a readable format, e.g. "May 23".
 */
export function formatDateLabel(dateStr) {
  if (!dateStr) return '';
  const [year, month, day] = dateStr.split('-');
  const dateObj = new Date(year, month - 1, day);
  return dateObj.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

/**
 * Formats a YYYY-MM-DD date string into a longer readable format, e.g. "Sat, May 23, 2026".
 */
export function formatFullDateLabel(dateStr) {
  if (!dateStr) return '';
  const [year, month, day] = dateStr.split('-');
  const dateObj = new Date(year, month - 1, day);
  return dateObj.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' });
}

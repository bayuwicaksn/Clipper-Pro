/**
 * Formats seconds into MM:SS.CC (Clock format for player)
 */
export function formatClock(sec: number): string {
  const safe = Math.max(0, sec || 0);
  const mins = Math.floor(safe / 60);
  const secs = Math.floor(safe % 60);
  const cs = Math.floor((safe % 1) * 100);
  return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}.${cs
    .toString()
    .padStart(2, "0")}`;
}

/**
 * Formats seconds into HH:MM:SS.CC (Duration format)
 */
export function formatDuration(sec: number): string {
  const safe = Math.max(0, sec || 0);
  const h = Math.floor(safe / 3600);
  const m = Math.floor((safe % 3600) / 60);
  const s = Math.floor(safe % 60);
  const cs = Math.floor((safe % 1) * 100);
  return `${h}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}.${cs
    .toString()
    .padStart(2, "0")}`;
}

/**
 * Formats seconds into HH:MM:SS (Standard time format)
 */
export function formatTimeHHMMSS(sec: number): string {
  const safe = Math.max(0, sec || 0);
  const h = Math.floor(safe / 3600);
  const m = Math.floor((safe % 3600) / 60);
  const s = Math.floor(safe % 60);
  
  if (h > 0) {
    return `${h}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  }
  return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
}

/**
 * Formats seconds into M:SS (Ruler label format)
 */
export function formatRulerLabel(sec: number): string {
  const safe = Math.max(0, sec || 0);
  const mins = Math.floor(safe / 60);
  const secs = Math.floor(safe % 60);
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

/**
 * Converts a timestamp string (HH:MM:SS or MM:SS) to total seconds
 */
export function timestampToSeconds(ts: string | number): number {
  if (typeof ts === 'number') return ts;
  if (!ts || typeof ts !== 'string') return 0;
  const parts = ts.split(':').map(parseFloat);
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
  if (parts.length === 2) return parts[0] * 60 + parts[1];
  return parts[0] || 0;
}
/**
 * Chooses a tick step in seconds for a timeline ruler
 */
export function chooseTickStep(rawStep: number): number {
  const steps = [0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800];
  for (const step of steps) {
    if (step >= rawStep) return step;
  }
  return 3600;
}

/**
 * Snaps a time value to the nearest increment
 */
export function snapTime(value: number, snap: number): number {
  if (!snap || snap <= 0) return value;
  return Math.round(value / snap) * snap;
}

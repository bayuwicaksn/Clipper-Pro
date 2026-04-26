import { useMemo } from 'react';
import { chooseTickStep } from '@/utils/time';

export function useTimelineMath(
  totalDuration: number,
  zoom: number,
  appMode: 'clipper' | 'editor'
) {
  const zoomFactor = useMemo(() => {
    return zoom * (appMode === 'clipper' ? Math.max(1, Math.min(totalDuration / 120, 8)) : 1);
  }, [zoom, appMode, totalDuration]);

  const trackWidth = useMemo(() => {
    let raw = 1200 * zoomFactor;
    if (isNaN(raw) || !isFinite(raw)) raw = 1200;
    return Math.max(1200, Math.round(raw));
  }, [zoomFactor]);

  const frameCount = useMemo(() => {
    let raw = 26 * Math.min(zoomFactor, 3);
    if (isNaN(raw) || !isFinite(raw)) raw = 26;
    return Math.max(24, Math.round(raw));
  }, [zoomFactor]);

  const ticks = useMemo(() => {
    const desiredTicks = Math.max(8, Math.round(12 * zoomFactor));
    const tickStepSec = chooseTickStep(totalDuration / desiredTicks);
    const minorTickStepSec = tickStepSec / 5;
    const tickCount = Math.max(0, Math.floor(totalDuration / tickStepSec));
    
    const majorTicks = Array.from({ length: tickCount + 1 }, (_, i) => i * tickStepSec);
    const minorTicks = [];
    
    for (let majorIdx = 0; majorIdx < majorTicks.length - 1; majorIdx += 1) {
      const base = majorTicks[majorIdx];
      for (let i = 1; i < 5; i += 1) {
        const tick = base + i * minorTickStepSec;
        if (tick < totalDuration) minorTicks.push(tick);
      }
    }
    
    return { majorTicks, minorTicks, tickStepSec };
  }, [totalDuration, zoomFactor]);

  return {
    zoomFactor,
    trackWidth,
    frameCount,
    ...ticks
  };
}

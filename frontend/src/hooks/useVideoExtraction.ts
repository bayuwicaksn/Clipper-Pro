import { useState, useEffect, useRef } from 'react';
import * as api from '../api/client';

interface CachedFrame {
  timestamp: number;
  dataUrl: string;
}

const frameCache = new Map<string, CachedFrame[]>();
const MAX_FRAME_CACHE_ENTRIES = 24;

export function useVideoExtraction(
  jobId: string | undefined,
  startTime: number,
  totalDuration: number,
  frameCount: number
) {
  const [frames, setFrames] = useState<CachedFrame[]>([]);
  const [isExtracting, setIsExtracting] = useState(false);

  useEffect(() => {
    let canceled = false;

    async function extract() {
      if (!jobId) {
        setFrames([]);
        return;
      }

      const cacheKey = [
        jobId,
        Math.round(startTime * 1000),
        Math.round(totalDuration * 1000),
        frameCount,
      ].join(":");

      if (frameCache.has(cacheKey)) {
        setFrames(frameCache.get(cacheKey)!);
        return;
      }

      setIsExtracting(true);
      try {
        const video = document.createElement("video");
        video.crossOrigin = "anonymous";
        video.muted = true;
        video.playsInline = true;
        video.preload = "auto";
        video.src = `${api.API_BASE}/api/preview_source/${jobId}`;

        await new Promise((resolve, reject) => {
          video.onloadedmetadata = resolve;
          video.onerror = reject;
        });

        const canvas = document.createElement("canvas");
        const ctx = canvas.getContext("2d");
        if (!ctx) return;

        canvas.width = 160;
        canvas.height = 90;

        const extracted: CachedFrame[] = [];
        const interval = totalDuration / (frameCount - 1);

        for (let i = 0; i < frameCount; i++) {
          if (canceled) break;
          const time = startTime + i * interval;
          
          await new Promise<void>((resolve) => {
            const onSeeked = () => {
              video.removeEventListener("seeked", onSeeked);
              resolve();
            };
            video.addEventListener("seeked", onSeeked);
            video.currentTime = time;
          });

          ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
          extracted.push({
            timestamp: time,
            dataUrl: canvas.toDataURL("image/jpeg", 0.7),
          });
        }

        if (!canceled) {
          frameCache.set(cacheKey, extracted);
          setFrames(extracted);
          
          // Cleanup cache if too large
          while (frameCache.size > MAX_FRAME_CACHE_ENTRIES) {
            const firstKey = frameCache.keys().next().value;
            if (firstKey) frameCache.delete(firstKey);
          }
        }
      } catch (err) {
        console.error("Frame extraction error:", err);
      } finally {
        if (!canceled) setIsExtracting(false);
      }
    }

    extract();
    return () => { canceled = true; };
  }, [jobId, startTime, totalDuration, frameCount]);

  return { frames, isExtracting };
}

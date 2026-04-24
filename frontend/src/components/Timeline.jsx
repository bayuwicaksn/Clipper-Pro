import React from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { useCurrentPlayerFrame } from "../hooks/useCurrentPlayerFrame";
import {
  Pause,
  ChevronDown,
  ChevronsLeft,
  ChevronsRight,
  Grid2X2,
  Magnet,
  Play,
  Search,
  Trash2,
  ZoomIn,
  ZoomOut,
} from "lucide-react";

const frameCache = new Map();
const MAX_FRAME_CACHE_ENTRIES = 24;

function formatClock(sec) {
  const safe = Math.max(0, sec || 0);
  const mins = Math.floor(safe / 60);
  const secs = Math.floor(safe % 60);
  const cs = Math.floor((safe % 1) * 100);
  return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}.${cs
    .toString()
    .padStart(2, "0")}`;
}

function formatDuration(sec) {
  const safe = Math.max(0, sec || 0);
  const h = Math.floor(safe / 3600);
  const m = Math.floor((safe % 3600) / 60);
  const s = Math.floor(safe % 60);
  const cs = Math.floor((safe % 1) * 100);
  return `${h}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}.${cs
    .toString()
    .padStart(2, "0")}`;
}

function chooseTickStep(rawStep) {
  const steps = [0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800];
  for (const step of steps) {
    if (step >= rawStep) return step;
  }
  return 3600;
}

function formatRulerLabel(sec) {
  const safe = Math.max(0, sec || 0);
  const mins = Math.floor(safe / 60);
  const secs = Math.floor(safe % 60);
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

function snapTime(value, snap) {
  if (!snap || snap <= 0) return value;
  return Math.round(value / snap) * snap;
}

function cacheFrames(key, frames) {
  frameCache.set(key, frames);
  while (frameCache.size > MAX_FRAME_CACHE_ENTRIES) {
    const firstKey = frameCache.keys().next().value;
    frameCache.delete(firstKey);
  }
}

function seekTo(video, time) {
  return new Promise((resolve) => {
    const onSeeked = () => {
      video.removeEventListener("seeked", onSeeked);
      resolve();
    };
    video.addEventListener("seeked", onSeeked, { once: true });
    video.currentTime = time;
  });
}

export default function Timeline({
  playerRef,
  isPlayerReady,
  jobId,
  clip,
  segments = [],
  appMode = 'clipper',
  activeSegmentIndex,
  setActiveSegmentIndex,
  currentTime: propCurrentTime,
  isPlaying,
  onTogglePlay,
  onSeek,
  totalStart,
  totalEnd,
  onUpdateSegmentBounds,
  onDeleteSegment,
}) {
  const canvasRef = React.useRef(null);
  const isScrubbing = React.useRef(false);
  const dragRef = React.useRef(null);

  // 1. Get high-performance frame from Player
  const playerFrame = useCurrentPlayerFrame(playerRef, isPlayerReady);

  const [zoom, setZoom] = React.useState(1);
  const [frames, setFrames] = React.useState([]);
  const [snapEnabled, setSnapEnabled] = React.useState(true);
  const hasClip = Boolean(clip);

  const safeTotalStart = Number(totalStart) || 0;
  const safeTotalEnd = Number(totalEnd) || 0;

  const startTime = totalStart !== undefined ? safeTotalStart : segments[0]?.start || 0;
  const endTime = totalEnd !== undefined ? safeTotalEnd : segments[segments.length - 1]?.end || 0;
  const totalDuration = Math.max(0.1, endTime - startTime);

  // 2. Decide which time to use for display
  // If playing, use the high-performance player frame. If not, use the prop.
  const activeSegStart = segments[activeSegmentIndex]?.start ?? startTime;
  const currentTime = isPlaying
    ? (playerFrame / 30) + activeSegStart
    : propCurrentTime;

  const zoomFactor = zoom * (appMode === 'clipper' ? Math.max(1, Math.min(totalDuration / 120, 8)) : 1);

  let rawTrackWidth = 1200 * zoomFactor;
  if (isNaN(rawTrackWidth) || !isFinite(rawTrackWidth)) rawTrackWidth = 1200;
  const trackWidth = Math.max(1200, Math.round(rawTrackWidth));

  let rawFrameCount = 26 * Math.min(zoomFactor, 3); // Max out frame count so it doesn't freeze browser
  if (isNaN(rawFrameCount) || !isFinite(rawFrameCount)) rawFrameCount = 26;
  const frameCount = Math.max(24, Math.round(rawFrameCount));

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
  const snapStepSec = 0.01; // Frame-accurate snapping for smooth movement

  const hasInitiallyScrolled = React.useRef(false);

  // Reset initial scroll when mode or clip changes
  React.useEffect(() => {
    hasInitiallyScrolled.current = false;
  }, [appMode, clip]);

  // Auto-scroll to keep playhead in view during playback, scrubbing, or initial load
  React.useEffect(() => {
    if (!canvasRef.current) return;
    const scrollContainer = canvasRef.current.parentElement;
    if (!scrollContainer) return;

    const pct = getPct(currentTime) / 100;
    const playheadPx = pct * trackWidth;

    const scrollLeft = scrollContainer.scrollLeft;
    const viewportWidth = scrollContainer.clientWidth;
    const buffer = 150; // Increased padding

    // Center playhead on initial load
    if (!hasInitiallyScrolled.current && trackWidth > 0 && viewportWidth > 0) {
      scrollContainer.scrollLeft = Math.max(0, playheadPx - viewportWidth / 2);
      hasInitiallyScrolled.current = true;
      return;
    }

    if (!isPlaying && !isScrubbing.current) return;

    if (playheadPx > scrollLeft + viewportWidth - buffer) {
      scrollContainer.scrollLeft = playheadPx - viewportWidth + buffer + 150;
    } else if (playheadPx < scrollLeft + buffer) {
      scrollContainer.scrollLeft = Math.max(0, playheadPx - buffer);
    }
  }, [currentTime, isPlaying, trackWidth]);

  const getPct = (time) => {
    const p = ((Number(time) - startTime) / totalDuration) * 100;
    if (isNaN(p) || !isFinite(p)) return 0;
    return Math.max(0, Math.min(100, p));
  };

  React.useEffect(() => {
    let canceled = false;

    async function extractFrames() {
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
        setFrames(frameCache.get(cacheKey));
        return;
      }

      try {
        const video = document.createElement("video");
        video.crossOrigin = "anonymous";
        video.muted = true;
        video.playsInline = true;
        video.preload = "auto";
        video.src = `http://${window.location.hostname}:5000/api/preview_source/${jobId}`;

        await new Promise((resolve, reject) => {
          video.onloadedmetadata = resolve;
          video.onerror = reject;
        });

        const canvas = document.createElement("canvas");
        canvas.width = 128;
        canvas.height = 72;
        const ctx = canvas.getContext("2d");

        if (!ctx) {
          setFrames([]);
          return;
        }

        const extracted = [];
        for (let i = 0; i < frameCount; i += 1) {
          if (canceled) return;
          const t = startTime + (i / Math.max(1, frameCount - 1)) * totalDuration;
          await seekTo(video, Math.min(video.duration || t, Math.max(0, t)));
          try {
            ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
            extracted.push(canvas.toDataURL("image/jpeg", 0.62));
          } catch {
            break;
          }
        }
        if (!canceled) {
          if (extracted.length > 0) {
            cacheFrames(cacheKey, extracted);
            setFrames(extracted);
          } else {
            setFrames([]);
          }
        }
      } catch {
        if (!canceled) setFrames([]);
      }
    }

    extractFrames();
    return () => {
      canceled = true;
    };
  }, [jobId, startTime, totalDuration, frameCount]);

  function handleScrub(event) {
    if (!canvasRef.current || !onSeek) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const pct = Math.max(0, Math.min(1, x / rect.width));
    onSeek(startTime + pct * totalDuration);
  }

  function handleScrubMove(event) {
    if (!isScrubbing.current) return;
    handleScrub(event);
  }

  const handleScrubUp = () => {
    isScrubbing.current = false;
    document.removeEventListener("mousemove", handleScrubMove);
    document.removeEventListener("mouseup", handleScrubUp);
  };

  const handleScrubDown = (event) => {
    isScrubbing.current = true;
    handleScrub(event);
    document.addEventListener("mousemove", handleScrubMove);
    document.addEventListener("mouseup", handleScrubUp);
  };

  function handleDragMove(event) {
    if (!dragRef.current || !canvasRef.current || !onUpdateSegmentBounds) return;
    const drag = dragRef.current;
    const rect = canvasRef.current.getBoundingClientRect();
    const deltaPx = event.clientX - drag.startX;
    const deltaSec = (deltaPx / rect.width) * totalDuration;

    const base = drag.base;
    if (!base) return;

    const snap = snapEnabled ? snapStepSec : 0;

    if (drag.type === "start") {
      const nextStart = snapTime(base.start + deltaSec, snap);
      onUpdateSegmentBounds(drag.index, nextStart, base.end);
      if (onSeek) onSeek(nextStart); // Scrub preview to the new start point
    } else if (drag.type === "end") {
      const nextEnd = snapTime(base.end + deltaSec, snap);
      onUpdateSegmentBounds(drag.index, base.start, nextEnd);
      if (onSeek) onSeek(nextEnd); // Scrub preview to the new end point
    } else {
      const duration = base.end - base.start;
      const nextStart = snapTime(base.start + deltaSec, snap);
      onUpdateSegmentBounds(drag.index, nextStart, nextStart + duration);
      if (onSeek) onSeek(nextStart); // Scrub preview to the new start point
    }
  }

  const handleDragUp = () => {
    dragRef.current = null;
    document.removeEventListener("mousemove", handleDragMove);
    document.removeEventListener("mouseup", handleDragUp);
  };

  const startHandleDrag = (event, index, type) => {
    event.stopPropagation();
    if (!segments[index]) return;
    dragRef.current = {
      index,
      type,
      startX: event.clientX,
      base: { start: segments[index].start, end: segments[index].end },
    };
    document.addEventListener("mousemove", handleDragMove);
    document.addEventListener("mouseup", handleDragUp);
  };

  if (!hasClip) return null;

  return (
    <div className="nle-timeline-shell">
      <div className="nle-timeline-toolbar">
        <div className="nle-timeline-toolbar-left">
          <Button variant="ghost" size="sm" className="h-7 px-2 text-xs font-semibold">
            <ChevronDown data-icon="inline-start" />
            Hide timeline
          </Button>
          <Separator orientation="vertical" className="h-5" />
          <Button variant="ghost" size="icon" className="size-7">
            <Grid2X2 />
          </Button>
          {appMode === 'editor' && (
            <Button
              variant="ghost"
              size="icon"
              className="size-7"
              onClick={() => {
                if (activeSegmentIndex !== null && onDeleteSegment) {
                  onDeleteSegment(activeSegmentIndex);
                }
              }}
            >
              <Trash2 />
            </Button>
          )}
        </div>

        <div className="nle-timeline-toolbar-center">
          <Button variant="ghost" size="icon" className="size-7">
            <ChevronsLeft />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="size-8 rounded-md border border-border/70"
            onClick={onTogglePlay}
          >
            {isPlaying ? <Pause className="fill-current" /> : <Play className="fill-current" />}
          </Button>
          <Button variant="ghost" size="icon" className="size-7">
            <ChevronsRight />
          </Button>
          <span className="nle-timeline-timecode">
            {formatClock(currentTime)} <span>/</span> {formatDuration(totalDuration)}
          </span>
        </div>

        <div className="nle-timeline-toolbar-right">
          <Button
            variant={snapEnabled ? "secondary" : "ghost"}
            size="sm"
            className="h-7 px-2 text-xs"
            onClick={() => setSnapEnabled((v) => !v)}
          >
            <Magnet data-icon="inline-start" />
            Snap
          </Button>
          <ZoomOut className="size-3.5 text-muted-foreground" />
          <input
            type="range"
            min="0.8"
            max="2.2"
            step="0.1"
            value={zoom}
            onChange={(e) => setZoom(parseFloat(e.target.value))}
            className="nle-timeline-zoom-slider"
          />
          <ZoomIn className="size-3.5 text-muted-foreground" />
          <Button variant="ghost" size="icon" className="size-7">
            <Search />
          </Button>
        </div>
      </div>

      <div className="nle-timeline-track-wrap">
        {appMode === 'editor' && (
          <Button variant="secondary" size="icon" className="nle-timeline-add-btn">
            +
          </Button>
        )}

        <div className="nle-timeline-scroll custom-scrollbar">
          <div className="nle-timeline-canvas" ref={canvasRef} style={{ width: `${trackWidth}px` }}>
            <div className="nle-timeline-ruler">
              {minorTicks.map((tickSec) => (
                <div
                  key={`minor-${tickSec}`}
                  className="nle-timeline-ruler-tick minor"
                  style={{ left: `${(tickSec / totalDuration) * 100}%` }}
                >
                  <div className="nle-timeline-ruler-line" />
                </div>
              ))}

              {majorTicks.map((tickSec) => (
                <div
                  key={tickSec}
                  className="nle-timeline-ruler-tick"
                  style={{ left: `${(tickSec / totalDuration) * 100}%` }}
                >
                  <div className="nle-timeline-ruler-line" />
                  <span>{formatRulerLabel(startTime + tickSec)}</span>
                </div>
              ))}
            </div>

            <div className="nle-timeline-track-body">
              {segments.map((seg, idx) => {
                const safeStart = Number(seg.start) || 0;
                const safeEnd = Number(seg.end) || 0;
                const widthPct = ((safeEnd - safeStart) / totalDuration) * 100;
                const leftPct = ((safeStart - startTime) / totalDuration) * 100;
                const active = idx === activeSegmentIndex;
                
                // Calculate exactly how many 42px thumbnails fit in the segment's physical width
                const segmentWidthPx = (widthPct / 100) * trackWidth;
                const segmentFrameCount = Math.max(1, Math.round(segmentWidthPx / 42));

                // Skip rendering if bounds are invalid
                if (safeEnd <= safeStart || isNaN(safeStart) || isNaN(safeEnd)) return null;

                const segmentFrames = Array.from({ length: segmentFrameCount }, (_, frameIdx) => {
                  if (!frames.length) return null;

                  // Calculate the time at this specific thumbnail within the segment
                  const frameTime = safeStart + (frameIdx / Math.max(1, segmentFrameCount - 1)) * (safeEnd - safeStart);
                  // Map that time to a ratio within the global startTime / totalDuration range
                  const globalRatio = (frameTime - startTime) / totalDuration;
                  const sourceIndex = Math.min(frames.length - 1, Math.max(0, Math.round(globalRatio * (frames.length - 1))));

                  return frames[sourceIndex];
                });

                return (
                  <div key={seg.id || idx} className="nle-timeline-video-row">
                    <div className="nle-timeline-video-lane is-row">
                      <Badge variant="secondary" className="nle-timeline-row-badge">
                        V{idx + 1}
                      </Badge>
                      {idx === 0 && (
                        <Badge variant="secondary" className="nle-timeline-fit-badge">
                          Fit
                        </Badge>
                      )}

                      <div
                        className={`nle-timeline-segment-hit ${active ? "active" : ""}`}
                        style={{ left: `${leftPct}%`, width: `${Math.max(widthPct, 2)}%` }}
                        onMouseDown={(event) => {
                          event.stopPropagation();
                          if (setActiveSegmentIndex) setActiveSegmentIndex(idx);

                          if (active) {
                            startHandleDrag(event, idx, "move");
                          }
                        }}
                      >
                        <div className="nle-timeline-thumb-strip nle-timeline-thumb-strip--segment">
                          {segmentFrames.map((frame, thumbIdx) => (
                            <div key={thumbIdx} className="nle-timeline-thumb">
                              <div
                                className={`nle-timeline-thumb-image ${frame ? "has-frame" : ""}`}
                                style={
                                  frame
                                    ? {
                                      backgroundImage: `url(${frame})`,
                                      backgroundSize: "cover",
                                      backgroundPosition: "center",
                                      backgroundRepeat: "no-repeat",
                                    }
                                    : undefined
                                }
                              />
                            </div>
                          ))}
                        </div>

                        {active && (
                          <>
                            <div
                              className="nle-segment-handle start"
                              onMouseDown={(e) => {
                                e.stopPropagation();
                                startHandleDrag(e, idx, "start");
                              }}
                            />
                            <div
                              className="nle-segment-handle end"
                              onMouseDown={(e) => {
                                e.stopPropagation();
                                startHandleDrag(e, idx, "end");
                              }}
                            />
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}

              <div className="nle-timeline-audio-lane" />
            </div>

            <div
              className="nle-timeline-playhead"
              style={{ left: `${getPct(currentTime)}%` }}
              onMouseDown={(event) => {
                event.stopPropagation();
                handleScrubDown(event);
              }}
            >
              <div className="nle-timeline-playhead-head" />
              <div className="nle-timeline-playhead-line" />
            </div>
          </div>
        </div>

        {appMode === 'editor' && (
          <Button variant="secondary" size="icon" className="nle-timeline-add-btn">
            +
          </Button>
        )}
      </div>
    </div>
  );
}

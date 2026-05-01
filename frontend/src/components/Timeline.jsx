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

import { useEditorStore } from '@/store/editorStore';
import {
  formatClock,
  formatDuration,
  formatRulerLabel,
  snapTime,
  timestampToSeconds
} from "@/utils/time";

import { useTimelineMath } from "../hooks/useTimelineMath";
import { useVideoExtraction } from "../hooks/useVideoExtraction";

export default function Timeline({
  playerRef,
  onUpdateSegmentBounds,
  onDeleteSegment,
}) {
  const {
    project,
    clips,
    activeClipIndex,
    segments,
    activeSegmentIndex,
    setActiveSegmentIndex,
    currentTime: storeCurrentTime,
    setCurrentTime,
    isPlaying,
    setSeekRequested,
    appMode
  } = useEditorStore();

  const clip = clips[activeClipIndex];
  const hasClip = Boolean(clip);
  const clipperSegment = React.useMemo(() => {
    if (appMode !== 'clipper' || !clip) return null;
    return {
      id: 'clipper-main',
      start: Math.max(0, clip.start_time ? timestampToSeconds(clip.start_time) : 0),
      end: Math.max(1, clip.end_time ? timestampToSeconds(clip.end_time) : 60),
      crop_x: clip.custom_crop_x || 0.5,
    };
  }, [appMode, clip]);
  const timelineSegments = React.useMemo(
    () => appMode === 'clipper' && clipperSegment ? [clipperSegment] : segments,
    [appMode, clipperSegment, segments]
  );

  // Clip absolute bounds in the source video
  const clipStartSecs = Math.max(0, clip?.start_time ? timestampToSeconds(clip.start_time) : 0);
  const clipEndSecs = Math.max(1, clip?.end_time ? timestampToSeconds(clip.end_time) : (clip?.duration ? timestampToSeconds(clip.duration) : 60));

  // In editor mode: startTime = clipStart (absolute), totalEnd = clipEnd (absolute)
  // Segments are absolute (e.g. 45–111s). leftPct = (seg.start - startTime) / totalDuration
  // maps segment at 45s to 0% on the timeline. Ruler/timecode show relative (0:00–1:06).
  // In clipper mode: full video range.
  const startTime = appMode === 'clipper' ? 0 : clipStartSecs;
  const totalEnd = appMode === 'clipper'
    ? (project?.video_duration ? timestampToSeconds(project.video_duration) : clipEndSecs)
    : clipEndSecs;
  const totalDuration = Math.max(0.1, totalEnd - startTime);
  const normalizedTimelineSegments = React.useMemo(() => {
    return timelineSegments
      .map((seg) => {
        const rawStart = Number(seg.start);
        const rawEnd = Number(seg.end);
        if (!Number.isFinite(rawStart) || !Number.isFinite(rawEnd)) return null;
        return {
          ...seg,
          start: Math.max(startTime, Math.min(totalEnd, rawStart)),
          end: Math.max(startTime, Math.min(totalEnd, rawEnd)),
        };
      })
      .filter((seg) => seg !== null && seg.end > seg.start);
  }, [timelineSegments, startTime, totalEnd]);
  const snapStepSec = 0.01;

  const [zoom, setZoom] = React.useState(1);
  const [snapEnabled, setSnapEnabled] = React.useState(true);
  const canvasRef = React.useRef(null);
  const isScrubbing = React.useRef(false);
  const dragRef = React.useRef(null);
  const hasInitiallyScrolled = React.useRef(false);
  const prevTotalDuration = React.useRef(totalDuration);

  // Reset zoom when totalDuration changes significantly (e.g. switching from full video to clip)
  React.useEffect(() => {
    const ratio = totalDuration / prevTotalDuration.current;
    if (ratio < 0.3 || ratio > 3) {
      setZoom(1);
      hasInitiallyScrolled.current = false;
    }
    prevTotalDuration.current = totalDuration;
  }, [totalDuration]);

  const { trackWidth, frameCount, majorTicks, minorTicks } = useTimelineMath(totalDuration, zoom, appMode);
  const { frames } = useVideoExtraction(project?.id, startTime, totalDuration, frameCount);
  const playerFrame = useCurrentPlayerFrame(playerRef);


  const activeTimelineSegment = appMode === 'clipper'
    ? normalizedTimelineSegments[0]
    : normalizedTimelineSegments[activeSegmentIndex];
  const activeSegStart = activeTimelineSegment?.start ?? startTime;
  const rawCurrentTime = isPlaying
    ? (playerFrame / 30) + activeSegStart
    : storeCurrentTime;
  const currentTime = appMode === 'clipper' && activeTimelineSegment
    ? Math.max(activeTimelineSegment.start, Math.min(activeTimelineSegment.end, rawCurrentTime))
    : rawCurrentTime;

  const onSeek = (time) => {
    const safeTime = appMode === 'clipper' && activeTimelineSegment
      ? Math.max(activeTimelineSegment.start, Math.min(activeTimelineSegment.end, time))
      : Math.max(0, time);
    setSeekRequested(safeTime);
    setCurrentTime(safeTime);
  };

  const onTogglePlay = () => useEditorStore.getState().setIsPlaying(!isPlaying);

  const getPct = React.useCallback((time) => {
    const p = ((Number(time) - startTime) / totalDuration) * 100;
    if (isNaN(p) || !isFinite(p)) return 0;
    return Math.max(0, Math.min(100, p));
  }, [startTime, totalDuration]);

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
  }, [currentTime, isPlaying, trackWidth, getPct]);

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
    if (!normalizedTimelineSegments[index]) return;
    dragRef.current = {
      index,
      type,
      startX: event.clientX,
      base: { start: normalizedTimelineSegments[index].start, end: normalizedTimelineSegments[index].end },
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
            {formatClock(appMode === 'editor' ? Math.max(0, currentTime - startTime) : currentTime)} <span>/</span> {formatDuration(totalDuration)}
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
            max="5"
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
                  <span>{formatRulerLabel(appMode === 'clipper' ? startTime + tickSec : tickSec)}</span>
                </div>
              ))}
            </div>

            <div className="nle-timeline-track-body">
              {normalizedTimelineSegments.map((seg, idx) => {
                const safeStart = Number(seg.start) || 0;
                const safeEnd = Number(seg.end) || 0;
                const widthPct = ((safeEnd - safeStart) / totalDuration) * 100;
                const leftPct = ((safeStart - startTime) / totalDuration) * 100;
                const active = appMode === 'clipper' ? idx === 0 : idx === activeSegmentIndex;

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
                      {idx === 0 && appMode === 'clipper' && (
                        <Badge variant="secondary" className="nle-timeline-fit-badge">
                          Fit
                        </Badge>
                      )}

                      <div
                        className={`nle-timeline-segment-hit ${active ? "active" : ""}`}
                        style={{ left: `${leftPct}%`, width: `${Math.max(widthPct, (4 / trackWidth) * 100)}%` }}
                        onMouseDown={(event) => {
                          event.stopPropagation();
                          if (setActiveSegmentIndex) setActiveSegmentIndex(idx);

                          // Seek to the start of the selected segment
                          if (onSeek) onSeek(seg.start);

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

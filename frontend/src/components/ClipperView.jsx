import React from 'react';
import Preview from './CustomPreview';
import Timeline from './Timeline';
import { timestampToSeconds, formatTimeHHMMSS } from "@/utils/time";

import { useEditorStore } from '@/store/editorStore';

export default function ClipperView({
  playerRef,
  setIsPlayerReady,
  isPlayerReady
}) {
  const {
    project,
    clips,
    activeClipIndex,
    currentTime,
    setCurrentTime,
    seekRequested,
    setSeekRequested,
    isPlaying,
    setIsPlaying,
    aspectRatio,
    setClips
  } = useEditorStore();

  const activeClip = clips[activeClipIndex];
  const activeClipStart = activeClip?.start_time ? timestampToSeconds(activeClip.start_time) : 0;
  const activeClipEnd = activeClip?.end_time ? timestampToSeconds(activeClip.end_time) : 60;
  const autoBackgroundEnabled = activeClip?.auto_background_enabled !== false;

  const setAutoBackgroundEnabled = (enabled) => {
    setClips(prev => {
      const updated = [...prev];
      if (updated[activeClipIndex]) {
        updated[activeClipIndex] = {
          ...updated[activeClipIndex],
          auto_background_enabled: enabled
        };
      }
      return updated;
    });
  };

  const handleSegmentBoundsChange = (segmentIndex, nextStart, nextEnd) => {
    setClips(prev => {
      const updated = [...prev];
      const clip = { ...updated[activeClipIndex] };
      let safeStart = Math.max(0, Math.min(nextStart, nextEnd - 1));
      let safeEnd = Math.max(safeStart + 1, nextEnd);
      if (project?.video_duration && safeEnd > project.video_duration) safeEnd = project.video_duration;
      clip.start_time = formatTimeHHMMSS(safeStart);
      clip.end_time = formatTimeHHMMSS(safeEnd);
      updated[activeClipIndex] = clip;
      return updated;
    });
  };

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* PREVIEW AREA */}
      <div className="flex-1 relative w-full overflow-hidden flex items-center justify-center min-h-0">
        <Preview
          playerRef={playerRef}
          setPlayerReady={setIsPlayerReady}
          appMode="clipper"
          jobId={project?.id}
          aspectRatio={aspectRatio}
          startSecs={activeClipStart}
          endSecs={activeClipEnd}
          currentTime={currentTime}
          cropX={activeClip?.custom_crop_x || 0.5}
          cropY={0.5}
          cropZ={1.0}
          autoBackgroundEnabled={autoBackgroundEnabled}
          setCropX={(newX) => {
            const updated = [...clips];
            updated[activeClipIndex] = { ...updated[activeClipIndex], custom_crop_x: newX };
            setClips(updated);
          }}
          onTimeUpdate={setCurrentTime}
          seekRequested={seekRequested}
          playing={isPlaying}
          onSegmentEnd={() => setIsPlaying(false)}
        />
      </div>

      {/* TIMELINE AREA */}
      <div className="nle-bottom-panel bg-card border-t border-border h-64 flex flex-col flex-shrink-0">
        <div className="nle-player-controls nle-player-controls--minimal">
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 text-xs font-semibold text-muted-foreground">
              <span>Auto Background</span>
              <button
                type="button"
                onClick={() => setAutoBackgroundEnabled(!autoBackgroundEnabled)}
                className={`w-[42px] h-[22px] rounded-full p-0.5 transition-colors ${autoBackgroundEnabled ? 'bg-primary' : 'bg-muted'}`}
                aria-pressed={autoBackgroundEnabled}
              >
                <span className={`block size-[18px] rounded-full bg-background shadow transition-transform ${autoBackgroundEnabled ? 'translate-x-5' : 'translate-x-0'}`} />
              </button>
            </label>
            <div className="nle-player-pill">
              CLIPPER MODE - CLIP {activeClipIndex + 1}
            </div>
          </div>
          <div className="font-mono text-xs tabular-nums">
             <span className="text-foreground font-bold">{new Date(Math.max(0, currentTime) * 1000).toISOString().substr(11, 8).replace(/^00:/, '')}</span>
             <span className="text-muted-foreground/30 mx-2">/</span>
             <span className="text-muted-foreground">
               {project?.video_duration ? formatTimeHHMMSS(project.video_duration) : '00:00'}
             </span>
          </div>
        </div>
        <div className="flex-1 overflow-hidden">
          <Timeline
            playerRef={playerRef}
            isPlayerReady={isPlayerReady}
            jobId={project?.id}
            clip={activeClip}
            segments={[{
              id: 'clipper-main',
              start: Math.max(0, activeClipStart),
              end: Math.max(1, activeClipEnd),
              crop_x: 0.5
            }]}
            appMode="clipper"
            totalStart={0}
            totalEnd={project?.video_duration ? timestampToSeconds(project.video_duration) : (activeClip?.duration ? timestampToSeconds(activeClip.duration) : 60)}
            activeSegmentIndex={0}
            currentTime={Math.max(0, currentTime)}
            onSeek={(time) => {
              setSeekRequested(Math.max(0, time));
              setCurrentTime(Math.max(0, time));
            }}
            isPlaying={isPlaying}
            onTogglePlay={() => setIsPlaying(!isPlaying)}
            onUpdateSegmentBounds={handleSegmentBoundsChange}
          />
        </div>
      </div>
    </div>
  );
}


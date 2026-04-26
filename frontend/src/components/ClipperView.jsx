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
          startSecs={0}
          endSecs={activeClip?.end_time ? timestampToSeconds(activeClip.end_time) : 60}
          currentTime={currentTime}
          cropX={activeClip?.custom_crop_x || 0.5}
          cropY={0.5}
          cropZ={1.0}
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
              start: Math.max(0, activeClip?.start_time ? timestampToSeconds(activeClip.start_time) : 0),
              end: Math.max(1, activeClip?.end_time ? timestampToSeconds(activeClip.end_time) : 60),
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


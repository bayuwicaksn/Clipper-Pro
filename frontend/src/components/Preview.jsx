import React, { useEffect, useMemo, useRef } from 'react';
import { Player } from '@remotion/player';
import { Clipper } from '../remotion/Clipper';

/**
 * Preview Component
 * A wrapper around Remotion Player that handles the video preview,
 * cropping, and caption rendering.
 */
const Preview = ({
  playerRef,
  setPlayerReady,
  appMode,
  jobId,
  startSecs,
  endSecs,
  currentTime,
  cropX,
  cropY,
  cropZ,
  setCropX,
  setCropY,
  setCropZ,
  onTimeUpdate,
  seekRequested,
  playing,
  onSegmentEnd,
  transcript,
  captionSettings,
}) => {
  
  // Calculate duration in frames (30 fps)
  const fps = 30;
  const durationInFrames = Math.max(1, Math.floor((endSecs - startSecs) * fps));

  // Sync seek requests
  useEffect(() => {
    if (seekRequested !== undefined && playerRef.current) {
        // seekRequested is in absolute seconds. 
        // Player frame is relative to startSecs.
        const frame = Math.floor((seekRequested - startSecs) * fps);
        playerRef.current.seekTo(Math.max(0, Math.min(frame, durationInFrames - 1)));
    }
  }, [seekRequested, startSecs, durationInFrames, playerRef]);

  // Sync playing state
  useEffect(() => {
    if (!playerRef.current) return;
    if (playing) {
      playerRef.current.play();
    } else {
      playerRef.current.pause();
    }
  }, [playing, playerRef]);

  // Handle time updates from the player
  const handleFrameUpdate = (frame) => {
    const absoluteTime = startSecs + (frame / fps);
    onTimeUpdate(absoluteTime);
    
    // Check for segment end
    if (frame >= durationInFrames - 1) {
       onSegmentEnd();
    }
  };

  // Memoize input props for Clipper to avoid unnecessary re-renders
  const inputProps = useMemo(() => ({
    videoSrc: `${window.location.protocol}//${window.location.hostname}:5000/api/preview_source/${jobId}`,
    transcript: transcript.map(t => ({
        text: t.text || t.word || "",
        startMs: t.startMs ?? (t.fromMs ?? 0),
        endMs: t.endMs ?? (t.toMs ?? 0)
    })),
    cropX,
    cropY,
    zoom: cropZ,
    startSecs,
    isPreview: true,
    appMode,
    captionSettings
  }), [jobId, transcript, cropX, cropY, cropZ, startSecs, appMode, captionSettings]);

  return (
    <div className="w-full h-full flex items-center justify-center bg-black/20 rounded-xl overflow-hidden shadow-2xl relative group">
      <Player
        ref={playerRef}
        component={Clipper}
        durationInFrames={durationInFrames}
        fps={fps}
        compositionWidth={1080}
        compositionHeight={1920}
        style={{
          width: '100%',
          height: '100%',
          maxHeight: '100%',
        }}
        inputProps={inputProps}
        controls={false}
        loop={false}
        autoPlay={playing}
        onFrameUpdate={handleFrameUpdate}
        onReady={() => setPlayerReady(true)}
      />
      
      {/* Play/Pause Overlay Indicator (Subtle) */}
      {!playing && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/10 pointer-events-none transition-opacity duration-300 opacity-0 group-hover:opacity-100">
           <div className="w-16 h-16 rounded-full bg-white/10 backdrop-blur-sm border border-white/20 flex items-center justify-center">
              <div className="w-0 h-0 border-t-[10px] border-t-transparent border-l-[15px] border-l-white border-b-[10px] border-b-transparent ml-1" />
           </div>
        </div>
      )}
    </div>
  );
};

export default Preview;

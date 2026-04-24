import React, { useEffect, useRef, useState, useCallback } from 'react';
import { CustomCaptions } from './CustomCaptions';

/**
 * Custom Preview Component
 * Replaces legacy player with standard HTML5 <video> and React state.
 */
const CustomPreview = ({
  playerRef,
  setPlayerReady,
  appMode,
  jobId,
  aspectRatio = '9:16',
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
  const videoRef = useRef(null);
  const listenersRef = useRef({ frameupdate: new Set() });
  const [isVideoReady, setIsVideoReady] = useState(false);
  const [currentTimeMs, setCurrentTimeMs] = useState(0);
  const [videoAspectRatio, setVideoAspectRatio] = useState(16 / 9);

  const videoSrc = `${window.location.protocol}//${window.location.hostname}:5000/api/preview_source/${jobId}`;

  // Interactive Dragging State
  const [dragState, setDragState] = useState(null); // { type: 'pan' | 'resize', startX, startY, initialX, initialY, initialZ }

  const startPan = useCallback((e) => {
    e.preventDefault();
    setDragState({
      type: 'pan',
      startX: e.clientX,
      startY: e.clientY,
      initialX: cropX || 0.5,
      initialY: cropY || 0.5
    });
  }, [cropX, cropY]);

  const startResize = useCallback((e, handle) => {
    e.preventDefault();
    e.stopPropagation();
    setDragState({
      type: 'resize',
      handle,
      startX: e.clientX,
      startY: e.clientY,
      initialZ: cropZ || 1.0
    });
  }, [cropZ]);

  const [isSnappedX, setIsSnappedX] = useState(false);
  const [isSnappedY, setIsSnappedY] = useState(false);

  useEffect(() => {
    if (!dragState) {
      setIsSnappedX(false);
      setIsSnappedY(false);
      return;
    }

    const handleMouseMove = (e) => {
      const dx = e.clientX - dragState.startX;
      const dy = e.clientY - dragState.startY;

      if (dragState.type === 'pan') {
        const container = videoRef.current?.parentElement;
        if (!container) return;

        const sensitivityX = 1 / (container.clientWidth * (cropZ || 1.0));
        const sensitivityY = 1 / (container.clientHeight * (cropZ || 1.0));

        let newX = dragState.initialX - dx * sensitivityX;
        let newY = dragState.initialY - dy * sensitivityY;

        // Snapping Logic (Center)
        const snapThreshold = 0.015;
        const snappedX = Math.abs(newX - 0.5) < snapThreshold;
        const snappedY = Math.abs(newY - 0.5) < snapThreshold;

        if (snappedX) newX = 0.5;
        if (snappedY) newY = 0.5;

        setIsSnappedX(snappedX);
        setIsSnappedY(snappedY);

        setCropX(Math.max(0, Math.min(1, newX)));
        setCropY(Math.max(0, Math.min(1, newY)));
      } else if (dragState.type === 'resize') {
        const sensitivity = 0.005;
        const zoomDelta = (dragState.handle.includes('t') ? -dy : dy) * sensitivity;
        setCropZ(Math.max(1.0, Math.min(5.0, dragState.initialZ + zoomDelta)));
      }
    };

    const handleMouseUp = () => {
      setDragState(null);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [dragState, cropZ, setCropX, setCropY, setCropZ]);

  // Expose methods to the parent via playerRef
  useEffect(() => {
    if (playerRef) {
      playerRef.current = {
        play: () => videoRef.current?.play(),
        pause: () => videoRef.current?.pause(),
        seekTo: (frame) => {
          if (videoRef.current) {
            const timeInSeconds = startSecs + (frame / 30);
            videoRef.current.currentTime = timeInSeconds;
            listenersRef.current['frameupdate']?.forEach(cb => cb());
          }
        },
        getCurrentFrame: () => {
          if (!videoRef.current) return 0;
          return Math.floor(Math.max(0, videoRef.current.currentTime - startSecs) * 30);
        },
        addEventListener: (event, callback) => {
          if (!listenersRef.current[event]) listenersRef.current[event] = new Set();
          listenersRef.current[event].add(callback);
        },
        removeEventListener: (event, callback) => {
          if (listenersRef.current[event]) {
            listenersRef.current[event].delete(callback);
          }
        }
      };
      setPlayerReady(true);
    }
  }, [playerRef, startSecs, setPlayerReady]);

  // Handle Play/Pause props
  useEffect(() => {
    if (!videoRef.current) return;
    if (playing) {
      videoRef.current.play().catch(e => console.warn("Play interrupted", e));
    } else {
      videoRef.current.pause();
    }
  }, [playing]);

  // Handle Seek Requested
  useEffect(() => {
    if (seekRequested !== undefined && videoRef.current) {
      videoRef.current.currentTime = seekRequested;
      listenersRef.current['frameupdate']?.forEach(cb => cb());
    }
  }, [seekRequested]);

  // Handle segment start changes
  useEffect(() => {
    if (videoRef.current && !playing && isVideoReady) {
      if (Math.abs(videoRef.current.currentTime - startSecs) > 0.1) {
        videoRef.current.currentTime = startSecs;
        listenersRef.current['frameupdate']?.forEach(cb => cb());
      }
    }
  }, [startSecs, playing, isVideoReady]);

  // Time Updates
  useEffect(() => {
    let animationFrameId;
    const updateTime = () => {
      if (videoRef.current) {
        const time = videoRef.current.currentTime;
        setCurrentTimeMs(time * 1000);
        onTimeUpdate(time);
        listenersRef.current['frameupdate']?.forEach(cb => cb());

        if (time >= endSecs && playing) {
          videoRef.current.pause();
          onSegmentEnd();
        }
      }
      animationFrameId = requestAnimationFrame(updateTime);
    };

    if (playing) {
      animationFrameId = requestAnimationFrame(updateTime);
    } else {
      if (videoRef.current) {
        setCurrentTimeMs(videoRef.current.currentTime * 1000);
        listenersRef.current['frameupdate']?.forEach(cb => cb());
      }
    }

    return () => cancelAnimationFrame(animationFrameId);
  }, [playing, onTimeUpdate, endSecs, onSegmentEnd]);

  const handleVideoCanPlay = () => {
    if (!isVideoReady) {
      setIsVideoReady(true);
      if (videoRef.current) {
        videoRef.current.currentTime = Math.max(0, startSecs);
      }
    }
  };

  // Video style for cropping - making it wrap the ACTUAL content
  const safeZ = cropZ || 1;
  const safeX = cropX || 0.5;
  const safeY = cropY || 0.5;

  const videoTransform = appMode === 'editor'
    ? `scale(${safeZ}) translate(${(0.5 - safeX) * 100}%, ${(0.5 - safeY) * 100}%)`
    : 'none';

  return (
    <div className="w-full h-full flex items-center justify-center bg-black rounded-xl overflow-hidden shadow-2xl relative">

      <div className="w-full h-full relative flex items-center justify-center overflow-hidden">

        {/* PROPORTIONAL VIDEO WRAPPER */}
        <div
          style={{
            position: 'relative',
            maxWidth: '100%',
            maxHeight: '100%',
            aspectRatio: videoAspectRatio || '16/9',
            transform: videoTransform,
            transformOrigin: 'center center',
            transition: dragState ? 'none' : 'transform 0.15s ease-out',
            zIndex: 10,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            // High visibility border in Editor Mode
            outline: appMode === 'editor'
              ? (dragState ? '4px solid #3b82f6' : '2px solid #3b82f6')
              : 'none',
            boxShadow: (appMode === 'editor' && dragState) ? '0 0 30px rgba(59, 130, 246, 0.6)' : 'none',
          }}
        >
          <video
            ref={videoRef}
            src={videoSrc}
            className="w-full h-full object-contain pointer-events-none"
            playsInline
            muted
            crossOrigin="anonymous"
            onCanPlay={handleVideoCanPlay}
            onLoadedMetadata={(e) => {
              if (e.target.videoHeight) {
                setVideoAspectRatio(e.target.videoWidth / e.target.videoHeight);
              }
            }}
          />

          {/* Interactive Handles (Inside the wrapper, so they track perfectly) */}
          {appMode === 'editor' && (
            <>
              {/* Internal Panning Area */}
              <div
                className="absolute inset-0 cursor-move pointer-events-auto z-10"
                onMouseDown={startPan}
              />

              {/* Corner Handles - Extremely high z-index and bright color */}
              <div className="absolute -top-3 -left-3 w-6 h-6 bg-white border-4 border-[#3b82f6] rounded-full cursor-nw-resize pointer-events-auto shadow-2xl z-50 hover:scale-125 transition-transform" onMouseDown={(e) => startResize(e, 'tl')} />
              <div className="absolute -top-3 -right-3 w-6 h-6 bg-white border-4 border-[#3b82f6] rounded-full cursor-ne-resize pointer-events-auto shadow-2xl z-50 hover:scale-125 transition-transform" onMouseDown={(e) => startResize(e, 'tr')} />
              <div className="absolute -bottom-3 -left-3 w-6 h-6 bg-white border-4 border-[#3b82f6] rounded-full cursor-sw-resize pointer-events-auto shadow-2xl z-50 hover:scale-125 transition-transform" onMouseDown={(e) => startResize(e, 'bl')} />
              <div className="absolute -bottom-3 -right-3 w-6 h-6 bg-white border-4 border-[#3b82f6] rounded-full cursor-se-resize pointer-events-auto shadow-2xl z-50 hover:scale-125 transition-transform" onMouseDown={(e) => startResize(e, 'br')} />
            </>
          )}
        </div>

        {/* Global Pan Area (Fallthrough for clicking outside the video) */}
        {appMode === 'editor' && (
          <div className="absolute inset-0 z-0 pointer-events-auto cursor-move" onMouseDown={startPan} />
        )}

        {/* 9:16 Mask & Vertical Frame Guidelines */}
        {appMode === 'editor' && (
          <div className="absolute inset-0 pointer-events-none flex items-center justify-center z-[20]">
            {aspectRatio === '9:16' ? (
              <>
                <div className="h-full bg-black/80 flex-1 border-r border-white/10" />
                <div 
                  className="h-full border-x border-white/20 shadow-[0_0_100px_rgba(0,0,0,0.9)] relative" 
                  style={{ aspectRatio: '9/16' }}
                >
                  {/* SNAP LINES (ONLY INSIDE VERTICAL FRAME) */}
                  {dragState && isSnappedX && (
                    <div className="absolute left-1/2 top-0 h-full w-[1px] bg-blue-400/50 -translate-x-1/2" />
                  )}
                  {dragState && isSnappedY && (
                    <div className="absolute top-1/2 left-0 w-full h-[1px] bg-blue-400/50 -translate-y-1/2" />
                  )}
                </div>
                <div className="h-full bg-black/80 flex-1 border-l border-white/10" />
              </>
            ) : (
              /* Horizontal Frame Guidelines */
              dragState && (isSnappedX || isSnappedY) && (
                <div className="absolute inset-0">
                  {isSnappedX && <div className="absolute left-1/2 top-0 h-full w-[1px] bg-blue-400/30 -translate-x-1/2" />}
                  {isSnappedY && <div className="absolute top-1/2 left-0 w-full h-[1px] bg-blue-400/30 -translate-y-1/2" />}
                </div>
              )
            )}
          </div>
        )}

        {/* Captions */}
        {transcript && transcript.length > 0 && (
          <div className="absolute inset-0 z-40 pointer-events-none flex items-center justify-center">
            <div className="relative h-full" style={{ aspectRatio: aspectRatio === '9:16' ? '9/16' : '16/9' }}>
              <CustomCaptions transcript={transcript} styleType="classic" settings={captionSettings} currentTimeMs={currentTimeMs} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default CustomPreview;

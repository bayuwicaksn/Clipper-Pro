import React, { useEffect, useRef, useState, useCallback } from 'react';
import { Minus, Plus } from 'lucide-react';
import { CustomCaptions } from './CustomCaptions';
import * as api from "../api/client";

/**
 * Custom Preview Component
 * Replaces legacy player with standard HTML5 <video> and React state.
 */
import { useEditorStore } from '@/store/editorStore';
import { useInteractivePreview } from '@/hooks/useInteractivePreview';

const CustomPreview = ({
  playerRef,
  setPlayerReady,
  startSecs,
  endSecs,
  cropX,
  cropY,
  cropZ,
  setCropX,
  setCropY,
  setCropZ,
  onSegmentEnd,
}) => {
  const {
    project,
    aspectRatio,
    currentTime,
    setCurrentTime,
    seekRequested,
    isPlaying: playing,
    transcript,
    captionSettings,
    setCaptionSettings,
    panX, setPanX,
    panY, setPanY,
    videoAspectRatio, setVideoAspectRatio,
    appMode
  } = useEditorStore();

  const onTimeUpdate = (time) => setCurrentTime(time);
  const jobId = project?.id;
  const videoRef = useRef(null);
  const captionOverlayRef = useRef(null);
  const aspectRatioBoxRef = useRef(null);
  const scrollAreaRef = useRef(null);
  const listenersRef = useRef({ frameupdate: new Set() });
  const [isVideoReady, setIsVideoReady] = useState(false);
  const [currentTimeMs, setCurrentTimeMs] = useState(0);
  const [viewZoom, setViewZoom] = useState(1.0); // 1.0 = Fit

  const [activeElement, setActiveElement] = useState(null); // null | 'video' | 'caption'

  const {
    dragState, setDragState,
    isCanvasPanning, setIsCanvasPanning,
    isSnappedX, isSnappedY, isSnappedZ, isSnappedCaptionX,
    canvasPanStart
  } = useInteractivePreview(videoRef, aspectRatioBoxRef, captionOverlayRef, {
    cropX, cropY, cropZ, setCropX, setCropY, setCropZ, captionSettings, setCaptionSettings, videoAspectRatio
  });

  const handleZoomChange = useCallback((newZoom) => {
    setViewZoom(newZoom);
    if (newZoom === 1.0) {
      setPanX(0);
      setPanY(0);
    }
  }, []);

  const videoSrc = jobId ? `${api.API_BASE}/api/preview_source/${jobId}` : null;

  const startPan = useCallback((e) => {
    e.preventDefault();
    setDragState({
      type: 'pan',
      startX: e.clientX,
      startY: e.clientY,
      initialX: cropX || 0.5,
      initialY: cropY || 0.5,
      initialZ: cropZ
    });
  }, [cropX, cropY, cropZ, setDragState]);

  const startCanvasPan = useCallback((e) => {
    if (e.target.closest('[data-no-canvas-pan]')) return;
    setActiveElement(null);
    setIsCanvasPanning(true);
    canvasPanStart.current = { x: e.clientX, y: e.clientY, panX: panX, panY: panY };
  }, [setIsCanvasPanning, canvasPanStart, panX, panY]);

  const handleCanvasDoubleClick = useCallback((e) => {
    if (e.target.closest('[data-no-canvas-pan]')) return;
    handleZoomChange(1.0); // Reset zoom to Fit
    setPanX(0);            // Center pan
    setPanY(0);
  }, [handleZoomChange]);

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
  }, [cropZ, setDragState]);

  const startCaptionDrag = useCallback((e) => {
    if (appMode !== 'editor') return;
    e.preventDefault();
    e.stopPropagation();
    setDragState({
      type: 'caption-pan',
      startX: e.clientX,
      startY: e.clientY,
      initialX: captionSettings?.captionX ?? 0.5,
      initialY: captionSettings?.captionY ?? 0.8
    });
  }, [appMode, captionSettings, setDragState]);

  const startCaptionResize = useCallback((e) => {
    if (appMode !== 'editor') return;
    e.preventDefault();
    e.stopPropagation();
    setDragState({
      type: 'caption-resize',
      startX: e.clientX,
      startY: e.clientY,
      initialSize: captionSettings?.fontSize ?? 42,
      initialWidth: captionSettings?.captionWidth ?? 85
    });
  }, [appMode, captionSettings, setDragState]);

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
    <div className="nle-player-container relative w-full h-full bg-[#1a1a1a] rounded-xl overflow-hidden group shadow-2xl">
      {/* Zoom Controls Overlay - FIXED (Outside scroll area) */}
      <div className="absolute bottom-6 right-6 z-[100] flex items-center gap-1 bg-[#121212]/90 backdrop-blur-md border border-white/10 p-1.5 rounded-full shadow-2xl pointer-events-auto transition-opacity opacity-0 group-hover:opacity-100">
        <button
          onClick={() => handleZoomChange(Math.max(0.25, viewZoom - 0.25))}
          className="w-8 h-8 flex items-center justify-center rounded-full hover:bg-white/10 text-white/70 hover:text-white transition-colors"
          title="Zoom Out"
        >
          <Minus size={16} />
        </button>

        <div className="h-4 w-[1px] bg-white/10 mx-1" />

        <button
          onClick={() => handleZoomChange(1.0)}
          className={`px-3 py-1 text-[11px] font-medium rounded-full transition-all ${viewZoom === 1.0
            ? 'bg-blue-600 text-white'
            : 'text-white/50 hover:text-white hover:bg-white/5'
            }`}
        >
          Fit
        </button>

        <div className="px-3 py-1 text-[11px] font-medium text-white/70 min-w-[42px] text-center tabular-nums">
          {Math.round(viewZoom * 100)}%
        </div>

        <div className="h-4 w-[1px] bg-white/10 mx-1" />

        <button
          onClick={() => handleZoomChange(Math.min(4.0, viewZoom + 0.25))}
          className="w-8 h-8 flex items-center justify-center rounded-full hover:bg-white/10 text-white/70 hover:text-white transition-colors"
          title="Zoom In"
        >
          <Plus size={16} />
        </button>
      </div>

      {/* CANVAS AREA - Figma-style Drag to Pan */}
      <div
        ref={scrollAreaRef}
        className={`w-full h-full overflow-hidden flex items-center justify-center p-8 scrollbar-none select-none ${isCanvasPanning ? 'cursor-grabbing' : 'cursor-grab'}`}
        onMouseDown={startCanvasPan}
        onDoubleClick={handleCanvasDoubleClick}
      >
        <div
          className="relative flex items-center justify-center flex-shrink-0"
          style={{
            height: `${viewZoom * 100}%`,
            aspectRatio: (aspectRatio === '9:16' || aspectRatio === '4:5' || aspectRatio === '1:1')
              ? aspectRatio.replace(':', '/')
              : '16/9',
            minHeight: viewZoom === 1.0 ? '100%' : 'auto',
            transform: `translate(${panX}px, ${panY}px)`,
            transition: isCanvasPanning ? 'none' : 'transform 0.15s ease-out',
            border: '1px solid rgba(255,255,255,0.12)',
            boxShadow: '0 0 0 1px rgba(255,255,255,0.06), 0 8px 32px rgba(0,0,0,0.6)',
            backgroundColor: 'black'
          }}
        >
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
              // High visibility border ONLY when active - Compensate for cropZ scale
              outline: appMode === 'editor' && activeElement === 'video'
                ? `${(dragState ? 2.5 : 1.5) / (cropZ || 1.0)}px solid #3b82f6`
                : 'none',
              boxShadow: (appMode === 'editor' && activeElement === 'video' && dragState) ? '0 0 30px rgba(59, 130, 246, 0.6)' : 'none',
            }}
          >
            <video
              ref={videoRef}
              src={videoSrc}
              className="w-full h-full object-contain pointer-events-none"
              playsInline
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
                {/* Selectable Overlay (when not active) */}
                {activeElement !== 'video' && (
                  <div
                    className="absolute inset-0 z-20 pointer-events-auto cursor-pointer"
                    onClick={() => setActiveElement('video')}
                  />
                )}

                {/* Internal Panning Area & Corner Handles (only when active) */}
                {activeElement === 'video' && (
                  <>
                    <div
                      data-no-canvas-pan
                      className="absolute inset-0 cursor-move pointer-events-auto z-10"
                      onMouseDown={(e) => { setActiveElement('video'); startPan(e); }}
                    />

                    {/* Corner Handles - Compensate scale to keep size consistent */}
                    <div
                      data-no-canvas-pan
                      className="absolute -top-2 -left-2 w-4 h-4 bg-white border-[3px] border-[#3b82f6] rounded-full cursor-nw-resize pointer-events-auto shadow-2xl z-50 transition-transform hover:brightness-110"
                      style={{ transform: `scale(${1 / (cropZ || 1.0)})` }}
                      onMouseDown={(e) => startResize(e, 'tl')}
                    />
                    <div
                      data-no-canvas-pan
                      className="absolute -top-2 -right-2 w-4 h-4 bg-white border-[3px] border-[#3b82f6] rounded-full cursor-ne-resize pointer-events-auto shadow-2xl z-50 transition-transform hover:brightness-110"
                      style={{ transform: `scale(${1 / (cropZ || 1.0)})` }}
                      onMouseDown={(e) => startResize(e, 'tr')}
                    />
                    <div
                      data-no-canvas-pan
                      className="absolute -bottom-2 -left-2 w-4 h-4 bg-white border-[3px] border-[#3b82f6] rounded-full cursor-sw-resize pointer-events-auto shadow-2xl z-50 transition-transform hover:brightness-110"
                      style={{ transform: `scale(${1 / (cropZ || 1.0)})` }}
                      onMouseDown={(e) => startResize(e, 'bl')}
                    />
                    <div
                      data-no-canvas-pan
                      className="absolute -bottom-2 -right-2 w-4 h-4 bg-white border-[3px] border-[#3b82f6] rounded-full cursor-se-resize pointer-events-auto shadow-2xl z-50 transition-transform hover:brightness-110"
                      style={{ transform: `scale(${1 / (cropZ || 1.0)})` }}
                      onMouseDown={(e) => startResize(e, 'br')}
                    />
                  </>
                )}
              </>
            )}
          </div>


          {/* DYNAMIC SAFE AREA MASK & SMART SNAPPING */}
          {appMode === 'editor' && (
            <div className="absolute inset-0 pointer-events-none flex items-center justify-center z-[20]">
              {(aspectRatio === '9:16' || aspectRatio === '4:5' || aspectRatio === '1:1') ? (
                <>
                  <div className="h-full bg-black/80 flex-1 border-r border-white/10" />
                  <div
                    className={`h-full border-x transition-colors duration-200 shadow-[0_0_100px_rgba(0,0,0,0.9)] relative ${isSnappedZ ? 'border-blue-400/80' : 'border-white/20'}`}
                    style={{ aspectRatio: aspectRatio.replace(':', '/') }}
                  >
                    {/* SNAP LINES (CLIPPED TO ACTIVE FRAME) */}
                    {dragState && isSnappedX && (
                      <div className="absolute left-1/2 top-0 h-full w-[1.5px] bg-blue-400 shadow-[0_0_8px_rgba(96,165,250,0.6)] -translate-x-1/2" />
                    )}
                    {dragState && isSnappedY && (
                      <div className="absolute top-1/2 left-0 w-full h-[1.5px] bg-blue-400 shadow-[0_0_8px_rgba(96,165,250,0.6)] -translate-y-1/2" />
                    )}
                  </div>
                  <div className="h-full bg-black/80 flex-1 border-l border-white/10" />
                </>
              ) : (
                /* Global Snapping Lines for Horizontal */
                dragState && (isSnappedX || isSnappedY) && (
                  <div className="absolute inset-0">
                    {isSnappedX && <div className="absolute left-1/2 top-0 h-full w-[1.5px] bg-blue-400/60 -translate-x-1/2" />}
                    {isSnappedY && <div className="absolute top-1/2 left-0 w-full h-[1.5px] bg-blue-400/60 -translate-y-1/2" />}
                  </div>
                )
              )}
            </div>
          )}

          {/* Captions - Proportional to Video Frame */}
          {transcript && transcript.length > 0 && captionSettings?.presetId !== 'none' && (
            <div className="absolute inset-0 z-40 pointer-events-none flex items-center justify-center">
              <div
                ref={aspectRatioBoxRef}
                className="relative h-full overflow-visible pointer-events-none"
                style={{
                  aspectRatio: (aspectRatio === '9:16' || aspectRatio === '4:5' || aspectRatio === '1:1')
                    ? aspectRatio.replace(':', '/')
                    : '16/9'
                }}
              >
                {/* Interaction Overlay for Captions */}
                {appMode === 'editor' && (
                  <div
                    ref={captionOverlayRef}
                    data-no-canvas-pan
                    className={`absolute group pointer-events-auto cursor-move ${dragState?.type?.startsWith('caption') ? 'z-[60]' : 'z-50'}`}
                    style={{
                      left: `${(captionSettings?.captionX ?? 0.5) * 100}%`,
                      top: `${(captionSettings?.captionY ?? 0.8) * 100}%`,
                      transform: "translate(-50%, -50%)",
                      width: `${captionSettings?.captionWidth ?? 100}%`,
                      height: `${(captionSettings?.fontSize ?? 32) * 2.5}px`,
                      // Dynamic Outline based on selection state
                      outline: activeElement === 'caption'
                        ? (dragState?.type?.startsWith('caption') ? '4px solid #3b82f6' : '2px solid #3b82f6')
                        : 'none',
                      boxShadow: (activeElement === 'caption' && dragState?.type?.startsWith('caption')) ? '0 0 30px rgba(59, 130, 246, 0.6)' : 'none',
                      borderRadius: '4px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      transition: dragState?.type?.startsWith('caption') ? 'none' : 'all 0.15s ease-out'
                    }}
                    onMouseDown={(e) => { setActiveElement('caption'); startCaptionDrag(e); }}
                  >
                    {/* Handles only visible when active */}
                    {activeElement === 'caption' && (
                      <>
                        <div data-no-canvas-pan className="absolute -top-3 -left-3 w-6 h-6 bg-white border-4 border-[#3b82f6] rounded-full cursor-nw-resize pointer-events-auto shadow-2xl z-50 hover:scale-125 transition-transform" onMouseDown={startCaptionResize} />
                        <div data-no-canvas-pan className="absolute -top-3 -right-3 w-6 h-6 bg-white border-4 border-[#3b82f6] rounded-full cursor-ne-resize pointer-events-auto shadow-2xl z-50 hover:scale-125 transition-transform" onMouseDown={startCaptionResize} />
                        <div data-no-canvas-pan className="absolute -bottom-3 -left-3 w-6 h-6 bg-white border-4 border-[#3b82f6] rounded-full cursor-sw-resize pointer-events-auto shadow-2xl z-50 hover:scale-125 transition-transform" onMouseDown={startCaptionResize} />
                        <div data-no-canvas-pan className="absolute -bottom-3 -right-3 w-6 h-6 bg-white border-4 border-[#3b82f6] rounded-full cursor-se-resize pointer-events-auto shadow-2xl z-50 hover:scale-125 transition-transform" onMouseDown={startCaptionResize} />
                      </>
                    )}

                    {isSnappedCaptionX && (
                      <div className="absolute left-1/2 top-[-100vh] h-[200vh] w-[1.5px] bg-blue-400 shadow-[0_0_8px_rgba(96,165,250,0.6)] -translate-x-1/2 z-0" />
                    )}
                  </div>
                )}

                <CustomCaptions
                  transcript={transcript}
                  styleType="classic"
                  settings={captionSettings}
                  currentTimeMs={currentTimeMs}
                />
              </div>
            </div>
          )}
        </div>

        {/* Helper Tooltip Overlay */}
        <div className="absolute bottom-6 left-6 z-[100] text-[10px] text-white/20 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
          Double click to reset view
        </div>
      </div>
    </div>
  );
};

export default CustomPreview;

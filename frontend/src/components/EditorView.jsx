import React from 'react';
import Preview from './CustomPreview';
import Timeline from './Timeline';
import Sidebar from './Sidebar';
import TranscriptPanel from './TranscriptPanel';
import { Button } from '@/components/ui/button';
import { 
  Scissors, Layers, Wand2, Cloud, LayoutTemplate, 
  Film, Sparkles, Type, Music, Zap 
} from 'lucide-react';

export default function EditorView({
  project,
  activeClip,
  activeClipIndex,
  segments,
  activeSegmentIndex,
  setActiveSegmentIndex,
  playerRef,
  setIsPlayerReady,
  currentTime,
  setCurrentTime,
  seekRequested,
  setSeekRequested,
  isPlaying,
  setIsPlaying,
  aspectRatio,
  transcript,
  isLoadingTranscript,
  loadTranscript,
  captionSettings,
  setCaptionSettings,
  setSegments,
  handleSplit,
  handleAutoSplit,
  handleAutoTrack,
  handleSegmentBoundsChange,
  handleDeleteSegment,
  handleSegmentEndPlayback,
  activeTab,
  setActiveTab,
  presets,
  isPlayerReady,
  setTranscript
}) {
  const activeSegment = segments[activeSegmentIndex];

  function NavItem({ id, icon: Icon, label, active, onClick }) {
    return (
      <div
        className={`nle-nav-item ${active ? 'active' : ''}`}
        onClick={() => onClick(active ? null : id)}
      >
        <Icon className="w-5 h-5" />
        <span className="nle-nav-label">{label}</span>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="nle-main-split">
        {/* FAR LEFT: TRANSCRIPT PANEL */}
        <TranscriptPanel
          transcript={transcript}
          currentTime={currentTime}
          isLoadingTranscript={isLoadingTranscript}
          setSeekRequested={setSeekRequested}
          setCurrentTime={setCurrentTime}
          loadTranscript={loadTranscript}
        />

        {/* CENTER: PREVIEW AREA */}
        <div className="nle-center-panel flex-1 bg-background relative flex flex-col overflow-hidden">
          <div className="flex-1 relative w-full overflow-hidden flex items-center justify-center min-h-0">
            {activeSegment && (
              <Preview
                playerRef={playerRef}
                setPlayerReady={setIsPlayerReady}
                appMode="editor"
                jobId={project?.id}
                aspectRatio={aspectRatio}
                startSecs={activeSegment.start}
                endSecs={activeSegment.end}
                currentTime={currentTime}
                cropX={activeSegment.crop_x || 0.5}
                cropY={activeSegment.crop_y || 0.5}
                cropZ={activeSegment.crop_z || 1.0}
                setCropX={(newX) => {
                  const newSegs = [...segments];
                  if (newSegs[activeSegmentIndex]) newSegs[activeSegmentIndex].crop_x = newX;
                  setSegments(newSegs);
                }}
                setCropY={(newY) => {
                  const newSegs = [...segments];
                  if (newSegs[activeSegmentIndex]) newSegs[activeSegmentIndex].crop_y = newY;
                  setSegments(newSegs);
                }}
                setCropZ={(newZ) => {
                  const newSegs = [...segments];
                  if (newSegs[activeSegmentIndex]) newSegs[activeSegmentIndex].crop_z = newZ;
                  setSegments(newSegs);
                }}
                onTimeUpdate={setCurrentTime}
                seekRequested={seekRequested}
                playing={isPlaying}
                onSegmentEnd={handleSegmentEndPlayback}
                transcript={transcript}
                captionSettings={captionSettings}
                setCaptionSettings={setCaptionSettings}
              />
            )}
          </div>
        </div>

        {/* RIGHT PANEL: SIDEBAR */}
        {activeTab && (
          <div className="nle-right-panel w-[360px] bg-card border-l border-border flex flex-col overflow-hidden">
            <Sidebar
              presets={presets}
              clip={activeClip}
              jobId={project?.id}
              clipIndex={activeSegmentIndex}
              activeTab={activeTab}
              captionSettings={captionSettings}
              setCaptionSettings={setCaptionSettings}
              currentTime={currentTime}
              onSeek={(time) => {
                setSeekRequested(time);
                setCurrentTime(time);
              }}
              transcript={transcript}
              setTranscript={setTranscript}
              isLoadingTranscript={isLoadingTranscript}
              onRegenerateTranscript={loadTranscript}
              onSplit={handleSplit}
              onAutoSplit={handleAutoSplit}
              onAutoTrack={handleAutoTrack}
            />
          </div>
        )}

        {/* NAVIGATION RIBBON */}
        <div className="nle-tools-ribbon">
          <NavItem id="ai-enhance" icon={Wand2} label="AI enhance" active={activeTab === 'ai-enhance'} onClick={setActiveTab} />
          <NavItem id="captions" icon={Layers} label="Captions" active={activeTab === 'captions'} onClick={setActiveTab} />
          <NavItem id="media" icon={Cloud} label="Media" active={activeTab === 'media'} onClick={setActiveTab} />
          <NavItem id="brand" icon={LayoutTemplate} label="Brand template" active={activeTab === 'brand'} onClick={setActiveTab} />
          <NavItem id="b-roll" icon={Film} label="B-Roll" active={activeTab === 'b-roll'} onClick={setActiveTab} />
          <NavItem id="transitions" icon={Sparkles} label="Transitions" active={activeTab === 'transitions'} onClick={setActiveTab} />
          <NavItem id="text" icon={Type} label="Text" active={activeTab === 'text'} onClick={setActiveTab} />
          <NavItem id="music" icon={Music} label="Music" active={activeTab === 'music'} onClick={setActiveTab} />
          <NavItem id="ai-hook" icon={Zap} label="AI hook" active={activeTab === 'ai-hook'} onClick={setActiveTab} />
        </div>
      </div>

      {/* BOTTOM PANEL: TIMELINE */}
      <div className="nle-bottom-panel bg-card border-t border-border h-64 flex flex-col flex-shrink-0">
        <div className="nle-player-controls nle-player-controls--minimal">
          <div className="flex items-center gap-3">
            <div className="nle-player-pill">
              EDITOR MODE - CLIP {activeClipIndex + 1}
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="font-mono text-xs tabular-nums">
              <span className="text-foreground font-bold">{new Date(Math.max(0, currentTime) * 1000).toISOString().substr(11, 8).replace(/^00:/, '')}</span>
              <span className="text-muted-foreground/30 mx-2">/</span>
              <span className="text-muted-foreground">
                {activeClip ? (activeClip.duration || activeClip.duration_display || '00:00') : '00:00'}
              </span>
            </div>
            <Button variant="secondary" size="sm" onClick={handleSplit} className="h-8 px-3 font-semibold">
              <Scissors className="size-3.5 mr-1.5" /> Split
            </Button>
          </div>
        </div>
        <div className="flex-1 overflow-hidden">
          <Timeline
            playerRef={playerRef}
            isPlayerReady={isPlayerReady}
            jobId={project?.id}
            clip={activeClip}
            segments={segments}
            appMode="editor"
            totalStart={Math.max(0, activeClip?.start_time ? timestampToSeconds(activeClip.start_time) : 0)}
            totalEnd={Math.max(1, activeClip?.end_time ? timestampToSeconds(activeClip.end_time) : (activeClip?.duration ? timestampToSeconds(activeClip.duration) : 60))}
            activeSegmentIndex={activeSegmentIndex}
            setActiveSegmentIndex={setActiveSegmentIndex}
            currentTime={Math.max(0, currentTime)}
            onSeek={(time) => {
              setSeekRequested(Math.max(0, time));
              setCurrentTime(Math.max(0, time));
            }}
            isPlaying={isPlaying}
            onTogglePlay={() => setIsPlaying((v) => !v)}
            onUpdateSegmentBounds={handleSegmentBoundsChange}
            onDeleteSegment={handleDeleteSegment}
          />
        </div>
      </div>
    </div>
  );
}

// Helpers duplicated here or extracted to a separate file later if needed
function timestampToSeconds(ts) {
  if (typeof ts === 'number') return ts;
  if (!ts || typeof ts !== 'string') return 0;
  const parts = ts.split(':').map(parseFloat);
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
  if (parts.length === 2) return parts[0] * 60 + parts[1];
  return parts[0] || 0;
}

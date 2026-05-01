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



import { useEditorStore } from '@/store/editorStore';

const PLAYER_SIZE_STORAGE_KEY = 'nle_editor_player_panel_size';
const MIN_PLAYER_SIZE = 0.25;
const MAX_PLAYER_SIZE = 4.0;
const DEFAULT_PLAYER_SIZE = 1.0;

function clampPlayerSize(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return DEFAULT_PLAYER_SIZE;
  return Math.max(MIN_PLAYER_SIZE, Math.min(MAX_PLAYER_SIZE, numeric));
}

function getStoredPlayerSize() {
  if (typeof window === 'undefined') return DEFAULT_PLAYER_SIZE;
  return clampPlayerSize(window.localStorage.getItem(PLAYER_SIZE_STORAGE_KEY));
}

function saveStoredPlayerSize(value) {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(PLAYER_SIZE_STORAGE_KEY, String(clampPlayerSize(value)));
}

function NavItem({ id, icon, label, active, onClick }) {
  const Icon = icon;
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

export default function EditorView({
  playerRef,
  setIsPlayerReady,
  isPlayerReady,
  presets,
  handleSplit,
  handleAutoSplit,
  handleAutoTrack,
  handleSegmentEndPlayback,
  handleDeleteSegment,
  handleSegmentBoundsChange
}) {
  const {
    clips, setClips,
    activeClipIndex,
    segments, setSegments,
    activeSegmentIndex,
    currentTime,
    fetchTranscript,
    activeTab, setActiveTab
  } = useEditorStore();

  const activeClip = clips[activeClipIndex];
  const activeSegment = segments[activeSegmentIndex];
  const editorPlayerSize = clampPlayerSize(activeSegment?.crop_z ?? getStoredPlayerSize());
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



  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="nle-main-split">
        {/* FAR LEFT: TRANSCRIPT PANEL */}
        <TranscriptPanel />

        {/* CENTER: PREVIEW AREA */}
        <div className="nle-center-panel flex-1 bg-background relative flex flex-col overflow-hidden">
          <div className="flex-1 relative w-full overflow-hidden flex items-center justify-center min-h-0">
            {activeSegment && (
              <Preview
                playerRef={playerRef}
                setPlayerReady={setIsPlayerReady}
                appMode="editor"
                startSecs={activeSegment.start}
                endSecs={activeSegment.end}
                cropX={activeSegment.crop_x || 0.5}
                cropY={activeSegment.crop_y || 0.5}
                cropZ={editorPlayerSize}
                autoBackgroundEnabled={autoBackgroundEnabled}
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
                  const safeZ = clampPlayerSize(newZ);
                  saveStoredPlayerSize(safeZ);
                  const newSegs = [...segments];
                  if (newSegs[activeSegmentIndex]) newSegs[activeSegmentIndex].crop_z = safeZ;
                  setSegments(newSegs);
                }}
                onSegmentEnd={handleSegmentEndPlayback}
              />
            )}
          </div>
        </div>

        {/* RIGHT PANEL: SIDEBAR */}
        {activeTab && (
          <div className="nle-right-panel w-[360px] bg-card border-l border-border flex flex-col overflow-hidden">
            <Sidebar
              presets={presets}
              onRegenerateTranscript={() => fetchTranscript(true)}
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
            onUpdateSegmentBounds={handleSegmentBoundsChange}
            onDeleteSegment={handleDeleteSegment}
          />
        </div>
      </div>
    </div>
  );
}


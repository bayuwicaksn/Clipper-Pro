import React, { useState, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import './EditorNLE.css';
import ClipperView from './ClipperView';
import EditorView from './EditorView';
import {
  ChevronLeft, Save, Download,
  Scissors, Layers
} from 'lucide-react';
import { timestampToSeconds } from "@/utils/time";
import * as api from "../api/client";

import { useEditorStore } from '@/store/editorStore';

const PLAYER_SIZE_STORAGE_KEY = 'nle_editor_player_panel_size';
const MIN_PLAYER_SIZE = 0.25;
const MAX_PLAYER_SIZE = 4.0;
const DEFAULT_PLAYER_SIZE = 1.0;

function getStoredPlayerSize() {
  if (typeof window === 'undefined') return DEFAULT_PLAYER_SIZE;
  const numeric = Number(window.localStorage.getItem(PLAYER_SIZE_STORAGE_KEY));
  if (!Number.isFinite(numeric)) return DEFAULT_PLAYER_SIZE;
  return Math.max(MIN_PLAYER_SIZE, Math.min(MAX_PLAYER_SIZE, numeric));
}

export default function EditorLayout({ project: initialProject, initialClipIndex = 0, onClose, notify }) {
  const playerRef = useRef(null);
  const [isPlayerReady, setIsPlayerReady] = useState(false);
  const [presets, setPresets] = useState([]);
  const [showAutoSplitConfirm, setShowAutoSplitConfirm] = useState(false);

  // Store State
  const {
    project, setProject,
    clips,
    activeClipIndex, setActiveClipIndex,
    appMode, setAppMode,
    segments, setSegments,
    activeSegmentIndex, setActiveSegmentIndex,
    captionSettings,
    currentTime, setCurrentTime,
    setSeekRequested,
    isPlaying, setIsPlaying,
    aspectRatio, setAspectRatio,
    isProcessing,
    statusMessage,
    exportProgress,
    saveStatus,
    isLoadingSavedState,
    loadProjectData,
    loadEditorState,
    saveEditorState,
    fetchTranscript,
    splitSegment,
    deleteSegment,
    updateSegmentBounds,
    handleSegmentEndPlayback,
    autoSplitSegments,
    autoTrackFace,
    startExport
  } = useEditorStore();

  const activeClip = clips[activeClipIndex];
  const activeClipStart = activeClip?.start_time ? timestampToSeconds(activeClip.start_time) : 0;
  const activeClipEnd = activeClip?.end_time ? timestampToSeconds(activeClip.end_time) : 60;

  const handleAutoSplitClick = () => {
    if (segments.length > 1) {
      setShowAutoSplitConfirm(true);
    } else {
      autoSplitSegments(notify);
    }
  };

  const confirmAutoSplit = () => {
    setShowAutoSplitConfirm(false);
    autoSplitSegments(notify);
  };

  // Initialize Project and Data
  React.useEffect(() => {
    if (initialProject) {
      setProject(initialProject);
      setActiveClipIndex(initialClipIndex);
      loadProjectData(initialProject.id);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps -- store setters are stable
  }, [initialProject, initialClipIndex]);

  // Handle Clip/State Loading
  React.useEffect(() => {
    if (project?.id && clips.length > 0) {
      loadEditorState(project.id, activeClipIndex);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps -- loadEditorState is stable
  }, [project?.id, activeClipIndex, clips.length]);

  // Safety: Clamp activeClipIndex
  React.useEffect(() => {
    if (clips.length > 0 && activeClipIndex >= clips.length) {
      setActiveClipIndex(0);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps -- setActiveClipIndex is stable
  }, [clips, activeClipIndex]);

  // In clipper mode, the segment is derived locally (activeSegment above).
  // Do NOT overwrite the shared segments store — that destroys editor auto-split data.
  // Only initialize segments if they are completely empty (first load, no saved state).
  React.useEffect(() => {
    if (appMode !== 'clipper' || !activeClip || activeClipEnd <= activeClipStart) return;
    if (segments.length > 0) return; // Preserve existing segments (editor auto-split data)

    setSegments([{
      id: 'clipper-main',
      start: activeClipStart,
      end: activeClipEnd,
      crop_x: activeClip.custom_crop_x ?? 0.5,
      crop_y: 0.5,
      crop_z: getStoredPlayerSize(),
      auto_background_enabled: activeClip.auto_background_enabled !== false
    }]);
    setActiveSegmentIndex(0);
  // eslint-disable-next-line react-hooks/exhaustive-deps -- only re-init segments on clip/mode change
  }, [
    appMode,
    activeClipIndex,
    activeClipStart,
    activeClipEnd,
    activeClip?.custom_crop_x,
    activeClip?.auto_background_enabled,
    project?.id
  ]);

  // Refetch transcript against current in-memory clip bounds, even before save.
  React.useEffect(() => {
    if (!activeClip || activeClipEnd <= activeClipStart) return;

    const timer = setTimeout(() => {
      fetchTranscript();
    }, 250);

    return () => clearTimeout(timer);
  // eslint-disable-next-line react-hooks/exhaustive-deps -- only refetch on clip bounds change
  }, [
    activeClipStart,
    activeClipEnd,
    activeClipIndex,
    project?.id
  ]);

  // Clipper Mode: Seek to start
  React.useEffect(() => {
    if (appMode === 'clipper' && activeClip) {
      setSeekRequested(activeClipStart);
      setCurrentTime(activeClipStart);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps -- intentionally omit setCurrentTime/setSeekRequested
  }, [activeClipIndex, appMode, activeClipStart]);

  // Fetch Presets
  React.useEffect(() => {
    api.fetchCaptionPresets()
      .then(data => {
        const noCaption = {
          id: 'none',
          name: 'None',
          icon: '🚫',
          font: { family: 'Inter', size: 90 },
          colors: { primary: '#666', outline: 'transparent' }
        };
        const PRESET_ICONS = {
          'classic': '🎬', 'default': '⭐', 'explosive': '💥', 'fast': '🏃',
          'hype': '🔥', 'line-focus': '📄', 'minimalist': '🤍', 'model': '🎥',
          'neo-minimal': '🖤', 'retro-gaming': '👾', 'vibrant': '🌈', 'word-focus': '🎯',
        };

        const pycapsPresets = (data.presets || []).map(p => ({
          id: p.id,
          name: p.name,
          icon: PRESET_ICONS[p.id] || '✨',
          font: { family: p.config?.fontName || 'Anton', size: p.config?.fontSize || 120 },
          colors: { primary: p.config?.primaryColor || '#FFFFFF', outline: p.config?.outlineColor || '#000000' },
          layout: { vertical_margin: p.config?.verticalMargin || 400 },
          css: p.config?.css || ''
        }));
        setPresets([noCaption, ...pycapsPresets]);
      })
      .catch(err => console.error("Could not fetch presets", err));
  }, []);

  // Keyboard Shortcuts
  React.useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.code === 'Space' && e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') {
        e.preventDefault();
        setIsPlaying(!isPlaying);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  // eslint-disable-next-line react-hooks/exhaustive-deps -- setIsPlaying is stable
  }, [isPlaying]);

  // Sync Active Segment
  React.useEffect(() => {
    if (segments.length === 0) return;
    if (!isPlaying && activeSegmentIndex !== -1) return;
    const epsilon = 0.005;
    let index = segments.findIndex(s => currentTime >= s.start - epsilon && currentTime < s.end - epsilon);
    if (index === -1) {
      const last = segments[segments.length - 1];
      if (currentTime >= last.end - epsilon) {
        index = segments.length - 1;
      }
    }
    if (index !== -1 && index !== activeSegmentIndex) {
      setActiveSegmentIndex(index);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps -- setActiveSegmentIndex is stable
  }, [currentTime, segments, isPlaying, activeSegmentIndex]);

  // Auto-save
  React.useEffect(() => {
    if (isLoadingSavedState) return;
    const timer = setTimeout(() => {
      saveEditorState();
    }, 2000);
    return () => clearTimeout(timer);
  // eslint-disable-next-line react-hooks/exhaustive-deps -- saveEditorState is stable
  }, [segments, captionSettings, clips, activeClipIndex, activeSegmentIndex, isLoadingSavedState, appMode]);




  const handleManualSave = async () => {
    await saveEditorState();
    if (useEditorStore.getState().saveStatus === 'saved') {
      notify("Progress saved successfully!", "success");
    } else {
      notify("Failed to save progress", "error");
    }
  };

  return (
    <div className="nle-workspace bg-background text-foreground font-sans">
      {/* Top Header */}
      <header className="nle-topbar border-b border-border bg-card/50 backdrop-blur-md px-6 py-3 flex justify-between items-center">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={onClose} className="hover:bg-accent">
            <ChevronLeft className="w-4 h-4 mr-1" /> Back
          </Button>
          <div className="text-sm font-bold tracking-tight">{project?.title || 'Untitled Project'}</div>
          <div className="flex items-center gap-2 px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider border border-border text-muted-foreground">
            {saveStatus === 'saving' && <div className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />}
            {saveStatus === 'saved' && <div className="w-1.5 h-1.5 rounded-full bg-green-500" />}
            {saveStatus === 'saving' ? 'Saving...' : 'Saved'}
          </div>
        </div>

        {/* MODE TOGGLE */}
        <div className="flex items-center bg-accent/50 p-1 rounded-lg border border-border">
          <button
            className={`px-4 py-1.5 text-sm font-medium rounded-md transition-all ${appMode === 'clipper' ? 'bg-background shadow text-foreground' : 'text-muted-foreground hover:text-foreground'}`}
            onClick={() => setAppMode('clipper')}
          >
            <Scissors className="w-4 h-4 inline mr-1.5 align-text-bottom" />
            Clipper
          </button>
          <button
            className={`px-4 py-1.5 text-sm font-medium rounded-md transition-all ${appMode === 'editor' ? 'bg-background shadow text-foreground' : 'text-muted-foreground hover:text-foreground'}`}
            onClick={() => setAppMode('editor')}
          >
            <Layers className="w-4 h-4 inline mr-1.5 align-text-bottom" />
            Editor
          </button>
        </div>

        <div className="flex items-center gap-2">
          {appMode === 'editor' && (
          <div className="flex items-center bg-white/5 rounded-lg p-1 border border-white/10">
            {['9:16', '16:9'].map(ratio => (
              <button
                key={ratio}
                onClick={() => setAspectRatio(ratio)}
                className={`px-3 py-1.5 rounded-md text-xs font-bold transition-all ${aspectRatio === ratio ? 'bg-blue-600 text-white shadow-lg' : 'text-foreground/40 hover:text-foreground/70'}`}
              >
                {ratio}
              </button>
            ))}
          </div>
          )}
          <Button variant="outline" size="sm" onClick={handleManualSave} disabled={saveStatus === 'saving'} className="h-8 font-bold">
            <Save className="w-3.5 h-3.5 mr-1.5" /> Save
          </Button>
          <Button size="sm" onClick={() => startExport(notify)} disabled={segments.length === 0} className="h-8 font-bold bg-white text-black hover:bg-white/90">
            <Download className="w-3.5 h-3.5 mr-1.5" /> Export Clip
          </Button>
        </div>
      </header>

      {/* Main View Area */}
      {appMode === 'clipper' ? (
        <ClipperView
          playerRef={playerRef}
          setIsPlayerReady={setIsPlayerReady}
          isPlayerReady={isPlayerReady}
        />
      ) : (
        <EditorView
          playerRef={playerRef}
          setIsPlayerReady={setIsPlayerReady}
          isPlayerReady={isPlayerReady}
          presets={presets}
          handleSplit={splitSegment}
          handleAutoSplit={handleAutoSplitClick}
          handleAutoTrack={() => autoTrackFace(notify)}
          handleSegmentBoundsChange={updateSegmentBounds}
          handleDeleteSegment={deleteSegment}
          handleSegmentEndPlayback={handleSegmentEndPlayback}
        />
      )}

      {/* PROCESSING OVERLAY */}
      {isProcessing && (
        <div className="absolute inset-0 bg-background/80 backdrop-blur-md z-[9999] flex flex-col items-center justify-center text-center p-6">
          <div className="nle-loader mb-6" />
          <h2 className="text-xl font-bold mb-2">Processing...</h2>
          <p className="text-primary font-medium mb-8">{statusMessage}</p>
          <div className="nle-export-progress-outer w-72">
            <div className="nle-export-progress-inner" style={{ width: `${exportProgress}%` }} />
            <span className="nle-export-progress-label">{exportProgress}%</span>
          </div>
          <p className="text-muted-foreground text-sm mt-8 opacity-60">This may take a minute. Please don't close the browser.</p>
        </div>
      )}

      <Dialog open={showAutoSplitConfirm} onOpenChange={setShowAutoSplitConfirm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirm Auto Split</DialogTitle>
            <DialogDescription>
              This will replace all {segments.length} existing segments. This cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowAutoSplitConfirm(false)}>Cancel</Button>
            <Button variant="destructive" onClick={confirmAutoSplit}>Replace Segments</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}


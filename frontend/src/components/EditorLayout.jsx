import React, { useState, useRef } from 'react';
import { Button } from '@/components/ui/button';
import './EditorNLE.css'; 
import ClipperView from './ClipperView';
import EditorView from './EditorView';
import {
  ChevronLeft, Save, Download,
  Scissors, Layers
} from 'lucide-react';

export default function EditorLayout({ project, initialClipIndex = 0, onClose, notify }) {
  const playerRef = useRef(null);
  const [isPlayerReady, setIsPlayerReady] = useState(false);
  const [clips, setClips] = useState([]);
  const [activeClipIndex, setActiveClipIndex] = useState(initialClipIndex);

  // App Mode: 'clipper' or 'editor'
  const [appMode, setAppMode] = useState('clipper');

  // Segments for reframing: [{ start, end, crop_x }]
  const [segments, setSegments] = useState([]);
  const [activeSegmentIndex, setActiveSegmentIndex] = useState(0);
  const [activeTab, setActiveTab] = useState('captions');

  // Caption Settings
  const [captionSettings, setCaptionSettings] = useState({
    presetId: 'default',
    fontName: 'Montserrat',
    fontSize: 42,
    primaryColor: '#FFFFFF',
    outlineColor: '#000000',
    outlineWidth: 8,
    fontWeight: 'Black',
    isItalic: false,
    isUnderline: false,
    isUppercase: true,
    shadowEnabled: true,
    shadowColor: '#000000',
    shadowOffsetX: 2,
    shadowOffsetY: 2,
    shadowBlur: 2,
    autoHighlight: true,
    highlightColorGreen: '#04f827',
    highlightColorYellow: '#fffd03',
    lineLimit: 2,
    captionX: 0.5,
    captionY: 0.82,
    verticalMargin: 150
  });

  const apiBase = `http://${window.location.hostname}:5000`;

  const loadTranscript = async (jobId, clipIdx, forceRedo = false) => {
    if (!jobId) return;
    setIsLoadingTranscript(true);
    try {
      const url = `${apiBase}/api/transcript/${jobId}/${clipIdx}${forceRedo ? '?force=true' : ''}`;
      const res = await fetch(url);
      const data = await res.json();
      if (Array.isArray(data)) {
        setTranscript(data);
      }
    } catch (err) {
      console.error("Failed to load transcript", err);
    } finally {
      setIsLoadingTranscript(false);
    }
  };

  const activeClip = clips[activeClipIndex];

  const activeSegment = appMode === 'clipper' ? {
    start: activeClip?.start_time ? timestampToSeconds(activeClip.start_time) : 0,
    end: activeClip?.end_time ? timestampToSeconds(activeClip.end_time) : 60,
    crop_x: activeClip?.custom_crop_x || 0.5,
    crop_y: 0.5,
    crop_z: 1.0
  } : segments[activeSegmentIndex];

  const [currentTime, setCurrentTime] = useState(0); 
  const [seekRequested, setSeekRequested] = useState(null); 
  const [isPlaying, setIsPlaying] = useState(false); 
  const [aspectRatio, setAspectRatio] = useState('9:16'); 
  const [isProcessing, setIsProcessing] = useState(false); 
  const [statusMessage, setStatusMessage] = useState(''); 
  const [exportProgress, setExportProgress] = useState(0); 

  // Save State
  const [saveStatus, setSaveStatus] = useState('saved'); 
  const [lastSaved, setLastSaved] = useState(null);
  const [isLoadingSavedState, setIsLoadingSavedState] = useState(true);

  // Transcript State
  const [transcript, setTranscript] = useState([]);
  const [isLoadingTranscript, setIsLoadingTranscript] = useState(false);

  // Safety: Clamp activeClipIndex when clips load
  React.useEffect(() => {
    if (clips.length > 0 && activeClipIndex >= clips.length) {
      setActiveClipIndex(0);
    }
  }, [clips, activeClipIndex]);

  React.useEffect(() => {
    if (project && project.id) {
      fetch(`${apiBase}/api/clips/${project.id}`)
        .then(res => res.json())
        .then(data => {
          setClips(data.clips || []);
        })
        .catch(err => console.error("Could not fetch clips", err));
    }
  }, [project, apiBase]);

  // Jump to clip start when activeClipIndex changes in clipper mode
  React.useEffect(() => {
    if (appMode === 'clipper' && activeClip) {
      const start = timestampToSeconds(activeClip.start_time);
      setSeekRequested(start);
      setCurrentTime(start);
    }
  }, [activeClipIndex, appMode]);

  const [presets, setPresets] = useState([]);

  React.useEffect(() => {
    fetch(`${apiBase}/api/captions/presets`)
      .then(res => res.json())
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
  }, [apiBase]);

  React.useEffect(() => {
    if (project && project.id && activeClip) {
      setIsLoadingSavedState(true);
      setSegments([]);

      fetch(`${apiBase}/api/load_editor/${project.id}?clip_index=${activeClipIndex}`)
        .then(res => res.json())
        .then(data => {
          if (data.exists && data.segments && data.segments.length > 0) {
            const clipStart = timestampToSeconds(activeClip.start_time);
            const clipEnd = timestampToSeconds(activeClip.end_time);
            const firstSegStart = data.segments[0].start;
            const lastSegEnd = data.segments[data.segments.length - 1].end;
            const isStale = (firstSegStart < clipStart - 60) || (lastSegEnd > clipEnd + 60);

            if (!isStale) {
              setSegments(data.segments);
              setActiveSegmentIndex(data.active_segment_index);
              if (data.caption_settings) {
                setCaptionSettings(prev => ({ ...prev, ...data.caption_settings }));
              }
              setLastSaved(data.saved_at);
              loadTranscript(project.id, activeClipIndex);
            }
          }
        })
        .catch(err => console.error("Could not load editor state", err))
        .finally(() => setIsLoadingSavedState(false));
    } else if (activeClip) {
      setIsLoadingSavedState(false);
    }
  }, [project, apiBase, activeClipIndex, !!activeClip]);

  React.useEffect(() => {
    if (isLoadingSavedState) return;
    if (activeClip && segments.length === 0) {
      const start = timestampToSeconds(activeClip.start_time);
      const end = timestampToSeconds(activeClip.end_time);
      setCurrentTime(start);
      setSegments([{
        id: Math.random().toString(36).substr(2, 9),
        start: start,
        end: end,
        crop_x: activeClip.custom_crop_x || 0.5,
        crop_z: 1.0
      }]);
      setActiveSegmentIndex(0);
    }
  }, [activeClip, segments.length, isLoadingSavedState]);

  React.useEffect(() => {
    if (appMode === 'editor' && project?.id && transcript.length === 0 && !isLoadingTranscript) {
      loadTranscript(project.id, activeClipIndex);
    }
  }, [appMode, project?.id, activeClipIndex]);

  React.useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.code === 'Space' && e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') {
        e.preventDefault();
        setIsPlaying(prev => !prev);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

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
  }, [currentTime, segments, isPlaying]);

  const saveProgress = async (isManual = false) => {
    if (!project?.id) return;
    setSaveStatus('saving');
    try {
      const payload = {
        active_clip_index: activeClipIndex,
        segments: segments,
        active_segment_index: activeSegmentIndex,
        caption_settings: captionSettings
      };
      if (appMode === 'clipper' && activeClip) {
        payload.clip = {
          start_time: activeClip.start_time,
          end_time: activeClip.end_time,
          custom_crop_x: activeClip.custom_crop_x
        };
      }
      const res = await fetch(`${apiBase}/api/save_editor/${project.id}?clip_index=${activeClipIndex}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.status === 'saved') {
        setSaveStatus('saved');
        setLastSaved(data.saved_at);
        if (isManual) notify("Progress saved successfully!", "success");
      } else {
        setSaveStatus('error');
      }
    } catch (err) {
      setSaveStatus('error');
    }
  };

  React.useEffect(() => {
    if (isLoadingSavedState) return;
    const timer = setTimeout(() => {
      saveProgress(false);
    }, 2000);
    return () => clearTimeout(timer);
  }, [segments, captionSettings, activeClipIndex, activeSegmentIndex, isLoadingSavedState, appMode, activeClip]);

  function handleSplit() {
    const segmentIndex = segments.findIndex(s => currentTime >= s.start && currentTime <= s.end);
    if (segmentIndex === -1) return;
    const seg = segments[segmentIndex];
    if (currentTime <= seg.start + 0.5 || currentTime >= seg.end - 0.5) return;
    const newSegments = [...segments];
    const secondHalf = { ...seg, id: Math.random().toString(36).substr(2, 9), start: currentTime };
    newSegments[segmentIndex] = { ...seg, end: currentTime };
    newSegments.splice(segmentIndex + 1, 0, secondHalf);
    setSegments(newSegments);
    setActiveSegmentIndex(segmentIndex + 1);
  }

  function handleSegmentBoundsChange(segmentIndex, nextStart, nextEnd) {
    if (appMode === 'clipper') {
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
      setSegments([]);
      setTranscript([]);
      return;
    }

    setSegments((prev) => {
      if (!prev[segmentIndex]) return prev;
      const updated = [...prev];
      const current = updated[segmentIndex];
      const prevSeg = updated[segmentIndex - 1];
      const nextSeg = updated[segmentIndex + 1];
      const minStart = prevSeg ? prevSeg.end + 0.001 : timestampToSeconds(activeClip?.start_time || "00:00");
      const maxEnd = nextSeg ? nextSeg.start - 0.001 : timestampToSeconds(activeClip?.end_time || "00:00");
      let safeStart = Math.max(minStart, Math.min(nextStart, current.end - 0.001));
      let safeEnd = Math.min(maxEnd, Math.max(nextEnd, safeStart + 0.001));
      updated[segmentIndex] = { ...current, start: safeStart, end: safeEnd };
      return updated;
    });
  }

  async function handleAutoSplit() {
    if (!project?.id || !activeClip) return;
    setIsProcessing(true);
    setStatusMessage('AI sedang membedah video...');
    const clipStart = timestampToSeconds(activeClip.start_time);
    const clipEnd = timestampToSeconds(activeClip.end_time);
    const eventSource = new EventSource(`${apiBase}/api/detect_scenes/${project.id}?start=${clipStart}&end=${clipEnd}`);

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.progress !== undefined) setStatusMessage(`AI sedang membedah video... (${data.progress}%)`);
      if (data.cuts) {
        const relevantCuts = data.cuts.filter(t => t > clipStart + 1 && t < clipEnd - 1);
        let newSegs = [];
        let lastT = clipStart;
        [...relevantCuts, clipEnd].forEach((t) => {
          newSegs.push({ id: Math.random().toString(36).substr(2, 9), start: lastT, end: t, crop_x: activeClip.custom_crop_x || 0.5 });
          lastT = t;
        });
        setSegments(newSegs);
        setActiveSegmentIndex(0);
        notify(`Automatically split into ${newSegs.length} scenes!`, "success");
        eventSource.close();
        setIsProcessing(false);
      }
      if (data.error) {
        notify("Error: " + data.error, "error");
        eventSource.close();
        setIsProcessing(false);
      }
    };
    eventSource.onerror = () => {
      eventSource.close();
      setIsProcessing(false);
      notify("Gagal mendeteksi scene.", "error");
    };
  }

  async function handleAutoTrack() {
    if (!project?.id || !activeClip || !activeSegment) return;
    setIsProcessing(true);
    setStatusMessage('Mendeteksi wajah di scene ini...');
    try {
      const res = await fetch(`${apiBase}/api/auto_track/${project.id}?clip_index=${activeClipIndex}&timestamp=${activeSegment.start}`);
      const data = await res.json();
      if (data.crop_x !== undefined) {
        const newSegs = [...segments];
        newSegs[activeSegmentIndex].crop_x = data.crop_x;
        setSegments(newSegs);
        notify("Wajah berhasil dideteksi dan di-center!", "success");
      } else {
        notify(data.error || "Gagal melacak wajah", "error");
      }
    } catch (err) {
      notify("Gagal menghubungi server", "error");
    } finally {
      setIsProcessing(false);
    }
  }

  async function handleExport() {
    if (!activeClip) return;
    setIsProcessing(true);
    setExportProgress(0);
    setStatusMessage('Menyiapkan proses rendering video...');
    try {
      const res = await fetch(`${apiBase}/api/export/${project.id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          filename: activeClip.filename,
          clip_index: activeClipIndex,
          segments: segments,
          caption_settings: captionSettings,
          transcript: transcript,
          aspect_ratio: aspectRatio
        })
      });
      const data = await res.json();
      if (data.export_id) {
        const eventSource = new EventSource(`${apiBase}/api/progress/${data.export_id}`);
        eventSource.onmessage = (event) => {
          const progressData = JSON.parse(event.data);
          if (progressData.message) setStatusMessage(progressData.message);
          if (progressData.progress !== undefined) setExportProgress(progressData.progress);
          if (progressData.step === 'done') {
            notify("Video berhasil di-export!", "success");
            eventSource.close();
            setIsProcessing(false);
          }
          if (progressData.step === 'error') {
            notify("Gagal meng-export video.", "error");
            eventSource.close();
            setIsProcessing(false);
          }
        };
      } else {
        notify("Gagal memulai export.", "error");
        setIsProcessing(false);
      }
    } catch (err) {
      setIsProcessing(false);
    }
  }

  function handleSegmentEndPlayback() {
    const nextIndex = activeSegmentIndex + 1;
    if (nextIndex < segments.length) {
      const nextStart = segments[nextIndex].start;
      setActiveSegmentIndex(nextIndex);
      setCurrentTime(nextStart);
      setSeekRequested(nextStart);
      return;
    }
    setIsPlaying(false);
  }

  function handleDeleteSegment(index) {
    if (segments.length <= 1) return;
    setSegments(prev => {
      const updated = prev.filter((_, i) => i !== index);
      if (activeSegmentIndex >= updated.length) setActiveSegmentIndex(updated.length - 1);
      return updated;
    });
  }

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
          <Button variant="outline" size="sm" onClick={() => saveProgress(true)} disabled={saveStatus === 'saving'} className="h-8 font-bold">
            <Save className="w-3.5 h-3.5 mr-1.5" /> Save
          </Button>
          <Button size="sm" onClick={handleExport} disabled={segments.length === 0} className="h-8 font-bold bg-white text-black hover:bg-white/90">
            <Download className="w-3.5 h-3.5 mr-1.5" /> Export Clip
          </Button>
        </div>
      </header>

      {/* Main View Area */}
      {appMode === 'clipper' ? (
        <ClipperView 
          project={project}
          activeClip={activeClip}
          activeClipIndex={activeClipIndex}
          playerRef={playerRef}
          setIsPlayerReady={setIsPlayerReady}
          currentTime={currentTime}
          setCurrentTime={setCurrentTime}
          seekRequested={seekRequested}
          setSeekRequested={setSeekRequested}
          isPlaying={isPlaying}
          setIsPlaying={setIsPlaying}
          handleSegmentBoundsChange={handleSegmentBoundsChange}
          setClips={setClips}
          isPlayerReady={isPlayerReady}
          aspectRatio={aspectRatio}
        />
      ) : (
        <EditorView 
          project={project}
          activeClip={activeClip}
          activeClipIndex={activeClipIndex}
          segments={segments}
          activeSegmentIndex={activeSegmentIndex}
          setActiveSegmentIndex={setActiveSegmentIndex}
          playerRef={playerRef}
          setIsPlayerReady={setIsPlayerReady}
          currentTime={currentTime}
          setCurrentTime={setCurrentTime}
          seekRequested={seekRequested}
          setSeekRequested={setSeekRequested}
          isPlaying={isPlaying}
          setIsPlaying={setIsPlaying}
          aspectRatio={aspectRatio}
          transcript={transcript}
          isLoadingTranscript={isLoadingTranscript}
          loadTranscript={() => loadTranscript(project.id, activeClipIndex, true)}
          captionSettings={captionSettings}
          setCaptionSettings={setCaptionSettings}
          setSegments={setSegments}
          handleSplit={handleSplit}
          handleAutoSplit={handleAutoSplit}
          handleAutoTrack={handleAutoTrack}
          handleSegmentBoundsChange={handleSegmentBoundsChange}
          handleDeleteSegment={handleDeleteSegment}
          handleSegmentEndPlayback={handleSegmentEndPlayback}
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          presets={presets}
          isPlayerReady={isPlayerReady}
          setTranscript={setTranscript}
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
    </div>
  );
}

// Helper Functions
function timestampToSeconds(ts) {
  if (typeof ts === 'number') return ts;
  if (!ts || typeof ts !== 'string') return 0;
  const parts = ts.split(':').map(parseFloat);
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
  if (parts.length === 2) return parts[0] * 60 + parts[1];
  return parts[0] || 0;
}

function formatTimeHHMMSS(sec) {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s < 10 ? '0' : ''}${s.toFixed(3)}`;
}

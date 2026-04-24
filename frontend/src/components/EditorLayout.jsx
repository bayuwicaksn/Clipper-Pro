import React, { useState, useRef } from 'react';
import { Button } from '@/components/ui/button';
import './EditorNLE.css'; // We will create this for NLE grid specifically
import Timeline from './Timeline';
import Sidebar from './Sidebar';
import Preview from './CustomPreview';
import {
  ChevronLeft, Save, Download,
  RotateCcw, Scissors,
  Sparkles, Type, Music, Layers, Wand2,
  Film, Cloud, LayoutTemplate, Zap
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
    captionX: 0.5,   // 0-1 normalized horizontal (0.5 = centered)
    captionY: 0.82,  // 0-1 normalized vertical (0.82 = near bottom)
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

  const [currentTime, setCurrentTime] = useState(0); // Tracks current video playhead
  const [seekRequested, setSeekRequested] = useState(null); // { time, signal: Date.now() }
  const [isPlaying, setIsPlaying] = useState(false); // Controls playback
  const [aspectRatio, setAspectRatio] = useState('9:16'); // '9:16' or '16:9'
  const [isProcessing, setIsProcessing] = useState(false); // Loading state
  const [statusMessage, setStatusMessage] = useState(''); // Text to show in overlay
  const [exportProgress, setExportProgress] = useState(0); // Export percentage

  // Save State
  const [saveStatus, setSaveStatus] = useState('saved'); // 'saved', 'saving', 'error'
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
      // Refresh clips metadata first
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
  }, [activeClipIndex, appMode]); // Only run when clip index or mode changes

  // Caption Presets
  const [presets, setPresets] = useState([]);

  // Fetch presets once on mount
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

  // Load editor state only when activeClip is definitively known
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

            // Only discard if clearly from an entirely different part of the video (e.g. > 1 minute off)
            const isStale = (firstSegStart < clipStart - 60) || (lastSegEnd > clipEnd + 60);

            if (!isStale) {
              setSegments(data.segments);
              setActiveSegmentIndex(data.active_segment_index);
              if (data.caption_settings) {
                setCaptionSettings(prev => ({ ...prev, ...data.caption_settings }));
              }
              setLastSaved(data.saved_at);
              // Trigger transcript load
              loadTranscript(project.id, activeClipIndex);
            } else {
              console.warn(`[SYNC] Discarding clearly stale segments for clip ${activeClipIndex}`);
            }
          }
        })
        .catch(err => console.error("Could not load editor state", err))
        .finally(() => setIsLoadingSavedState(false));
    } else if (activeClip) {
      // If we have activeClip but no fetch needed (edge case), stop loading
      setIsLoadingSavedState(false);
    }
  }, [project, apiBase, activeClipIndex, !!activeClip]);



  // Initialize segments ONLY IF there is no saved state yet and we're done checking
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
    } else if (activeClip && segments.length > 0) {
      // If segments exist, just ensure playhead is within bounds if it's the first load
      const start = timestampToSeconds(activeClip.start_time);
      if (currentTime < start) setCurrentTime(start);
    }
  }, [activeClip, segments.length, isLoadingSavedState]);

  // Reload transcript when entering editor mode if not present
  React.useEffect(() => {
    if (appMode === 'editor' && project?.id && transcript.length === 0 && !isLoadingTranscript) {
      loadTranscript(project.id, activeClipIndex);
    }
  }, [appMode, project?.id, activeClipIndex]);

  // Keyboard shortcuts
  React.useEffect(() => {
    const handleKeyDown = (e) => {
      // Toggle Play/Pause on Space
      if (e.code === 'Space' && e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') {
        e.preventDefault();
        setIsPlaying(prev => !prev);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Store current time in a ref for use in effects without triggering them
  // We update this synchronously during render to ensure it's always fresh 
  // for effects that run after the same render cycle.
  const currentTimeRef = React.useRef(currentTime);
  currentTimeRef.current = currentTime;

  // Track the last segment ID to detect transitions
  const lastActiveId = React.useRef(activeSegment?.id);

  // Auto-sync active segment based on playhead position
  React.useEffect(() => {
    if (segments.length === 0) return;

    // ONLY auto-sync segment while playing or if it's the very first load
    // This allows manual selection when paused (user can click selection without playhead 'following')
    if (!isPlaying && activeSegmentIndex !== -1) return;

    // Find segment that contains currentTime with a small buffer for precision
    const epsilon = 0.005;
    let index = segments.findIndex(s => currentTime >= s.start - epsilon && currentTime < s.end - epsilon);

    // Special case: if we're at or beyond the very end of the last segment
    if (index === -1) {
      const last = segments[segments.length - 1];
      if (currentTime >= last.end - epsilon) {
        index = segments.length - 1;
      }
    }

    // If we are in a gap (index === -1), we don't update activeSegmentIndex.
    // This keeps the player visible even between segments and allows 
    // sequence playback to jump from the previous segment to the next one.
    if (index !== -1 && index !== activeSegmentIndex) {
      setActiveSegmentIndex(index);
    }
  }, [currentTime, segments, isPlaying]);

  // --- SAVE LOGIC ---
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

      // Pass the current active clip index so saves are independent
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
        if (isManual) notify(data.error || "Failed to save progress.", "error");
        console.error("Save failed with data:", data);
      }
    } catch (err) {
      console.error("Save network error:", err);
      setSaveStatus('error');
      if (isManual) notify("Network error while saving.", "error");
    }
  };

  // Debounced Auto-save
  React.useEffect(() => {
    if (isLoadingSavedState) return;
    if (appMode === 'editor' && segments.length === 0) return;
    const timer = setTimeout(() => {
      saveProgress(false);
    }, 2000); // Save after 2 seconds of inactivity
    return () => clearTimeout(timer);
  }, [segments, captionSettings, activeClipIndex, activeSegmentIndex, isLoadingSavedState, appMode, activeClip]);



  function handleSplit() {
    // Find the segment currently under currentTime
    const segmentIndex = segments.findIndex(s => currentTime >= s.start && currentTime <= s.end);
    if (segmentIndex === -1) return;

    const seg = segments[segmentIndex];
    // Prevent split too close to edges
    if (currentTime <= seg.start + 0.5 || currentTime >= seg.end - 0.5) return;

    const newSegments = [...segments];
    const secondHalf = {
      ...seg,
      id: Math.random().toString(36).substr(2, 9),
      start: currentTime
    };

    newSegments[segmentIndex] = { ...seg, end: currentTime };
    newSegments.splice(segmentIndex + 1, 0, secondHalf);

    setSegments(newSegments);
    setActiveSegmentIndex(segmentIndex + 1);
  }

  // Helper to format seconds to HH:MM:SS.mmm to preserve millisecond precision
  function formatTimeHHMMSS(sec) {
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = sec % 60;
    return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s < 10 ? '0' : ''}${s.toFixed(3)}`;
  }

  function handleSegmentBoundsChange(segmentIndex, nextStart, nextEnd) {
    if (appMode === 'clipper') {
      // In clipper mode, we are editing the main clip bounds.
      setClips(prev => {
        const updated = [...prev];
        const clip = { ...updated[activeClipIndex] };

        let safeStart = Math.max(0, Math.min(nextStart, nextEnd - 1));
        let safeEnd = Math.max(safeStart + 1, nextEnd);

        if (project?.video_duration && safeEnd > project.video_duration) {
          safeEnd = project.video_duration;
        }

        clip.start_time = formatTimeHHMMSS(safeStart);
        clip.end_time = formatTimeHHMMSS(safeEnd);

        updated[activeClipIndex] = clip;
        return updated;
      });
      // Clear out segments so it regenerates properly when switching back to editor
      setSegments([]);
      // Clear transcript so it forces a regeneration for the new bounds
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

      safeStart = Math.min(safeStart, safeEnd - 0.001);

      updated[segmentIndex] = {
        ...current,
        start: safeStart,
        end: safeEnd,
      };
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

      if (data.progress !== undefined) {
        setStatusMessage(`AI sedang membedah video... (${data.progress}%)`);
      }

      if (data.cuts) {
        const clipStart = timestampToSeconds(activeClip.start_time);
        const clipEnd = timestampToSeconds(activeClip.end_time);
        const relevantCuts = data.cuts.filter(t => t > clipStart + 1 && t < clipEnd - 1);

        if (relevantCuts.length === 0) {
          notify("No clear scene changes detected within this segment.", "info");
        } else {
          // Rebuild segments list
          let newSegs = [];
          let lastT = clipStart;
          [...relevantCuts, clipEnd].forEach((t) => {
            newSegs.push({
              id: Math.random().toString(36).substr(2, 9),
              start: lastT,
              end: t,
              crop_x: activeClip.custom_crop_x || 0.5
            });
            lastT = t;
          });
          setSegments(newSegs);
          setActiveSegmentIndex(0);
          notify(`Automatically split into ${newSegs.length} scenes!`, "success");
        }
        eventSource.close();
        setIsProcessing(false);
      }

      if (data.error) {
        notify("Error: " + data.error, "error");
        eventSource.close();
        setIsProcessing(false);
      }
    };

    eventSource.onerror = (err) => {
      console.error("EventSource failed", err);
      eventSource.close();
      setIsProcessing(false);
      notify("Gagal mendeteksi scene. Pastikan server Python sudah jalan!", "error");
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
      console.error(err);
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
          segments: segments, // Passing the full array of split segments
          caption_settings: captionSettings,
          transcript: transcript, // Send current transcript to skip re-transcription
          aspect_ratio: aspectRatio
        })
      });
      const data = await res.json();
      if (data.export_id) {
        // notify("Export started! The video is being rendered.", "success");

        // Start listening for progress
        const eventSource = new EventSource(`${apiBase}/api/progress/${data.export_id}`);

        eventSource.onmessage = (event) => {
          const progressData = JSON.parse(event.data);

          if (progressData.message) setStatusMessage(progressData.message);
          if (progressData.progress !== undefined && progressData.progress >= 0) {
            setExportProgress(progressData.progress);
          }

          if (progressData.step === 'done') {
            notify("Video berhasil di-export!", "success");
            eventSource.close();
            setIsProcessing(false);
          }

          if (progressData.step === 'error') {
            notify("Gagal meng-export video: " + progressData.message, "error");
            eventSource.close();
            setIsProcessing(false);
          }
        };

        eventSource.onerror = (err) => {
          console.error("Export Progress Error:", err);
          eventSource.close();
          // Don't necessarily stop processing yet, let it retry or wait for timeout
          // but for UX safety:
          setIsProcessing(false);
          notify("Koneksi ke server terputus saat export.", "error");
        };
      } else {
        notify(data.error || "Gagal memulai export.", "error");
        setIsProcessing(false);
      }
    } catch (err) {
      console.error("Export failed", err);
      notify("Gagal menghubungi server untuk export.", "error");
      setIsProcessing(false);
    }
  }

  function handleSegmentEndPlayback() {
    if (!activeSegment) return;
    const nextIndex = activeSegmentIndex + 1;
    if (nextIndex < segments.length) {
      const nextStart = segments[nextIndex].start;
      setActiveSegmentIndex(nextIndex);
      setCurrentTime(nextStart);
      setSeekRequested(nextStart);
      return;
    }

    // End of chain: stop playback at current segment end.
    setIsPlaying(false);
    setCurrentTime(activeSegment.end);
    setSeekRequested(activeSegment.end);
  }

  function handleDeleteSegment(index) {
    if (segments.length <= 1) {
      notify("Cannot delete the last segment", "error");
      return;
    }
    setSegments((prev) => {
      const updated = prev.filter((_, i) => i !== index);
      // Adjust active index if necessary
      if (activeSegmentIndex >= updated.length) {
        setActiveSegmentIndex(updated.length - 1);
      }
      return updated;
    });
  }

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
    <div className="nle-workspace bg-background text-foreground font-sans">
      {/* Top Header */}
      <header className="nle-topbar border-b border-border bg-card/50 backdrop-blur-md px-6 py-3 flex justify-between items-center">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={onClose} className="hover:bg-accent">
            <ChevronLeft className="w-4 h-4 mr-1" /> Back
          </Button>
          <div className="text-sm font-bold tracking-tight">{project?.title || 'Untitled Project'}</div>
          <div
            className={`flex items-center gap-2 px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider border transition-colors ${saveStatus === 'error' ? 'border-destructive text-destructive' : 'border-border text-muted-foreground'}`}
            onClick={() => saveStatus === 'error' && saveProgress(true)}
          >
            {saveStatus === 'saving' && <div className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />}
            {saveStatus === 'saved' && <div className="w-1.5 h-1.5 rounded-full bg-green-500" />}
            {saveStatus === 'saving' ? 'Saving...' : saveStatus === 'error' ? 'Save Error' : 'Saved'}
            {lastSaved && saveStatus === 'saved' && (
              <span className="opacity-60 ml-1 font-normal">
                {new Date(lastSaved).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
            )}
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
          {/* Aspect Ratio Selector */}
          <div className="flex items-center bg-white/5 rounded-lg p-1 border border-white/10">
            <button
              onClick={() => setAspectRatio('9:16')}
              className={`px-3 py-1.5 rounded-md text-xs font-bold transition-all ${aspectRatio === '9:16'
                  ? 'bg-blue-600 text-white shadow-lg'
                  : 'text-foreground/40 hover:text-foreground/70'
                }`}
            >
              9:16
            </button>
            <button
              onClick={() => setAspectRatio('16:9')}
              className={`px-3 py-1.5 rounded-md text-xs font-bold transition-all ${aspectRatio === '16:9'
                  ? 'bg-blue-600 text-white shadow-lg'
                  : 'text-foreground/40 hover:text-foreground/70'
                }`}
            >
              16:9
            </button>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => saveProgress(true)}
            disabled={saveStatus === 'saving'}
            className="h-8 font-bold"
          >
            <Save className="w-3.5 h-3.5 mr-1.5" /> Save
          </Button>
          <Button
            size="sm"
            onClick={handleExport}
            disabled={segments.length === 0}
            className="h-8 font-bold bg-white text-black hover:bg-white/90"
          >
            <Download className="w-3.5 h-3.5 mr-1.5" /> Export Clip
          </Button>
        </div>
      </header>

      {/* Main Flex Area */}
      <div className="nle-main-split">

        {/* FAR LEFT: TRANSCRIPT PANEL (Hidden in Clipper Mode) */}
        {appMode === 'editor' && (
          <TranscriptPanel
            transcript={transcript}
            currentTime={currentTime}
            isLoadingTranscript={isLoadingTranscript}
            setSeekRequested={setSeekRequested}
            setCurrentTime={setCurrentTime}
            loadTranscript={() => loadTranscript(project.id, activeClipIndex, true)}
          />
        )}

        {/* CENTER: PREVIEW AREA */}
        <div className="nle-center-panel flex-1 bg-background relative flex flex-col overflow-hidden">
          <div className="flex-1 relative w-full overflow-hidden flex items-center justify-center min-h-0">
            {activeClip && activeSegment && project?.id && (
              <>
                <Preview
                  playerRef={playerRef}
                  setPlayerReady={setIsPlayerReady}
                  appMode={appMode}
                  jobId={project.id}
                  aspectRatio={aspectRatio}
                  startSecs={appMode === 'clipper' ? 0 : activeSegment.start}
                  endSecs={activeSegment.end}
                  currentTime={currentTime}
                  cropX={activeSegment.crop_x || 0.5}
                  cropY={activeSegment.crop_y || 0.5}
                  cropZ={activeSegment.crop_z || 1.0}
                  setCropX={(newX) => {
                    if (appMode === 'clipper') {
                      setClips(prev => {
                        const updated = [...prev];
                        updated[activeClipIndex] = { ...updated[activeClipIndex], custom_crop_x: newX };
                        return updated;
                      });
                    } else {
                      const newSegs = [...segments];
                      if (newSegs[activeSegmentIndex]) newSegs[activeSegmentIndex].crop_x = newX;
                      setSegments(newSegs);
                    }
                  }}
                  setCropY={(newY) => {
                    if (appMode === 'editor') {
                      const newSegs = [...segments];
                      if (newSegs[activeSegmentIndex]) newSegs[activeSegmentIndex].crop_y = newY;
                      setSegments(newSegs);
                    }
                  }}
                  onTimeUpdate={setCurrentTime}
                  seekRequested={seekRequested}
                  playing={isPlaying}
                  onSegmentEnd={handleSegmentEndPlayback}
                  transcript={transcript}
                  captionSettings={captionSettings}
                  setCaptionSettings={setCaptionSettings}
                  setCropZ={(newZ) => {
                    if (appMode === 'editor') {
                      const newSegs = [...segments];
                      if (newSegs[activeSegmentIndex]) newSegs[activeSegmentIndex].crop_z = newZ;
                      setSegments(newSegs);
                    }
                  }}
                />
              </>
            )}
          </div>

        </div>

        {/* RIGHT PANEL: SIDEBAR */}
        {appMode === 'editor' && activeTab && (
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
              onRegenerateTranscript={() => {
                loadTranscript(project.id, activeClipIndex, true);
              }}
              onSplit={handleSplit}
              onAutoSplit={handleAutoSplit}
              onAutoTrack={handleAutoTrack}
            />
          </div>
        )}

        {/* NAVIGATION RIBBON */}
        {appMode === 'editor' && (
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

      {/* BOTTOM PANEL: TIMELINE */}
      <div className="nle-bottom-panel bg-card border-t border-border h-64 flex flex-col flex-shrink-0">
        <div className="nle-player-controls nle-player-controls--minimal">
          <div className="flex items-center gap-3">
            <div className="nle-player-pill">
              {activeClip ? `CLIP ${activeClipIndex + 1}` : 'NO CLIP'}
            </div>
            <div className="text-[10px] font-medium text-muted-foreground/80">
              {activeClip ? activeClip.resolution : '--'} @ {activeClip ? activeClip.fps : '--'}fps
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="font-mono text-xs tabular-nums">
              <span className="text-foreground font-bold">{new Date(Math.max(0, currentTime) * 1000).toISOString().substr(11, 8).replace(/^00:/, '')}</span>
              <span className="text-muted-foreground/30 mx-2">/</span>
              <span className="text-muted-foreground">
                {appMode === 'clipper' && project?.video_duration ? formatTimeHHMMSS(project.video_duration) : (activeClip ? (activeClip.duration || activeClip.duration_display || '00:00') : '00:00')}
              </span>
            </div>
            {appMode === 'editor' && (
              <Button variant="secondary" size="sm" onClick={handleSplit} className="h-8 px-3 font-semibold">
                <Scissors className="size-3.5 mr-1.5" /> Split
              </Button>
            )}
          </div>
        </div>
        <div className="flex-1 overflow-hidden">
          <Timeline
            playerRef={playerRef}
            isPlayerReady={isPlayerReady}
            jobId={project?.id}
            clip={activeClip}
            segments={appMode === 'clipper' ? [{
              id: 'clipper-main',
              start: Math.max(0, activeClip?.start_time ? timestampToSeconds(activeClip.start_time) : 0),
              end: Math.max(1, activeClip?.end_time ? timestampToSeconds(activeClip.end_time) : 60),
              crop_x: 0.5
            }] : segments}
            appMode={appMode}
            totalStart={appMode === 'clipper' ? 0 : Math.max(0, activeClip?.start_time ? timestampToSeconds(activeClip.start_time) : 0)}
            totalEnd={appMode === 'clipper' && project?.video_duration ? timestampToSeconds(project.video_duration) : Math.max(1, activeClip?.end_time ? timestampToSeconds(activeClip.end_time) : (activeClip?.duration ? timestampToSeconds(activeClip.duration) : 60))}
            activeSegmentIndex={appMode === 'clipper' ? 0 : activeSegmentIndex}
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

// --- Optimized Sub-Components ---

// --- Optimized Sub-Components ---

// REMOVED React.memo to ensure it always responds to parent state updates
const TranscriptPanel = ({
  transcript, currentTime, isLoadingTranscript,
  setSeekRequested, setCurrentTime, loadTranscript
}) => {
  const safeTranscript = Array.isArray(transcript) ? transcript : [];

  return (
    <div className="nle-left-panel bg-card border-r border-border flex flex-col w-[340px]">
      <div className="px-6 py-5 border-b border-border/40 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted-foreground flex items-center gap-2">
            <Type className="w-3 h-3" /> Transcript
          </h3>
        </div>

        <div className="flex items-center gap-4">
          <label className="flex items-center gap-2 cursor-pointer group">
            <input type="checkbox" className="w-4 h-4 rounded border-border bg-background accent-primary cursor-pointer" />
            <span className="text-xs text-muted-foreground group-hover:text-foreground transition-colors">Transcript only</span>
          </label>
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={loadTranscript}
          className="w-full justify-start h-9 text-xs font-bold border-white/5 bg-white/5 hover:bg-white/10"
        >
          <span className="text-primary mr-2">+</span> Add a section
        </Button>
      </div>

      <div className="p-6 overflow-y-auto flex-1 custom-scrollbar transcript-flow">
        <div className="flex flex-wrap gap-x-1.5 gap-y-3 leading-[1.8] items-baseline">
          {safeTranscript.length === 0 && !isLoadingTranscript && (
            <p className="text-sm text-muted-foreground/60 italic">No transcript available.</p>
          )}

          {safeTranscript.map((w, i) => {
            if (!w) return null;
            const curT = Number(currentTime);
            const wStart = Number(w.start);
            const wEnd = Number(w.end);

            const isActive = curT >= (wStart - 0.1) && curT < (wEnd + 0.1);

            const prevWord = safeTranscript[i - 1];
            const hasGap = prevWord && (wStart - Number(prevWord.end) > 1.2);
            const isHighlight = w.word && /^(selamat|pagi|siang|malam|senior|saya|pakar|screen|time|mayapada|beliau|ngomong|presiden|adaptasi)/i.test(w.word);

            return (
              <React.Fragment key={i}>
                {hasGap && (
                  <span className="text-muted-foreground/20 px-1 tracking-[0.2em] font-bold text-[10px]">...</span>
                )}
                <span
                  data-active={isActive}
                  className={`cursor-pointer px-1.5 py-0.5 rounded-sm transition-all duration-150 text-[15px] font-medium tracking-tight
                    ${isActive
                      ? 'bg-[#34D399] text-black font-bold scale-110 shadow-[0_0_20px_rgba(52,211,153,0.5)] z-10'
                      : isHighlight
                        ? 'text-[#FDE047] opacity-100'
                        : 'text-foreground/70 hover:text-foreground hover:bg-foreground/10 opacity-90'
                    }`}
                  onClick={() => {
                    setSeekRequested(wStart);
                    setCurrentTime(wStart);
                  }}
                >
                  {w.word}
                </span>
              </React.Fragment>
            );
          })}
        </div>
      </div>
    </div>
  );
};

// Helper Functions
function timestampToSeconds(ts) {
  if (typeof ts === 'number') return ts;
  if (!ts || typeof ts !== 'string') return 0;
  const parts = ts.split(':').map(parseFloat);
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
  if (parts.length === 2) return parts[0] * 60 + parts[1];
  return parts[0] || 0;
}


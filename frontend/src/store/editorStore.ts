import { create } from 'zustand';
import * as api from '../api/client';
import { Project, Clip, Segment, Word, AppMode } from '../types';
import { timestampToSeconds, formatTimeHHMMSS } from '../utils/time';

const ACTIVE_TAB_STORAGE_KEY = 'nle_active_tab';

function getInitialAppMode(): AppMode {
  if (typeof window === 'undefined') return 'clipper';
  const saved = window.localStorage.getItem(ACTIVE_TAB_STORAGE_KEY);
  return saved === 'editor' || saved === 'clipper' ? saved : 'clipper';
}

function persistAppMode(appMode: AppMode) {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(ACTIVE_TAB_STORAGE_KEY, appMode);
}

interface EditorState {
  // Data
  project: Project | null;
  clips: Clip[];
  activeClipIndex: number;
  appMode: AppMode;
  segments: Segment[];
  activeSegmentIndex: number;
  activeTab: string;
  transcript: Word[];
  aspectRatio: string;
  
  // Player State
  currentTime: number;
  isPlaying: boolean;
  seekRequested: number | null;
  
  // UI / UX State
  isLoadingSavedState: boolean;
  isLoadingTranscript: boolean;
  isProcessing: boolean;
  statusMessage: string;
  exportProgress: number;
  saveStatus: 'saved' | 'saving' | 'error';
  lastSaved: string | null;
  
  // Preview Navigation State
  panX: number;
  panY: number;
  videoAspectRatio: number;
  
  // Actions
  setProject: (project: Project | null) => void;
  setClips: (clips: Clip[]) => void;
  setActiveClipIndex: (index: number) => void;
  setAppMode: (mode: AppMode) => void;
  setSegments: (segments: Segment[]) => void;
  setActiveSegmentIndex: (index: number) => void;
  setActiveTab: (tab: string) => void;
  setTranscript: (transcript: Word[]) => void;
  setAspectRatio: (ratio: string) => void;
  
  setPanX: (x: number) => void;
  setPanY: (y: number) => void;
  setVideoAspectRatio: (ratio: number) => void;
  
  setCurrentTime: (time: number) => void;
  setIsPlaying: (playing: boolean) => void;
  setSeekRequested: (time: number | null) => void;
  
  setIsProcessing: (processing: boolean) => void;
  setStatusMessage: (message: string) => void;
  setExportProgress: (progress: number) => void;
  setSaveStatus: (status: 'saved' | 'saving' | 'error') => void;

  // Caption Settings
  captionSettings: any; // Using any for now to match the complex object
  setCaptionSettings: (settings: any | ((prev: any) => any)) => void;

  // Thunks / Complex Actions
  loadProjectData: (projectId: string) => Promise<void>;
  loadEditorState: (projectId: string, clipIndex: number) => Promise<void>;
  saveEditorState: () => Promise<void>;
  fetchTranscript: (force?: boolean) => Promise<void>;
  
  splitSegment: () => void;
  deleteSegment: (index: number) => void;
  updateSegmentBounds: (index: number, start: number, end: number) => void;
  handleSegmentEndPlayback: () => void;
  
  autoSplitSegments: (notify: any) => Promise<void>;
  autoTrackFace: (notify: any) => Promise<void>;
  startExport: (notify: any) => Promise<void>;
  applyCaptionPreset: (preset: any) => void;
}

export const useEditorStore = create<EditorState>((set, get) => ({
  // Initial State
  project: null,
  clips: [],
  activeClipIndex: 0,
  appMode: getInitialAppMode(),
  segments: [],
  activeSegmentIndex: 0,
  activeTab: 'captions',
  transcript: [],
  aspectRatio: '9:16',
  
  currentTime: 0,
  isPlaying: false,
  seekRequested: null,
  
  isLoadingSavedState: false,
  isLoadingTranscript: false,
  isProcessing: false,
  statusMessage: '',
  exportProgress: 0,
  saveStatus: 'saved',
  lastSaved: null,
  
  panX: 0,
  panY: 0,
  videoAspectRatio: 16 / 9,
  
  captionSettings: {
    presetId: 'default',
    fontName: 'Montserrat',
    fontSize: 100,
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
    captionWidth: 100,
    verticalMargin: 150
  },

  // Simple Actions
  setProject: (project) => set({ project }),
  setClips: (clips) => set((state) => ({ 
    clips: typeof clips === 'function' ? clips(state.clips) : clips 
  })),
  setActiveClipIndex: (activeClipIndex) => set({ activeClipIndex }),
  setAppMode: (appMode) => {
    persistAppMode(appMode);
    set({ appMode });
  },
  setSegments: (segments) => set((state) => ({ 
    segments: typeof segments === 'function' ? segments(state.segments) : segments 
  })),
  setActiveSegmentIndex: (activeSegmentIndex) => set({ activeSegmentIndex }),
  setActiveTab: (activeTab) => set({ activeTab }),
  setTranscript: (transcript) => set((state) => ({
    transcript: typeof transcript === 'function' ? transcript(state.transcript) : transcript
  })),
  setAspectRatio: (aspectRatio) => set({ aspectRatio }),
  
  setPanX: (panX) => set({ panX }),
  setPanY: (panY) => set({ panY }),
  setVideoAspectRatio: (videoAspectRatio) => set({ videoAspectRatio }),
  
  setCurrentTime: (currentTime) => set({ currentTime }),
  setIsPlaying: (isPlaying) => set({ isPlaying }),
  setSeekRequested: (seekRequested) => set({ seekRequested }),
  
  setIsProcessing: (isProcessing) => set({ isProcessing }),
  setStatusMessage: (statusMessage) => set({ statusMessage }),
  setExportProgress: (exportProgress) => set({ exportProgress }),
  setSaveStatus: (saveStatus) => set({ saveStatus }),

  setCaptionSettings: (settings) => set((state) => ({
    captionSettings: typeof settings === 'function' ? settings(state.captionSettings) : settings
  })),

  // Complex Actions
  loadProjectData: async (projectId) => {
    try {
      const data = await api.fetchClips(projectId);
      set({ 
        clips: (data.clips || []).map((clip: any) => ({
          ...clip,
          auto_background_enabled: clip.auto_background_enabled !== false
        }))
      });
    } catch (err) {
      console.error("Could not fetch clips", err);
    }
  },

  loadEditorState: async (projectId, clipIndex) => {
    const { clips } = get();
    const activeClip = clips[clipIndex];
    if (!activeClip) return;

    set({ isLoadingSavedState: true, segments: [] });

    try {
      const data = await api.loadEditorState(projectId, clipIndex);
      if (data.exists && data.segments && data.segments.length > 0) {
        const clipStart = timestampToSeconds(activeClip.start_time);
        const clipEnd = timestampToSeconds(activeClip.end_time);
        const firstSegStart = data.segments[0].start;
        const lastSegEnd = data.segments[data.segments.length - 1].end;
        
        // Safety check if segments are outside clip bounds (stale data)
        const isStale = (firstSegStart < clipStart - 60) || (lastSegEnd > clipEnd + 60);

        if (!isStale) {
          set({ 
            segments: data.segments,
            activeSegmentIndex: data.active_segment_index || 0,
            lastSaved: data.saved_at
          });
          if (data.caption_settings) {
            set((state) => ({ captionSettings: { ...state.captionSettings, ...data.caption_settings } }));
          }
          // Also fetch transcript
          get().fetchTranscript();
        }
      }
    } catch (err) {
      console.error("Could not load editor state", err);
    } finally {
      set({ isLoadingSavedState: false });
    }
  },

  fetchTranscript: async (force = false) => {
    const { project, clips, activeClipIndex } = get();
    if (!project?.id) return;

    set({ isLoadingTranscript: true });
    try {
      const activeClip = clips[activeClipIndex];
      const bounds = activeClip ? {
        start: timestampToSeconds(activeClip.start_time),
        end: timestampToSeconds(activeClip.end_time),
      } : undefined;
      const data = await api.fetchTranscript(project.id, activeClipIndex, force, bounds);
      if (Array.isArray(data)) {
        set({ transcript: data });
      }
    } catch (err) {
      console.error("Failed to load transcript", err);
    } finally {
      set({ isLoadingTranscript: false });
    }
  },

  saveEditorState: async () => {
    const { project, activeClipIndex, segments, activeSegmentIndex, captionSettings, appMode, clips } = get();
    if (!project?.id) return;

    set({ saveStatus: 'saving' });
    try {
      const activeClip = clips[activeClipIndex];
      const payload: any = {
        segments,
        active_segment_index: activeSegmentIndex,
        caption_settings: captionSettings,
      };

      if (activeClip) {
        payload.clip = {
          start_time: activeClip.start_time,
          end_time: activeClip.end_time,
          custom_crop_x: activeClip.custom_crop_x,
          auto_background_enabled: activeClip.auto_background_enabled !== false
        };
      }

      const data = await api.saveEditorState(project.id, activeClipIndex, payload);
      if (data.status === 'saved') {
        set({ saveStatus: 'saved', lastSaved: data.saved_at });
      } else {
        set({ saveStatus: 'error' });
      }
    } catch (err) {
      set({ saveStatus: 'error' });
    }
  },

  splitSegment: () => {
    const { segments, currentTime, activeSegmentIndex } = get();
    const segmentIndex = segments.findIndex(s => currentTime >= s.start && currentTime <= s.end);
    if (segmentIndex === -1) return;
    const seg = segments[segmentIndex];
    if (currentTime <= seg.start + 0.5 || currentTime >= seg.end - 0.5) return;
    
    const newSegments = [...segments];
    const secondHalf = { ...seg, id: Math.random().toString(36).substr(2, 9), start: currentTime };
    newSegments[segmentIndex] = { ...seg, end: currentTime };
    newSegments.splice(segmentIndex + 1, 0, secondHalf);
    
    set({ 
      segments: newSegments, 
      activeSegmentIndex: segmentIndex + 1 
    });
  },

  deleteSegment: (index) => {
    const { segments, activeSegmentIndex } = get();
    if (segments.length <= 1) return;
    
    const updated = segments.filter((_, i) => i !== index);
    let nextActiveIndex = activeSegmentIndex;
    if (activeSegmentIndex >= updated.length) nextActiveIndex = updated.length - 1;
    
    set({ 
      segments: updated, 
      activeSegmentIndex: nextActiveIndex 
    });
  },

  updateSegmentBounds: (segmentIndex, nextStart, nextEnd) => {
    const { appMode, clips, activeClipIndex, project } = get();
    
    if (appMode === 'clipper') {
      const updatedClips = [...clips];
      const clip = { ...updatedClips[activeClipIndex] };
      let safeStart = Math.max(0, Math.min(nextStart, nextEnd - 1));
      let safeEnd = Math.max(safeStart + 1, nextEnd);
      if (project?.video_duration && safeEnd > project.video_duration) safeEnd = project.video_duration;
      
      clip.start_time = formatTimeHHMMSS(safeStart);
      clip.end_time = formatTimeHHMMSS(safeEnd);
      clip.auto_background_enabled = clip.auto_background_enabled !== false;
      updatedClips[activeClipIndex] = clip;
      
      set({ 
        clips: updatedClips,
        segments: [],
        transcript: []
      });
      return;
    }

    const { segments } = get();
    if (!segments[segmentIndex]) return;
    
    const updated = [...segments];
    const current = updated[segmentIndex];
    const prevSeg = updated[segmentIndex - 1];
    const nextSeg = updated[segmentIndex + 1];
    const activeClip = clips[activeClipIndex];
    
    const minStart = prevSeg ? prevSeg.end + 0.001 : timestampToSeconds(activeClip?.start_time || "00:00");
    const maxEnd = nextSeg ? nextSeg.start - 0.001 : timestampToSeconds(activeClip?.end_time || "00:00");
    
    let safeStart = Math.max(minStart, Math.min(nextStart, current.end - 0.001));
    let safeEnd = Math.min(maxEnd, Math.max(nextEnd, safeStart + 0.001));
    
    updated[segmentIndex] = { ...current, start: safeStart, end: safeEnd };
    set({ segments: updated });
  },

  handleSegmentEndPlayback: () => {
    const { activeSegmentIndex, segments } = get();
    const nextIndex = activeSegmentIndex + 1;
    
    if (nextIndex < segments.length) {
      // Continuous playback — only advance index, no seek.
      // Video keeps playing naturally; startSecs effect won't seek because playing=true.
      set({ activeSegmentIndex: nextIndex });
      return;
    }
    set({ isPlaying: false });
  },

  autoSplitSegments: async (notify) => {
    const { project, clips, activeClipIndex, segments, setIsProcessing, setStatusMessage, setSegments, setActiveSegmentIndex, setCurrentTime, setSeekRequested } = get();
    const activeClip = clips[activeClipIndex];
    if (!project?.id || !activeClip) return;

    // UI handles confirmation, proceeding directly.

    const clipStart = timestampToSeconds(activeClip.start_time);
    const clipEnd = timestampToSeconds(activeClip.end_time);

    setSegments([]);
    setActiveSegmentIndex(0);
    setCurrentTime(clipStart);
    setSeekRequested(clipStart);

    setIsProcessing(true);
    setStatusMessage('AI sedang membedah video...');
    
    const eventSource = new EventSource(`${api.API_BASE}/api/detect_scenes/${project.id}?start=${clipStart}&end=${clipEnd}`);

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.progress !== undefined) setStatusMessage(`AI sedang membedah video... (${data.progress}%)`);
      if (data.cuts) {
        const clipDuration = Math.max(0, clipEnd - clipStart);

        // Parse and filter valid numeric cuts
        const rawCuts: number[] = data.cuts
          .map((raw: number) => Number(raw))
          .filter((t: number) => Number.isFinite(t) && t >= 0);

        // Simple detection: if the largest cut fits within clipDuration,
        // cuts are relative (0-based). Otherwise they're absolute.
        const maxCut = rawCuts.length > 0 ? Math.max(...rawCuts) : 0;
        const cutsAreRelative = rawCuts.length > 0 && maxCut <= clipDuration + 1 && clipStart > 1;
        const offset = cutsAreRelative ? clipStart : 0;

        console.log('[AutoSplit] raw cuts:', rawCuts);
        console.log('[AutoSplit] clipStart:', clipStart, 'clipEnd:', clipEnd, 'clipDuration:', clipDuration);
        console.log('[AutoSplit] maxCut:', maxCut, 'relative?', cutsAreRelative, 'offset:', offset);

        const normalizedCuts = rawCuts
          .map((t: number) => t + offset)
          .filter((t: number) => t > clipStart + 1 && t < clipEnd - 1)
          .sort((a: number, b: number) => a - b)
          .filter((t: number, idx: number, arr: number[]) => idx === 0 || Math.abs(t - arr[idx - 1]) > 0.25);

        console.log('[AutoSplit] normalizedCuts:', normalizedCuts);
        let newSegs: Segment[] = [];
        let lastT = clipStart;
        [...normalizedCuts, clipEnd].forEach((t) => {
          newSegs.push({ 
            id: Math.random().toString(36).substr(2, 9), 
            start: lastT, 
            end: t, 
            crop_x: activeClip.custom_crop_x || 0.5,
            auto_background_enabled: activeClip.auto_background_enabled !== false
          });
          lastT = t;
        });
        setSegments(newSegs);
        console.log('[AutoSplit] final segments:', newSegs.map(s => ({ id: s.id, start: s.start, end: s.end })));
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
  },

  autoTrackFace: async (notify) => {
    const { project, clips, activeClipIndex, segments, activeSegmentIndex, setIsProcessing, setStatusMessage, setSegments } = get();
    const activeClip = clips[activeClipIndex];
    const activeSegment = segments[activeSegmentIndex];
    if (!project?.id || !activeClip || !activeSegment) return;

    setIsProcessing(true);
    setStatusMessage('Mendeteksi wajah di scene ini...');
    try {
      const data = await api.autoTrackFace(project.id, activeClipIndex, activeSegment.start);
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
  },

  startExport: async (notify) => {
    const { 
      project, clips, activeClipIndex, segments, 
      captionSettings, transcript, aspectRatio,
      setIsProcessing, setStatusMessage, setExportProgress 
    } = get();
    
    const activeClip = clips[activeClipIndex];
    if (!project?.id || !activeClip) return;

    setIsProcessing(true);
    setExportProgress(0);
    setStatusMessage('Menyiapkan proses rendering video...');
    
    try {
      const data = await api.startExport(project.id, {
        filename: activeClip.filename,
        clip_index: activeClipIndex,
        segments: segments,
        caption_settings: captionSettings,
        transcript: transcript,
        aspect_ratio: aspectRatio,
        auto_background_enabled: activeClip.auto_background_enabled !== false
      });

      if (data.export_id) {
        const eventSource = new EventSource(`${api.API_BASE}/api/progress/${data.export_id}`);
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
        eventSource.onerror = () => {
          eventSource.close();
          setIsProcessing(false);
          notify("Koneksi export terputus.", "error");
        };
      } else {
        notify("Gagal memulai export.", "error");
        setIsProcessing(false);
      }
    } catch (err) {
      setIsProcessing(false);
      notify("Gagal menghubungi server untuk export.", "error");
    }
  },

  applyCaptionPreset: (p) => {
    set((state) => ({
      captionSettings: {
        ...state.captionSettings,
        presetId: p.id,
        presetName: p.name,
        primaryColor: p.colors?.primary || state.captionSettings.primaryColor,
        outlineColor: p.colors?.outline || state.captionSettings.outlineColor,
        outlineWidth: p.layout?.outline_width || state.captionSettings.outlineWidth,
        shadowEnabled: !!p.layout?.shadow,
        verticalMargin: p.layout?.vertical_margin || state.captionSettings.verticalMargin
      }
    }));
  }
}));

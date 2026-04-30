import { EditorSlice } from './types';
import { AppMode } from '../../types';

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

export const createBaseSlice: EditorSlice<any> = (set, get) => ({
  // Data State
  project: null,
  clips: [],
  activeClipIndex: 0,
  appMode: getInitialAppMode(),
  segments: [],
  activeSegmentIndex: 0,
  activeTab: 'captions',
  transcript: [],
  aspectRatio: '9:16',
  
  // Player State
  currentTime: 0,
  isPlaying: false,
  seekRequested: null,
  
  // UI State
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

  // Basic Setters
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
});

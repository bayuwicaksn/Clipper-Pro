import { StateCreator } from 'zustand';
import { 
  Project, Clip, Segment, Word, AppMode, 
  CaptionSettings, CaptionPreset, NotifyFn 
} from '../../types';

export interface EditorDataState {
  project: Project | null;
  clips: Clip[];
  activeClipIndex: number;
  appMode: AppMode;
  segments: Segment[];
  activeSegmentIndex: number;
  activeTab: string;
  transcript: Word[];
  aspectRatio: string;
}

export interface PlayerState {
  currentTime: number;
  isPlaying: boolean;
  seekRequested: number | null;
}

export interface UIState {
  isLoadingSavedState: boolean;
  isLoadingTranscript: boolean;
  isProcessing: boolean;
  statusMessage: string;
  exportProgress: number;
  saveStatus: 'saved' | 'saving' | 'error';
  lastSaved: string | null;
  panX: number;
  panY: number;
  videoAspectRatio: number;
}

export interface EditorActions {
  setProject: (project: Project | null) => void;
  setClips: (clips: Clip[] | ((prev: Clip[]) => Clip[])) => void;
  setActiveClipIndex: (index: number) => void;
  setAppMode: (mode: AppMode) => void;
  setSegments: (segments: Segment[] | ((prev: Segment[]) => Segment[])) => void;
  setActiveSegmentIndex: (index: number) => void;
  setActiveTab: (tab: string) => void;
  setTranscript: (transcript: Word[] | ((prev: Word[]) => Word[])) => void;
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

  captionSettings: CaptionSettings;
  setCaptionSettings: (settings: CaptionSettings | ((prev: CaptionSettings) => CaptionSettings)) => void;

  loadProjectData: (projectId: string) => Promise<void>;
  loadEditorState: (projectId: string, clipIndex: number) => Promise<void>;
  saveEditorState: () => Promise<void>;
  fetchTranscript: (force?: boolean) => Promise<void>;
  
  splitSegment: () => void;
  deleteSegment: (index: number) => void;
  updateSegmentBounds: (index: number, start: number, end: number) => void;
  handleSegmentEndPlayback: () => void;
  
  autoSplitSegments: (notify: NotifyFn) => Promise<void>;
  autoTrackFace: (notify: NotifyFn) => Promise<void>;
  startExport: (notify: NotifyFn) => Promise<void>;
  applyCaptionPreset: (preset: CaptionPreset) => void;
}

export type EditorFullState = EditorDataState & PlayerState & UIState & EditorActions;

export type EditorSlice<T> = StateCreator<
  EditorFullState,
  [],
  [],
  T
>;

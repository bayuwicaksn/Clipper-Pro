export type AppMode = 'clipper' | 'editor';

export type TabId = 
  | 'ai-enhance' 
  | 'captions' 
  | 'media' 
  | 'brand' 
  | 'b-roll' 
  | 'transitions' 
  | 'text' 
  | 'music' 
  | 'ai-hook'
  | null;

export interface Project {
  id: string;
  slug: string;
  title: string;
  status: string;
  thumbnail?: string;
  video_duration?: number;
  created_at?: string;
  created_timestamp?: number;
  clip_count?: number;
  video_url?: string;
}

export interface Clip {
  clip_index: number;
  filename: string;
  title: string;
  start_time: string;
  end_time: string;
  duration?: string;
  duration_display?: string;
  duration_seconds?: number;
  exported?: boolean;
  exports?: ExportedFile[];
  auto_background_enabled?: boolean;
}
}

export interface ExportedFile {
  filename: string;
  version_label?: string;
}

export interface Segment {
  id: string; // Required UUID for fresh start
  start: number;
  end: number;
  crop_x?: number;
  crop_y?: number;
  crop_z?: number;
  auto_background_enabled?: boolean;
}

export interface ProgressState {
  step: string;
  message: string;
  progress: number;
}

export interface CaptionSettings {
  presetId: string;
  presetName?: string;
  fontName: string;
  fontSize: number;
  fontWeight: string;
  primaryColor: string;
  outlineColor: string;
  outlineWidth: number;
  isItalic: boolean;
  isUnderline: boolean;
  isUppercase: boolean;
  shadowEnabled: boolean;
  shadowColor: string;
  shadowOffsetX: number;
  shadowOffsetY: number;
  shadowBlur: number;
  autoHighlight: boolean;
  highlightColorGreen: string;
  highlightColorYellow: string;
  lineLimit: number;
  captionX: number;
  captionY: number;
  captionWidth: number;
  verticalMargin: number;
}

export interface CaptionPreset {
  id: string;
  name: string;
  colors?: {
    primary?: string;
    outline?: string;
  };
  layout?: {
    outline_width?: number;
    shadow?: boolean;
    vertical_margin?: number;
  };
}

export interface Word {
  word: string;
  start: number;
  end: number;
  confidence?: number;
  speaker?: string;
}

export interface TranscriptResponse {
  words: Word[];
}

export interface EditorStatePayload {
  segments: Segment[];
  active_segment_index: number;
  caption_settings: Partial<CaptionSettings>;
  clip?: {
    start_time: string;
    end_time: string;
    custom_crop_x?: number;
    auto_background_enabled: boolean;
  };
}

export interface EditorStateResponse {
  exists: boolean;
  segments?: Segment[];
  active_segment_index?: number;
  caption_settings?: Partial<CaptionSettings>;
  saved_at?: string;
  status?: string;
}

export type NotifyFn = (message: string, type: 'success' | 'error' | 'info' | 'warning') => void;

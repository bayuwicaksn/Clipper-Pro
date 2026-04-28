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

export interface ExportedFile {
  filename: string;
  version_label?: string;
}

export interface Segment {
  id?: string | number;
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
  fontSize: number;
  color: string;
  strokeColor: string;
  strokeWidth: number;
  fontFamily: string;
  uppercase: boolean;
  animation?: string;
  preset?: string;
  vertical_pos?: number;
}

export interface Word {
  word: string;
  start: number;
  end: number;
  confidence?: number;
  speaker?: string;
}

export interface Transcript {
  words: Word[];
}

import { 
  Project, 
  Clip, 
  Segment, 
  CaptionSettings, 
  ProgressState,
  EditorStatePayload,
  EditorStateResponse,
  CaptionPreset,
  Word
} from "../types";

export const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

/**
 * Generic API helper for fetch
 */
async function apiFetch<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = endpoint.startsWith('http') ? endpoint : `${API_BASE}${endpoint}`;
  
  const headers = new Headers(options.headers);
  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }
  
  // If explicitly set to empty, let the browser decide (for FormData)
  if (headers.get('Content-Type') === '') {
    headers.delete('Content-Type');
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || errorData.error || `HTTP error! status: ${response.status}`);
  }

  return response.json();
}

// ─── Projects ────────────────────────────────────────────────────────────────

export const fetchProjects = () => apiFetch<Project[]>('/api/projects');

export const deleteProject = (id: string) => 
  apiFetch<{ status: string; id: string }>(`/api/projects/${id}`, { method: 'DELETE' });

// ─── Jobs / Pipeline ─────────────────────────────────────────────────────────

export const startProcessing = (data: { url: string; [key: string]: any }) => 
  apiFetch<{ job_id: string; status: string }>('/api/process', {
    method: 'POST',
    body: JSON.stringify(data),
  });

export const getJobStatus = (jobId: string) => 
  apiFetch<{ status: string; progress: number; status_message?: string }>(`/api/status/${jobId}`);

export const fetchClips = (jobId: string) => 
  apiFetch<{ clips: Clip[] }>(`/api/clips/${jobId}`);

// ─── Editor State ────────────────────────────────────────────────────────────

export const loadEditorState = (jobId: string, clipIndex: number) => 
  apiFetch<EditorStateResponse>(`/api/load_editor/${jobId}?clip_index=${clipIndex}`);

export const saveEditorState = (jobId: string, clipIndex: number, payload: EditorStatePayload) => 
  apiFetch<{ status: string; saved_at: string }>(`/api/save_editor/${jobId}?clip_index=${clipIndex}`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });

// ─── Captions & AI ───────────────────────────────────────────────────────────

export const fetchCaptionPresets = () => 
  apiFetch<{ presets: CaptionPreset[] }>('/api/captions/presets');

export const fetchTranscript = (
  jobId: string,
  clipIdx: number,
  force: boolean = false,
  bounds?: { start?: number; end?: number }
) => {
  const params = new URLSearchParams();
  if (force) params.set('force', 'true');
  if (bounds?.start !== undefined) params.set('start', String(bounds.start));
  if (bounds?.end !== undefined) params.set('end', String(bounds.end));
  const query = params.toString();
  return apiFetch<Word[]>(`/api/transcript/${jobId}/${clipIdx}${query ? `?${query}` : ''}`);
};

export const generateCaptionComposition = async (
  jobId: string, 
  transcript: Word[], 
  captionSettings: CaptionSettings, 
  aspectRatio: string = '9:16'
): Promise<string> => {
  const response = await fetch(`${API_BASE}/api/caption_composition/${jobId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ transcript, caption_settings: captionSettings, aspect_ratio: aspectRatio }),
  });
  if (!response.ok) throw new Error('Failed to generate caption composition');
  const blob = await response.blob();
  return URL.createObjectURL(blob);
};

export const autoTrackFace = (jobId: string, clipIndex: number, timestamp: number) => 
  apiFetch<{ crop_x?: number; error?: string }>(`/api/auto_track/${jobId}?clip_index=${clipIndex}&timestamp=${timestamp}`);

// ─── Export ──────────────────────────────────────────────────────────────────

export const startExport = (jobId: string, payload: {
  filename: string;
  clip_index: number;
  segments: Segment[];
  caption_settings: CaptionSettings;
  transcript: Word[];
  aspect_ratio: string;
  auto_background_enabled: boolean;
}) => 
  apiFetch<{ export_id: string }>(`/api/export/${jobId}`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });

export const deleteExport = (jobId: string, filename: string) => 
  apiFetch<{ status: string }>(`/api/export/${jobId}/${filename}`, { method: 'DELETE' });

// ─── Utils ───────────────────────────────────────────────────────────────────

export const uploadCookies = (file: File) => {
  const formData = new FormData();
  formData.append('file', file);
  return apiFetch<{ message: string }>('/api/upload-cookies', {
    method: 'POST',
    body: formData,
    headers: {
      // Don't set Content-Type for FormData, browser will do it with boundary
      'Content-Type': '', 
    },
  });
};

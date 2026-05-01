import { EditorSlice } from './types';
import { timestampToSeconds } from '../../utils/time';
import { createSSEConnection } from '../../utils/sse';
import * as api from '../../api/client';

export const createProjectSlice: EditorSlice<any> = (set, get) => ({
  loadProjectData: async (projectId: string) => {
    try {
      const data = await api.fetchClips(projectId);
      set({ 
        clips: (data.clips || []).map((clip) => ({
          ...clip,
          auto_background_enabled: clip.auto_background_enabled !== false
        }))
      });
    } catch (err) {
      console.error("Could not fetch clips", err);
    }
  },

  loadEditorState: async (projectId: string, clipIndex: number) => {
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
            lastSaved: data.saved_at || null
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

  saveEditorState: async () => {
    const { project, activeClipIndex, segments, activeSegmentIndex, captionSettings, clips } = get();
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
        set({ saveStatus: 'saved', lastSaved: data.saved_at || null });
      } else {
        set({ saveStatus: 'error' });
      }
    } catch (err) {
      set({ saveStatus: 'error' });
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
        const url = `${api.API_BASE}/api/progress/${data.export_id}`;
        createSSEConnection(url, {
          onMessage: (msg) => {
            if (msg.message) setStatusMessage(msg.message);
            if (msg.progress !== undefined) setExportProgress(msg.progress);
          },
          onDone: () => {
            notify("Video berhasil di-export!", "success");
            setIsProcessing(false);
          },
          onError: (err) => {
            setIsProcessing(false);
            notify("Gagal meng-export video: " + err, "error");
          }
        });
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
        highlightColor1: p.colors?.highlight1 || state.captionSettings.highlightColor1,
        highlightColor2: p.colors?.highlight2 || state.captionSettings.highlightColor2,
        outlineWidth: p.layout?.outline_width || state.captionSettings.outlineWidth,
        shadowEnabled: !!p.layout?.shadow,
        verticalMargin: p.layout?.vertical_margin || state.captionSettings.verticalMargin
      }
    }));
  }
});

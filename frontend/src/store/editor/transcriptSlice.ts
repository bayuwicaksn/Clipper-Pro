import { EditorSlice } from './types';
import { timestampToSeconds } from '../../utils/time';
import * as api from '../../api/client';

export const createTranscriptSlice: EditorSlice<any> = (set, get) => ({
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
});

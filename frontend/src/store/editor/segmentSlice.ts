import { EditorSlice } from './types';
import { generateId } from '../../utils/id';
import { timestampToSeconds, formatTimeHHMMSS } from '../../utils/time';
import { createSSEConnection } from '../../utils/sse';
import * as api from '../../api/client';
import { Segment } from '../../types';

export const createSegmentSlice: EditorSlice<any> = (set, get) => ({
  splitSegment: () => {
    const { segments, currentTime } = get();
    const segmentIndex = segments.findIndex(s => currentTime >= s.start && currentTime <= s.end);
    if (segmentIndex === -1) return;
    const seg = segments[segmentIndex];
    if (currentTime <= seg.start + 0.5 || currentTime >= seg.end - 0.5) return;
    
    const newSegments = [...segments];
    const secondHalf = { ...seg, id: generateId(), start: currentTime };
    newSegments[segmentIndex] = { ...seg, end: currentTime };
    newSegments.splice(segmentIndex + 1, 0, secondHalf);
    
    set({ 
      segments: newSegments, 
      activeSegmentIndex: segmentIndex + 1 
    });
  },

  deleteSegment: (index: number) => {
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

  updateSegmentBounds: (segmentIndex: number, nextStart: number, nextEnd: number) => {
    const { appMode, clips, activeClipIndex, project, segments } = get();
    
    if (appMode === 'clipper') {
      const updatedClips = [...clips];
      const clip = { ...updatedClips[activeClipIndex] };
      let safeStart = Math.max(0, Math.min(nextStart, nextEnd - 1));
      let safeEnd = Math.max(safeStart + 1, nextEnd);
      if (project?.video_duration && safeEnd > project.video_duration) safeEnd = project.video_duration;
      
      clip.start_time = formatTimeHHMMSS(safeStart);
      clip.end_time = formatTimeHHMMSS(safeEnd);
      updatedClips[activeClipIndex] = clip;
      
      set({ 
        clips: updatedClips,
        segments: [],
        transcript: []
      });
      return;
    }

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
      set({ activeSegmentIndex: nextIndex });
      return;
    }
    set({ isPlaying: false });
  },

  autoSplitSegments: async (notify) => {
    const { project, clips, activeClipIndex, setIsProcessing, setStatusMessage, setSegments, setActiveSegmentIndex, setCurrentTime, setSeekRequested } = get();
    const activeClip = clips[activeClipIndex];
    if (!project?.id || !activeClip) return;

    const clipStart = timestampToSeconds(activeClip.start_time);
    const clipEnd = timestampToSeconds(activeClip.end_time);

    setSegments([]);
    setActiveSegmentIndex(0);
    setCurrentTime(clipStart);
    setSeekRequested(clipStart);

    setIsProcessing(true);
    setStatusMessage('AI sedang membedah video...');
    
    const url = `${api.API_BASE}/api/detect_scenes/${project.id}?start=${clipStart}&end=${clipEnd}`;
    
    createSSEConnection(url, {
      onProgress: (data) => {
        if (data.progress !== undefined) setStatusMessage(`AI sedang membedah video... (${data.progress}%)`);
      },
      onDone: (data) => {
        if (data.cuts) {
          const clipDuration = Math.max(0, clipEnd - clipStart);
          const rawCuts: number[] = data.cuts
            .map((raw: number) => Number(raw))
            .filter((t: number) => Number.isFinite(t) && t >= 0);

          const maxCut = rawCuts.length > 0 ? Math.max(...rawCuts) : 0;
          const cutsAreRelative = rawCuts.length > 0 && maxCut <= clipDuration + 1 && clipStart > 1;
          const offset = cutsAreRelative ? clipStart : 0;

          const normalizedCuts = rawCuts
            .map((t: number) => t + offset)
            .filter((t: number) => t > clipStart + 1 && t < clipEnd - 1)
            .sort((a: number, b: number) => a - b)
            .filter((t: number, idx: number, arr: number[]) => idx === 0 || Math.abs(t - arr[idx - 1]) > 0.25);

          let newSegs: Segment[] = [];
          let lastT = clipStart;
          [...normalizedCuts, clipEnd].forEach((t) => {
            newSegs.push({ 
              id: generateId(), 
              start: lastT, 
              end: t, 
              crop_x: activeClip.custom_crop_x || 0.5,
              auto_background_enabled: activeClip.auto_background_enabled !== false
            });
            lastT = t;
          });
          setSegments(newSegs);
          setActiveSegmentIndex(0);
          notify(`Automatically split into ${newSegs.length} scenes!`, "success");
        }
        setIsProcessing(false);
      },
      onError: (err) => {
        setIsProcessing(false);
        notify("Gagal mendeteksi scene: " + err, "error");
      }
    });
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
        newSegs[activeSegmentIndex] = { ...newSegs[activeSegmentIndex], crop_x: data.crop_x };
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
});

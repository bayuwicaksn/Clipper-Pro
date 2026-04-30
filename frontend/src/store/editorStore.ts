import { create } from 'zustand';
import { EditorFullState } from './editor/types';
import { createBaseSlice } from './editor/baseSlice';
import { createSegmentSlice } from './editor/segmentSlice';
import { createTranscriptSlice } from './editor/transcriptSlice';
import { createProjectSlice } from './editor/projectSlice';

/**
 * Main Editor Store - Assembled from modular slices.
 * Handles state for:
 * - Base data (Project, Clips, AppMode)
 * - Segment actions (Split, AI tools)
 * - Transcript management
 * - Project persistence & Export
 * - Player status
 */
export const useEditorStore = create<EditorFullState>()((...a) => ({
  ...createBaseSlice(...a),
  ...createSegmentSlice(...a),
  ...createTranscriptSlice(...a),
  ...createProjectSlice(...a),
}));

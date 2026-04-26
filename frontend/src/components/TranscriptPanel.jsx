import React from 'react';
import { Type } from 'lucide-react';
import { Button } from '@/components/ui/button';

import { useEditorStore } from '@/store/editorStore';

const TranscriptPanel = () => {
  const {
    transcript,
    currentTime,
    isLoadingTranscript,
    setSeekRequested,
    setCurrentTime,
    fetchTranscript
  } = useEditorStore();
  
  const loadTranscript = () => fetchTranscript(true);
  const safeTranscript = Array.isArray(transcript) ? transcript : [];

  return (
    <div className="nle-left-panel bg-card border-r border-border flex flex-col w-[340px]">
      <div className="px-6 py-5 border-b border-border/40 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted-foreground flex items-center gap-2">
            <Type className="w-3 h-3" /> Transcript
          </h3>
        </div>

        <div className="flex items-center gap-4">
          <label className="flex items-center gap-2 cursor-pointer group">
            <input type="checkbox" className="w-4 h-4 rounded border-border bg-background accent-primary cursor-pointer" />
            <span className="text-xs text-muted-foreground group-hover:text-foreground transition-colors">Transcript only</span>
          </label>
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={loadTranscript}
          className="w-full justify-start h-9 text-xs font-bold border-white/5 bg-white/5 hover:bg-white/10"
        >
          <span className="text-primary mr-2">+</span> Add a section
        </Button>
      </div>

      <div className="p-6 overflow-y-auto flex-1 custom-scrollbar transcript-flow">
        <div className="flex flex-wrap gap-x-1.5 gap-y-3 leading-[1.8] items-baseline">
          {safeTranscript.length === 0 && !isLoadingTranscript && (
            <p className="text-sm text-muted-foreground/60 italic">No transcript available.</p>
          )}

          {safeTranscript.map((w, i) => {
            if (!w) return null;
            const curT = Number(currentTime);
            const wStart = Number(w.start);
            const wEnd = Number(w.end);

            const isActive = curT >= (wStart - 0.1) && curT < (wEnd + 0.1);

            const prevWord = safeTranscript[i - 1];
            const hasGap = prevWord && (wStart - Number(prevWord.end) > 1.2);
            const isHighlight = w.word && /^(selamat|pagi|siang|malam|senior|saya|pakar|screen|time|mayapada|beliau|ngomong|presiden|adaptasi)/i.test(w.word);

            return (
              <React.Fragment key={i}>
                {hasGap && (
                  <span className="text-muted-foreground/20 px-1 tracking-[0.2em] font-bold text-[10px]">...</span>
                )}
                <span
                  data-active={isActive}
                  className={`cursor-pointer px-1.5 py-0.5 rounded-sm transition-all duration-150 text-[15px] font-medium tracking-tight
                    ${isActive
                      ? 'bg-[#34D399] text-black font-bold scale-110 shadow-[0_0_20px_rgba(52,211,153,0.5)] z-10'
                      : isHighlight
                        ? 'text-[#FDE047] opacity-100'
                        : 'text-foreground/70 hover:text-foreground hover:bg-foreground/10 opacity-90'
                    }`}
                  onClick={() => {
                    setSeekRequested(wStart);
                    setCurrentTime(wStart);
                  }}
                >
                  {w.word}
                </span>
              </React.Fragment>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default TranscriptPanel;

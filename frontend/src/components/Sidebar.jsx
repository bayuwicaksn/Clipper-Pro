import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Sparkles, ChevronDown, Type, Scissors, Cloud, LayoutTemplate, Film, Music, Zap } from 'lucide-react';

import { useEditorStore } from '@/store/editorStore';

export default function Sidebar({
  presets,
  onAutoSplit,
  onAutoTrack,
  onRegenerateTranscript
}) {
  const {
    clips,
    activeClipIndex,
    activeTab,
    captionSettings,
    setCaptionSettings,
    applyCaptionPreset
  } = useEditorStore();

  const clip = clips[activeClipIndex];

  const [activeSubTab, setActiveSubTab] = useState('Presets');

  useEffect(() => {
    if (activeTab === 'captions') {
      // Intentional: reset sub-tab when switching to captions panel
      setActiveSubTab('Presets'); // eslint-disable-line react-hooks/set-state-in-effect
    }
  }, [activeTab]);

  const updateSettings = (key, value) => {
    setCaptionSettings({ ...captionSettings, [key]: value });
  };

  if (!clip) return <div className="nle-panel-content p-8 text-center text-zinc-500">Select a clip</div>;

  if (activeTab !== 'captions') {
    const panelMeta = {
      'ai-enhance': {
        icon: Sparkles,
        title: 'AI Enhance',
        description: 'Analyze this clip and prepare smart edit assists.',
        actions: [
          { label: 'Auto Split Scenes', icon: Scissors, onClick: onAutoSplit },
          { label: 'Auto Track Face', icon: Sparkles, onClick: onAutoTrack },
          { label: 'Regenerate Transcript', icon: Type, onClick: onRegenerateTranscript },
        ],
      },
      media: { icon: Cloud, title: 'Media', description: 'Media controls for this clip will appear here.' },
      brand: { icon: LayoutTemplate, title: 'Brand Template', description: 'Brand styling and reusable templates will appear here.' },
      'b-roll': { icon: Film, title: 'B-Roll', description: 'B-roll suggestions and inserts will appear here.' },
      transitions: { icon: Sparkles, title: 'Transitions', description: 'Transition controls will appear here.' },
      text: { icon: Type, title: 'Text', description: 'Text overlays and title controls will appear here.' },
      music: { icon: Music, title: 'Music', description: 'Music and audio controls will appear here.' },
      'ai-hook': { icon: Zap, title: 'AI Hook', description: 'Hook generation controls will appear here.' },
    };

    const meta = panelMeta[activeTab] || panelMeta.media;
    const Icon = meta.icon;

    return (
      <div className="flex flex-col h-full bg-[#0d0d0e]">
        <div className="border-b border-[#27272a] px-5 py-4">
          <div className="flex items-center gap-2 text-sm font-bold text-white">
            <Icon className="w-4 h-4" />
            {meta.title}
          </div>
        </div>
        <div className="flex-1 p-5 space-y-4 overflow-y-auto custom-scrollbar">
          <p className="text-sm leading-6 text-zinc-400">{meta.description}</p>
          {meta.actions?.map((action) => {
            const ActionIcon = action.icon;
            return (
              <Button
                key={action.label}
                variant="outline"
                size="sm"
                onClick={action.onClick}
                className="w-full justify-start h-10 text-xs font-bold border-white/5 bg-white/5 hover:bg-white/10"
              >
                <ActionIcon className="w-3.5 h-3.5 mr-2" />
                {action.label}
              </Button>
            );
          })}
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-[#0d0d0e]">
      <div className="flex border-b border-[#27272a]">
        {['Presets', 'Font', 'Effects'].map(tab => (
          <div
            key={tab}
            onClick={() => setActiveSubTab(tab)}
            className={`flex-1 text-center py-4 text-[11px] font-bold uppercase tracking-widest cursor-pointer transition-colors ${activeSubTab === tab ? 'text-white border-b-2 border-white' : 'text-zinc-500 hover:text-zinc-300'}`}
          >
            {tab}
          </div>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto custom-scrollbar p-5 space-y-8">
        {activeSubTab === 'Presets' && (
          <div className="grid grid-cols-2 gap-3 pb-20">
            {/* None option */}
            <div
              className={`group relative aspect-square rounded-xl bg-[#1e1e21] border-2 flex flex-col items-center justify-center cursor-pointer transition-all ${captionSettings.presetId === 'none' ? 'border-white bg-white/5' : 'border-[#27272a] hover:border-zinc-500'}`}
              onClick={() => setCaptionSettings(prev => ({
                ...prev,
                presetId: 'none',
                presetName: 'None'
              }))}
            >
              <div className="text-2xl text-zinc-600 group-hover:text-zinc-400 transition-colors">✕</div>
              <div className="absolute bottom-2 text-[10px] font-bold uppercase tracking-widest text-zinc-500">None</div>
            </div>

            {presets
              .filter(p => p.id !== 'none')
              .map((p, idx) => (
                <div
                  key={idx}
                  className={`group relative aspect-square rounded-xl bg-[#1e1e21] border-2 flex flex-col items-center justify-center cursor-pointer transition-all ${captionSettings.presetId === p.id ? 'border-white bg-white/5' : 'border-[#27272a] hover:border-zinc-500'}`}
                  onClick={() => applyCaptionPreset(p)}
                >
                  <div className="flex items-center justify-center h-full w-full p-4 overflow-hidden" style={{
                    fontFamily: `"${p.font?.family || 'Anton'}", sans-serif`,
                    color: p.colors?.primary || '#fff',
                    WebkitTextStroke: `1px ${p.colors?.outline || '#000'}`,
                    fontSize: '28px',
                    fontWeight: 900,
                  }}>
                    {p.icon || 'Aa'}
                  </div>
                  <div className="absolute bottom-2 text-[10px] font-bold uppercase tracking-widest text-zinc-500">{p.name}</div>
                </div>
              ))
            }
          </div>
        )}

        {activeSubTab === 'Font' && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <span className="text-sm font-bold text-white">Font settings</span>
              <ChevronDown className="w-4 h-4 text-zinc-500" />
            </div>

            {/* Font Family */}
            <div className="relative">
              <select 
                className="w-full bg-[#1e1e21] border border-[#27272a] rounded-xl px-4 py-3.5 text-sm text-white appearance-none cursor-pointer focus:border-zinc-500 outline-none"
                value={captionSettings.fontName}
                onChange={(e) => updateSettings('fontName', e.target.value)}
              >
                <option value="Montserrat">Montserrat</option>
                <option value="Anton">Anton</option>
                <option value="Inter">Inter</option>
                <option value="Roboto">Roboto</option>
              </select>
              <ChevronDown className="absolute right-4 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500 pointer-events-none" />
            </div>

            {/* Size, Weight, Color */}
            <div className="flex gap-2">
              <div className="w-11 h-11 rounded-full border-4 border-[#1e1e21] cursor-pointer shadow-xl flex-shrink-0" style={{ backgroundColor: captionSettings.primaryColor }}>
                 <input type="color" className="opacity-0 w-full h-full cursor-pointer" value={captionSettings.primaryColor} onChange={(e) => updateSettings('primaryColor', e.target.value)} />
              </div>
              <div className="flex-1 flex items-center bg-[#1e1e21] border border-[#27272a] rounded-xl px-4 group focus-within:border-zinc-500">
                <input 
                  type="number" className="bg-transparent w-full text-white text-sm font-bold outline-none" 
                  value={captionSettings.fontSize} 
                  onChange={(e) => updateSettings('fontSize', parseInt(e.target.value))}
                />
                <span className="text-zinc-500 text-xs font-medium ml-1">px</span>
              </div>
              <div className="flex-1 relative">
                <select 
                  className="w-full h-full bg-[#1e1e21] border border-[#27272a] rounded-xl px-4 py-2.5 text-sm text-white appearance-none font-bold outline-none cursor-pointer"
                  value={captionSettings.fontWeight}
                  onChange={(e) => updateSettings('fontWeight', e.target.value)}
                >
                  <option value="Black">Black</option>
                  <option value="Bold">Bold</option>
                  <option value="Medium">Medium</option>
                  <option value="Regular">Regular</option>
                </select>
                <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-zinc-500 pointer-events-none" />
              </div>
            </div>

            {/* Decoration */}
            <div className="flex items-center justify-between pt-1">
              <span className="text-sm font-medium text-zinc-400">Decoration</span>
              <div className="flex gap-6 pr-2">
                <button 
                  className={`italic text-xl font-serif transition-colors ${captionSettings.isItalic ? 'text-white' : 'text-zinc-600 hover:text-zinc-400'}`}
                  onClick={() => updateSettings('isItalic', !captionSettings.isItalic)}
                >I</button>
                <button 
                  className={`underline text-xl transition-colors ${captionSettings.isUnderline ? 'text-white' : 'text-zinc-600 hover:text-zinc-400'}`}
                  onClick={() => updateSettings('isUnderline', !captionSettings.isUnderline)}
                >U</button>
              </div>
            </div>

            {/* Uppercase Toggle */}
            <div className="flex items-center justify-between pt-1">
              <span className="text-sm font-medium text-zinc-400">Uppercase</span>
              <div 
                className={`w-[52px] h-[28px] rounded-full p-1 cursor-pointer transition-all duration-200 ${captionSettings.isUppercase ? 'bg-white' : 'bg-[#27272a]'}`}
                onClick={() => updateSettings('isUppercase', !captionSettings.isUppercase)}
              >
                <div className={`w-5 h-5 rounded-full shadow-md transition-transform duration-200 ${captionSettings.isUppercase ? 'translate-x-[24px] bg-black' : 'translate-x-0 bg-white'}`} />
              </div>
            </div>

            {/* Font Stroke */}
            <div className="flex items-center justify-between pt-2">
              <span className="text-sm font-medium text-zinc-400">Font stroke</span>
              <div className="flex items-center gap-3">
                 <div className="w-9 h-9 rounded-full border-2 border-[#1e1e21] cursor-pointer shadow-lg" style={{ backgroundColor: captionSettings.outlineColor }}>
                    <input type="color" className="opacity-0 w-full h-full cursor-pointer" value={captionSettings.outlineColor} onChange={(e) => updateSettings('outlineColor', e.target.value)} />
                 </div>
                 <div className="w-24 flex items-center bg-[#1e1e21] border border-[#27272a] rounded-xl px-3 py-2.5">
                    <input type="number" className="bg-transparent w-full text-white text-sm font-bold outline-none text-right" value={captionSettings.outlineWidth} onChange={(e) => updateSettings('outlineWidth', parseInt(e.target.value))} />
                    <span className="text-zinc-500 text-[10px] font-bold ml-1">px</span>
                 </div>
              </div>
            </div>

            {/* Font Shadows */}
            <div className="space-y-4 pt-2">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-zinc-400">Font shadows</span>
                <div 
                  className={`w-[52px] h-[28px] rounded-full p-1 cursor-pointer transition-all duration-200 ${captionSettings.shadowEnabled ? 'bg-white' : 'bg-[#27272a]'}`}
                  onClick={() => updateSettings('shadowEnabled', !captionSettings.shadowEnabled)}
                >
                  <div className={`w-5 h-5 rounded-full shadow-md transition-transform duration-200 ${captionSettings.shadowEnabled ? 'translate-x-[24px] bg-black' : 'translate-x-0 bg-white'}`} />
                </div>
              </div>
              
              {captionSettings.shadowEnabled && (
                <div className="flex gap-2 animate-in fade-in slide-in-from-top-2 duration-200">
                   <div className="w-10 h-10 rounded-full border-2 border-[#1e1e21] cursor-pointer shadow-lg flex-shrink-0" style={{ backgroundColor: captionSettings.shadowColor }}>
                      <input type="color" className="opacity-0 w-full h-full cursor-pointer" value={captionSettings.shadowColor} onChange={(e) => updateSettings('shadowColor', e.target.value)} />
                   </div>
                   <div className="flex-1 flex items-center bg-[#1e1e21] border border-[#27272a] rounded-xl px-3 py-2">
                      <input type="number" className="bg-transparent w-full text-white text-xs font-bold outline-none text-right" value={captionSettings.shadowOffsetX} onChange={(e) => updateSettings('shadowOffsetX', parseInt(e.target.value))} />
                      <span className="text-zinc-500 text-[10px] font-bold ml-1">x</span>
                   </div>
                   <div className="flex-1 flex items-center bg-[#1e1e21] border border-[#27272a] rounded-xl px-3 py-2">
                      <input type="number" className="bg-transparent w-full text-white text-xs font-bold outline-none text-right" value={captionSettings.shadowOffsetY} onChange={(e) => updateSettings('shadowOffsetY', parseInt(e.target.value))} />
                      <span className="text-zinc-500 text-[10px] font-bold ml-1">y</span>
                   </div>
                   <div className="flex-1 flex items-center bg-[#1e1e21] border border-[#27272a] rounded-xl px-3 py-2">
                      <input type="number" className="bg-transparent w-full text-white text-xs font-bold outline-none text-right" value={captionSettings.shadowBlur} onChange={(e) => updateSettings('shadowBlur', parseInt(e.target.value))} />
                      <span className="text-zinc-500 text-[10px] font-bold ml-1">blur</span>
                   </div>
                </div>
              )}
            </div>

            {/* AI Keywords Highlighter */}
            <div className="space-y-4 pt-6 border-t border-[#27272a]">
              <div className="flex items-center justify-between">
                <span className="text-sm font-bold text-white">AI keywords highlighter</span>
                <div 
                  className={`w-[52px] h-[28px] rounded-full p-1 cursor-pointer transition-all duration-200 ${captionSettings.autoHighlight ? 'bg-white' : 'bg-[#27272a]'}`}
                  onClick={() => updateSettings('autoHighlight', !captionSettings.autoHighlight)}
                >
                  <div className={`w-5 h-5 rounded-full shadow-md transition-transform duration-200 ${captionSettings.autoHighlight ? 'translate-x-[24px] bg-black' : 'translate-x-0 bg-white'}`} />
                </div>
              </div>

              {captionSettings.autoHighlight && (
                <div className="space-y-3 animate-in fade-in duration-300">
                  <div className="bg-[#1e1e21] border border-[#27272a] rounded-xl px-4 py-3.5 flex items-center gap-4 hover:border-zinc-500 transition-colors cursor-pointer group">
                    <div className="w-6 h-6 rounded-full bg-[#04f827] shadow-[0_0_10px_rgba(4,248,39,0.3)]" />
                    <span className="text-xs text-zinc-400 font-mono tracking-wider group-hover:text-zinc-200">04f827FF</span>
                  </div>
                  <div className="bg-[#1e1e21] border border-[#27272a] rounded-xl px-4 py-3.5 flex items-center gap-4 hover:border-zinc-500 transition-colors cursor-pointer group">
                    <div className="w-6 h-6 rounded-full bg-[#fffd03] shadow-[0_0_10px_rgba(255,253,3,0.3)]" />
                    <span className="text-xs text-zinc-400 font-mono tracking-wider group-hover:text-zinc-200">FFFD03FF</span>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

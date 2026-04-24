import React, { useMemo } from "react";
import {
  AbsoluteFill,
  useCurrentFrame,
  useVideoConfig,
  Sequence,
  spring,
  interpolate,
} from "remotion";
import { createTikTokStyleCaptions, Caption } from "@remotion/captions";

interface CaptionsProps {
  transcript: Caption[];
  style?: string;
  settings?: any;
}

export const Captions: React.FC<CaptionsProps> = ({ transcript, style = "classic", settings }) => {
  const { fps } = useVideoConfig();

  const switchEveryMs = useMemo(() => {
    const limit = settings?.lineLimit ?? 2;
    if (limit === 1) return 800;
    if (limit === 3) return 2200;
    return 1500;
  }, [settings?.lineLimit]);

  const { pages } = useMemo(() => {
    // PyCaps Parity: Chunk by Character Limit instead of purely by Time
    // This prevents 4-line captions when someone speaks very quickly
    const limit = settings?.lineLimit ?? 2;
    const maxChars = limit === 1 ? 12 : (limit === 3 ? 40 : 25);
    
    const pagesResult = [];
    let currentTokens = [];
    let currentChars = 0;
    
    transcript.forEach((t: any) => {
       // Support both standard Remotion {text} and raw {word}
       const text = (t.text || t.word || "").trim();
       if (!text) return;
       
       const len = text.length;
       // If adding this word exceeds limit (and we already have at least 1 word), cut here
       if (currentChars + len > maxChars && currentTokens.length > 0) {
           pagesResult.push({
               startMs: currentTokens[0].startMs,
               tokens: currentTokens
           });
           currentTokens = [];
           currentChars = 0;
       }
       
       currentTokens.push({ ...t, text: ` ${text}` }); // Ensure spacing
       currentChars += len + 1; // +1 for the space
    });
    
    if (currentTokens.length > 0) {
       pagesResult.push({
           startMs: currentTokens[0].startMs,
           tokens: currentTokens
       });
    }
    
    return { pages: pagesResult };
  }, [transcript, settings?.lineLimit]);

  return (
    <AbsoluteFill>
      {pages.map((page, index) => {
        const nextPage = pages[index + 1] ?? null;
        const startFrame = (page.startMs / 1000) * fps;
        const endFrame = Math.min(
          nextPage ? (nextPage.startMs / 1000) * fps : Infinity,
          startFrame + (switchEveryMs / 1000) * fps
        );
        const durationInFrames = Math.max(1, Math.ceil(endFrame - startFrame));
        if (isNaN(startFrame) || isNaN(durationInFrames) || durationInFrames <= 0) return null;

        return (
          <Sequence key={index} from={Math.floor(startFrame)} durationInFrames={durationInFrames}>
            <CaptionPage page={page} styleType={style} settings={settings} />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};

const CaptionPage: React.FC<{ page: any; styleType: string; settings: any }> = ({ page, styleType, settings }) => {
  const frame = useCurrentFrame();
  const { fps, width } = useVideoConfig();

  const LEAD_TIME_MS = 80;
  const currentTimeMs = (frame / fps) * 1000;
  const absoluteTimeMs = page.startMs + currentTimeMs + LEAD_TIME_MS;

  // Settings from Sidebar
  const verticalMargin = settings?.verticalMargin ?? 150;
  const primaryColor = settings?.primaryColor ?? "#FFFFFF";
  const highlightColorGreen = settings?.highlightColorGreen ?? "#04f827"; 
  const highlightColorYellow = settings?.highlightColorYellow ?? "#fffd03"; 
  const outlineColor = settings?.outlineColor ?? "#000000";
  const outlineWidth = settings?.outlineWidth ?? 8;
  const fontSize = settings?.fontSize ?? 100;
  const fontName = settings?.fontName || "Montserrat";
  const fontWeight = settings?.fontWeight || "Black";
  const isItalic = settings?.isItalic || false;
  const isUnderline = settings?.isUnderline || false;
  const isUppercase = settings?.isUppercase !== false;
  
  // Shadow Settings
  const shadowEnabled = settings?.shadowEnabled !== false;
  const shadowColor = settings?.shadowColor ?? "#000000";
  const shadowX = settings?.shadowOffsetX ?? 2;
  const shadowY = settings?.shadowOffsetY ?? 2;
  const shadowBlur = settings?.shadowBlur ?? 2;

  const autoHighlight = settings?.autoHighlight !== false;

  const activeIndex = useMemo(() => {
    const strictIndex = page.tokens.findIndex((t: any) =>
      absoluteTimeMs >= t.fromMs && absoluteTimeMs < t.toMs
    );
    if (strictIndex !== -1) return strictIndex;
    let closestIndex = 0;
    let minDistance = Infinity;
    page.tokens.forEach((t: any, idx: number) => {
      const center = (t.fromMs + t.toMs) / 2;
      const distance = Math.abs(absoluteTimeMs - center);
      if (distance < minDistance) {
        minDistance = distance;
        closestIndex = idx;
      }
    });
    return closestIndex;
  }, [page.tokens, absoluteTimeMs]);

  // Position settings (normalized 0-1)
  const captionX = settings?.captionX ?? 0.5;
  const captionY = settings?.captionY ?? 0.82;

  return (
    <AbsoluteFill>
      <div
        className="text-center"
        style={{
          position: "absolute",
          left: `${captionX * 100}%`,
          top: `${captionY * 100}%`,
          transform: "translate(-50%, -50%)",
          maxWidth: width * 0.85,
          lineHeight: 1.0,
          textWrap: "balance", // The magic property for PyCaps parity
          perspective: "1000px",
        }}
      >
        {page.tokens.map((token: any, i: number) => {
          const isActive = i === activeIndex;
          
          // Opus Feature: AI Keywords
          const isGreenKeyword = autoHighlight && /^(sukses|kaya|uang|viral|trending|presiden)/i.test(token.text.trim());
          const isYellowKeyword = autoHighlight && /^(penting|rahasia|masalah|solusi|gila|keren|tips|trik|cara)/i.test(token.text.trim());
          
          const isPast = i < activeIndex;
          const isFuture = i > activeIndex;
          
          const spr = spring({
            frame: Math.max(0, (absoluteTimeMs - token.fromMs) / 1000 * fps),
            fps,
            config: { stiffness: 300, damping: 20 },
          });

          // Preset-specific animation logic
          const isIntense = ['explosive', 'hype', 'vibrant'].includes(styleType);
          const isBouncy = ['explosive', 'hype', 'vibrant', 'model', 'fast'].includes(styleType);
          
          let color = primaryColor;
          let opacity = 1;

          // 3-State Logic for colors
          if (isActive) {
            color = highlightColorGreen;
          } else if (isPast) {
            color = primaryColor;
          } else if (isFuture) {
            color = primaryColor;
            // Classic presets usually don't dim as aggressively, intense ones do
            opacity = isIntense ? 0.6 : 0.8; 
          }

          // Keyword overrides (only if not active)
          if (!isActive) {
            if (isGreenKeyword) color = highlightColorGreen;
            else if (isYellowKeyword) color = highlightColorYellow;
          }

          // Dynamic animations based on preset
          let scale = 1;
          let translateY = 0;
          let rotate = 0;

          if (isActive) {
             if (isBouncy) {
                scale = interpolate(spr, [0, 1], [1, 1.25]);
                translateY = interpolate(spr, [0, 1], [0, -12]);
             } else {
                scale = interpolate(spr, [0, 1], [1, 1.1]);
                translateY = interpolate(spr, [0, 1], [0, -4]);
             }
             
             if (isIntense) {
                rotate = interpolate(spr, [0, 1], [0, i % 2 === 0 ? -4 : 4]);
             }
          }

          let shadow = shadowEnabled 
            ? `${shadowX}px ${shadowY}px ${shadowBlur}px ${shadowColor}` 
            : "none";
            
          // Add glow effect ONLY for intense active words
          if (isActive && shadowEnabled && isIntense) {
             shadow = `${shadow}, 0 0 15px ${color}`;
          }
          
          let stroke = `${(fontSize * outlineWidth) / 1000}px ${outlineColor}`;

          return (
            <span
              key={i}
              className={`inline-block tracking-tighter ${isUppercase ? 'uppercase' : ''}`}
              style={{
                fontFamily: `"${fontName}", sans-serif`,
                fontSize: `${fontSize}px`,
                fontWeight: fontWeight === 'Black' ? 900 : (fontWeight === 'Bold' ? 700 : (fontWeight === 'Medium' ? 500 : 400)),
                fontStyle: isItalic ? 'italic' : 'normal',
                textDecoration: isUnderline ? 'underline' : 'none',
                color,
                opacity,
                textShadow: shadow,
                WebkitTextStroke: stroke,
                transform: `scale(${scale}) translateY(${translateY}px) rotate(${rotate}deg)`,
                transformOrigin: "center center",
                margin: "0 8px",
                transition: "color 0.1s ease-out, opacity 0.1s ease-out",
                willChange: "transform, color, opacity",
              }}
            >
              {token.text}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

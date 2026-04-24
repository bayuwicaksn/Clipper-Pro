import React, { useMemo } from 'react';

export const CustomCaptions = ({ transcript, styleType = "classic", settings, currentTimeMs }) => {
  if (settings?.presetId === 'none') return null;

  const switchEveryMs = useMemo(() => {
    const limit = settings?.lineLimit ?? 2;
    if (limit === 1) return 800;
    if (limit === 3) return 2200;
    return 1500;
  }, [settings?.lineLimit]);

  const { pages } = useMemo(() => {
    const limit = settings?.lineLimit ?? 2;
    const maxChars = limit === 1 ? 12 : (limit === 3 ? 40 : 25);
    
    const pagesResult = [];
    let currentTokens = [];
    let currentChars = 0;
    
    if (!Array.isArray(transcript)) return { pages: [] };

    transcript.forEach((t) => {
       const text = (t.text || t.word || "").trim();
       if (!text) return;
       
       // Handle seconds to milliseconds conversion if needed
       // OpenAI/Whisper usually return seconds (e.g. 1.2), while others use MS (e.g. 1200)
       let start = t.startMs || t.fromMs || t.start;
       let end = t.endMs || t.toMs || t.end;
       
       if (start !== undefined && start < 10000 && !t.startMs && !t.fromMs) start *= 1000;
       if (end !== undefined && end < 10000 && !t.endMs && !t.toMs) end *= 1000;

       const len = text.length;
       if (currentChars + len > maxChars && currentTokens.length > 0) {
           pagesResult.push({
               startMs: currentTokens[0].startMs,
               tokens: currentTokens
           });
           currentTokens = [];
           currentChars = 0;
       }
       
       currentTokens.push({ ...t, text: ` ${text}`, startMs: start, endMs: end }); 
       currentChars += len + 1; 
    });
    
    if (currentTokens.length > 0) {
       pagesResult.push({
           startMs: currentTokens[0].startMs,
           tokens: currentTokens
       });
    }
    
    return { pages: pagesResult };
  }, [transcript, settings?.lineLimit]);

  // Find active page
  const activePage = pages.find((page, index) => {
    const nextPage = pages[index + 1];
    const startTime = page.startMs;
    const endTime = nextPage ? nextPage.startMs : startTime + switchEveryMs;
    return currentTimeMs >= startTime && currentTimeMs < endTime;
  });

  if (!activePage) return null;

  const LEAD_TIME_MS = 80;
  const absoluteTimeMs = currentTimeMs + LEAD_TIME_MS;

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
  
  const shadowEnabled = settings?.shadowEnabled !== false;
  const shadowColor = settings?.shadowColor ?? "#000000";
  const shadowX = settings?.shadowOffsetX ?? 2;
  const shadowY = settings?.shadowOffsetY ?? 2;
  const shadowBlur = settings?.shadowBlur ?? 2;

  const autoHighlight = settings?.autoHighlight !== false;

  const activeIndex = (() => {
    const strictIndex = activePage.tokens.findIndex((t) =>
      absoluteTimeMs >= t.startMs && absoluteTimeMs < t.endMs
    );
    if (strictIndex !== -1) return strictIndex;
    let closestIndex = 0;
    let minDistance = Infinity;
    activePage.tokens.forEach((t, idx) => {
      const center = (t.startMs + t.endMs) / 2;
      const distance = Math.abs(absoluteTimeMs - center);
      if (distance < minDistance) {
        minDistance = distance;
        closestIndex = idx;
      }
    });
    return closestIndex;
  })();

  const captionX = settings?.captionX ?? 0.5;
  const captionY = settings?.captionY ?? 0.82;

  return (
    <div
      className="text-center absolute"
      style={{
        left: `${captionX * 100}%`,
        top: `${captionY * 100}%`,
        transform: "translate(-50%, -50%)",
        width: '85%',
        lineHeight: 1.0,
        textWrap: "balance",
        perspective: "1000px",
        pointerEvents: 'none',
        zIndex: 50
      }}
    >
      {activePage.tokens.map((token, i) => {
        const isActive = i === activeIndex;
        
        const isGreenKeyword = autoHighlight && /^(sukses|kaya|uang|viral|trending|presiden)/i.test(token.text.trim());
        const isYellowKeyword = autoHighlight && /^(penting|rahasia|masalah|solusi|gila|keren|tips|trik|cara)/i.test(token.text.trim());
        
        const isPast = i < activeIndex;
        const isFuture = i > activeIndex;
        
        // Pseudo-spring animation
        const timeSinceActive = Math.max(0, absoluteTimeMs - (token.fromMs || token.startMs));
        const progress = Math.min(1, timeSinceActive / 150); // 150ms animation duration
        
        const isIntense = ['explosive', 'hype', 'vibrant'].includes(styleType);
        const isBouncy = ['explosive', 'hype', 'vibrant', 'model', 'fast'].includes(styleType);
        
        let color = primaryColor;
        let opacity = 1;

        if (isActive) {
          color = highlightColorGreen;
        } else if (isPast) {
          color = primaryColor;
        } else if (isFuture) {
          color = primaryColor;
          opacity = isIntense ? 0.6 : 0.8; 
        }

        if (!isActive) {
          if (isGreenKeyword) color = highlightColorGreen;
          else if (isYellowKeyword) color = highlightColorYellow;
        }

        let scale = 1;
        let translateY = 0;
        let rotate = 0;

        if (isActive) {
           if (isBouncy) {
              scale = 1 + (0.25 * Math.sin(progress * Math.PI)); // Bouncy effect
              translateY = -12 * Math.sin(progress * Math.PI);
           } else {
              scale = 1 + (0.1 * progress);
              translateY = -4 * progress;
           }
           
           if (isIntense) {
              rotate = (i % 2 === 0 ? -4 : 4) * progress;
           }
        }

        let shadow = shadowEnabled 
          ? `${shadowX}px ${shadowY}px ${shadowBlur}px ${shadowColor}` 
          : "none";
          
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
  );
};

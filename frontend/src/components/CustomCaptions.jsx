import React, { useMemo } from 'react';



export const CustomCaptions = ({ transcript, styleType = "classic", settings, currentTimeMs, frameHeight, aspectRatio = '9:16', inlineMode = false }) => {

  // Derive the original video height based on standard 1080p width to match backend's video_h
  // If portrait (9:16), it's 1920. If landscape (16:9), it's 1080. If square, 1080.
  const videoAspectRatio = aspectRatio;
  let refHeight = 1920; // Default portrait
  if (videoAspectRatio === '16:9') refHeight = 1080;
  else if (videoAspectRatio === '1:1') refHeight = 1080;
  else if (videoAspectRatio === '4:5') refHeight = 1350;

  // Proportional scale factor — matches the exact scale of the preview frame
  const scaleFactor = (frameHeight || refHeight) / refHeight;

  const switchEveryMs = useMemo(() => {
    const limit = settings?.lineLimit ?? 2;
    if (limit === 1) return 800;
    if (limit === 3) return 2200;
    return 1500;
  }, [settings?.lineLimit]);

  const { pages } = useMemo(() => {
    const limit = settings?.lineLimit ?? 2;
    const fontSize = settings?.fontSize ?? 100;
    const captionWidthPct = settings?.captionWidth ?? 85;
    
    // Estimate max width in pixels for the container (relative to 1080 baseline)
    const containerWidthPx = 1080 * (captionWidthPct / 100);
    const maxChunkWidthPx = containerWidthPx * limit * 0.95; // 5% safety margin
    
    const isUppercase = settings?.isUppercase !== false;
    const charWidthRatio = isUppercase ? 0.7 : 0.55;
    const charWidthPx = fontSize * charWidthRatio;
    const spaceWidthPx = fontSize * 0.3;

    const pagesResult = [];
    let currentTokens = [];
    let currentWidthPx = 0;

    if (!Array.isArray(transcript)) return { pages: [] };

    transcript.forEach((t) => {
      let text = (t.text || t.word || "").trim();
      if (!text) return;

      // Handle seconds to milliseconds conversion if needed
      let start = t.startMs || t.fromMs || t.start;
      let end = t.endMs || t.toMs || t.end;

      if (start !== undefined && start < 10000 && !t.startMs && !t.fromMs) start *= 1000;
      if (end !== undefined && end < 10000 && !t.endMs && !t.toMs) end *= 1000;

      const rawText = text;
      if (isUppercase) text = text.toUpperCase();
      
      const wordWidthPx = text.length * charWidthPx;
      let forceBreak = false;

      if (currentTokens.length > 0) {
        const prevToken = currentTokens[currentTokens.length - 1];
        const pauseDurationMs = start - prevToken.endMs;
        
        // 1. Break on speech pause > 400ms
        if (pauseDurationMs > 400) forceBreak = true;
        
        // 2. Break on end of sentence or clause
        const prevText = prevToken.rawText || prevToken.text;
        if (/[.!?,]$/.test(prevText.trim())) forceBreak = true;
        
        // 3. Break on visual width limit
        if (currentWidthPx + spaceWidthPx + wordWidthPx > maxChunkWidthPx) forceBreak = true;
      }

      if (forceBreak && currentTokens.length > 0) {
        pagesResult.push({
          startMs: currentTokens[0].startMs,
          tokens: currentTokens
        });
        currentTokens = [];
        currentWidthPx = 0;
      }

      currentTokens.push({ ...t, text: ` ${rawText}`, rawText, startMs: start, endMs: end });
      currentWidthPx += wordWidthPx + (currentTokens.length > 1 ? spaceWidthPx : 0);
    });

    if (currentTokens.length > 0) {
      pagesResult.push({
        startMs: currentTokens[0].startMs,
        tokens: currentTokens
      });
    }

    return { pages: pagesResult };
  }, [transcript, settings?.lineLimit, settings?.fontSize, settings?.captionWidth, settings?.isUppercase]);

  if (settings?.presetId === 'none') return null;

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

  // ── Extract settings with defaults (matching caption_generator.py) ──
  const primaryColor = settings?.primaryColor ?? "#FFFFFF";
  const highlightColor1 = settings?.highlightColor1 ?? "#04f827";
  const highlightColor2 = settings?.highlightColor2 ?? "#fffd03";
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

  // Support dynamic overriding via CSS variables for smooth interaction/resizing
  const currentFontSize = `var(--caption-font-size, ${fontSize})`;
  const scaledFontSize = `calc(${currentFontSize} * ${scaleFactor})`;
  const scaledFontSizePx = `calc(${scaledFontSize} * 1px)`;
  const scaledOutline = (fontSize * outlineWidth) / 1000 * scaleFactor;
  const scaledShadowX = shadowX * scaleFactor;
  const scaledShadowY = shadowY * scaleFactor;
  const scaledShadowBlur = shadowBlur * scaleFactor;
  const scaledMargin = Math.max(2, 8 * scaleFactor);

  const activeIndex = (() => {
    return activePage.tokens.findIndex((t) =>
      absoluteTimeMs >= t.startMs && absoluteTimeMs < t.endMs
    );
  })();

  const captionX = settings?.captionX ?? 0.5;
  const captionY = settings?.captionY ?? 0.82;

  return (
    <div
      className={inlineMode ? "text-center" : "text-center absolute"}
      style={{
        left: inlineMode ? undefined : `${captionX * 100}%`,
        top: inlineMode ? undefined : `${captionY * 100}%`,
        transform: inlineMode ? undefined : "translate(-50%, -50%)",
        width: inlineMode ? 'fit-content' : `${settings?.captionWidth ?? 85}%`,
        maxWidth: inlineMode ? '100%' : undefined,
        height: inlineMode ? 'fit-content' : undefined,
        lineHeight: 1.0,
        textWrap: "balance",
        perspective: "1000px",
        pointerEvents: 'none',
        zIndex: inlineMode ? undefined : 50
      }}
    >
      {activePage.tokens.map((token, i) => {
        const isActive = i === activeIndex;

        // Auto-highlight regex — synced with caption_generator.py GREEN_REGEX / YELLOW_REGEX
        const isColor1Keyword = autoHighlight && /^(sukses|kaya|uang|viral|trending|presiden|milyar|triliun|cuan|profit|untung|berhasil)/i.test(token.text.trim());
        const isColor2Keyword = autoHighlight && /^(penting|rahasia|masalah|solusi|gila|keren|tips|trik|cara|fakta|bukti|seru|menarik|wow)/i.test(token.text.trim());

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
          // When active, use Color 2 if it's a Color 2 keyword, otherwise use Color 1 (default highlight)
          color = isColor2Keyword ? highlightColor2 : highlightColor1;
        } else {
          // Future/Past words stay as primary color (color biasa)
          color = primaryColor;
          if (isFuture) {
            opacity = isIntense ? 0.6 : 0.8;
          }
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
          ? `${scaledShadowX}px ${scaledShadowY}px ${scaledShadowBlur}px ${shadowColor}`
          : "none";

        if (isActive && shadowEnabled && isIntense) {
          shadow = `${shadow}, 0 0 ${15 * scaleFactor}px ${color}`;
        }

        let stroke = `${scaledOutline}px ${outlineColor}`;

        return (
          <span
            key={i}
            className={`inline-block tracking-tighter ${isUppercase ? 'uppercase' : ''}`}
            style={{
              fontFamily: `"${fontName}", sans-serif`,
              fontSize: scaledFontSizePx,
              fontWeight: fontWeight === 'Black' ? 900 : (fontWeight === 'Bold' ? 700 : (fontWeight === 'Medium' ? 500 : 400)),
              fontStyle: isItalic ? 'italic' : 'normal',
              textDecoration: isUnderline ? 'underline' : 'none',
              color,
              opacity,
              textShadow: shadow,
              WebkitTextStroke: stroke,
              transform: `scale(${scale}) translateY(${translateY}px) rotate(${rotate}deg)`,
              transformOrigin: "center center",
              margin: `0 ${scaledMargin}px`,
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

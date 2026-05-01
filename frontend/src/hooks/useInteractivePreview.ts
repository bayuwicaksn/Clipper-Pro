import { useCallback, useRef, useState, useEffect } from 'react';
import { useEditorStore } from '../store/editorStore';

interface DragState {
  type: 'pan' | 'resize' | 'caption-pan' | 'caption-resize';
  startX: number;
  startY: number;
  initialX: number;
  initialY: number;
  initialZ: number;
  initialWidth?: number;
  initialSize?: number;
  handle?: string;
  rect?: DOMRect;
  containerRect?: DOMRect;
}

export function useInteractivePreview(
  videoRef: React.RefObject<HTMLVideoElement>,
  aspectRatioBoxRef: React.RefObject<HTMLDivElement>,
  captionOverlayRef: React.RefObject<HTMLDivElement>,
  props: {
    cropX: number;
    cropY: number;
    cropZ: number;
    setCropX: (val: number) => void;
    setCropY: (val: number) => void;
    setCropZ: (val: number) => void;
  }
) {
  const {
    videoAspectRatio,
    setCaptionSettings,
    panX, setPanX,
    panY, setPanY,
  } = useEditorStore();

  const [dragState, setDragState] = useState<DragState | null>(null);
  const [isCanvasPanning, setIsCanvasPanning] = useState(false);
  const [isSnappedX, setIsSnappedX] = useState(false);
  const [isSnappedY, setIsSnappedY] = useState(false);
  const [isSnappedZ, setIsSnappedZ] = useState(false);
  const [isSnappedCaptionX, setIsSnappedCaptionX] = useState(false);
  
  const canvasPanStartRef = useRef({ x: 0, y: 0, panX: 0, panY: 0 });

  const handleMouseMove = useCallback((e: MouseEvent) => {
    let rafId: number | null = null;
    if (rafId) return;

    rafId = requestAnimationFrame(() => {
      rafId = null;

      if (dragState) {
        const dx = e.clientX - dragState.startX;
        const dy = e.clientY - dragState.startY;

        if (dragState.type === 'pan') {
          const container = videoRef.current?.parentElement;
          if (!container) return;

          const sensitivityX = 1 / (container.clientWidth * (props.cropZ || 1.0));
          const sensitivityY = 1 / (container.clientHeight * (props.cropZ || 1.0));

          let newX = dragState.initialX - dx * sensitivityX;
          let newY = dragState.initialY - dy * sensitivityY;

          const snapThreshold = 0.015;
          const snappedX = Math.abs(newX - 0.5) < snapThreshold;
          const snappedY = Math.abs(newY - 0.5) < snapThreshold;

          if (snappedX) newX = 0.5;
          if (snappedY) newY = 0.5;

          setIsSnappedX(snappedX);
          setIsSnappedY(snappedY);
          props.setCropX(Math.max(0, Math.min(1, newX)));
          props.setCropY(Math.max(0, Math.min(1, newY)));

        } else if (dragState.type === 'resize') {
          const sensitivity = 0.005;
          const zoomDelta = (dragState.handle?.includes('t') ? -dy : dy) * sensitivity;
          let newZ = dragState.initialZ + zoomDelta;

          const container = videoRef.current?.parentElement;
          if (container) {
            const videoAR = videoAspectRatio || 16 / 9;
            const W_p = container.clientWidth;
            const H_p = container.clientHeight;
            const W_dom = Math.min(W_p, H_p * videoAR);
            const H_dom = Math.min(H_p, W_p / videoAR);

            const snapPoints = [1.0];
            [9/16, 4/5, 1/1, videoAR].forEach(val => {
              const W_m = Math.min(W_p, H_p * val);
              const H_m = Math.min(H_p, W_p / val);
              snapPoints.push(W_m / W_dom, H_m / H_dom);
            });

            const zSnapThreshold = 0.06;
            let snapped = false;
            for (const pt of snapPoints) {
              if (Math.abs(newZ - pt) < zSnapThreshold) {
                newZ = pt;
                snapped = true;
                break;
              }
            }
            setIsSnappedZ(snapped);
          }
          props.setCropZ(Math.max(0.1, Math.min(10.0, newZ)));

        } else if (dragState.type === 'caption-pan') {
          const container = aspectRatioBoxRef.current;
          if (!container) return;

          const sensitivityX = 1 / container.clientWidth;
          const sensitivityY = 1 / container.clientHeight;

          const newX = dragState.initialX + dx * sensitivityX;
          const newY = dragState.initialY + dy * sensitivityY;

          const snapThreshold = 0.015;
          const snappedX = Math.abs(newX - 0.5) < snapThreshold;
          const finalX = snappedX ? 0.5 : newX;
          setIsSnappedCaptionX(snappedX);

          if (captionOverlayRef.current) {
            captionOverlayRef.current.style.left = `${finalX * 100}%`;
            captionOverlayRef.current.style.top = `${newY * 100}%`;
          }

          setCaptionSettings((prev: any) => ({ ...prev, captionX: finalX, captionY: newY }));

        } else if (dragState.type === 'caption-resize') {
          if (!dragState.rect || !dragState.containerRect || !dragState.handle) return;
          
          const rect = dragState.rect;
          const container = dragState.containerRect;
          const mx = e.clientX;
          
          let fixedX = 0;
          let fixedY = 0;
          let scale = 1;

          // Identify the fixed anchor point based on the handle being dragged
          if (dragState.handle === 'nw') {
            fixedX = rect.right;
            fixedY = rect.bottom;
            scale = (fixedX - mx) / rect.width;
          } else if (dragState.handle === 'ne') {
            fixedX = rect.left;
            fixedY = rect.bottom;
            scale = (mx - fixedX) / rect.width;
          } else if (dragState.handle === 'sw') {
            fixedX = rect.right;
            fixedY = rect.top;
            scale = (fixedX - mx) / rect.width;
          } else if (dragState.handle === 'se') {
            fixedX = rect.left;
            fixedY = rect.top;
            scale = (mx - fixedX) / rect.width;
          }

          // Enforce minimum reasonable scale
          scale = Math.max(0.1, scale);

          const newWidthPx = rect.width * scale;
          const newHeightPx = rect.height * scale;

          let newCenterX = 0;
          let newCenterY = 0;

          if (dragState.handle === 'nw') {
            newCenterX = fixedX - newWidthPx / 2;
            newCenterY = fixedY - newHeightPx / 2;
          } else if (dragState.handle === 'ne') {
            newCenterX = fixedX + newWidthPx / 2;
            newCenterY = fixedY - newHeightPx / 2;
          } else if (dragState.handle === 'sw') {
            newCenterX = fixedX - newWidthPx / 2;
            newCenterY = fixedY + newHeightPx / 2;
          } else if (dragState.handle === 'se') {
            newCenterX = fixedX + newWidthPx / 2;
            newCenterY = fixedY + newHeightPx / 2;
          }

          // Convert absolute center to relative captionX, captionY
          const relX = (newCenterX - container.left) / container.width;
          const relY = (newCenterY - container.top) / container.height;

          const newSize = (dragState.initialSize || 100) * scale;
          const newWidthPct = (dragState.initialWidth || 85) * scale;

          // DIRECT DOM UPDATE for instant feedback
          if (captionOverlayRef.current) {
            captionOverlayRef.current.style.left = `${relX * 100}%`;
            captionOverlayRef.current.style.top = `${relY * 100}%`;
            captionOverlayRef.current.style.setProperty('--caption-font-size', String(newSize));
            captionOverlayRef.current.style.setProperty('--caption-max-width', `${newWidthPct}%`);
          }

          // Sync back to React state (this will eventually trigger re-render, but DOM is already updated)
          setCaptionSettings((prev: any) => ({ 
            ...prev, 
            captionX: relX, 
            captionY: relY,
            fontSize: Math.round(newSize), 
            captionWidth: Math.round(newWidthPct) 
          }));
        }
      } else if (isCanvasPanning) {
        setPanX(canvasPanStartRef.current.panX + (e.clientX - canvasPanStartRef.current.x));
        setPanY(canvasPanStartRef.current.panY + (e.clientY - canvasPanStartRef.current.y));
      }
    });
  }, [dragState, isCanvasPanning, props, videoAspectRatio, setCaptionSettings, setPanX, setPanY, videoRef, aspectRatioBoxRef, captionOverlayRef]);

  useEffect(() => {
    const handleMouseUp = () => {
      if (captionOverlayRef.current) {
        captionOverlayRef.current.style.removeProperty('--caption-font-size');
        captionOverlayRef.current.style.removeProperty('--caption-max-width');
      }
      setDragState(null);
      setIsCanvasPanning(false);
      setIsSnappedCaptionX(false);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [handleMouseMove]);

  return {
    dragState, setDragState,
    isCanvasPanning, setIsCanvasPanning,
    isSnappedX, isSnappedY, isSnappedZ, isSnappedCaptionX,
    canvasPanStartRef
  };
}

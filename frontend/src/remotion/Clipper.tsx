import { z } from "zod";
import {
  AbsoluteFill,
  Video,
  useVideoConfig,
  useCurrentFrame,
  interpolate,
} from "remotion";
import { Captions } from "./Captions";

export const clipperSchema = z.object({
  videoSrc: z.string(),
  transcript: z.array(
    z.object({
      text: z.string(),
      startMs: z.number(),
      endMs: z.number(),
    })
  ),
  captionStyle: z.string().optional(),
  cropX: z.number().optional().default(0.5),
  cropY: z.number().optional().default(0.5),
  zoom: z.number().optional().default(1),
  startSecs: z.number().optional().default(0),
  isPreview: z.boolean().optional().default(false),
  appMode: z.string().optional().default('editor'),
  captionSettings: z.object({
    verticalMargin: z.number().optional(),
    horizontalMargin: z.number().optional(),
    fontSize: z.number().optional(),
    fontName: z.number().optional(), // Should be string, but some presets might send ID
    primaryColor: z.string().optional(),
    outlineColor: z.string().optional(),
  }).optional(),
});

type ClipperProps = z.infer<typeof clipperSchema>;

export const Clipper: React.FC<ClipperProps> = ({
  videoSrc,
  transcript,
  captionStyle = "classic",
  cropX,
  cropY = 0.5,
  zoom,
  startSecs = 0,
  isPreview = false,
  appMode = 'editor',
  captionSettings,
}) => {
  const { width, height, fps } = useVideoConfig();
  const frame = useCurrentFrame();
  const startFrame = Math.floor(startSecs * fps);

  // Calculate the portrait guide dimensions (9:16)
  const portraitWidth = height * (9 / 16);
  const portraitLeft = (width / 2) - (portraitWidth / 2);

  return (
    <AbsoluteFill className="bg-black overflow-hidden">
      {/* Background Layer: Blurred and Scaled to Fill (Only in editor) */}
      {appMode !== 'clipper' && (
        <AbsoluteFill className="scale-110 blur-xl opacity-50">
          <Video
            src={videoSrc}
            className="w-full h-full object-cover"
            muted
            startFrom={startFrame}
          />
        </AbsoluteFill>
      )}

      {/* Video Content Layer */}
      <AbsoluteFill className="flex items-center justify-center">
        <div
          className="relative"
          style={{
            width: (isPreview || appMode === 'clipper') ? width : portraitWidth,
            height: height,
            overflow: 'hidden',
          }}
        >
          {/* The actual video being cropped/transformed */}
          <Video
            src={videoSrc}
            startFrom={startFrame}
            style={{
              height: "100%",
              width: "auto",
              position: "absolute",
              left: "50%",
              top: "50%",
              transform: appMode === 'clipper' 
                ? `translate(-50%, -50%) scale(1.0)` 
                : `translate(-50%, -50%) 
                   translate(
                     calc((0.5 - var(--crop-x, ${cropX})) * 100% * var(--zoom, ${zoom})),
                     calc((0.5 - var(--crop-y, ${cropY})) * 100% * var(--zoom, ${zoom}))
                   ) 
                   scale(var(--zoom, ${zoom}))`,
            }}
          />

          {/* Portrait Guide (only in preview editor) */}
          {isPreview && appMode !== 'clipper' && (
            <div 
              style={{
                position: 'absolute',
                top: 0,
                bottom: 0,
                left: '50%',
                transform: 'translateX(-50%)',
                width: portraitWidth,
                border: '2px solid rgba(255, 255, 255, 0.8)',
                boxShadow: '0 0 0 9999px rgba(0, 0, 0, 0.9)',
                zIndex: 10,
                pointerEvents: 'none'
              }}
            />
          )}

          {/* Captions Layer (only in editor) */}
          {appMode !== 'clipper' && (
            <div 
              style={{
                position: 'absolute',
                top: 0,
                bottom: 0,
                left: '50%',
                transform: 'translateX(-50%)',
                width: portraitWidth,
                zIndex: 20,
                pointerEvents: 'none'
              }}
            >
              <Captions
                transcript={transcript}
                style={captionStyle}
                settings={captionSettings}
              />
            </div>
          )}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

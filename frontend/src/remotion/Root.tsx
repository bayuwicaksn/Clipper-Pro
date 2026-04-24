import { registerComposition } from 'remotion';
import { Clipper, clipperSchema } from './Clipper';

registerComposition({
  id: 'Clipper',
  component: Clipper,
  durationInFrames: 1800, // Default 60s, will be overridden by props anyway
  fps: 30,
  width: 1080,
  height: 1920,
  schema: clipperSchema,
  defaultProps: {
    videoSrc: "",
    transcript: [],
    cropX: 0.5,
    cropY: 0.5,
    zoom: 1.0,
    startSecs: 0,
    captionStyle: "classic",
    captionSettings: {
      primaryColor: "#FFD700",
      fontSize: 90,
      verticalMargin: 150
    }
  }
});

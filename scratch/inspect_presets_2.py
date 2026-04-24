from pycaps.template import TemplateLoader
import os

# Try to find where templates are stored
loader = TemplateLoader(template="karaoke")
print(f"Template path: {loader.path}")
preset_dir = os.path.dirname(loader.path)
print(f"Presets found in: {preset_dir}")
print(os.listdir(preset_dir))

from pycaps.pipeline import CapsPipelineBuilder
import inspect

print("Methods in CapsPipelineBuilder:")
builder = CapsPipelineBuilder()
for name, obj in inspect.getmembers(builder):
    if not name.startswith('_') and inspect.ismethod(obj):
        print(f"- {name}")

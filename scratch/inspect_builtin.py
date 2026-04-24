from pycaps.template import BuiltinTemplate
import inspect

print("Members of BuiltinTemplate:")
for name, obj in inspect.getmembers(BuiltinTemplate):
    if not name.startswith('_'):
        print(f"- {name}")

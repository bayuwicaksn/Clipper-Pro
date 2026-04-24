import pycaps.template as py_temp
import inspect

print("Classes in pycaps.template:")
for name, obj in inspect.getmembers(py_temp):
    if inspect.isclass(obj):
        print(f"- {name}")

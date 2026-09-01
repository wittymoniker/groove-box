import sys
import inspect
import importlib

import groovebox

EXPECTED_MODULES = [
    groovebox,
    importlib.import_module("composition_state"),
    importlib.import_module("dj_effects"),
    importlib.import_module("fractal_spatial_engine"),
    importlib.import_module("videogame_engine"),
    importlib.import_module("fast_widgets"),
]

expected = {}
for mod in EXPECTED_MODULES:
    for name, obj in vars(mod).items():
        if not name.startswith("_") and inspect.isclass(obj):
            expected.setdefault(name, obj)
missing = sorted(set(expected) - set(groovebox.COMPONENT_CLASS_REGISTRY))
assert not missing, f"Unregistered usable classes: {missing}"
assert len(groovebox.COMPONENT_CLASS_REGISTRY) >= len(expected)
print(f"PASS: {len(expected)} usable application classes are registered and lazily reachable")

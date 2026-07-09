import importlib.util, os, sys

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

def _load_nodes():
    current_dir = os.path.dirname(__file__)
    sys.path.insert(0, current_dir)
    for f in sorted(os.listdir(current_dir)):
        if f == "__init__.py" or not f.endswith(".py"):
            continue
        name = f[:-3]
        spec = importlib.util.spec_from_file_location(name, os.path.join(current_dir, f))
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if hasattr(mod, "NODE_CLASS_MAPPINGS"):
                NODE_CLASS_MAPPINGS.update(mod.NODE_CLASS_MAPPINGS)
            if hasattr(mod, "NODE_DISPLAY_NAME_MAPPINGS"):
                NODE_DISPLAY_NAME_MAPPINGS.update(mod.NODE_DISPLAY_NAME_MAPPINGS)

_load_nodes()

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]

import importlib.util as _ilu
import os as _os

_spec = _ilu.spec_from_file_location(
    "anonymizer._core",
    _os.path.join(_os.path.dirname(__file__), "anonymizer.py"),
)
_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

Anonymizer = _mod.Anonymizer

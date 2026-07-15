"""Provide robosuite's optional local macro module without editing site-packages.

Upstream robosuite 1.4.0 imports ``robosuite.macros_private`` only to detect
whether local settings were initialized.  Its packaged fallback opens a shared
``/tmp/robosuite.log`` at import time.  Registering the optional module here
keeps the isolated uv environment immutable and preserves upstream macro
defaults.
"""

from __future__ import annotations

import sys
import types


private_macros = types.ModuleType("robosuite.macros_private")
private_macros.CACHE_NUMBA = True
private_macros.CONSOLE_LOGGING_LEVEL = "WARN"
private_macros.FILE_LOGGING_LEVEL = "DEBUG"
private_macros.MUJOCO_GPU_RENDERING = True
sys.modules[private_macros.__name__] = private_macros

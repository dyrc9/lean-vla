"""Bind the outer ``libero`` package to the frozen LIBERO-Safety checkout.

LIBERO-Safety vendors its Python sources under ``libero/libero`` but does not
provide the outer ``libero/__init__.py`` used by the standard editable LIBERO
installation.  A regular package installed by OpenPI therefore wins over the
namespace directory and silently selects the wrong benchmark registry.  This
small overlay supplies only the outer package and points submodule discovery at
the frozen LIBERO-Safety tree; it does not copy or alter benchmark code.
"""

from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[3]
__path__ = [str(_REPO_ROOT / "external" / "LIBERO-Safety" / "libero")]


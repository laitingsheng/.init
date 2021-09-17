import platform

from . import _mains


def _main():
    _m = getattr(_mains, f"_{platform.system().lower()}_main", None)
    if _m:
        _m()
    else:
        raise RuntimeError(f"Unsupported platform {platform.system()}")

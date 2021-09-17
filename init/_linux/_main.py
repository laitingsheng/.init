import os
import sys

import lsb_release

from . import _mains


def _main():
    if os.getuid() != 0:
        raise RuntimeError("Initialisation requires root privilige")

    distinfo = lsb_release.get_distro_information()

    _m = getattr(_mains, f"_{distinfo['ID'].lower()}_main", None)

    if _m:
        _m()
    else:
        raise RuntimeError(f"Unsupported Linux distribution {distinfo['DESCRIPTION']}")

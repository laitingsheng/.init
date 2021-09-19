import json

from ._classes import _Initialiser


def _main():
    with open("config.ubuntu.json", "r", encoding="utf-8") as f:
        config = json.load(f)

    _Initialiser(config).run()

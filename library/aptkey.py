#!/usr/bin/python3
# -*- coding: utf-8 -*-

import hashlib
import http
import os
import shutil
import zlib
from pathlib import Path
from typing import final

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.urls import fetch_url


@final
class BinaryFingerprint:
    __slots__ = ("_crc32", "_length", "_sha3_512", "_sha512")

    def __init__(self, data: bytes) -> None:
        self._length = len(data)
        self._crc32 = f"{zlib.crc32(data):08X}"
        self._sha512 = hashlib.sha512(data, usedforsecurity=False).hexdigest()
        self._sha3_512 = hashlib.sha3_512(data, usedforsecurity=False).hexdigest()

    @property
    def lines(self) -> list[str]:
        return [
            f"length : {self._length}\n",
            f"crc32 : {self._crc32}\n",
            f"sha512 : {self._sha512}\n",
            f"sha3_512 : {self._sha3_512}\n",
        ]


@final
class APTKey:
    __slots__ = ("_after", "_aptdir", "_before", "_fsgroup", "_fsowner", "_module")

    def __init__(self, module: AnsibleModule, aptdir: Path, fsowner: str, fsgroup: str) -> None:
        self._module = module
        self._aptdir = aptdir
        self._fsowner = fsowner
        self._fsgroup = fsgroup
        self._before: dict[Path, bytes] = {}
        self._after: dict[Path, bytes] = {}

    def diff(self) -> tuple[bool, dict[str, str]]:
        return self._before != self._after, {
            "before": self._format(self._before),
            "before_header": "keyrings",
            "after": self._format(self._after),
            "after_header": "keyrings",
        }

    def flush(self) -> None:
        if self._module.check_mode:
            return

        for path, data in self._after.items():
            if data:
                path.write_bytes(data)
                path.chmod(0o644)
                shutil.chown(path, self._fsowner, self._fsgroup)

    def populate(self) -> None:
        keyrings_dir = self._aptdir / "keyrings"
        keyserver: str = self._module.params["keyserver"]
        keys: list[dict[str, str]] = self._module.params["keys"] or []

        for entry in keys:
            name = entry["name"]
            keypath = entry["path"]
            if keypath is None:
                keypath = str(keyrings_dir / ".".join((name, entry["suffix"])))

            keyurl = entry["url"]
            if keyurl is None:
                keyid = entry["id"]
                if keyid is None:
                    continue
                keyurl = f"{keyserver}/pks/lookup?op=get&search=0x{keyid}"

            dest = Path(keypath)
            resp, info = fetch_url(self._module, keyurl)
            if info["status"] != http.HTTPStatus.OK:
                self._module.fail_json(**info)

            self._after[dest] = resp.read()

    def prepare(self) -> None:
        trusted_gpg = self._aptdir / "trusted.gpg"
        if trusted_gpg.exists():
            self._before[trusted_gpg] = trusted_gpg.read_bytes()
            self._after[trusted_gpg] = b""
            if not self._module.check_mode:
                trusted_gpg.unlink()

        self._prepare_directory(self._aptdir / "trusted.gpg.d")
        self._prepare_directory(self._aptdir / "keyrings")

    def _format(self, state: dict[Path, bytes]) -> str:
        return "".join(
            f"[{path}] {line}" for path, data in state.items() if data for line in BinaryFingerprint(data).lines
        )

    def _prepare_directory(self, directory: Path) -> None:
        if directory.exists():
            for dirpath, dirnames, filenames in os.walk(directory, topdown=False):
                base = Path(dirpath)
                for filename in sorted(filenames):
                    path = base / filename
                    self._before[path] = path.read_bytes()
                    self._after[path] = b""
                    if not self._module.check_mode:
                        path.unlink()
                if not self._module.check_mode:
                    for dirname in sorted(dirnames):
                        (base / dirname).rmdir()
            if not self._module.check_mode:
                directory.chmod(0o755)
        elif not self._module.check_mode:
            directory.mkdir(mode=0o755)

        if not self._module.check_mode:
            shutil.chown(directory, self._fsowner, self._fsgroup)


def _run_module() -> None:
    module = AnsibleModule(
        argument_spec={
            "keys": {
                "type": "list",
                "elements": "dict",
                "default": [],
                "options": {
                    "name": {
                        "type": "str",
                        "required": True,
                    },
                    "url": {
                        "type": "str",
                    },
                    "id": {
                        "type": "str",
                    },
                    "path": {
                        "type": "str",
                    },
                    "suffix": {
                        "type": "str",
                        "default": "asc",
                    },
                },
            },
            "keyserver": {
                "type": "str",
                "default": "https://keyserver.ubuntu.com",
            },
        },
        supports_check_mode=True,
    )

    apt_key = APTKey(module, Path("/etc/apt"), "root", "root")
    apt_key.prepare()
    apt_key.populate()
    apt_key.flush()

    changed, diff = apt_key.diff()
    module.exit_json(changed=changed, diff=diff)


if __name__ == "__main__":
    _run_module()

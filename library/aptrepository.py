#!/usr/bin/python3
# -*- coding: utf-8 -*-

import os
import shutil
from pathlib import Path
from typing import final

import apt
from ansible.module_utils.basic import AnsibleModule


@final
class APTRepository:
    __slots__ = ("_after", "_aptdir", "_before", "_fsgroup", "_fsowner", "_module")

    def __init__(self, module: AnsibleModule, aptdir: Path, fsowner: str, fsgroup: str) -> None:
        self._module = module
        self._aptdir = aptdir
        self._fsowner = fsowner
        self._fsgroup = fsgroup
        self._before: dict[Path, list[str]] = {}
        self._after: dict[Path, list[str]] = {}

    def diff(self) -> tuple[bool, dict[str, str]]:
        return self._before != self._after, {
            "before": self._format(self._before),
            "before_header": "repositories",
            "after": self._format(self._after),
            "after_header": "repositories",
        }

    def flush(self) -> None:
        if self._module.check_mode:
            return

        for path, lines in self._after.items():
            if lines:
                path.write_text("".join(lines), encoding="utf-8")
                path.chmod(0o644)
                shutil.chown(path, self._fsowner, self._fsgroup)

    def populate(self) -> None:
        keyrings_dir = self._aptdir / "keyrings"
        sources_list_d = self._aptdir / "sources.list.d"
        repos: list[dict] = self._module.params["repositories"] or []

        for entry in repos:
            name: str = entry["name"]
            url: str = entry["url"]
            keypath: str | None = entry["keypath"]
            if keypath is None:
                keypath = str(keyrings_dir / ".".join((entry["keyring"] or name, entry["keyring_suffix"])))
            dest = sources_list_d / f"{name}.list"

            components = "".join(f" {c}" for c in entry["components"])
            self._after.setdefault(dest, []).extend(
                f"deb [signed-by={keypath}] {url} {dist}{components}\n" for dist in entry["distributions"]
            )

    def prepare(self) -> None:
        sources_list = self._aptdir / "sources.list"
        if sources_list.exists():
            self._before[sources_list] = sources_list.read_text(encoding="utf-8").splitlines(keepends=True)
            self._after[sources_list] = []
            if not self._module.check_mode:
                sources_list.unlink()

        self._prepare_directory(self._aptdir / "sources.list.d")

    def _format(self, state: dict[Path, list[str]]) -> str:
        return "".join(f"[{path}:{i}] {line}" for path, lines in state.items() for i, line in enumerate(lines, 1))

    def _prepare_directory(self, directory: Path) -> None:
        if directory.exists():
            for dirpath, dirnames, filenames in os.walk(directory, topdown=False):
                base = Path(dirpath)
                for filename in sorted(filenames):
                    path = base / filename
                    self._before[path] = path.read_text(encoding="utf-8").splitlines(keepends=True)
                    self._after[path] = []
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
            "repositories": {
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
                        "required": True,
                    },
                    "distributions": {
                        "type": "list",
                        "elements": "str",
                        "required": True,
                    },
                    "components": {
                        "type": "list",
                        "elements": "str",
                        "default": [],
                    },
                    "keypath": {
                        "type": "str",
                    },
                    "keyring": {
                        "type": "str",
                    },
                    "keyring_suffix": {
                        "type": "str",
                        "default": "asc",
                    },
                },
            },
            "update_cache": {
                "type": "bool",
                "default": False,
            },
        },
        supports_check_mode=True,
    )

    repo = APTRepository(module, Path("/etc/apt"), "root", "root")
    repo.prepare()
    repo.populate()
    repo.flush()

    changed, diff = repo.diff()

    if module.params["update_cache"] and not module.check_mode:
        with apt.Cache() as cache:
            cache.update()

    module.exit_json(changed=changed, diff=diff)


if __name__ == "__main__":
    _run_module()

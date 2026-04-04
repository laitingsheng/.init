#!/usr/bin/python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import fnmatch
import re
from typing import cast, final

import apt
import apt_pkg
from ansible.module_utils.basic import AnsibleModule


@final
class APTInstall:
    __slots__ = (
        "_cache",
        "_changed",
        "_manual_after",
        "_manual_before",
        "_module",
        "_purge_regex",
        "_version_after",
        "_version_before",
    )

    _cache: apt.Cache
    _changed: bool
    _manual_after: set[str]
    _manual_before: set[str]
    _module: AnsibleModule
    _purge_regex: re.Pattern[str] | None
    _version_after: dict[str, str]
    _version_before: dict[str, str]

    def __init__(self, module: AnsibleModule) -> None:
        self._cache = cast(apt.Cache, None)
        self._changed = False
        self._manual_after = set()
        self._manual_before = set()
        self._module = module
        patterns: list[str] = module.params["purge_patterns"]
        self._purge_regex = re.compile("|".join(f"({fnmatch.translate(p)})" for p in patterns)) if patterns else None
        self._version_after = {}
        self._version_before = {}

    def __enter__(self) -> APTInstall:
        self._cache = apt.Cache().__enter__()
        return self

    def __exit__(self, *args: object, **kwargs: object) -> None:
        self._cache.__exit__(*args, **kwargs)

    def commit(self) -> None:
        self._cache.commit()

    def diff(self) -> tuple[bool, dict[str, str]]:
        return self._changed, {
            "before": self._format(self._version_before, self._manual_before),
            "before_header": "package states",
            "after": self._format(self._version_after, self._manual_after),
            "after_header": "package states",
        }

    def mark(self) -> None:
        self._mark_purge()
        self._mark_install()
        for pkg in self._cache.get_changes():
            self._changed = True
            if pkg.marked_delete:
                self._version_after.pop(pkg.name, None)
            elif pkg.marked_upgrade:
                self._version_after[pkg.name] = pkg.candidate.version
            elif pkg.marked_install:
                self._version_after[pkg.name] = pkg.candidate.version

    def prepare(self) -> None:
        apt_pkg.config.set("APT::Install-Recommends", str(self._module.params["install_recommends"]))
        apt_pkg.config.set("APT::Install-Suggests", str(self._module.params["install_suggests"]))
        if self._module.params["update_cache"]:
            self._cache.update()
            self._cache.open()
        all_auto = self._module.params["all_auto"]
        with self._cache.actiongroup():
            for pkg in self._cache:
                if pkg.is_installed:
                    self._version_before[pkg.name] = pkg.installed.version
                    self._version_after[pkg.name] = pkg.installed.version
                    if not pkg.is_auto_installed:
                        self._manual_before.add(pkg.name)
                        if all_auto:
                            pkg.mark_auto(True)
                        else:
                            self._manual_after.add(pkg.name)

    def _format(self, versions: dict[str, str], manual: set[str]) -> str:
        return "".join("{}: {} <{}>\n".format(n, v, "manual" if n in manual else "auto") for n, v in versions.items())

    def _mark_install(self) -> None:
        unknown: list[str] = []
        with self._cache.actiongroup():
            for name in self._module.params["install"]:
                pkg = self._cache.get(name)
                if pkg:
                    self._manual_after.add(pkg.name)
                    pkg.mark_install(auto_inst=True, from_user=True)
                    pkg.mark_auto(False)
                else:
                    unknown.append(name)
        if unknown:
            self._module.warn("Unknown packages in install: " + ", ".join(unknown))

    def _mark_purge(self) -> None:
        unknown: list[str] = []
        with self._cache.actiongroup():
            if self._purge_regex:
                for pkg in self._cache:
                    if self._purge_regex.fullmatch(pkg.name):
                        self._manual_after.discard(pkg.name)
                        pkg.mark_delete(purge=True)
            for name in self._module.params["purge"]:
                pkg = self._cache.get(name)
                if pkg:
                    self._manual_after.discard(pkg.name)
                    pkg.mark_delete(purge=True)
                else:
                    unknown.append(name)
        if unknown:
            self._module.warn("Unknown packages in purge: " + ", ".join(unknown))


def _run_module() -> None:
    module = AnsibleModule(
        argument_spec={
            "install": {
                "type": "list",
                "elements": "str",
                "default": [],
            },
            "purge": {
                "type": "list",
                "elements": "str",
                "default": [],
            },
            "purge_patterns": {
                "type": "list",
                "elements": "str",
                "default": [],
            },
            "all_auto": {
                "type": "bool",
                "default": True,
            },
            "update_cache": {
                "type": "bool",
                "default": False,
            },
            "install_recommends": {
                "type": "bool",
                "default": True,
            },
            "install_suggests": {
                "type": "bool",
                "default": False,
            },
        },
        supports_check_mode=True,
    )

    with APTInstall(module) as installer:
        installer.prepare()
        installer.mark()

        changed, diff = installer.diff()

        if module.check_mode:
            module.exit_json(changed=changed, diff=diff)

        installer.commit()

    module.exit_json(changed=changed, diff=diff)


if __name__ == "__main__":
    _run_module()

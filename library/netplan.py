#!/usr/bin/python3
# -*- coding: utf-8 -*-

import shutil
from pathlib import Path
from typing import final

import yaml
from ansible.module_utils.basic import AnsibleModule


@final
class Netplan:
    __slots__ = ("_after", "_before", "_configdir", "_fsgroup", "_fsowner", "_module")

    def __init__(self, module: AnsibleModule, configdir: Path, fsowner: str, fsgroup: str) -> None:
        self._module = module
        self._configdir = configdir
        self._fsowner = fsowner
        self._fsgroup = fsgroup
        self._before: dict[Path, str] = {}
        self._after: dict[Path, str] = {}

    def diff(self) -> tuple[bool, dict[str, str]]:
        return self._before != self._after, {
            "before": self._format(self._before),
            "before_header": "netplan",
            "after": self._format(self._after),
            "after_header": "netplan",
        }

    def flush(self) -> None:
        if self._module.check_mode:
            return

        for path, content in self._after.items():
            if content:
                path.write_text(content, encoding="utf-8")
                path.chmod(0o600)
                shutil.chown(path, self._fsowner, self._fsgroup)

    def populate(self) -> None:
        ethernets: list[dict] = self._module.params["ethernets"] or []
        if not ethernets:
            return

        network: dict = {"version": 2}
        renderer: str | None = self._module.params["renderer"]
        if renderer:
            network["renderer"] = renderer

        network["ethernets"] = {}
        for nic in ethernets:
            name = nic.pop("name")
            network["ethernets"][name] = _compact(nic)

        dest = self._configdir / "00-manual.yaml"
        self._after[dest] = yaml.dump(
            {"network": network},
            default_flow_style=False,
            sort_keys=False,
        )

    def prepare(self) -> None:
        if not self._configdir.exists():
            if not self._module.check_mode:
                self._configdir.mkdir(mode=0o755)
                shutil.chown(self._configdir, self._fsowner, self._fsgroup)
            return

        for path in sorted(self._configdir.glob("*.yaml")):
            self._before[path] = path.read_text(encoding="utf-8")
            self._after[path] = ""
            if not self._module.check_mode:
                path.unlink()

    def _format(self, state: dict[Path, str]) -> str:
        return "".join(f"[{path}]\n{content}" for path, content in state.items() if content)


def _compact(obj: dict | list) -> dict | list:
    if isinstance(obj, dict):
        compacted = {}
        for k, v in obj.items():
            if v is None:
                continue
            cleaned = _compact(v)
            if isinstance(cleaned, (dict, list)) and not cleaned:
                continue
            compacted[k] = cleaned
        return compacted
    if isinstance(obj, list):
        return [_compact(item) for item in obj]
    return obj


def _run_module() -> None:
    module = AnsibleModule(
        argument_spec={
            "ethernets": {
                "type": "list",
                "elements": "dict",
                "default": [],
                "options": {
                    "name": {
                        "type": "str",
                        "required": True,
                    },
                    "dhcp4": {
                        "type": "bool",
                    },
                    "dhcp6": {
                        "type": "bool",
                    },
                    "macaddress": {
                        "type": "str",
                    },
                    "addresses": {
                        "type": "list",
                        "elements": "str",
                        "default": [],
                    },
                    "nameservers": {
                        "type": "dict",
                        "options": {
                            "addresses": {
                                "type": "list",
                                "elements": "str",
                                "default": [],
                            },
                            "search": {
                                "type": "list",
                                "elements": "str",
                                "default": [],
                            },
                        },
                    },
                    "routes": {
                        "type": "list",
                        "elements": "dict",
                        "default": [],
                        "options": {
                            "to": {
                                "type": "str",
                                "required": True,
                            },
                            "via": {
                                "type": "str",
                                "required": True,
                            },
                            "metric": {
                                "type": "int",
                            },
                        },
                    },
                },
            },
            "renderer": {
                "type": "str",
                "choices": ["networkd", "NetworkManager"],
            },
        },
        supports_check_mode=True,
    )

    plan = Netplan(module, Path("/etc/netplan"), "root", "root")
    plan.prepare()
    plan.populate()
    plan.flush()

    changed, diff = plan.diff()

    module.exit_json(changed=changed, diff=diff)


if __name__ == "__main__":
    _run_module()

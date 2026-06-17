#!/usr/bin/python3
import http
import os
from pathlib import Path
from typing import Final

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.urls import fetch_url

ARCH_MAP: Final[dict[str, str]] = {"amd64": "x86_64", "arm64": "arm64"}
OS_MAP: Final[dict[str, str]] = {"linux": "Linux", "darwin": "Darwin"}


def _default_install_base() -> Path:
    if os.geteuid() == 0:
        return Path("/usr/local/share/hadolint")
    xdg_data = os.environ.get("XDG_DATA_HOME")
    if xdg_data:
        return Path(xdg_data) / "hadolint"
    return Path.home() / ".local" / "share" / "hadolint"


def _default_bin_dir() -> Path:
    if os.geteuid() == 0:
        return Path("/usr/local/bin")
    xdg_bin = os.environ.get("XDG_BIN_HOME")
    if xdg_bin:
        return Path(xdg_bin)
    return Path.home() / ".local" / "bin"


def main() -> None:
    module = AnsibleModule(
        argument_spec={
            "install_base": {"type": "path", "default": None},
            "bin_dir": {"type": "path", "default": None},
            "version": {"type": "str", "required": True},
            "os": {"type": "str", "required": True, "choices": list(OS_MAP)},
            "arch": {"type": "str", "required": True, "choices": list(ARCH_MAP)},
            "force": {"type": "bool", "default": False},
        },
        supports_check_mode=True,
    )
    version = module.params["version"]
    os_name = OS_MAP[module.params["os"]]
    arch = ARCH_MAP[module.params["arch"]]
    force = module.params["force"]
    install_base = Path(module.params["install_base"]) if module.params["install_base"] else _default_install_base()
    bin_dir = Path(module.params["bin_dir"]) if module.params["bin_dir"] else _default_bin_dir()
    link = bin_dir / "hadolint"

    versions_dir = install_base / "versions"
    binary_path = versions_dir / version

    if not force and binary_path.is_file() and link.is_symlink() and link.resolve() == binary_path.resolve():
        module.exit_json(changed=False, msg=f"hadolint {version} already installed")

    if module.check_mode:
        module.exit_json(changed=True, msg=f"Would install hadolint {version}")

    url = f"https://github.com/hadolint/hadolint/releases/download/v{version}/hadolint-{os_name}-{arch}"
    response, info = fetch_url(module, url)
    if info["status"] != http.HTTPStatus.OK:
        module.fail_json(**info)

    install_base.mkdir(parents=True, exist_ok=True)
    install_base.chmod(0o755)
    versions_dir.mkdir(exist_ok=True)
    versions_dir.chmod(0o755)
    binary_path.write_bytes(response.read())
    binary_path.chmod(0o755)

    bin_dir.mkdir(parents=True, exist_ok=True)
    link.unlink(missing_ok=True)
    link.symlink_to(binary_path.relative_to(bin_dir, walk_up=True))

    module.exit_json(changed=True, msg=f"Installed hadolint {version}")


if __name__ == "__main__":
    main()

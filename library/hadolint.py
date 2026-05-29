#!/usr/bin/python3
import http
from pathlib import Path
from typing import Final

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.urls import fetch_url

ARCH_MAP: Final[dict[str, str]] = {"amd64": "x86_64", "arm64": "arm64"}
OS_MAP: Final[dict[str, str]] = {"linux": "Linux", "darwin": "Darwin"}


def main() -> None:
    module = AnsibleModule(
        argument_spec={
            "install_base": {"type": "path", "default": "/usr/local/hadolint"},
            "bin_dir": {"type": "path", "default": "/usr/local/bin"},
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
    install_base = Path(module.params["install_base"])
    bin_dir = Path(module.params["bin_dir"])
    link = bin_dir / "hadolint"

    version_dir = install_base / version
    binary_path = version_dir / "hadolint"

    if not force and binary_path.is_file() and link.is_symlink() and link.resolve() == binary_path.resolve():
        module.exit_json(changed=False, msg=f"hadolint {version} already installed")

    if module.check_mode:
        module.exit_json(changed=True, msg=f"Would install hadolint {version}")

    url = f"https://github.com/hadolint/hadolint/releases/download/v{version}/hadolint-{os_name}-{arch}"
    response, info = fetch_url(module, url)
    if info["status"] != http.HTTPStatus.OK:
        module.fail_json(**info)

    install_base.mkdir(exist_ok=True)
    install_base.chmod(0o755)
    version_dir.mkdir(exist_ok=True)
    version_dir.chmod(0o755)
    binary_path.write_bytes(response.read())
    binary_path.chmod(0o755)

    link.unlink(missing_ok=True)
    link.symlink_to(binary_path.relative_to(bin_dir, walk_up=True))

    module.exit_json(changed=True, msg=f"Installed hadolint {version}")


if __name__ == "__main__":
    main()

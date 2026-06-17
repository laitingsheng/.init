#!/usr/bin/python3
import http
import io
import os
import tarfile
from pathlib import Path

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.urls import fetch_url

DOWNLOAD_BASE = "https://downloads.cursor.com/lab"
BINARY_NAME = "cursor-agent"
LINK_NAMES = ("agent", "cursor-agent")


def _default_install_base() -> Path:
    if os.geteuid() == 0:
        return Path("/usr/local/share/cursor-agent")
    xdg_data = os.environ.get("XDG_DATA_HOME")
    if xdg_data:
        return Path(xdg_data) / "cursor-agent"
    return Path.home() / ".local" / "share" / "cursor-agent"


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
            "os": {"type": "str", "required": True, "choices": ["linux", "darwin"]},
            "arch": {"type": "str", "required": True, "choices": ["x64", "arm64"]},
            "force": {"type": "bool", "default": False},
        },
        supports_check_mode=True,
    )
    version = module.params["version"]
    os_name = module.params["os"]
    arch = module.params["arch"]
    force = module.params["force"]
    install_base = Path(module.params["install_base"]) if module.params["install_base"] else _default_install_base()
    bin_dir = Path(module.params["bin_dir"]) if module.params["bin_dir"] else _default_bin_dir()

    versions_dir = install_base / "versions"
    version_dir = versions_dir / version
    binary_path = version_dir / BINARY_NAME
    links = [bin_dir / name for name in LINK_NAMES]

    if (
        not force
        and binary_path.is_file()
        and all(link.is_symlink() and link.resolve() == binary_path.resolve() for link in links)
    ):
        module.exit_json(changed=False, msg=f"cursor-agent {version} already installed")

    if module.check_mode:
        module.exit_json(changed=True, msg=f"Would install cursor-agent {version}")

    archive_url = f"{DOWNLOAD_BASE}/{version}/{os_name}/{arch}/agent-cli-package.tar.gz"
    response, info = fetch_url(module, archive_url)
    if info["status"] != http.HTTPStatus.OK:
        module.fail_json(**info)

    install_base.mkdir(parents=True, exist_ok=True)
    install_base.chmod(0o755)
    versions_dir.mkdir(exist_ok=True)
    versions_dir.chmod(0o755)
    version_dir.mkdir(exist_ok=True)
    version_dir.chmod(0o755)
    with tarfile.open(fileobj=io.BytesIO(response.read())) as tar:
        members = tar.getmembers()
        for m in members:
            m.name = m.name.removeprefix("dist-package/")
        tar.extractall(version_dir, members=[m for m in members if m.name], filter="data")
    binary_path.chmod(0o755)

    bin_dir.mkdir(parents=True, exist_ok=True)
    for link in links:
        link.unlink(missing_ok=True)
        link.symlink_to(binary_path.relative_to(bin_dir, walk_up=True))

    module.exit_json(changed=True, msg=f"Installed cursor-agent {version}")


if __name__ == "__main__":
    main()

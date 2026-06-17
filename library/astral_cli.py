#!/usr/bin/python3
import http
import io
import os
import tarfile
from pathlib import Path
from typing import Final

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.urls import fetch_url

TOOL_BINARIES: Final[dict[str, list[str]]] = {
    "uv": ["uv", "uvx"],
    "ruff": ["ruff"],
    "ty": ["ty"],
}


def _default_share_dir() -> Path:
    if os.geteuid() == 0:
        return Path("/usr/local/share")
    xdg_data = os.environ.get("XDG_DATA_HOME")
    if xdg_data:
        return Path(xdg_data)
    return Path.home() / ".local" / "share"


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
            "tool": {"type": "str", "required": True, "choices": list(TOOL_BINARIES)},
            "share_dir": {"type": "path", "default": None},
            "bin_dir": {"type": "path", "default": None},
            "version": {"type": "str", "required": True},
            "arch": {"type": "str", "required": True},
            "platform": {"type": "str", "required": True},
            "os": {"type": "str", "required": True},
            "abi": {"type": "str", "required": True},
            "force": {"type": "bool", "default": False},
        },
        supports_check_mode=True,
    )
    tool = module.params["tool"]
    version = module.params["version"]
    arch = module.params["arch"]
    platform_name = module.params["platform"]
    os_name = module.params["os"]
    abi = module.params["abi"]
    force = module.params["force"]
    share_dir = Path(module.params["share_dir"]) if module.params["share_dir"] else _default_share_dir()
    bin_dir = Path(module.params["bin_dir"]) if module.params["bin_dir"] else _default_bin_dir()
    binaries = TOOL_BINARIES[tool]

    version_dir = share_dir / tool / "versions" / version
    binary_paths = [version_dir / binary for binary in binaries]
    links = [bin_dir / binary for binary in binaries]

    if not force and all(
        bp.is_file() and lk.is_symlink() and lk.resolve() == bp.resolve() for bp, lk in zip(binary_paths, links)
    ):
        module.exit_json(changed=False, msg=f"{tool} {version} already installed")

    if module.check_mode:
        module.exit_json(changed=True, msg=f"Would install {tool} {version}")

    target_triple = f"{arch}-{platform_name}-{os_name}-{abi}"
    url = f"https://github.com/astral-sh/{tool}/releases/download/{version}/{tool}-{target_triple}.tar.gz"
    response, info = fetch_url(module, url)
    if info["status"] != http.HTTPStatus.OK:
        module.fail_json(**info)

    version_dir.mkdir(parents=True, exist_ok=True)
    archive_prefix = f"{tool}-{target_triple}"
    with tarfile.open(fileobj=io.BytesIO(response.read())) as tar:
        for binary, binary_path in zip(binaries, binary_paths):
            extracted = tar.extractfile(f"{archive_prefix}/{binary}")
            if extracted is None:
                module.fail_json(msg=f"Failed to extract {archive_prefix}/{binary}")
            binary_path.write_bytes(extracted.read())
            binary_path.chmod(0o755)

    bin_dir.mkdir(parents=True, exist_ok=True)
    for link, binary_path in zip(links, binary_paths):
        link.unlink(missing_ok=True)
        link.symlink_to(binary_path.relative_to(bin_dir, walk_up=True))

    module.exit_json(changed=True, msg=f"Installed {tool} {version}")


if __name__ == "__main__":
    main()

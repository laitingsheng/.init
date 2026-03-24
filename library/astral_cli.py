#!/usr/bin/python3
import http
import io
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


def main() -> None:
    module = AnsibleModule(
        argument_spec={
            "tool": {"type": "str", "required": True, "choices": list(TOOL_BINARIES)},
            "install_base": {"type": "path", "default": "/usr/local/astral"},
            "bin_dir": {"type": "path", "default": "/usr/local/bin"},
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
    install_base = Path(module.params["install_base"])
    bin_dir = Path(module.params["bin_dir"])
    binaries = TOOL_BINARIES[tool]

    version_dir = install_base / tool / version
    binary_paths = [version_dir / binary for binary in binaries]
    links = [bin_dir / binary for binary in binaries]

    if not force and all(
        bp.is_file() and lk.is_symlink() and lk.resolve() == bp.resolve()
        for bp, lk in zip(binary_paths, links)
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

    for link, binary_path in zip(links, binary_paths):
        link.unlink(missing_ok=True)
        link.symlink_to(binary_path.relative_to(bin_dir, walk_up=True))

    module.exit_json(changed=True, msg=f"Installed {tool} {version}")


if __name__ == "__main__":
    main()

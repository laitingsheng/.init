#!/usr/bin/python3
import http
from pathlib import Path

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.urls import fetch_url

GCS_BUCKET = "https://storage.googleapis.com/claude-code-dist-86c565f3-f756-42ad-8dfa-d59b1c096819/claude-code-releases"


def _build_platform(os_name: str, arch: str) -> str:
    return f"{os_name}-{arch}"


def main() -> None:
    module = AnsibleModule(
        argument_spec={
            "install_base": {"type": "path", "default": "/usr/local/claude"},
            "bin_dir": {"type": "path", "default": "/usr/local/bin"},
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
    install_base = Path(module.params["install_base"])
    bin_dir = Path(module.params["bin_dir"])
    link = bin_dir / "claude"
    platform = _build_platform(os_name, arch)

    version_dir = install_base / version
    binary_path = version_dir / "claude"
    rel_target = binary_path.relative_to(bin_dir, walk_up=True)

    if not force and binary_path.is_file() and link.is_symlink() and link.resolve() == binary_path.resolve():
        module.exit_json(changed=False, msg=f"claude {version} already installed")

    if module.check_mode:
        module.exit_json(
            changed=True,
            msg=f"Would install claude {version}",
        )

    binary_url = f"{GCS_BUCKET}/{version}/{platform}/claude"
    response, info = fetch_url(module, binary_url)
    if info["status"] != http.HTTPStatus.OK:
        module.fail_json(**info)

    version_dir.mkdir(parents=True, exist_ok=True)
    binary_path.write_bytes(response.read())
    binary_path.chmod(0o755)

    link.unlink(missing_ok=True)
    link.symlink_to(rel_target)

    module.exit_json(changed=True, msg=f"Installed claude {version}")


if __name__ == "__main__":
    main()

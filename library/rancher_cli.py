#!/usr/bin/python3
import http
import io
import tarfile
from pathlib import Path

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.urls import fetch_url


def main() -> None:
    module = AnsibleModule(
        argument_spec={
            "install_base": {"type": "path", "default": "/usr/local/rancher"},
            "bin_dir": {"type": "path", "default": "/usr/local/bin"},
            "version": {"type": "str", "required": True},
            "os": {"type": "str", "required": True, "choices": ["linux", "darwin"]},
            "arch": {"type": "str", "required": True, "choices": ["amd64", "arm64"]},
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
    link = bin_dir / "rancher"

    version_dir = install_base / version
    binary_path = version_dir / "rancher"

    if not force and binary_path.is_file() and link.is_symlink() and link.resolve() == binary_path.resolve():
        module.exit_json(changed=False, msg=f"rancher {version} already installed")

    if module.check_mode:
        module.exit_json(changed=True, msg=f"Would install rancher {version}")

    url = f"https://github.com/rancher/cli/releases/download/v{version}/rancher-{os_name}-{arch}-v{version}.tar.gz"
    response, info = fetch_url(module, url)
    if info["status"] != http.HTTPStatus.OK:
        module.fail_json(**info)

    install_base.mkdir(exist_ok=True)
    install_base.chmod(0o755)
    version_dir.mkdir(exist_ok=True)
    version_dir.chmod(0o755)
    member_name = f"./rancher-v{version}/rancher"
    with tarfile.open(fileobj=io.BytesIO(response.read())) as tar:
        extracted = tar.extractfile(member_name)
        if extracted is None:
            module.fail_json(msg=f"Failed to extract {member_name}")
        binary_path.write_bytes(extracted.read())
    binary_path.chmod(0o755)

    link.unlink(missing_ok=True)
    link.symlink_to(binary_path.relative_to(bin_dir, walk_up=True))

    module.exit_json(changed=True, msg=f"Installed rancher {version}")


if __name__ == "__main__":
    main()

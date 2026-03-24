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
            "install_base": {"type": "path", "default": "/usr/local/glab"},
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
    link = bin_dir / "glab"

    version_dir = install_base / version
    binary_path = version_dir / "glab"

    if not force and binary_path.is_file() and link.is_symlink() and link.resolve() == binary_path.resolve():
        module.exit_json(changed=False, msg=f"glab {version} already installed")

    if module.check_mode:
        module.exit_json(changed=True, msg=f"Would install glab {version}")

    url = f"https://gitlab.com/gitlab-org/cli/-/releases/v{version}/downloads/glab_{version}_{os_name}_{arch}.tar.gz"
    response, info = fetch_url(module, url)
    if info["status"] != http.HTTPStatus.OK:
        module.fail_json(**info)

    version_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(response.read())) as tar:
        extracted = tar.extractfile("bin/glab")
        if extracted is None:
            module.fail_json(msg="Failed to extract bin/glab")
        binary_path.write_bytes(extracted.read())
    binary_path.chmod(0o755)

    link.unlink(missing_ok=True)
    link.symlink_to(binary_path.relative_to(bin_dir, walk_up=True))

    module.exit_json(changed=True, msg=f"Installed glab {version}")


if __name__ == "__main__":
    main()

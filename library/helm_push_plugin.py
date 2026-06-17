#!/usr/bin/python3
import http
import io
import os
import shutil
import tarfile
from pathlib import Path

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.urls import fetch_url

PLUGIN_NAME = "cm-push"
STORE_NAME = "helm-cm-push"


def _default_share_dir() -> Path:
    if os.geteuid() == 0:
        return Path("/usr/local/share")
    xdg_data = os.environ.get("XDG_DATA_HOME")
    if xdg_data:
        return Path(xdg_data)
    return Path.home() / ".local" / "share"


def _default_prefix() -> Path:
    return _default_share_dir() / "helm" / "plugins"


def main() -> None:
    module = AnsibleModule(
        argument_spec={
            "share_dir": {"type": "path", "default": None},
            "prefix": {"type": "path", "default": None},
            "version": {"type": "str", "required": True},
            "os": {"type": "str", "required": True},
            "arch": {"type": "str", "required": True},
            "force": {"type": "bool", "default": False},
        },
        supports_check_mode=True,
    )
    version = module.params["version"]
    os_name = module.params["os"]
    arch = module.params["arch"]
    force = module.params["force"]
    share_dir = Path(module.params["share_dir"]).expanduser() if module.params["share_dir"] else _default_share_dir()
    prefix = Path(module.params["prefix"]).expanduser() if module.params["prefix"] else _default_prefix()

    install_base = share_dir / STORE_NAME
    versions_dir = install_base / "versions"
    version_dir = versions_dir / version
    plugin_yaml = version_dir / "plugin.yaml"
    binary_path = version_dir / "bin" / "helm-cm-push"
    link = prefix / PLUGIN_NAME

    if (
        not force
        and plugin_yaml.is_file()
        and binary_path.is_file()
        and link.is_symlink()
        and link.resolve() == version_dir.resolve()
    ):
        module.exit_json(changed=False, msg=f"helm-push {version} already installed")

    url = (
        f"https://github.com/chartmuseum/helm-push/releases/download/v{version}"
        f"/helm-push_{version}_{os_name}_{arch}.tar.gz"
    )
    if module.check_mode:
        module.exit_json(changed=True, msg=f"Would install helm-push {version} to {version_dir}")

    response, info = fetch_url(module, url)
    if info["status"] != http.HTTPStatus.OK:
        module.fail_json(msg=f"Failed to download {url}: {info['msg']}")

    install_base.mkdir(parents=True, exist_ok=True)
    install_base.chmod(0o755)
    versions_dir.mkdir(exist_ok=True)
    versions_dir.chmod(0o755)
    version_dir.mkdir(exist_ok=True)
    version_dir.chmod(0o755)
    with tarfile.open(fileobj=io.BytesIO(response.read()), mode="r:gz") as tar:
        tar.extractall(version_dir, filter="data")
    binary_path.chmod(0o755)

    prefix.mkdir(parents=True, exist_ok=True)
    if link.is_symlink():
        link.unlink()
    elif link.exists():
        shutil.rmtree(link)
    link.symlink_to(version_dir.relative_to(prefix, walk_up=True))

    module.exit_json(changed=True, msg=f"Installed helm-push {version} to {version_dir}")


if __name__ == "__main__":
    main()

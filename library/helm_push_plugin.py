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
            "prefix": {"type": "path", "required": True},
            "version": {"type": "str", "required": True},
            "os": {"type": "str", "required": True},
            "arch": {"type": "str", "required": True},
        },
        supports_check_mode=True,
    )
    version = module.params["version"]
    os_name = module.params["os"]
    arch = module.params["arch"]
    prefix = Path(module.params["prefix"]).expanduser()
    target = prefix / "cm-push"
    url = (
        f"https://github.com/chartmuseum/helm-push/releases/download/v{version}"
        f"/helm-push_{version}_{os_name}_{arch}.tar.gz"
    )
    if module.check_mode:
        response, info = fetch_url(module, url, method="HEAD")
        if info["status"] != http.HTTPStatus.OK:
            module.fail_json(msg=f"Failed to check URL {url}: {info['msg']}")
        content_length = int(info.get("content-length", 0))
        module.exit_json(
            changed=True,
            msg=f"Would download {content_length} bytes and install helm-push {version} to {target}",
        )
    try:
        response, info = fetch_url(module, url)
        if info["status"] != http.HTTPStatus.OK:
            module.fail_json(msg=f"Failed to download {url}: {info['msg']}")
        data = response.read()
        (target / "bin").mkdir(parents=True, exist_ok=True)
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
            plugin_yaml = tar.extractfile("plugin.yaml")
            if plugin_yaml is None:
                module.fail_json(msg="Failed to extract plugin.yaml")
            (target / "plugin.yaml").write_bytes(plugin_yaml.read())
            binary = tar.extractfile("bin/helm-cm-push")
            if binary is None:
                module.fail_json(msg="Failed to extract bin/helm-cm-push")
            binary_path = target / "bin" / "helm-cm-push"
            binary_path.write_bytes(binary.read())
            binary_path.chmod(0o755)
        module.exit_json(changed=True, msg=f"Installed helm-push {version} to {target}")
    except Exception as e:
        module.fail_json(msg=f"Failed to install helm-push: {e}")


if __name__ == "__main__":
    main()

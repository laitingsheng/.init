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
    prefix = Path(module.params["prefix"])
    target = prefix / "rancher"
    url = f"https://github.com/rancher/cli/releases/download/v{version}/rancher-{os_name}-{arch}-v{version}.tar.gz"
    if module.check_mode:
        response, info = fetch_url(module, url, method="HEAD")
        if info["status"] != http.HTTPStatus.OK:
            module.fail_json(msg=f"Failed to check URL {url}: {info['msg']}")
        content_length = int(info.get("content-length", 0))
        module.exit_json(
            changed=True,
            msg=f"Would download {content_length} bytes and install rancher {version} to {target}",
        )
    try:
        response, info = fetch_url(module, url)
        if info["status"] != http.HTTPStatus.OK:
            module.fail_json(msg=f"Failed to download {url}: {info['msg']}")
        data = response.read()
        member_name = f"./rancher-v{version}/rancher"
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
            member = tar.getmember(member_name)
            extracted = tar.extractfile(member)
            if extracted is None:
                module.fail_json(msg=f"Failed to extract {member_name}")
            with target.open("wb") as f:
                f.write(extracted.read())
            target.chmod(0o755)
        module.exit_json(changed=True, msg=f"Installed rancher {version} to {target}")
    except Exception as e:
        module.fail_json(msg=f"Failed to install rancher: {e}")


if __name__ == "__main__":
    main()

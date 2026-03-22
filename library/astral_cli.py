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
            "tool": {
                "type": "str",
                "required": True,
                "choices": list(TOOL_BINARIES),
            },
            "prefix": {"type": "path", "default": "/usr/local/bin"},
            "version": {"type": "str", "required": True},
            "arch": {"type": "str", "required": True},
            "platform": {"type": "str", "required": True},
            "os": {"type": "str", "required": True},
            "abi": {"type": "str", "required": True},
        },
        supports_check_mode=True,
    )
    tool = module.params["tool"]
    version = module.params["version"]
    arch = module.params["arch"]
    platform_name = module.params["platform"]
    os_name = module.params["os"]
    abi = module.params["abi"]
    prefix = Path(module.params["prefix"]).expanduser()
    target_triple = f"{arch}-{platform_name}-{os_name}-{abi}"
    url = f"https://github.com/astral-sh/{tool}/releases/download/{version}/{tool}-{target_triple}.tar.gz"
    if module.check_mode:
        response, info = fetch_url(module, url, method="HEAD")
        if info["status"] != http.HTTPStatus.OK:
            module.fail_json(msg=f"Failed to check URL {url}: {info['msg']}")
        content_length = int(info.get("content-length", 0))
        module.exit_json(
            changed=True,
            msg=f"Would download {content_length} bytes and install {tool} {version} to {prefix}",
        )
    try:
        response, info = fetch_url(module, url)
        if info["status"] != http.HTTPStatus.OK:
            module.fail_json(msg=f"Failed to download {url}: {info['msg']}")
        data = response.read()
        binaries = TOOL_BINARIES[tool]
        archive_prefix = f"{tool}-{target_triple}"
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
            for binary in binaries:
                member_path = f"{archive_prefix}/{binary}"
                extracted = tar.extractfile(member_path)
                if extracted is None:
                    module.fail_json(msg=f"Failed to extract {member_path}")
                target = prefix / binary
                with target.open("wb") as f:
                    f.write(extracted.read())
                target.chmod(0o755)
        module.exit_json(
            changed=True,
            msg=f"Installed {tool} {version} to {prefix}: {', '.join(binaries)}",
        )
    except Exception as e:
        module.fail_json(msg=f"Failed to install {tool}: {e}")


if __name__ == "__main__":
    main()

import fnmatch
import math
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict
from urllib import request

import apt
import apt_pkg
import lsb_release
from aptsources.sourceslist import SourcesList

_DIST_INFO = lsb_release.get_distro_information()


def _reset_file(file: Path):
    file.unlink(True)
    file.touch(0o644, False)
    os.chown(file, 0, 0)


def _reset_folder(folder: Path):
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(0o755, False, False)
    os.chown(folder, 0, 0)


class _Variables:
    __slots__ = "autoremove", "codename", "desktop", "max_download_size", "max_install_size", "prune", "release", "upgrade", "wsl"

    def __init__(self, variables: Dict[str, Any]):
        self.codename = _DIST_INFO["CODENAME"]
        self.release = _DIST_INFO["RELEASE"]
        self.desktop = False
        self.wsl = True
        self.prune = True
        self.autoremove = True
        self.upgrade = True
        self.max_download_size = math.inf
        self.max_install_size = math.inf

        for k, v in variables.items():
            setattr(self, k, v)

        if self.wsl and not fnmatch.fnmatchcase(platform.release(), "*-microsoft-standard-WSL2"):
            self.wsl = False

        if self.wsl:
            self.desktop = False

        if self.max_download_size is None:
            self.max_download_size = math.inf

        if self.max_install_size is None:
            self.max_install_size = math.inf


class _Entries:
    __slots__ = "architectures", "components", "dists", "uri"

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class _APTConfig:
    __slots__ = "_keys", "_packages", "_preferences", "_preferences_d", "_sources", "_sources_list_d", "_trusted_gpg_d", "_variables"

    def __init__(self, apt_config: Dict[str, Any], variables: _Variables):
        self._sources_list_d = Path("/etc/apt/sources.list.d")
        self._preferences_d = Path("/etc/apt/preferences.d")
        self._trusted_gpg_d = Path("/etc/apt/trusted.gpg.d")

        self._variables = variables

        sources = self._sources = {}
        keys = self._keys = {}
        packages = self._packages = set()

        for source_name, source_config in apt_config.items():
            output = source_config.get("output", source_name)
            entries = sources[output] = sources.get(output, {})
            entries[source_name] = _Entries(
                uri=self._normalise_uri(source_config["uri"]),
                dists=source_config["dists"] if "dists" in source_config else [
                    f"{self._variables.codename}{suffix}"
                    for suffix in source_config["dist_suffices"]
                ] if "dist_suffices" in source_config else [self._variables.codename],
                components=source_config.get("components", ["main"]),
                architectures=source_config.get("architectures", [])
            )

            if "key" in source_config:
                if source_name in keys:
                    raise RuntimeError(f"duplicate key for {source_name}")
                else:
                    keys[source_name] = self._normalise_uri(source_config["key"])

            packages.update(source_config.get("packages", []))

        if self._variables.wsl:
            packages.add("ubuntu-wsl")
            packages.add("wsl")

            if "cuda" in apt_config:
                sources["nvidia"]["cuda"].uri = "https://mirrors.aliyun.com/nvidia-cuda/wsl-ubuntu/x86_64"
                keys["cuda"] = "https://mirrors.aliyun.com/nvidia-cuda/wsl-ubuntu/x86_64/7fa2af80.pub"

    def _normalise_uri(self, uri_config) -> str:
        if isinstance(uri_config, str):
            return uri_config
        if isinstance(uri_config, dict):
            format_args = {}
            for k, v in uri_config["format_args"].items():
                if "value" in v:
                    format_args[k] = v["value"]
                else:
                    variable = getattr(self._variables, v["variable"])
                    if "method" in v:
                        func = v["method"]
                        variable = getattr(variable, func["name"])(*func.get("args", []), **func.get("kwargs", {}))
                    format_args[k] = variable
            return uri_config["template"].format(**format_args)
        else:
            raise TypeError(f"{uri_config} is neither a string nor a recognised config")

    def autoremove(self):
        if self._variables.autoremove:
            cache = apt_pkg.Cache()
            dep = apt_pkg.DepCache(cache)
            with apt_pkg.ActionGroup(dep):
                for package in cache.packages:
                    if dep.is_garbage(package):
                        dep.mark_delete(package, True)

                dep.commit(apt.progress.base.AcquireProgress(), apt.progress.base.InstallProgress())

    def init(self):
        apt_pkg.init()
        # sources_list = apt_pkg.SourceList()
        # sources_list.read_main_list()
        # apt_pkg.Cache().update(apt.progress.base.AcquireProgress(), sources_list)

    def install(self):
        cache = apt_pkg.Cache()
        dep = apt_pkg.DepCache(cache)
        with apt_pkg.ActionGroup(dep):
            for package in cache.packages:
                if package.name in self._packages:
                    dep.mark_install(package, True, True)
                    dep.mark_auto(package, False)
                    self._packages.remove(package.name)
                else:
                    dep.mark_auto(package, True)

            dep.commit(apt.progress.base.AcquireProgress(), apt.progress.base.InstallProgress())

        if self._packages:
            print("The following packages are missing in the current APT repositories:", file=sys.stderr)
            for package in self._packages:
                print(f"    * {package}", file=sys.stderr)

    def prune(self):
        if self._variables.prune:
            _reset_folder(self._sources_list_d)
            _reset_folder(self._preferences_d)
            _reset_folder(self._trusted_gpg_d)

            _reset_file(Path("/etc/apt/sources.list"))
            _reset_file(Path("/etc/apt/preferences"))
            _reset_file(Path("/etc/apt/trusted.gpg"))
            Path("/etc/apt/trusted.gpg~").unlink(True)

    def save_keys(self):
        for k, v in self._keys.items():
            with request.urlopen(v) as f:
                p = subprocess.run(["gpg", "--dearmor"], input=f.read(), capture_output=True)

            if p.returncode:
                raise RuntimeError(f"failed to fetch key for {k}\n{p.stderr.decode('utf-8')}")

            with open(self._trusted_gpg_d / f"{k}.gpg", "wb") as f:
                f.write(p.stdout)

    def save_sources(self):
        sources_list = SourcesList()
        for k, entries in self._sources.items():
            file = self._sources_list_d / f"{k}.list"
            for entry in entries.values():
                for dist in entry.dists:
                    sources_list.add(
                        "deb",
                        entry.uri,
                        dist,
                        entry.components,
                        file=file,
                        architectures=entry.architectures
                    )
        sources_list.save()

    def upgrade(self):
        if self._variables.upgrade:
            cache = apt_pkg.Cache()
            dep = apt_pkg.DepCache(cache)
            with apt_pkg.ActionGroup(dep):
                dep.upgrade(True)
                dep.commit(apt.progress.base.AcquireProgress(), apt.progress.base.InstallProgress())


class _Initialiser:
    __slots__ = "_apt", "_variables"

    def __init__(self, config: Dict[str, Any]):
        self._variables = _Variables(config.get("variables", {}))
        self._apt = _APTConfig(config["apt"], self._variables)

    def prune(self):
        self._apt.prune()

    def run_apt(self):
        self._apt.init()
        self._apt.install()
        self._apt.autoremove()
        self._apt.upgrade()

    def save(self):
        self._apt.save_sources()
        self._apt.save_keys()

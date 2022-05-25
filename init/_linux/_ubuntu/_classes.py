import configparser
import fnmatch
import math
import operator
import os
import platform
import shutil
import subprocess
import sys
import urllib.request
from abc import ABCMeta
from multiprocessing import Pool
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List

import lsb_release
from apt import Cache, Package
from aptsources.sourceslist import SourceEntry, SourcesList

_APT_PREFERENCES_DIR = Path("/etc/apt/preferences.d")
_APT_SOURCES_LIST_DIR = Path("/etc/apt/sources.list.d")
_APT_TRUSTED_GPG_DIR = Path("/etc/apt/trusted.gpg.d")


def _exponentials(space: int) -> Iterator[int]:
    start = 1
    while True:
        yield start
        start *= space


class _SimpleData(metaclass=ABCMeta):
    __slots__ = ()

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, f"_{k}", v)

    def __repr__(self) -> str:
        attributes = ", ".join(f"{attr}={getattr(self, attr)}" for attr in self._attributes)
        return f"{self.__class__.__name__}({attributes})"

    @property
    def _attributes(self) -> Iterable[str]:
        return self.__slots__


class _APTKeyFile(_SimpleData):
    __slots__ = "_name", "_uri"

    def save(self):
        with urllib.request.urlopen(self._uri) as f:
            p = subprocess.run(["gpg", "--dearmor"], input=f.read(), capture_output=True)

        if p.returncode:
            raise RuntimeError(f"failed to fetch key for {self._name}\n{p.stderr.decode('utf-8')}")

        key_path = _APT_TRUSTED_GPG_DIR / f"{self._name}.gpg"
        with open(key_path, "wb") as f:
            f.write(p.stdout)
        os.chown(key_path, 0, 0)
        os.chmod(key_path, 0o644)


class _APTRemoteRepoFile(_SimpleData):
    __slots__ = "_name", "_url"

    def write_to(self, source_list: SourcesList):
        file = _APT_SOURCES_LIST_DIR / f"{self._name}.list"
        with urllib.request.urlopen(self._url) as f:
            source_list.list.extend(
                SourceEntry(line, file)
                for line in f.read().decode("utf-8").splitlines()
            )


class _APTRepoFile(_SimpleData):
    __slots__ = "_architectures", "_components", "_dists", "_name", "_uri"

    def write_to(self, sources_list: SourcesList):
        file = _APT_SOURCES_LIST_DIR / f"{self._name}.list"
        for dist in self._dists:
            sources_list.add("deb", self._uri, dist, self._components, file=file, architectures=self._architectures)


class _WSLConfigFile(_SimpleData):
    __slots__ = (
        "_automount_enabled",
        "_automount_mountFsTab",
        "_automount_options",
        "_automount_root",
        "_network_generateHosts",
        "_network_generateResolvConf",
        "_interop_enabled",
        "_interop_appendWindowsPath",
        "_user_default",
        "_wsl2_guiapplications"
    )

    _DEFAULT_USER = os.environ.get("SUDO_USER", os.environ["USER"])

    def __init__(self, **kwargs):
        self._automount_enabled = True
        self._automount_mountFsTab = True
        self._automount_options = "metadata,umask=0022,fmask=0022,dmask=0022"
        self._automount_root = "/mnt/"
        self._network_generateHosts = True
        self._network_generateResolvConf = True
        self._interop_enabled = True
        self._interop_appendWindowsPath = False
        self._user_default = None
        self._wsl2_guiapplications = True

        for section_name, section in kwargs.items():
            for attribute_name, attribute in section.items():
                setattr(self, f"_{section_name}_{attribute_name}", attribute)

        if self._user_default is None:
            self._user_default = self._DEFAULT_USER

    def save(self):
        config = configparser.ConfigParser()
        for variable in self._attributes:
            _, section, option = variable.split('_')
            if not config.has_section(section):
                config.add_section(section)
            config.set(section, option, str(getattr(self, variable)))

        wsl_conf_path = Path("/etc/wsl.conf")
        with open(wsl_conf_path, "w", encoding="utf-8") as f:
            config.write(f)
        os.chown(wsl_conf_path, 0, 0)
        os.chmod(wsl_conf_path, 0o644)


class _Initialiser(_SimpleData):
    __slots__ = (
        "_apt_keys",
        "_apt_packages",
        "_apt_repos",
        "_var_autoremove",
        "_var_codename",
        "_var_desktop",
        "_var_keep_old_config",
        "_var_max_download_size",
        "_var_max_install_size",
        "_var_release",
        "_var_upgrade",
        "_var_wsl",
        "_wsl_conf"
    )

    _DIST_INFO = lsb_release.get_distro_information()

    _SIZE_TABLE = {
        k: v
        for k, v in zip(
            ("", "K", "M", "G", "T", "P", "E", "Z", "Y"),
            _exponentials(1024)
        )
    }

    @staticmethod
    def _reset_files(*args: List[Path]):
        for file in args:
            file.unlink(True)
            file.touch(0o644, False)
            os.chown(file, 0, 0)

    @staticmethod
    def _reset_folders(*args: List[Path]):
        for folder in args:
            if folder.exists():
                shutil.rmtree(folder)
            folder.mkdir(0o755, False, False)
            os.chown(folder, 0, 0)

    def __init__(self, config: Dict[str, Any]):
        self._var_codename = self._DIST_INFO["CODENAME"]
        self._var_release = self._DIST_INFO["RELEASE"]
        self._var_keep_old_config = False
        self._var_desktop = False
        self._var_wsl = True
        self._var_autoremove = True
        self._var_upgrade = True
        self._var_max_download_size = None
        self._var_max_install_size = None

        # the "variables" field is optional
        for k, v in config.get("variables", {}).items():
            setattr(self, f"_var_{k}", v)

        # TODO: add detection of different WSL versions instead of boolean value
        if self._var_wsl and not fnmatch.fnmatchcase(platform.release(), "*-microsoft-standard-WSL2"):
            print(f"Disabling WSL on non-WSL Ubuntu installation...", file=sys.stderr)
            self._var_wsl = False

        # TODO: maybe removed in the future when WSLg releases
        if self._var_wsl:
            self._var_desktop = False

        self._normalise_sizes("max_download", "max_install")

        apt_config = config["apt"]

        # parepare for overwriting the config if requested
        if not self._var_keep_old_config:
            self._apt_repos = [
                _APTRemoteRepoFile(
                    name=repo_name,
                    url=self._normalise_uri(repo_config["url"])
                ) if "url" in repo_config else _APTRepoFile(
                    name=repo_name,
                    uri=self._normalise_uri(repo_config["uri"]),
                    dists=repo_config["dists"] if "dists" in repo_config else [
                        f"{self._var_codename}{suffix}"
                        for suffix in repo_config["codename_suffices"]
                    ] if "codename_suffices" in repo_config else [self._var_codename],
                    components=repo_config.get("components", ["main"]),
                    architectures=repo_config.get("architectures", [])
                )
                for repo_name, repo_config in apt_config["repos"].items()
            ]
            self._apt_keys = [
                _APTKeyFile(
                    name=key_name,
                    uri=self._normalise_uri(key_uri)
                )
                for key_name, key_uri in apt_config["keys"].items()
            ]

        self._apt_packages = apt_config["packages"]

        if self._var_wsl:
            self._apt_packages.extend(("wsl", "ubuntu-wsl"))

            self._wsl_conf = _WSLConfigFile(**config["wsl"])

    @property
    def _attributes(self) -> Iterable[str]:
        for attr in self.__slots__:
            if attr.startswith("_var_"):
                yield attr

    def _apt(self):
        if not self._var_keep_old_config:
            self._reset_folders(_APT_SOURCES_LIST_DIR, _APT_PREFERENCES_DIR, _APT_TRUSTED_GPG_DIR)
            self._reset_files(Path("/etc/apt/sources.list"), Path("/etc/apt/preferences"), Path("/etc/apt/trusted.gpg"))
            Path("/etc/apt/trusted.gpg~").unlink(True)

            sources_list = SourcesList()
            for repo in self._apt_repos:
                repo.write_to(sources_list)
            sources_list.save()

            with Pool() as pool:
                pool.map(operator.methodcaller("save"), self._apt_keys)

        with Cache() as cache:
            cache.update()

        # first mark all packages to be edited (install/upgrade)
        packages = set(self._apt_packages)
        with Cache() as cache, cache.actiongroup():
            for package in cache:
                package_name = package.name
                if package_name in packages:
                    package.mark_install(True, True, True)
                    package.mark_auto(False)
                    packages.remove(package_name)
                else:
                    package.mark_auto(True)
            cache.commit()
        if packages:
            print("The following missing packages were ignored:", file=sys.stderr)
            for package in packages:
                print(f"  * {package}", file=sys.stderr)

        # remove unused packages if requested
        with Cache() as cache, cache.actiongroup():
            for package in cache:
                if package.is_auto_removable:
                    if self._var_autoremove:
                        package.mark_delete(True, True)
                elif package.is_upgradable:
                    if self._var_upgrade:
                        package.mark_upgrade(not package.is_auto_installed)
            cache.commit()

    def _normalise_sizes(self, *args: List[str]):
        for size_key in args:
            size_name = f"_var_{size_key}_size"
            size = getattr(self, size_name)
            if size is None:
                setattr(self, size_name, math.inf)
            elif isinstance(size, (int, float)):
                setattr(self, size_name, size)
            elif isinstance(size, dict):
                setattr(self, size_name, size["size"] * self._SIZE_TABLE[size["unit"]])
            else:
                raise ValueError(f"Unrecognised size specification for {size_key} ({size})")

    def _normalise_uri(self, uri_config) -> str:
        if isinstance(uri_config, str):
            return uri_config
        if isinstance(uri_config, dict):
            format_args = {}
            for k, v in uri_config["format_args"].items():
                if isinstance(v, (str, int, float, bool)):
                    format_args[k] = v
                elif isinstance(v, dict):
                    format_args[k] = getattr(self, f"_substitute_{v.pop('type')}")(**v)
                else:
                    raise TypeError(f"unrecognised format_args type ({format_args})")
            return uri_config["template"].format(**format_args)
        raise TypeError(f"{uri_config} is neither a string nor a recognised config")

    def _size_check(self, package: Package) -> bool:
        pass

    def _substitute_method(self, name: str, args=[], kwargs={}) -> str:
        return getattr(self, f"_sup_method_{name}")(*args, **kwargs)

    def _substitute_variable(self, name: str) -> str:
        return getattr(self, f"_var_{name}")

    def _sup_method_cuda_uri_folder(self) -> str:
        return f"ubuntu{self._var_release.replace('.', '')}"

    def run(self):
        self._apt()

        if self._var_wsl:
            self._wsl_conf.save()

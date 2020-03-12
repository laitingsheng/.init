#!/usr/bin/env bash

export DEBIAN_FRONTEND=noninteractive

# terminate script by Ctrl-C
function _terminate() {
    echo "Exit due to Ctrl-C"
    exit 1;
}
trap _terminate INT;

if [[ ${UID} != 0 ]]
then
    echo "Requires root to execute this script" >&2
    exit 1
fi

# predefined variables
DIR=`dirname ${BASH_SOURCE[0]}`
DIST=$(lsb_release -cs)
RELEASE=$(lsb_release -rs)
REPO="http://au.archive.ubuntu.com/ubuntu"
DESKTOP=yes

while getopts ":d:r:sv:w" ARG
do
    case ${ARG} in
        d )
            DIST=${OPTARG}
            ;;
        r )
            REPO=${OPTARG}
            ;;
        s )
            unset DESKTOP
            ;;
        v )
            RELEASE=${OPTARG}
            ;;
        w )
            unset DESKTOP
            WSL=yes;
            ;;
        : )
            echo "-${OPTARG} requires an argument" >&2
            exit 1
            ;;
        * )
            echo "-${OPTARG} was not recognised" >&2
            exit 1
            ;;
    esac
done

cat <<- EOL
Configuration:
    Distribution: ${DIST}
    Release: ${RELEASE}
    Repository: ${REPO}
    Destop Mode: ${DESKTOP:-no}
    WSL Mode: ${WSL:-no}
EOL

# update sources
rm -rf /etc/apt/sources.list.d
mkdir -m 755 /etc/apt/sources.list.d
install -o root -g root -m 644 -T ${DIR}/lists/sources.list /etc/apt/sources.list
install -o root -g root -m 644 ${DIR}/lists/base/* /etc/apt/sources.list.d
sed -i "s|%REPO%|${REPO}|;s/%RELEASE%/${RELEASE}/g;s/%DIST%/${DIST}/g" /etc/apt/sources.list.d/*.list

# update keys
rm -f /etc/apt/trusted.gpg /etc/apt/trusted.gpg~ /etc/apt/trusted.gpg.d/*.gpg
# 1. Ubuntu Main Key; 2. GitHub CLI Key
xargs apt-key adv --keyserver keyserver.ubuntu.com --recv-key <<- EOL
3B4FE6ACC0B21F32
C99B11DEB97541F0
EOL
xargs apt-key adv -q --fetch-keys <<- EOL
https://packages.microsoft.com/keys/microsoft.asc
https://download.docker.com/linux/ubuntu/gpg
https://packages.cloud.google.com/apt/doc/apt-key.gpg
https://apt.releases.hashicorp.com/gpg
https://deb.nodesource.com/gpgkey/nodesource.gpg.key
https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB
http://developer.download.nvidia.com/compute/cuda/repos/ubuntu2004/x86_64/7fa2af80.pub
EOL

# update preferences
rm -rf /etc/apt/preferences.d
mkdir -m 755 /etc/apt/preferences.d
install -o root -g root -m 644 -T ${DIR}/preferences/preferences /etc/apt/preferences
install -o root -g root -m 644 ${DIR}/preferences/base/* /etc/apt/preferences.d

if [[ ${DESKTOP} ]]
then
    install -o root -g root -m 644 ${DIR}/lists/desktop/* /etc/apt/sources.list.d

    xargs apt-key adv -q --fetch-keys <<- EOL
https://dl.google.com/linux/linux_signing_key.pub
https://repo.steampowered.com/steam/archive/precise/steam.gpg
EOL

    install -o root -g root -m 644 ${DIR}/preferences/desktop/* /etc/apt/preferences.d
fi

# refresh
apt-get update
apt list --installed | cut -d '/' -f1 | xargs apt-mark auto

# remove LXC & Snap for WSL
if [[ ${WSL} ]]
then
    apt-get purge -fy lxd lxd-client snapd
fi

# common system packages
xargs apt-get install -fy <<- EOL
ubuntu-minimal
ubuntu-standard
ubuntu-server
language-pack-en
language-pack-zh-hans
language-pack-zh-hant
locales-all
fonts-noto
errno
parallel
expect
tree
p7zip-full
EOL

if [[ ${DESKTOP} ]]
then
    apt-get install ubuntu-desktop
fi

# WSL only system packages
if [[ ${WSL} ]]
then
    apt-get install -fy ubuntu-wsl wsl
fi

# development
xargs apt-get install -fy <<- EOL
build-essential
cmake-extras
meson
gcc-multilib
g++-multilib
gcc-opt
uuid-dev
uuid-runtime
gdc
gcovr
flex
bison
git-all
git-ftp
git-lfs
gh
grip
subversion
ruby-all-dev
python3-all-dbg
python3-pip
python3-venv
python3-coverage-test-runner
python3-autopep8
mypy
cython3-dbg
jupyter
gradle
maven
openjdk-8-jdk
openjdk-11-jdk
haskell-platform
haskell-stack
valgrind-dbg
mono-complete
lldb
llvm-dev
ldc
clang
clang-format
clang-tidy
clang-tools
clangd
texlive
texlive-full
gccgo
golang
gnugo
nodejs
julia
terraform
intel-hpckit
cuda-toolkit-11-2
ocl-icd-opencl-dev
EOL

# libraries
xargs apt-get install -fy <<- EOL
libboost-all-dev
libyaml-cpp-dev
libfmt-dev
EOL

# common apps
xargs apt-get install -fy <<- EOL
azure-cli
dotnet-sdk-*
docker-ce
google-cloud-sdk
kubeadm
EOL

# apps only for desktop
if [[ ${DESKTOP} ]]
then
    apt-get install google-chrome-stable steam code
fi

if [[ ${WSL} ]]
then
    install -o root -g root -m 644 wsl.conf /etc/wsl.conf
fi

update-locale LANG=en_AU.utf8 LANGUAGE=en_AU.utf8 LC_ALL=en_AU.utf8

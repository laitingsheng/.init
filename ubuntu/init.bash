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
UPGRADE=yes

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
        u )
            unset UPGRADE
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
    Upgrade: ${UPGRADE:-no}
EOL

# update sources
rm -rf /etc/apt/sources.list.d
mkdir -m 755 /etc/apt/sources.list.d
install -o root -g root -m 644 -T ${DIR}/lists/sources.list /etc/apt/sources.list
install -o root -g root -m 644 ${DIR}/lists/base/* /etc/apt/sources.list.d
sed -i "s|%REPO%|${REPO}|;s/%RELEASE%/${RELEASE}/g;s/%DIST%/${DIST}/g" /etc/apt/sources.list.d/*.list
install -o root -g root -m 644 ${DIR}/lists/nvidia/${RELEASE}.list /etc/apt/sources.list.d/nvidia.list

# update keys
rm -f /etc/apt/trusted.gpg /etc/apt/trusted.gpg~ /etc/apt/trusted.gpg.d/*.gpg
# Add back Ubuntu Archive key
apt-key add /usr/share/keyrings/ubuntu-archive-keyring.gpg
xargs apt-key adv -q --fetch-keys <<- EOL
https://packages.microsoft.com/keys/microsoft.asc
https://cli.github.com/packages/githubcli-archive-keyring.gpg
https://download.docker.com/linux/ubuntu/gpg
https://packages.cloud.google.com/apt/doc/apt-key.gpg
https://apt.releases.hashicorp.com/gpg
https://deb.nodesource.com/gpgkey/nodesource.gpg.key
https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB
EOL
cat lists/nvidia/20.04.key.url | xargs apt-key adv -q --fetch-keys

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

# refresh index
apt-get update

if [[ ${UPGRADE} ]]
then
    apt-get dist-upgrade -fy
    apt-get upgrade -fy
fi

# unmark all packages
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
mle
p7zip-full
neofetch
httpie
bat
gpustat
ctop
hub
zsh
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
r-base
mypy
cython3-dbg
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
cuda
ocl-icd-opencl-dev
cargo
EOL

# libraries
xargs apt-get install -fy <<- EOL
libboost-all-dev
libyaml-cpp-dev
libfmt-dev
EOL

# Python modules
xargs apt-get install -fy <<- EOL
ansible
jupyter
python3-openstackclient
python3-seaborn
python3-sklearn-pandas
EOL

# common apps
xargs apt-get install -fy <<- EOL
aws-shell
azure-cli
dotnet-sdk-*
docker-ce
google-cloud-sdk
kubeadm
EOL

# funny apps
xargs apt-get install -fy <<- EOL
ansiweather
EOL

# NPM global packages
xargs npm install -g <<- EOL
serve
react
typescript
leetcode-cli
EOL

# apps only for desktop
if [[ ${DESKTOP} ]]
then
    apt-get install google-chrome-stable steam code
fi

if [[ ${WSL} ]]
then
    install -o root -g root -m 644 wsl.conf /etc/wsl.conf
    # the first user ID on WSL/Ubuntu will always be 1000
    sed -i "s|%USER%|$(id -nu 1000)|" /etc/wsl.conf
fi

update-alternatives --set editor /usr/bin/vim.basic
update-locale LANG=en_AU.utf8 LANGUAGE=en_AU.utf8 LC_ALL=en_AU.utf8
usermod -aG docker ${USER}

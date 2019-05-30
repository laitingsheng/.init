#!/usr/bin/env bash

# colours
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# logging levels
INFO="${YELLOW}INFO${NC}"
WARNING="${RED}WARNING${NC}"

info_echo() {
    printf "$INFO: $*\n"
}

info_printf() {
    printf "$INFO: $*"
}

warning_echo() {
    printf "$WARNING: $*\n"
}

warning_printf() {
    printf "$WARNING: $*"
}

# check if current is root
if [[ $EUID -ne 0 ]]
then
    warning_printf "This script must be run as root, use \"sudo $0"
    [[ ! -z $@ ]] && printf " $*"
    echo "\" instead"
    return 1
fi

if uname -a | grep -q Microsoft
then
    # add wsl.conf to /etc to enable permission bits on NTFS for WSL
    info_echo "Adding wsl.conf to /etc"
    cat > /etc/wsl.conf <<- EOL
[automount]
enabled = true
root = /mnt/
options = "metadata,fmask=0133,dmask=0022"
mountFsTab = true

[network]
generateHosts = true
generateResolvConf = true

[interop]
enabled = true
appendWindowsPath = true
EOL
    chown root:root /etc/wsl.conf
    chmod 644 /etc/wsl.conf
fi

info_echo "Removing unnecessary lxd and snap"
apt-get -y purge lxd lxd-client snapd

print_usage() {
    echo "Usage: (sudo) $0 [-d distro] [-r repo]"
}

repo="au.archive.ubuntu.com/ubuntu"
distro="bionic"

while getopts ":d:r:" opt; do
    case $opt in
        d )
            distro=$OPTARG
            ;;
        r )
            repo=$OPTARG
            ;;
        \? )
            print_usage
            exit 0
            ;;
        : )
            warning_echo "-$OPTARG requires an argument"
            print_usage
            exit 1
            ;;
    esac
done

# create a sources.list file
for pool in $distro $distro-updates $distro-backports $distro-security
do
    echo "deb http://$repo $pool main restricted universe multiverse"
done > /etc/apt/sources.list
echo "deb http://archive.canonical.com/ubuntu $distro partner" >> /etc/apt/sources.list

info_echo "Refreshing the index and installing/upgrading packages"
apt-get update
# generate the list
apt-get install <<- EOL
gcc
g++
make
wget
curl
libboost-dev-all
clang
clang-format
clang-tidy
clang-tools
llvm
valgrind
gdb
lldb
openjdk-8-jdk
openjdk-11-jdk
haskell-platform
perl
git
nano
moreutils
parallel
htop
net-tools
expect
tree
EOL
# Upgrade the rest
apt-get -y dist-upgrade
apt-get -y upgrade

info_echo "Script finalised"

#!/usr/bin/env bash

# exit on error
set -eu

# source the common file
source utils.sh || exit $?

EXIT_PRINT()
{
    # [ ${CURRENT_STEP:-''} -a ${ON_EXIT_MSG:-''} ] || exit
    [ $? -ne 0 ] && printf $RED || printf $GREEN
    printf "Current step: $CURRENT_STEP\nMessage: $ON_EXIT_MSG\n${NC}"
}
trap EXIT_PRINT EXIT

# disable interactive mode
export DEBIAN_FRONTEND=noninteractive

# fix current umask
umask 0022

print_usage()
{
    cat <<- EOL
Usage: (sudo) $0 [OPTIONS]
Standard Options:
    -d distribution
        Specify the target Ubuntu distribution
        Default: bionic
    -l locale (country code)
        Used to generate and update locale. It will be used to generate a URL for official Ubuntu repository if -r is not specified
        Default: au
    -r repository URL
        Can be a custom repository URL
        Default: http://[locale].archive.ubuntu.com/ubuntu or fall back to http://archive.ubuntu.com/ubuntu if the previous URL is invalid
    -w
        Set interop.appendWindowsPath option in /etc/wsl.conf to true
Extra Options:
    -h
        Print this message
EOL
}

# default settings
dist='bionic'
loc='au'
win_path='false'

# parse options
while getopts ':d:hl:p:r:w' opt
do
    case $opt in
        d )
            CURRENT_STEP='Validate $dist pattern'
            dist=$OPTARG
            ON_EXIT_MSG="'$dist' should contain lowercase letters only"
            grep -Eq '^[a-z]+$' <<< $dist
            ;;
        h)
            print_usage
            exit 0
            ;;
        l )
            CURRENT_STEP='Validate $loc pattern'
            loc=$OPTARG
            ON_EXIT_MSG="'$loc' should contain lowercase letters only"
            grep -Eq '^[a-z]+$' <<< $dist
            ;;
        r )
            repo=$OPTARG
            ;;
        w )
            win_path='true'
            ;;
        \? )
            CURRENT_STEP='Parse arguments'
            ON_EXIT_MSG="unknown argument '-$OPTARG'"
            print_usage
            exit 1
            ;;
        : )
            CURRENT_STEP='Parse arguments'
            ON_EXIT_MSG="'-$OPTARG' requires an argument"
            print_usage
            exit 1
            ;;
    esac
done

# check if current is root
if [ $EUID -ne 0 ]
then
    CURRENT_STEP='Testing if running as root'
    ON_EXIT_MSG="This script must be run as root, use 'sudo $0 $*' instead"
    exit 126
fi

# WSL only
if grep -iq microsoft <(uname -a)
then
    CURRENT_STEP='Install wsl.conf to /etc'
    ON_EXIT_MSG='Fail to install the correct wsl.conf to /etc'
    # add wsl.conf to /etc/ for customised configuration
    info_echo 'Adding wsl.conf to /etc/'
    install -o root -g root -m 644 templates/wsl.conf.template /etc/wsl.conf
    sed -i "s/%INTEROP_APPEND_WINDOWS_PATH%/$win_path/" /etc/wsl.conf
fi

CURRENT_STEP='Update timezone to Australia/Melbourne'
ON_EXIT_MSG='Fail to set timezone'
# set timezone for tzdata
ln -fs /usr/share/zoneinfo/Australia/Melbourne /etc/localtime

CURRENT_STEP='Modify /etc/apt/sources.list'
ON_EXIT_MSG='Failed to modify /etc/apt/sources.list'
# generate sources.list from template
info_echo 'Updating /etc/apt/sources.list'
install -o root -g root -m 644 templates/ubuntu.sources.list.template /etc/apt/sources.list
sed -i "s/%COMMAND%/deb/;s|%REPO%|${repo:-http://${loc:-}${loc:+.}archive.ubuntu.com/ubuntu}|;s/%DIST%/$dist/" /etc/apt/sources.list

CURRENT_STEP='Refresh index'
ON_EXIT_MSG='Repository URL may not be valid or check the Internet connection'
# manage packages
info_echo 'Refreshing the index and installing/upgrading packages'
apt-get update
apt-get dist-upgrade -fy
apt-get upgrade -fy

CURRENT_STEP='Remove LXC and snapd'
ON_EXIT_MSG='Fail to purge LXC packages'
# Remove Ubuntu builtin container
info_echo 'Removing unnecessary lxd and snap'
apt-get purge lxd lxd-client snapd -fy

CURRENT_STEP='Install packages'
ON_EXIT_MSG="Some of the packges is not available for '$dist' distribution"
xargs apt-get install -fy <<- EOL
bash
sudo
cron
locales
software-properties-common
gcc
g++
make
wget
curl
perl
git
nano
moreutils
parallel
htop
net-tools
expect
tree
vim
python
python-pip
python3
python3-pip
maven
EOL

CURRENT_STEP='Add Docker to APT repository'
ON_EXIT_MSG='Fail to add Docker repository'
# official Docker repo
info_echo 'Adding Docker repository'
curl -fsSL 'https://download.docker.com/linux/ubuntu/gpg' | apt-key add -
echo "deb https://download.docker.com/linux/ubuntu $dist stable" >> /etc/apt/sources.list
apt-get update

CURRENT_STEP='Install Docker'
ON_EXIT_MSG="Docker stable channel may not be available for '$dist'"
info_echo 'Installing Docker'
xargs apt-get install -fy <<- EOL
containerd.io
docker-ce
docker-ce-cli
EOL

CURRENT_STEP='Update locale'
ON_EXIT_MSG='Fail to set locale'
# Generate & change locale
locale="en_${loc^^}.utf8"
info_echo "Changing locale to $locale"
locale-gen $locale || exit $?
update-locale LANG=$locale LC_ALL=$locale LANGUAGE=$locale

CURRENT_STEP='Fianlised'
ON_EXIT_MSG='Base script execution completed'

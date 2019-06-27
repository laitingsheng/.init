#!/usr/bin/env bash

source utils.sh || exit $?

# check if current is root
if [[ $EUID -ne 0 ]]
then
	warning_echo "This script must be run as root, use 'sudo $0$([ ! -z "$*" ] && printf " $*")' instead"
	exit 126
fi

print_usage() {
	echo "Usage: (sudo) $0 [-d distribution] [-l location] [-u user]"
}

# default settings
dist='bionic'
loc='au'
win_path='false'

# parse options
while getopts ":d:l:u:w" opt
do
	case $opt in
		d )
			dist=$OPTARG
			;;
		l )
			loc=$OPTARG
			;;
		u )
			user=$OPTARG
			id -u $user &> /dev/null
			if [ $? -ne 0 ]
			then
				warning_echo "'$user' is an invalid user name"
				exit 1
			fi
			if [ ! -d ~$user ]
			then
				warning_echo "'$user' does not have home directory"
				exit 1
			fi
			;;
		w )
			win_path='true'
			;;
		\? )
			print_usage
			exit 0
			;;
		: )
			warning_echo "'-$OPTARG' requires an argument"
			print_usage
			exit 1
			;;
	esac
done

[ -z $user ] && warning_echo "user was not set" && exit 1

# WSL only
if uname -a | grep -q Microsoft
then
	# add wsl.conf to /etc/ for customised configuration
	info_echo "Adding wsl.conf to /etc/"
	install -o root -g root -m 644 templates/wsl.conf.template /etc/wsl.conf
	sed -i "s/%INTEROP_APPEND_WINDOWS_PATH%/$win_path/" /etc/wsl.conf
fi

info_echo "Removing unnecessary lxd and snap"
apt-get -y purge lxd lxd-client snapd

# generate sources.list from template
install -o root -g root -m 644 templates/ubuntu.sources.list.template /etc/apt/sources.list
sed -i "s/%COMMAND%/deb/;s/%PREFIX%/$loc./;s/%DIST%/$dist/" /etc/apt/sources.list

# manage packages
info_echo "Refreshing the index and installing/upgrading packages"
sudo apt-get update
apt-get -y install <<- EOL
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
EOL
# Upgrade the rest
apt-get -y dist-upgrade
apt-get -y upgrade

# clone repo for nano syntax highlight
info_echo "Cloning nano rc repo"
git clone https://github.com/scopatz/nanorc.git ~$user/.nano
chown -R $user:$user .nano
chmod -R go-w ~$user/.nano
ln -s ~$user/.nano/nanorc ~$user/.nanorc
chmod $user:$user ~$user/.nanorc

info_echo "Script finalised"

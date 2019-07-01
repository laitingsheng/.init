#!/usr/bin/env bash

# exit on error
set -e

# disable interactive mode
export DEBIAN_FRONTEND=noninteractive

# test installed packages
while read cmd
do
    which $cmd
done <<- EOL
sudo
crontab
gcc
g++
make
wget
curl
perl
git
nano
parallel
htop
ifconfig
expect
tree
vim
vimtutor
EOL

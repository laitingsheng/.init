#!/usr/bin/env bash

# exit on error & prevent unset variable
set -eu

source ubuntu.base.sh $*

# install extra packages
apt-get -y install libboost-all-dev clang clang-format clang-tidy clang-tools llvm valgrind gdb lldb openjdk-8-jdk openjdk-11-jdk haskell-platform

# official Docker repo
info_echo "Adding Docker repo"
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | apt-key add -
echo "deb https://download.docker.com/linux/ubuntu $dist stable" >> /etc/apt/sources.list

# official Ansible repo
info_echo "Adding Ansible PPA"
add-apt-repository -uy ppa:ansible/ansible

info_echo "Installing Docker & Ansible"
apt-get install -y ansible docker-ce docker-ce-cli containerd.io

# Miniconda 3
info_echo "downloading Miniconda 3"
wget -O install.sh https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
chmod 755 install.sh
info_echo "installing Miniconda 3"
mkdir -p /var/lib/conda
./install.sh -bf -p /var/lib/conda
rm -f install.sh

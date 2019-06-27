#!/usr/bin/env bash

source ubuntu-desktop.sh $* || exit $?

# install extra packages
apt-get -y install <<- EOL
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
EOL

# official Docker repo
info_echo "Adding Docker repo"
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
echo "deb https://download.docker.com/linux/ubuntu $distro stable" >> /etc/apt/sources.list

# official Ansible repo
info_echo "Adding Ansible PPA"
add-apt-repository ppa:ansible/ansible

info_echo "Installing Docker & Ansible"
apt-get -y install <<- EOL
ansible
docker-ce
docker-ce-cli
containerd.io
EOL

# Miniconda 3
info_echo "downloading Miniconda 3"
wget -O install.sh https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
chmod 755 install.sh
info_echo "installing Miniconda 3"
mkdir -p /var/lib/conda
./install.sh -bf -p /var/lib/conda
rm -f install.sh

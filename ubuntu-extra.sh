#!/usr/bin/env bash

source ubuntu-base.sh || exit $?

info_echo "Adding Ansible PPA"
add-apt-repository ppa:ansible/ansible

info_echo "Adding Docker repo"
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
add-apt-repository "deb https://download.docker.com/linux/ubuntu $distro stable"
apt-get update


apt-get -y install <<- EOL
ansible
docker-ce
docker-ce-cli
containerd.io
EOL

wget -O install.sh https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
chmod 755 install.sh
./install.sh
rm -f install.sh

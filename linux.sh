#!/usr/bin/env bash

source utils.sh || exit $?

# install docker-machine
version=$(curl -fLs https://api.github.com/repos/docker/machine/releases/latest | grep 'tag_name' | cut -d '"' -f 4)
wget -O /tmp/docker-machine "https://github.com/docker/machine/releases/download/$version/docker-machine-Linux-x86_64"
install -o root -g root -m 755 /tmp/docker-machine /usr/local/bin/docker-machine
rm /tmp/docker-machine

# install docker-machine bash completions
install_completion()
SCRIPTS=(docker-machine-prompt.bash docker-machine-wrapper.bash docker-machine.bash)
parallel -d ' ' -j 200% " \
wget -O /tmp/{} https://raw.githubusercontent.com/docker/machine/$version/contrib/completion/bash/{} && \
install -o root -g root -m 644 /tmp/{} /etc/bash_completion.d/{} && \
rm /tmp/{} \
" ::: ${SCRIPTS[@]}

# install kubectl for Kubernetes
version=$(curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt)
wget -O /tmp/kubectl "https://storage.googleapis.com/kubernetes-release/release/$version/bin/linux/amd64/kubectl"
install -o root -g root -m 755 /tmp/kubectl /usr/local/bin/kubectl
rm /tmp/kubectl

# install Skaffold
wget -O /tmp/skaffold 'https://storage.googleapis.com/skaffold/releases/latest/skaffold-linux-amd64'
install -o root -g root -m 755 /tmp/skaffold /usr/local/bin/skaffold
rm /tmp/skaffold

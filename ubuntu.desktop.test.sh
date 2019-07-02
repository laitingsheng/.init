#!/usr/bin/env bash

# exit on error
set -e

source ubuntu.base.test.sh

# test Boost Library
ldconfig -p | grep -P 'libboost_\w*?\.so\.[\d\.]+'

while read cmd
do
    which $cmd
done <<- EOL
clang
clang-format
clang-tidy
valgrind
gdb
lldb
ghc
stack
docker
docker-compose
ansible
EOL

# different Java versions
/usr/lib/jvm/java-1.8.0-openjdk-amd64/bin/java -version
/usr/lib/jvm/java-1.11.0-openjdk-amd64/bin/java -version

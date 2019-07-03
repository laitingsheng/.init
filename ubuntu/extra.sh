#!/usr/bin/env bash

source ubuntu/base.sh $* || exit $?

CURRENT_STEP='Install extra packages'
ON_EXIT_MSG="Some of the packges is not available for '$dist' distribution"
# install extra packages
xargs apt-get install -fy <<- EOL
libboost-all-dev
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
haskell-stack
mono-complete
EOL

CURRENT_STEP='Fianlised'
ON_EXIT_MSG='Desktop script execution completed'

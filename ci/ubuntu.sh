#!/usr/bin/env bash

# exit on error & prevent unset variable
set -eu

bash ubuntu/$1.sh -d bionic -l us

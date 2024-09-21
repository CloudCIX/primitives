#!/bin/sh

usage() {
  echo "usage: $0 <target directory>"
}

if [ -z "$1" ]; then
  usage()
  exit 1
fi

target=$1
mydir=$(dirname $(readlink -e $0))
repo="${mydir}/../"

mkdir -p "$target" || exit 2

if ! ls -l "$target" | head -n 1 | grep -q '^total 0$'; then
  echo "Directory ${target} not empty, exiting."
  exit 3
fi

virtualenv "$target"
. "${target}/bin/activate"

pip install -e "$repo"

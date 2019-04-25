#!/usr/bin/env bash
# Copyright 2019 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -euxo pipefail

# TODO: point to twitter/scoot after merging twitter/scoot#420!
scoot_repo="${1:-https://github.com/cosmicexplorer/scoot}"
# TODO: point to master after merging twitter/scoot#420!
scoot_repo_ref="${2:-make-scoot-run-locally-for-pants}"

export GOPATH="${GOPATH:-$(readlink -f ../go)}"

# It is unclear how else to make go read all the dependent projects without this exact directory
# setup.
clone_dir="${GOPATH}/src/github.com/twitter/scoot"

if [[ ! -d "$clone_dir" ]]; then
  mkdir -p ../go/src/github.com/twitter
  mkdir -p ../go/bin
  git clone "$scoot_repo" "$clone_dir"
  pushd "$clone_dir"
  git fetch origin "$scoot_repo_ref"
  git checkout "$scoot_repo_ref"
  popd
fi

pushd "$clone_dir"

# Scoot will use this tool when creating a local cluster.
bash ./get_fs_util.sh

# TODO: merge twitter/scoot#420!
PATH="/usr/bin:${PATH}" dep ensure -update

# Mix stdout and stderr, and tee it to both, so we can consume one stream then close it in an
# integration test without causing errors.
PATH="/usr/bin:${PATH}" go run ./binaries/setup-cloud-scoot/main.go --strategy local.local \
   2>&1 | tee /dev/fd/2

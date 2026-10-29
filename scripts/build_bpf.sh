#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Compiles the HID-BPF programs in bpf/ into bin/, which goes into the plugin zip. Needs Linux with
# clang, llvm-strip and the libbpf headers (on Ubuntu: clang, llvm, libbpf-dev); other names of the
# tools come in CLANG and LLVM_STRIP, such as clang-15. BTF stays in the objects: libbpf needs it
# to load struct_ops programs.
set -euo pipefail

clang="${CLANG:-clang}"
strip="${LLVM_STRIP:-llvm-strip}"
project="$(cd "$(dirname "$0")/.." && pwd)"
# Debian keeps asm/types.h under the architecture's triplet.
multiarch="/usr/include/$(uname -m)-linux-gnu"

mkdir -p "$project/bin"
for source in "$project"/bpf/*.bpf.c; do
    object="$project/bin/$(basename "${source%.c}").o"
    # The file names in the line info start from the project, not from this machine's folders, so
    # the object is the same wherever it is built and carries no local path into the zip.
    "$clang" -target bpf -O2 -g -Wall -Werror -ffile-prefix-map="$project"=. \
        -I"$project/bpf" -I"$multiarch" -c "$source" -o "$object"
    "$strip" -g "$object"
    echo "$object"
done

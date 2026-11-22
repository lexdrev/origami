#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Builds vkBasalt, the Vulkan layer the sharpness loads into the games, into bin/vkbasalt/, which
# goes into the plugin zip: lib64/ for 64-bit games and lib32/ for 32-bit ones. Bazzite has the
# layer in its image and SteamOS does not, so ORIGAMI brings its own to both.
#
# The source is vkBasalt's release, unmodified (zlib licence). It is built with zig, a C and C++
# compiler that targets 32-bit x86 and an old glibc by itself: the libraries ask for glibc 2.31,
# which Steam's own container for games has, and carry the C++ library inside. They need libX11
# from the system; a library with libX11's name and the few functions the layer calls stands in
# for it at link time. Vulkan's, SPIR-V's and X11's headers and the GLSL compiler come as
# releases and Ubuntu 22.04 packages, each checked against its SHA-256.
#
# Needs Linux with curl, dpkg-deb, pkg-config and either uv or Python's venv; nothing is installed
# into the system. The tools and the build live in ORIGAMI_BUILD_DIR (/tmp/origami-vkbasalt), the
# downloads in out/cache/vkbasalt/. A build that is up to date is not made again.
set -euo pipefail

VKBASALT=0.3.2.10
GLIBC=2.31
TOOLS="meson==1.12.1 ninja==1.13.2 ziglang==0.17.1"
UBUNTU=http://archive.ubuntu.com/ubuntu/pool
# Address and SHA-256 of each download.
SOURCES=(
    "https://github.com/DadSchoorse/vkBasalt/releases/download/v$VKBASALT/vkBasalt-$VKBASALT.tar.gz eb196ff446fa36ec0ca99c4406d753c1fa210afddeec5e7a76e1c2e74ed605e3"
    "https://github.com/KhronosGroup/Vulkan-Headers/archive/refs/tags/v1.3.250.tar.gz c4c5a706a1f8f4d329fec2909b8c3fef4a4be043f393dbde5ce1439daa1194ab"
    "$UBUNTU/main/libx/libx11/libx11-dev_1.7.5-1_amd64.deb 4b06bfd5ad9409ade5dd873ddd732d1c1f90aa1581e545c432a60303b08e980e"
    "$UBUNTU/main/x/xorgproto/x11proto-dev_2021.5-1_all.deb 7cb2471a23ea50e197cec019d0596840b6ddd714e8deb75e427472e820e83548"
    "$UBUNTU/universe/s/spirv-headers/spirv-headers_1.6.1+1.3.204.0-3_all.deb 15b58ab1ddffbc7162cae76701d3c36c234275f5192ed54817a18078953f114d"
    "$UBUNTU/universe/g/glslang/glslang-tools_11.8.0+1.3.204.0-1_amd64.deb f28d516d6d8bd2e6bf178084b21ec1bfef9a09c649b43a38503cc9cd30b4f191"
)

project="$(cd "$(dirname "$0")/.." && pwd)"
target="$project/bin/vkbasalt"
cache="$project/out/cache/vkbasalt"
work="${ORIGAMI_BUILD_DIR:-/tmp/origami-vkbasalt}"
stamp="$(sha256sum "$0" | cut -d' ' -f1)"

if [ -f "$target/lib64/libvkbasalt.so" ] && [ -f "$target/lib32/libvkbasalt.so" ] &&
    [ "$(cat "$target/BUILD" 2>/dev/null)" = "$stamp" ]; then
    echo "$target is up to date"
    exit 0
fi

mkdir -p "$cache" "$work"
for source in "${SOURCES[@]}"; do
    read -r url sum <<<"$source"
    file="$cache/$(basename "$url")"
    [ -f "$file" ] || curl -fsSL -o "$file" "$url"
    if ! echo "$sum  $file" | sha256sum -c - >/dev/null; then
        rm -f "$file"
        echo "$(basename "$url") is not the file this script was written for" >&2
        exit 1
    fi
done

cd "$work"
rm -rf src sys
mkdir -p src sys
tar -xzf "$cache/vkBasalt-$VKBASALT.tar.gz" -C src
tar -xzf "$cache/v1.3.250.tar.gz" -C src
for package in "$cache"/*.deb; do dpkg-deb -x "$package" sys; done
source_dir="$work/src/vkBasalt-$VKBASALT"
includes="'-I$work/src/Vulkan-Headers-1.3.250/include', '-I$work/sys/usr/include'"

if [ ! -x venv/bin/meson ]; then
    if command -v uv >/dev/null; then
        uv venv -q venv
        # shellcheck disable=SC2086
        VIRTUAL_ENV="$work/venv" uv pip install -q $TOOLS
    else
        python3 -m venv venv
        # shellcheck disable=SC2086
        venv/bin/pip install -q $TOOLS
    fi
fi
python="$work/venv/bin/python"
export ZIG_GLOBAL_CACHE_DIR="$work/zig-cache" ZIG_LOCAL_CACHE_DIR="$work/zig-cache"
export PATH="$work/sys/usr/bin:$work/venv/bin:$PATH"

twice() {
    "$@" 2>/dev/null || "$@"
}

build() {
    local bits="$1" triple="$2" family="$3" cpu="$4"
    local tools="$work/tools$bits" stub="$work/stub$bits"
    mkdir -p "$tools" "$stub" "pc$bits"

    # zig takes a target with its glibc version only when it knows the language of the source,
    # and under WSL 1 it cannot read a source from the standard input at all: what comes there
    # goes into a file whose name tells the language.
    local tool suffix
    for tool in cc c++; do
        suffix=c
        [ "$tool" = "c++" ] && suffix=cpp
        {
            echo '#!/usr/bin/env bash'
            echo 'arguments=()'
            echo 'input=""'
            echo 'for argument in "$@"; do'
            echo '    if [ "$argument" = "-" ]; then'
            echo "        input=\$(mktemp --suffix=.$suffix)"
            echo '        cat > "$input"'
            echo '        arguments+=("$input")'
            echo '    else'
            echo '        arguments+=("$argument")'
            echo '    fi'
            echo 'done'
            echo "\"$python\" -m ziglang $tool -target $triple.$GLIBC \"\${arguments[@]}\""
            echo 'code=$?'
            echo '[ -z "$input" ] || rm -f "$input"'
            echo 'exit $code'
        } >"$tools/$tool"
        chmod +x "$tools/$tool"
    done

    {
        echo 'void *XOpenDisplay(const char *name) { return 0; }'
        echo 'int XCloseDisplay(void *display) { return 0; }'
        echo 'int XQueryKeymap(void *display, char *keys) { return 0; }'
        echo 'unsigned long XStringToKeysym(const char *name) { return 0; }'
        echo 'unsigned char XKeysymToKeycode(void *display, unsigned long keysym) { return 0; }'
    } >"$stub/x11.c"
    # The first use of a target builds zig's own run-time libraries, so it comes before the build
    # proper, one compiler at a time; under WSL 1 the first try can fail on the empty cache.
    echo '#include <string>' >"$stub/warm.cpp"
    echo 'int size() { return static_cast<int>(std::string("a").size()); }' >>"$stub/warm.cpp"
    twice "$tools/cc" -shared -fPIC -Wl,-soname,libX11.so.6 -o "$stub/libX11.so" "$stub/x11.c"
    twice "$tools/c++" -shared -fPIC -std=c++2a -o "$stub/warm.so" "$stub/warm.cpp"
    {
        echo "Name: X11"
        echo "Description: X Library"
        echo "Version: 1.7.5"
        echo "Cflags: -I$work/sys/usr/include"
        echo "Libs: -L$stub -lX11"
    } >"pc$bits/x11.pc"

    # The libraries carry no symbols for debugging (-s), and no path of this machine. They are
    # never unloaded (-z nodelete): Vulkan's loader unloads a layer with its instance, and zig
    # has no crtbegin, whose part it is to run a library's C++ destructors then. Left registered,
    # they would run as the game exits, in memory that is no longer there.
    {
        echo "[binaries]"
        echo "c = '$tools/cc'"
        echo "cpp = '$tools/c++'"
        echo "ar = ['$python', '-m', 'ziglang', 'ar']"
        echo "strip = 'strip'"
        echo "pkg-config = 'pkg-config'"
        echo
        echo "[built-in options]"
        echo "c_args = [$includes, '-ffile-prefix-map=$work=.']"
        echo "cpp_args = [$includes, '-ffile-prefix-map=$work=.']"
        echo "c_link_args = ['-s', '-Wl,-z,nodelete']"
        echo "cpp_link_args = ['-s', '-Wl,-z,nodelete']"
        echo
        echo "[properties]"
        echo "pkg_config_libdir = '$work/pc$bits'"
        echo
        echo "[host_machine]"
        echo "system = 'linux'"
        echo "cpu_family = '$family'"
        echo "cpu = '$cpu'"
        echo "endian = 'little'"
    } >"cross$bits.ini"

    rm -rf "build$bits" "stage$bits"
    meson setup "build$bits" "$source_dir" --cross-file "cross$bits.ini" --buildtype=release \
        --prefix=/usr --libdir=lib -Dwith_json=false >"setup$bits.log" 2>&1 ||
        { tail -30 "setup$bits.log" >&2; exit 1; }
    # Three files at a time: under WSL 1 more of zig's processes trip over each other's cache.
    meson compile -j 3 -C "build$bits" >"compile$bits.log" 2>&1 ||
        { tail -40 "compile$bits.log" >&2; exit 1; }
    # Installing takes the path of the stand-in libX11 out of the library.
    meson install -C "build$bits" --destdir "$work/stage$bits" >"install$bits.log" 2>&1 ||
        { tail -20 "install$bits.log" >&2; exit 1; }
    mkdir -p "$target/lib$bits"
    cp "stage$bits/usr/lib/libvkbasalt.so" "$target/lib$bits/libvkbasalt.so"
    chmod 644 "$target/lib$bits/libvkbasalt.so"
}

rm -rf "$target"
build 64 x86_64-linux-gnu x86_64 x86_64
build 32 x86-linux-gnu x86 i686
for library in "$target"/lib*/libvkbasalt.so; do
    if readelf -d "$library" | grep -q "RUNPATH\|RPATH" || grep -q "$work" "$library"; then
        echo "$library carries a path of this machine" >&2
        exit 1
    fi
    if ! readelf -d "$library" | grep -q NODELETE; then
        echo "$library can be unloaded" >&2
        exit 1
    fi
    echo "$library $(sha256sum "$library" | cut -d' ' -f1)"
done
echo "$stamp" >"$target/BUILD"

# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Put the LSP plugins of the sound filter into bin/lv2/lsp-plugins.lv2/, for build_zip.py.

They come unmodified from Arch Linux's package lsp-plugins-lv2, built from LSP's source under
LGPL-3.0-or-later: the multiband compressor and the limiter, their descriptions, and a manifest
that names only these two. The package is checked against its SHA-256 and kept in out/cache/.
The same build runs on Bazzite and SteamOS (glibc 2.38 or newer, libcairo and libsndfile).
"""

import hashlib
import io
import sys
import tarfile
import urllib.request
from compression import zstd
from pathlib import Path

PACKAGE = "lsp-plugins-lv2-1.2.22-1-x86_64.pkg.tar.zst"
URL = f"https://archive.archlinux.org/packages/l/lsp-plugins-lv2/{PACKAGE}"
SHA256 = "49b37861d815241b1f08c44c8dab80cfceb389865ae5c9eaec453056743c5676"
BUNDLE = "lsp-plugins.lv2"
LIBRARY = "lsp-plugins-lv2.so"
PLUGINS = ("mb_compressor_stereo", "limiter_stereo")
SOURCE = f"usr/lib/lv2/{BUNDLE}"


def manifest() -> str:
    entries = "".join(
        f"\n<http://lsp-plug.in/plugins/lv2/{name}>\n"
        f"\ta lv2:Plugin ;\n\tlv2:binary <{LIBRARY}> ;\n\trdfs:seeAlso <{name}.ttl> .\n"
        for name in PLUGINS
    )
    return (
        "@prefix lv2: <http://lv2plug.in/ns/lv2core#> .\n"
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n" + entries
    )


def package(cache: Path) -> bytes:
    path = cache / PACKAGE
    if not path.is_file():
        cache.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(URL, timeout=120) as response:
            path.write_bytes(response.read())
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != SHA256:
        path.unlink()
        raise ValueError(f"{PACKAGE} has SHA-256 {digest}, expected {SHA256}")
    return data


def fetch(project: Path) -> Path:
    target = project / "bin" / "lv2" / BUNDLE
    target.mkdir(parents=True, exist_ok=True)
    archive = zstd.decompress(package(project / "out" / "cache"))
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        for name in (LIBRARY, *(f"{plugin}.ttl" for plugin in PLUGINS)):
            member = tar.extractfile(f"{SOURCE}/{name}")
            if member is None:
                raise FileNotFoundError(f"{SOURCE}/{name} is not in {PACKAGE}")
            (target / name).write_bytes(member.read())
    (target / "manifest.ttl").write_bytes(manifest().encode("utf-8"))
    return target


def main() -> None:
    sys.stdout.write(f"{fetch(Path(__file__).resolve().parent.parent)}\n")


if __name__ == "__main__":
    main()

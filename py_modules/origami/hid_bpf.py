# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

"""HID-BPF programs, loaded with the system's libbpf.

A HID-BPF program is a struct_ops map of the kernel's hid_bpf_ops: the kernel calls its hooks for
one HID device, whose id (the number after the dot in 0003:0B05:1B4C.0007) the map carries in its
first member. The link that attaches it belongs to this process, so the program leaves the device
when ORIGAMI closes it, and also when the process ends however it ends: nothing outlives the plugin.

Decky's Python bundles ctypes, and Bazzite ships libbpf for udev-hid-bpf.
"""

import ctypes
import errno
import functools
import os
from pathlib import Path

LIBBPF = "libbpf.so.1"

_POINTER = ctypes.c_void_p
_SIGNATURES: dict[str, tuple[list[type], type | None]] = {
    "bpf_object__open_file": ([ctypes.c_char_p, _POINTER], _POINTER),
    "bpf_object__load": ([_POINTER], ctypes.c_int),
    "bpf_object__close": ([_POINTER], None),
    "bpf_object__find_map_by_name": ([_POINTER, ctypes.c_char_p], _POINTER),
    "bpf_map__initial_value": ([_POINTER, ctypes.POINTER(ctypes.c_size_t)], _POINTER),
    "bpf_map__attach_struct_ops": ([_POINTER], _POINTER),
    "bpf_map__update_elem": (
        [_POINTER, _POINTER, ctypes.c_size_t, _POINTER, ctypes.c_size_t, ctypes.c_uint64],
        ctypes.c_int,
    ),
    "bpf_link__destroy": ([_POINTER], ctypes.c_int),
}


@functools.cache
def _libbpf() -> ctypes.CDLL:
    """libbpf with the signatures ORIGAMI calls; raises OSError when the system has none."""
    library = ctypes.CDLL(LIBBPF, use_errno=True)
    for name, (argtypes, restype) in _SIGNATURES.items():
        function = getattr(library, name)
        function.argtypes = argtypes
        function.restype = restype
    return library


class HidBpfProgram:
    """A HID-BPF program attached to one HID device until it is closed."""

    def __init__(self, path: Path, ops: str, hid_id: int) -> None:
        """Load the object file and attach its struct_ops map `ops`; raise OSError on failure."""
        library = _libbpf()
        bpf_object = library.bpf_object__open_file(os.fsencode(path), None)
        if not bpf_object:
            raise _last_error(f"Cannot open {path}")
        try:
            link = _load_and_attach(library, bpf_object, path, ops, hid_id)
        except BaseException:
            library.bpf_object__close(bpf_object)
            raise
        self.hid_id = hid_id
        self._library = library
        self._object: int | None = bpf_object
        self._link: int | None = link

    def update(self, map_name: str, key: bytes, value: bytes) -> None:
        """Write one element of a map the program reads; raise OSError on failure."""
        if self._object is None:
            raise OSError(errno.EBADF, "The program is closed")
        bpf_map = _find_map(self._library, self._object, map_name)
        result = self._library.bpf_map__update_elem(bpf_map, key, len(key), value, len(value), 0)
        _check(result, f"Cannot write {map_name}")

    def close(self) -> None:
        """Take the program off the device; closing it again does nothing."""
        if self._object is None:
            return
        self._library.bpf_link__destroy(self._link)
        self._library.bpf_object__close(self._object)
        self._object = self._link = None


def _load_and_attach(
    library: ctypes.CDLL, bpf_object: int, path: Path, ops: str, hid_id: int
) -> int:
    """Point the struct_ops map at the device, load the object and attach; return the link."""
    ops_map = _find_map(library, bpf_object, ops)
    size = ctypes.c_size_t()
    data = library.bpf_map__initial_value(ops_map, ctypes.byref(size))
    if not data or size.value < ctypes.sizeof(ctypes.c_int):
        raise OSError(errno.EINVAL, f"{ops} in {path.name} is not a struct_ops map")
    ctypes.c_int.from_address(data).value = hid_id
    _check(library.bpf_object__load(bpf_object), f"Cannot load {path.name}")
    link = library.bpf_map__attach_struct_ops(ops_map)
    if not link:
        raise _last_error(f"Cannot attach {ops} to HID device {hid_id}")
    return link


def _find_map(library: ctypes.CDLL, bpf_object: int, name: str) -> int:
    bpf_map = library.bpf_object__find_map_by_name(bpf_object, name.encode())
    if not bpf_map:
        raise OSError(errno.ENOENT, f"No map {name} in the program")
    return bpf_map


def _check(result: int, message: str) -> None:
    # libbpf returns a negative errno from calls that return an int.
    if result < 0:
        raise OSError(-result, f"{message}: {os.strerror(-result)}")


def _last_error(message: str) -> OSError:
    # Calls that return a pointer give NULL and set errno.
    code = ctypes.get_errno()
    return OSError(code, f"{message}: {os.strerror(code)}")

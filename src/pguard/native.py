"""ctypes binding to the C++20 signal core (cpp/). Results must match signal.features.extract."""

from __future__ import annotations

import ctypes as C
import os
import sys
from collections.abc import Iterable
from pathlib import Path

from .acquisition.windows_wifi import Sample
from .signal.features import Params, State, WindowFeatures

ABI_VERSION = 1
_FLAG_NAMES = ((1, "no_samples"), (2, "corrupt_samples"), (4, "low_coverage"), (8, "stale"))
_STATES = (State.NO_DATA, State.UNCERTAIN, State.QUIET, State.MOTION)
_EPS = 1e-9


class NativeUnavailable(RuntimeError):
    """The native core is not built or has an incompatible ABI."""


class _Params(C.Structure):
    _fields_ = [(n, C.c_double) for n in (
        "window_s", "expected_hz", "stale_s", "min_coverage", "min_quality",
        "motion_threshold_db")]


class _Window(C.Structure):
    _fields_ = [("t_start", C.c_double), ("t_end", C.c_double), ("n_valid", C.c_size_t),
                ("n_corrupt", C.c_size_t), ("quality", C.c_double), ("mean_dbm", C.c_double),
                ("motion_energy", C.c_double), ("has_mean", C.c_int32),
                ("has_energy", C.c_int32), ("flags", C.c_uint32), ("state", C.c_int32)]


def _candidates() -> list[Path]:
    names = ("pguard_native.dll", "libpguard_native.so", "libpguard_native.dylib")
    roots = [Path(__file__).resolve().parents[2] / "cpp" / "build"]
    if env := os.environ.get("PGUARD_NATIVE_LIB"):
        return [Path(env)]
    return [root / name for root in roots for name in names]


_lib: C.CDLL | None = None


def load() -> C.CDLL:
    global _lib
    if _lib is not None:
        return _lib
    for path in _candidates():
        if not path.is_file():
            continue
        if sys.platform == "win32":
            os.add_dll_directory(str(path.parent))
        try:
            lib = C.CDLL(str(path))
        except OSError as exc:
            raise NativeUnavailable(f"cannot load {path}: {exc}") from exc
        lib.pg_abi_version.restype = C.c_int32
        if lib.pg_abi_version() != ABI_VERSION:
            raise NativeUnavailable(f"{path} has ABI {lib.pg_abi_version()}, expected {ABI_VERSION}")
        lib.pg_extract_series.restype = C.c_int64
        lib.pg_extract_series.argtypes = [
            C.POINTER(C.c_double), C.POINTER(C.c_int32), C.c_size_t, C.c_double, C.c_double,
            C.POINTER(_Params), C.POINTER(_Window), C.c_size_t]
        lib.pg_ring_create.restype = C.c_void_p
        lib.pg_ring_create.argtypes = [C.c_size_t]
        lib.pg_ring_destroy.argtypes = [C.c_void_p]
        lib.pg_ring_push.restype = C.c_int32
        lib.pg_ring_push.argtypes = [C.c_void_p, C.c_double, C.c_int32]
        lib.pg_ring_drain.restype = C.c_size_t
        lib.pg_ring_drain.argtypes = [C.c_void_p, C.POINTER(C.c_double), C.POINTER(C.c_int32),
                                      C.c_size_t]
        lib.pg_ring_dropped.restype = C.c_uint64
        lib.pg_ring_dropped.argtypes = [C.c_void_p]
        _lib = lib
        return lib
    raise NativeUnavailable("native core not built: cmake -S cpp -B cpp/build && "
                            "cmake --build cpp/build")


def extract_native(samples: Iterable[Sample], t0: float, t1: float, p: Params) -> list[WindowFeatures]:
    lib = load()
    data = list(samples)
    n = len(data)
    t = (C.c_double * n)(*(s.t for s in data))
    rssi = (C.c_int32 * n)(*(s.rssi_dbm for s in data))
    params = _Params(p.window_s, p.expected_hz, p.stale_s, p.min_coverage, p.min_quality,
                     p.motion_threshold_db)
    capacity = max(0, int((t1 - t0) / p.window_s + _EPS)) if p.window_s > 0 else 0
    out = (_Window * max(capacity, 1))()
    count = lib.pg_extract_series(t, rssi, n, t0, t1, C.byref(params), out, capacity)
    if count == -1:
        raise ValueError("invalid parameters rejected by the native core")
    if count < 0:
        raise RuntimeError(f"native extract failed with status {count}")
    return [
        WindowFeatures(
            t_start=w.t_start, t_end=w.t_end, n_valid=w.n_valid, n_corrupt=w.n_corrupt,
            quality=w.quality, flags=tuple(name for bit, name in _FLAG_NAMES if w.flags & bit),
            mean_dbm=w.mean_dbm if w.has_mean else None,
            motion_energy=w.motion_energy if w.has_energy else None,
            state=_STATES[w.state], params_version=p.version,
        )
        for w in out[:count]
    ]


class Ring:
    """The C driver shim's ring buffer. Overwritten samples are counted, never hidden."""

    def __init__(self, capacity: int) -> None:
        self._lib = load()
        self._capacity = capacity
        self._ring = self._lib.pg_ring_create(capacity)
        if not self._ring:
            raise ValueError("capacity must be positive")

    def push(self, t: float, rssi: int) -> bool:
        return bool(self._lib.pg_ring_push(self._ring, t, rssi))

    def drain(self) -> tuple[list[float], list[int]]:
        t = (C.c_double * self._capacity)()
        rssi = (C.c_int32 * self._capacity)()
        n = self._lib.pg_ring_drain(self._ring, t, rssi, self._capacity)
        return list(t[:n]), list(rssi[:n])

    @property
    def dropped(self) -> int:
        return int(self._lib.pg_ring_dropped(self._ring))

    def close(self) -> None:
        if self._ring:
            self._lib.pg_ring_destroy(self._ring)
            self._ring = None

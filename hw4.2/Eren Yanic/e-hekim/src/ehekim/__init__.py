"""e-hekim — Turkish medical semantic search and RAG over hospital articles.

Importing this package applies one environment compatibility fix before torch is
loaded; see :func:`_disable_torch_native_jit_if_unbuildable`.
"""

from __future__ import annotations

import os
import sysconfig
from pathlib import Path

__version__ = "1.0.0"


def _disable_torch_native_jit_if_unbuildable() -> bool:
    """Fall back to aten kernels when Triton cannot JIT-compile on this machine.

    torch >= 2.13 routes a few aten ops (e.g. ``bmm`` for the outer products in
    Gemma-3 RoPE, which this project's embedding model uses) through Triton
    kernels. Triton compiles a small CUDA shim at first use with the system
    compiler, which requires the CPython development headers. On a machine with
    only the Python *runtime* installed (no ``python3-devel`` / ``python3-dev``)
    that compile fails with ``Python.h: No such file or directory`` and the
    first embedding call dies — even though the model itself loaded fine.

    ``TORCH_DISABLE_NATIVE_JIT=1`` makes torch use its ordinary aten kernels
    instead. The results are numerically equivalent; only the fused fast path is
    given up. Setting it here, rather than asking every user to export a
    variable, keeps ``uv run`` working out of the box on a stock system. It must
    be set before torch is imported, hence its placement in the package
    ``__init__``.

    An explicit value already present in the environment always wins.
    """
    if os.environ.get("TORCH_DISABLE_NATIVE_JIT"):
        return False
    include_dir = sysconfig.get_config_var("INCLUDEPY")
    if include_dir and Path(include_dir, "Python.h").exists():
        return False  # headers present, let Triton do its thing
    os.environ["TORCH_DISABLE_NATIVE_JIT"] = "1"
    return True


TORCH_NATIVE_JIT_DISABLED = _disable_torch_native_jit_if_unbuildable()

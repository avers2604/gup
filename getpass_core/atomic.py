"""Atomic replacement of generated files in their destination directory."""
from contextlib import contextmanager
import os
import tempfile


@contextmanager
def atomic_output(path):
    path = os.path.abspath(path)
    fd, temporary = tempfile.mkstemp(prefix=".get-", suffix=os.path.splitext(path)[1],
                                     dir=os.path.dirname(path))
    os.close(fd)
    try:
        yield temporary
        with open(temporary, "r+b") as stream:
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

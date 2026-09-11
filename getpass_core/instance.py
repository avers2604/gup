"""Process lifetime lock: a data directory has a single desktop writer."""
import os
from contextlib import contextmanager


@contextmanager
def single_instance(directory):
    os.makedirs(directory, exist_ok=True)
    stream = open(os.path.join(directory, ".application.lock"), "a+b")
    try:
        stream.seek(0)
        stream.write(b"0")
        stream.flush()
        stream.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        stream.close()
        raise RuntimeError("Программа уже открыта с этим каталогом данных") from None
    try:
        yield
    finally:
        stream.close()

"""Directory-anchored artifact I/O; these are file integrity controls, not isolation."""

from contextlib import contextmanager
import os
from pathlib import Path
from uuid import uuid4
from .config import ConfigError


@contextmanager
def anchored_parent(root, relative, create=False):
    parts = Path(relative).parts
    if Path(relative).is_absolute() or not parts or ".." in parts:
        raise ConfigError("Invalid artifact path.")
    descriptors = []
    try:
        descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        descriptors.append(descriptor)
        for part in parts[:-1]:
            if create:
                try:
                    os.mkdir(part, mode=0o700, dir_fd=descriptor)
                except FileExistsError:
                    pass
            descriptor = os.open(
                part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor
            )
            descriptors.append(descriptor)
        yield descriptor, parts[-1]
    except OSError:
        raise ConfigError(
            "Artifact directory is unavailable or contains a symlink."
        ) from None
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def write_artifact(root, relative, raw):
    if os.name == "nt":
        # The caller rejects symlinks and junctions; Windows lacks dir_fd support.
        path = Path(root) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        for parent in [path, *path.parents]:
            if parent.is_symlink() or getattr(parent, "is_junction", lambda: False)():
                raise ConfigError(
                    "Artifact paths cannot contain symlinks or junctions."
                )
        import tempfile

        descriptor, temporary = tempfile.mkstemp(
            dir=path.parent, prefix=".eliot-write-"
        )
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError:
                if path.read_bytes() != raw:
                    raise ConfigError(
                        "That artifact already exists with different content. Choose a new filename."
                    ) from None
        finally:
            Path(temporary).unlink(missing_ok=True)
        return
    with anchored_parent(root, relative, True) as (parent, name):
        temporary = ".eliot-write-" + uuid4().hex
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=parent,
        )
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(
                    temporary,
                    name,
                    src_dir_fd=parent,
                    dst_dir_fd=parent,
                    follow_symlinks=False,
                )
            except FileExistsError:
                descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent)
                with os.fdopen(descriptor, "rb") as stream:
                    if stream.read(len(raw) + 1) != raw:
                        raise ConfigError(
                            "That artifact already exists with different content. Choose a new filename."
                        ) from None
            os.fsync(parent)
        finally:
            os.unlink(temporary, dir_fd=parent)


def read_artifact(root, relative, maximum):
    if os.name == "nt":
        path = Path(root) / relative
        for parent in [path, *path.parents]:
            if parent.is_symlink() or getattr(parent, "is_junction", lambda: False)():
                raise ConfigError(
                    "Artifact paths cannot contain symlinks or junctions."
                )
        with path.open("rb") as stream:
            raw = stream.read(maximum + 1)
    else:
        with anchored_parent(root, relative) as (parent, name):
            descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent)
            with os.fdopen(descriptor, "rb") as stream:
                raw = stream.read(maximum + 1)
    if len(raw) > maximum:
        raise ConfigError("The artifact exceeds the input-size limit.")
    return raw

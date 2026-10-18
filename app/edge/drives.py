"""Which drives an edge device can see, and where a library's folder is on them.

Linux: the drives are mounted below the folders bind-mounted into the container (/media, /mnt, /run/media, ...);
each mount's device number leads to its filesystem UUID in udev's database.
Windows: ludexis-edge maps each drive letter to /drives/<letter> and writes the letters' volume serials to
/state/drives.json, since Docker Desktop shows no device information.
"""

import json
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath

UDEV_DATA = Path("/run/udev/data")
WINDOWS_DRIVES = Path("/drives")
STATE_DIR = Path(os.environ.get("EDGE_STATE_DIR", "/state"))
DEFAULT_ROOTS = ("/media", "/mnt", "/run/media")


def drive_key(drive_id: str) -> str:
    """Linux shows an NTFS drive's 64-bit serial and Windows its low 32 bits; both end in the same 8 hex digits."""
    return drive_id.replace("-", "").lower()[-8:]


@dataclass
class Drive:
    id: str
    mount: str
    label: str | None = None
    total: int | None = None
    free: int | None = None

    def report(self) -> dict:
        return {"id": self.id, "mount": self.mount, "label": self.label, "total": self.total, "free": self.free}


class EdgePathError(Exception):
    """A library folder the device cannot reach; the message is shown in the web app."""


def roots() -> list[str]:
    extra = [root for root in os.environ.get("EDGE_ROOTS", "").split(":") if root]
    return [*DEFAULT_ROOTS, *extra]


def _usage(path: str) -> tuple[int | None, int | None]:
    try:
        usage = shutil.disk_usage(path)
        return usage.total, usage.free
    except OSError:
        return None, None


def _udev(major_minor: str) -> dict[str, str]:
    try:
        lines = (UDEV_DATA / f"b{major_minor}").read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    return dict(line[2:].split("=", 1) for line in lines if line.startswith("E:") and "=" in line)


def _unescape(value: str) -> str:
    # mountinfo writes spaces and other special characters as octal escapes.
    return re.sub(r"\\([0-7]{3})", lambda match: chr(int(match.group(1), 8)), value)


def linux_drives(mountinfo: str | None = None) -> list[Drive]:
    """Filesystems mounted strictly below one of the roots; the roots themselves are the host's system disk."""
    text = mountinfo if mountinfo is not None else Path("/proc/self/mountinfo").read_text(encoding="utf-8")
    bases = roots()
    drives: dict[str, Drive] = {}
    for line in text.splitlines():
        fields = line.split()
        if len(fields) < 5:
            continue
        mount = _unescape(fields[4])
        if not any(mount.startswith(base.rstrip("/") + "/") for base in bases):
            continue
        properties = _udev(fields[2])
        uuid = properties.get("ID_FS_UUID")
        if not uuid or uuid in drives:
            continue
        total, free = _usage(mount)
        drives[uuid] = Drive(uuid, mount, properties.get("ID_FS_LABEL"), total, free)
    return list(drives.values())


def windows_drives() -> list[Drive]:
    try:
        letters = json.loads((STATE_DIR / "drives.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        letters = {}
    drives = []
    for letter, info in sorted(letters.items()):
        mount = WINDOWS_DRIVES / letter.upper()
        if info.get("serial") and mount.is_dir():
            total, free = _usage(str(mount))
            drives.append(Drive(info["serial"], f"{letter.upper()}:\\", info.get("label"), total, free))
    return drives


def visible_drives(os_name: str) -> list[Drive]:
    return windows_drives() if os_name == "windows" else linux_drives()


def _find(drives: list[Drive], drive_id: str | None) -> Drive | None:
    if not drive_id:
        return None
    return next((drive for drive in drives if drive_key(drive.id) == drive_key(drive_id)), None)


def library_root(os_name: str, library: dict, drives: list[Drive]) -> tuple[Path, Drive | None, str]:
    """The folder to scan inside the container, the drive holding it and the folder's path below that drive."""
    known = _find(drives, library.get("drive_id"))
    if os_name == "windows":
        typed = PureWindowsPath(library["path"])
        if not typed.drive or not typed.drive.endswith(":"):
            raise EdgePathError(f"{library['path']} is not a Windows path such as E:\\Games")
        subpath = library.get("drive_subpath") if known else PurePosixPath(*typed.parts[1:]).as_posix()
        letter = known.mount[0] if known else typed.drive[0].upper()
        drive = known or next((drive for drive in drives if drive.mount[0] == letter), None)
        root = WINDOWS_DRIVES / letter / (subpath or "")
        if not (WINDOWS_DRIVES / letter).is_dir():
            raise EdgePathError(f"Drive {letter}: is not mapped into the edge device; plug it in and run: ludexis-edge restart")
        return root, drive, subpath or ""

    if known:
        subpath = library.get("drive_subpath") or ""
        return Path(str(PurePosixPath(known.mount) / subpath)), known, subpath
    root = PurePosixPath(library["path"])
    if not any(str(root) == base or str(root).startswith(base.rstrip("/") + "/") for base in roots()):
        raise EdgePathError(f"{root} is outside the folders the edge device can see; add its parent folder to EDGE_ROOTS in .env and run: ludexis-edge restart")
    # The drive is the deepest mount that holds the folder.
    holders = [drive for drive in drives if str(root) == drive.mount or str(root).startswith(drive.mount.rstrip("/") + "/")]
    drive = max(holders, key=lambda candidate: len(candidate.mount), default=None)
    subpath = root.relative_to(drive.mount).as_posix() if drive else ""
    return Path(str(root)), drive, "" if subpath == "." else subpath

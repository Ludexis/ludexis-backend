import io
import json
import uuid
import zipfile

import pytest
from fastapi.testclient import TestClient

from main import app
from app.edge import drives
from app.edge.drives import Drive, EdgePathError, library_root, linux_drives

client = TestClient(app)

MOUNTINFO = """\
22 1 8:2 / / rw,relatime shared:1 - ext4 /dev/sda2 rw
35 22 8:2 /media /media ro,relatime master:1 - ext4 /dev/sda2 rw
36 35 8:17 / /media/me/My\\040Games ro,relatime master:9 - ntfs3 /dev/sdb1 ro
37 22 8:2 /mnt /mnt ro,relatime master:1 - ext4 /dev/sda2 rw
"""


@pytest.fixture
def udev(tmp_path, monkeypatch):
    monkeypatch.setattr(drives, "UDEV_DATA", tmp_path)
    (tmp_path / "b8:2").write_text("E:ID_FS_UUID=system-disk\n")
    (tmp_path / "b8:17").write_text("E:ID_FS_UUID=0123456789ABCDEF\nE:ID_FS_LABEL=Games\n")
    return tmp_path


def test_linux_lists_drives_below_the_roots_but_not_the_system_disk(udev):
    found = linux_drives(MOUNTINFO)
    assert [(drive.id, drive.mount, drive.label) for drive in found] == [("0123456789ABCDEF", "/media/me/My Games", "Games")]


def test_linux_finds_a_known_drive_wherever_it_is_mounted_now():
    library = {"path": "/media/me/Old/Games", "drive_id": "0123456789ABCDEF", "drive_subpath": "Games"}
    root, drive, subpath = library_root("linux", library, [Drive("0123456789ABCDEF", "/mnt/ludexis/0123456789ABCDEF")])
    assert str(root).replace("\\", "/") == "/mnt/ludexis/0123456789ABCDEF/Games"
    assert subpath == "Games"


def test_linux_learns_the_drive_from_the_typed_path():
    root, drive, subpath = library_root("linux", {"path": "/media/me/USB/Games/VN"}, [Drive("AB12-CD34", "/media/me/USB")])
    assert drive.id == "AB12-CD34"
    assert subpath == "Games/VN"


def test_linux_refuses_folders_it_cannot_see():
    with pytest.raises(EdgePathError, match="EDGE_ROOTS"):
        library_root("linux", {"path": "/home/me/Games"}, [])


def test_windows_follows_a_drive_to_its_new_letter(tmp_path, monkeypatch):
    monkeypatch.setattr(drives, "WINDOWS_DRIVES", tmp_path)
    (tmp_path / "F").mkdir()
    library = {"path": "E:\\Games", "drive_id": "0123456789ABCDEF", "drive_subpath": "Games"}
    root, drive, subpath = library_root("windows", library, [Drive("89ABCDEF", "F:\\")])
    assert root == tmp_path / "F" / "Games"


def test_windows_explains_an_unmapped_letter(tmp_path, monkeypatch):
    monkeypatch.setattr(drives, "WINDOWS_DRIVES", tmp_path)
    with pytest.raises(EdgePathError, match="ludexis-edge restart"):
        library_root("windows", {"path": "Z:\\Games"}, [])


def test_the_bundle_needs_the_current_token_and_carries_it():
    headers = {"Authorization": f"Bearer {client.post('/api/auth/login', json={'username': 'admin', 'password': 'Admin123!'}).json()['access_token']}"}
    edge = client.post("/api/edge-devices/", headers=headers, json={"name": f"Bundle-{uuid.uuid4().hex[:8]}"}).json()

    assert client.post(f"/api/edge-devices/{edge['id']}/bundle", headers=headers, json={"os": "linux", "token": "ldx_wrong"}).status_code == 403

    for os_name, installer in (("linux", "install.sh"), ("windows", "install.ps1")):
        response = client.post(f"/api/edge-devices/{edge['id']}/bundle", headers=headers, json={"os": os_name, "token": edge["token"]})
        assert response.status_code == 200
        archive = zipfile.ZipFile(io.BytesIO(response.content))
        names = set(archive.namelist())
        assert {"ludexis-edge/.env", "ludexis-edge/docker-compose.yml", f"ludexis-edge/{installer}"} <= names
        assert f"LUDEXIS_EDGE_TOKEN={edge['token']}" in archive.read("ludexis-edge/.env").decode()
    assert archive.getinfo("ludexis-edge/install.ps1").external_attr >> 16 == 0o644


def _scan(tmp_path, monkeypatch, known, store_new):
    from app.edge import agent as agent_module

    for name, data in {"Same.zip": b"a" * 10, "Resized.zip": b"b" * 20, "New.zip": b"c" * 5}.items():
        (tmp_path / name).write_bytes(data)
    edge = agent_module.EdgeAgent("http://server", "ldx_test", "linux")
    sent = {}
    monkeypatch.setattr(agent_module, "library_root", lambda os_name, library, found: (tmp_path, None, None))
    monkeypatch.setattr(edge, "_progress", lambda *args: None)
    monkeypatch.setattr(edge, "_call", lambda method, path, **kwargs: {"entries": known})
    monkeypatch.setattr(edge, "_send", lambda job_id, report: sent.update(report))
    hashed = []
    monkeypatch.setattr(edge.scanner, "_compute_file_hash", lambda path, on_chunk=None: hashed.append(path.name) or "h" * 64)
    edge.scan("job", {"id": "lib", "name": "Games", "path": str(tmp_path)}, store_new=store_new)
    return sent, hashed


def test_an_automatic_edge_scan_hashes_nothing_and_reports_new_or_resized_files_as_pending(tmp_path, monkeypatch):
    known = {"Same.zip": [10, "2020-01-01T00:00:00+00:00", True], "Resized.zip": [10, "2020-01-01T00:00:00+00:00", True]}

    sent, hashed = _scan(tmp_path, monkeypatch, known, store_new=False)

    assert hashed == []
    assert [item["relative_path"] for item in sent["items"]] == ["Same.zip"]
    assert sorted(sent["pending"]) == ["New.zip", "Resized.zip"]

    sent, hashed = _scan(tmp_path, monkeypatch, known, store_new=True)
    # A scan someone started hashes the new, resized and re-dated files, never sends pending.
    assert sorted(hashed) == ["New.zip", "Resized.zip", "Same.zip"]
    assert "pending" not in sent

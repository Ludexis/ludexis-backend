"""Prints what the edge device sees: the server, its libraries, and whether each library's drive is here.

Run inside the edge container by ludexis-edge status and restart.
"""

import os
import sys
import time

import requests

from app import __version__
from app.edge.drives import EdgePathError, library_root, visible_drives


def main() -> int:
    server = os.environ.get("LUDEXIS_SERVER_URL", "").rstrip("/")
    token = os.environ.get("LUDEXIS_EDGE_TOKEN", "")
    os_name = os.environ.get("EDGE_OS", "linux")
    # Right after the container starts its first connection can fail, so try a few times.
    for attempt in range(3):
        try:
            response = requests.get(f"{server}/api/edge/agent/libraries", headers={"Authorization": f"Bearer {token}"}, timeout=15)
            break
        except requests.RequestException as exc:
            if attempt == 2:
                print(f"Server     {server}: not reachable ({exc})")
                return 1
            time.sleep(3)
    if response.status_code == 401:
        print(f"Server     {server}: the token was refused; download a new bundle from Admin > Edge")
        return 1
    response.raise_for_status()
    libraries = response.json()
    drives = visible_drives(os_name)
    print(f"Server     {server}: connected (edge {__version__})")
    print(f"Drives     {', '.join(f'{drive.label or drive.id} at {drive.mount}' for drive in drives) or 'none'}")
    if not libraries:
        print("Libraries  none yet; add one on the server under Admin > Libraries with this device as its location")
    problems = 0
    for library in libraries:
        try:
            root, _, _ = library_root(os_name, library, drives)
            state = "ready" if root.is_dir() else ("drive not connected" if library.get("drive_id") else "folder not found")
        except EdgePathError as exc:
            state = str(exc)
        problems += state != "ready"
        print(f"Library    {library['name']} ({library['path']}): {state}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

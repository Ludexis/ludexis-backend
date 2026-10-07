import os
import subprocess
import sys
from pathlib import Path


def reveal(path: Path) -> bool:
    """Show the path in the file manager of the machine running the server.

    Returns False where there is no desktop to show it on, such as a container.
    """
    if sys.platform == "win32":
        # Explorer wants the path quoted after the comma; Windows paths cannot contain quotes.
        subprocess.Popen(f'explorer /select,"{path}"')
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(path)])
    elif os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
        subprocess.Popen(["xdg-open", str(path if path.is_dir() else path.parent)])
    else:
        return False
    return True

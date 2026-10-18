Ludexis edge device for Windows

1. Install Docker Desktop and start it once.
2. In this folder, in PowerShell: powershell -ExecutionPolicy Bypass -File install.ps1
   It copies the device to %LOCALAPPDATA%\Ludexis\edge, adds the ludexis-edge command and starts it.
3. On the server, add a library under Admin > Libraries with this device as its location and the folder's
   path as Windows shows it (for example E:\Games), then run: ludexis-edge restart

After the first scan the library is known by its drive's serial number, so it is found again under another
drive letter. Docker Desktop only sees drives that were there when the container started: after plugging a
drive in, run ludexis-edge restart. Mapped network drives are not visible to Docker Desktop.

Commands: ludexis-edge start | restart | stop | status | logs | update

Ludexis edge device for Linux

1. Install Docker Engine with the Compose plugin.
2. In this folder: sudo ./install.sh
   It copies the device to /opt/ludexis-edge, installs the ludexis-edge command and a udev rule, and starts it.
3. On the server, add a library under Admin > Libraries with this device as its location and the folder's
   path as this machine shows it (for example /media/you/Games). The device scans it at its next check-in.

After the first scan the library is known by its drive's UUID: plugging that drive in mounts it read-only
(unless the desktop mounts it first) and starts the edge device, which scans it when autoscan is on.

Commands: ludexis-edge start | restart | stop | status | logs | update
Folders outside /media, /mnt and /run/media: add them to EDGE_ROOTS in /opt/ludexis-edge/.env, then
run ludexis-edge restart.

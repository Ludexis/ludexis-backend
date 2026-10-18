#!/bin/sh
# Installs the Ludexis edge device: run once from the unzipped bundle with: sudo ./install.sh
set -eu

[ "$(id -u)" = 0 ] || { echo "Run it with sudo: sudo ./install.sh" >&2; exit 1; }
command -v docker >/dev/null || { echo "Docker is not installed (https://docs.docker.com/engine/install/)" >&2; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "The Docker Compose plugin is not installed" >&2; exit 1; }

DIR=/opt/ludexis-edge
HERE=$(cd "$(dirname "$0")" && pwd)

mkdir -p "$DIR/state" "$DIR/providers" /usr/local/lib/ludexis-edge /mnt/ludexis
if [ "$HERE" != "$DIR" ]; then
  cp "$HERE/docker-compose.yml" "$HERE/.env" "$DIR/"
fi
sed -i "s/^EDGE_HOSTNAME=.*/EDGE_HOSTNAME=$(hostname)/" "$DIR/.env"
chmod 600 "$DIR/.env"
# The container runs as uid 1000 and writes which drives belong to its libraries into state/.
chown -R 1000:1000 "$DIR/state"

install -m 755 "$HERE/ludexis-edge" /usr/local/bin/ludexis-edge
install -m 755 "$HERE/ludexis-drive" /usr/local/lib/ludexis-edge/ludexis-drive
install -m 644 "$HERE/ludexis-drive@.service" /etc/systemd/system/ludexis-drive@.service
install -m 644 "$HERE/99-ludexis-edge.rules" /etc/udev/rules.d/99-ludexis-edge.rules
systemctl daemon-reload
udevadm control --reload

/usr/local/bin/ludexis-edge start
echo
echo "Installed. Add a library on the server (Admin > Libraries) with this device as its location."
echo "From then on, plugging in that drive mounts it read-only and starts the edge device."

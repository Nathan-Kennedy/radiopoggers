#!/usr/bin/env bash
set -euo pipefail

install_dir="${1:-$HOME/azuracast}"

mkdir -p "$install_dir"
cd "$install_dir"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker nao esta disponivel dentro desta distro WSL."
  echo "Abra Docker Desktop > Settings > Resources > WSL Integration e habilite Ubuntu-24.04."
  exit 10
fi

if [ ! -f docker.sh ]; then
  curl -fsSL https://raw.githubusercontent.com/AzuraCast/AzuraCast/main/docker.sh > docker.sh
  chmod a+x docker.sh
fi

echo ""
echo "Instalador oficial baixado em $install_dir/docker.sh"
echo "Quando ele perguntar as portas, use: HTTP=8080, HTTPS=8443, SFTP=2022."
echo ""

./docker.sh install


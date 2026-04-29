#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -f .env ]; then
  echo "ERROR: No existe el archivo .env. Copiá .env.example y completá los valores."
  exit 1
fi

echo "==> Actualizando código..."
git pull

echo "==> Construyendo y reiniciando..."
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

echo "==> Limpiando imágenes viejas..."
docker image prune -f

echo "==> Listo."

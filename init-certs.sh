#!/bin/bash
# Run this ONCE on first deploy to obtain the initial Let's Encrypt certificate.
# After this, the certbot service in docker-compose.prod.yml auto-renews.
#
# Usage:
#   chmod +x init-certs.sh
#   ./init-certs.sh yourdomain.com your@email.com

set -e

DOMAIN=${1:?Usage: ./init-certs.sh DOMAIN EMAIL}
EMAIL=${2:?Usage: ./init-certs.sh DOMAIN EMAIL}

echo "==> Starting nginx on port 80 for ACME challenge..."
docker compose -f docker-compose.prod.yml up -d nginx

echo "==> Waiting for nginx to be ready..."
sleep 3

echo "==> Requesting certificate for $DOMAIN..."
docker compose -f docker-compose.prod.yml run --rm certbot certonly \
  --webroot \
  --webroot-path /var/www/certbot \
  --email "$EMAIL" \
  --agree-tos \
  --no-eff-email \
  -d "$DOMAIN"

echo "==> Reloading nginx with SSL config..."
docker compose -f docker-compose.prod.yml restart nginx

echo ""
echo "Done! Certificate obtained. Run the full stack with:"
echo "  docker compose -f docker-compose.prod.yml up -d"

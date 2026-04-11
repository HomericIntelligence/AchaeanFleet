#!/usr/bin/env bash
# generate-certs.sh — Generate a local CA + TLS certificates for the homeric-mesh.
#
# Creates:
#   tls/certs/ca.crt          — Root CA certificate (trusted by all containers)
#   tls/certs/ca.key          — Root CA private key  (NEVER commit; in .gitignore)
#   tls/certs/caddy.crt       — Caddy TLS server certificate
#   tls/certs/caddy.key       — Caddy private key
#   tls/certs/nats.crt        — NATS TLS server certificate
#   tls/certs/nats.key        — NATS private key
#
# Usage:
#   bash tls/generate-certs.sh
#   bash tls/generate-certs.sh --days 3650   # 10-year certs for dev
#
# Requires: openssl (present in all base images via ca-certificates dep)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CERTS_DIR="${SCRIPT_DIR}/certs"
DAYS="${2:-825}"  # 825 days (~2.25 years) — below Apple's 2-year browser limit

# Parse --days flag
while [[ $# -gt 0 ]]; do
  case "$1" in
    --days) DAYS="$2"; shift 2 ;;
    *) shift ;;
  esac
done

mkdir -p "${CERTS_DIR}"

echo "==> Generating local CA..."
openssl genrsa -out "${CERTS_DIR}/ca.key" 4096

openssl req -new -x509 \
  -key "${CERTS_DIR}/ca.key" \
  -out "${CERTS_DIR}/ca.crt" \
  -days "${DAYS}" \
  -subj "/C=US/O=HomericIntelligence/CN=Homeric-Mesh-CA"

echo "==> Generating Caddy TLS certificate (SAN: caddy, 172.20.0.1, localhost)..."
openssl genrsa -out "${CERTS_DIR}/caddy.key" 2048

openssl req -new \
  -key "${CERTS_DIR}/caddy.key" \
  -out "${CERTS_DIR}/caddy.csr" \
  -subj "/C=US/O=HomericIntelligence/CN=caddy"

openssl x509 -req \
  -in "${CERTS_DIR}/caddy.csr" \
  -CA "${CERTS_DIR}/ca.crt" \
  -CAkey "${CERTS_DIR}/ca.key" \
  -CAcreateserial \
  -out "${CERTS_DIR}/caddy.crt" \
  -days "${DAYS}" \
  -extfile <(cat <<EOF
subjectAltName = DNS:caddy,DNS:localhost,IP:127.0.0.1,IP:172.20.0.1
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
EOF
)

rm -f "${CERTS_DIR}/caddy.csr"

echo "==> Generating NATS TLS certificate (SAN: nats, localhost)..."
openssl genrsa -out "${CERTS_DIR}/nats.key" 2048

openssl req -new \
  -key "${CERTS_DIR}/nats.key" \
  -out "${CERTS_DIR}/nats.csr" \
  -subj "/C=US/O=HomericIntelligence/CN=nats"

openssl x509 -req \
  -in "${CERTS_DIR}/nats.csr" \
  -CA "${CERTS_DIR}/ca.crt" \
  -CAkey "${CERTS_DIR}/ca.key" \
  -CAcreateserial \
  -out "${CERTS_DIR}/nats.crt" \
  -days "${DAYS}" \
  -extfile <(cat <<EOF
subjectAltName = DNS:nats,DNS:localhost,IP:127.0.0.1
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
EOF
)

rm -f "${CERTS_DIR}/nats.csr"

# Restrict private key permissions
chmod 600 "${CERTS_DIR}"/*.key

echo ""
echo "==> Certificates written to ${CERTS_DIR}/"
echo ""
echo "    ca.crt      — Install as trusted CA in containers (mounted at /certs/ca.crt)"
echo "    caddy.crt / caddy.key  — Mount into the Caddy container"
echo "    nats.crt  / nats.key   — Mount into the NATS container (when deployed)"
echo ""
echo "    IMPORTANT: tls/certs/ is in .gitignore. Never commit private keys."
echo ""
echo "==> Verify with:"
echo "    openssl verify -CAfile ${CERTS_DIR}/ca.crt ${CERTS_DIR}/caddy.crt"
echo "    openssl verify -CAfile ${CERTS_DIR}/ca.crt ${CERTS_DIR}/nats.crt"

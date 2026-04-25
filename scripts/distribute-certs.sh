#!/usr/bin/env bash
# Distribute TLS certs to Nomad client hosts via SCP.
#
# Copies ca.crt, caddy.{crt,key}, nats.{crt,key} from $CERT_SRC_DIR to
# $CERT_DEST_DIR on each host, then sets correct permissions (600 *.key, 644 *.crt).
#
# Required env:
#   NOMAD_CLIENT_HOSTS       space-separated hostnames or IPs
#   CERT_SRC_DIR             local directory containing the cert files
#   SSH_KEY_FILE             path to the ed25519 deploy private key
#   SSH_KNOWN_HOSTS_FILE     path to an ssh known_hosts file (no StrictHostKeyChecking=no)
#
# Optional env:
#   CERT_DEST_DIR   destination directory on each host (default: /etc/achaean/certs)
#   SSH_USER        remote user (default: nomad)

set -euo pipefail

: "${NOMAD_CLIENT_HOSTS:?NOMAD_CLIENT_HOSTS is required}"
: "${CERT_SRC_DIR:?CERT_SRC_DIR is required}"
: "${SSH_KEY_FILE:?SSH_KEY_FILE is required}"
: "${SSH_KNOWN_HOSTS_FILE:?SSH_KNOWN_HOSTS_FILE is required}"

CERT_DEST_DIR="${CERT_DEST_DIR:-/etc/achaean/certs}"
SSH_USER="${SSH_USER:-nomad}"

SSH_OPTS="-i ${SSH_KEY_FILE} -o UserKnownHostsFile=${SSH_KNOWN_HOSTS_FILE} -o BatchMode=yes -o ConnectTimeout=10"

ERRORS=0

for host in $NOMAD_CLIENT_HOSTS; do
  echo "==> ${host}"

  # shellcheck disable=SC2086
  if ! ssh $SSH_OPTS "${SSH_USER}@${host}" "sudo mkdir -p ${CERT_DEST_DIR}"; then
    echo "ERROR: ${host}: failed to create ${CERT_DEST_DIR}"
    ERRORS=$((ERRORS + 1))
    continue
  fi

  for f in ca.crt caddy.crt caddy.key nats.crt nats.key; do
    # Stage to /tmp first — SCP doesn't need root; sudo mv into dest
    # shellcheck disable=SC2086
    if ! scp $SSH_OPTS "${CERT_SRC_DIR}/${f}" "${SSH_USER}@${host}:/tmp/${f}"; then
      echo "ERROR: ${host}: scp failed for ${f}"
      ERRORS=$((ERRORS + 1))
      continue 2
    fi
    # shellcheck disable=SC2086
    if ! ssh $SSH_OPTS "${SSH_USER}@${host}" "sudo mv /tmp/${f} ${CERT_DEST_DIR}/${f}"; then
      echo "ERROR: ${host}: mv /tmp/${f} -> ${CERT_DEST_DIR}/${f} failed"
      ERRORS=$((ERRORS + 1))
      continue 2
    fi
  done

  # shellcheck disable=SC2086
  if ! ssh $SSH_OPTS "${SSH_USER}@${host}" \
      "sudo chmod 600 ${CERT_DEST_DIR}/caddy.key ${CERT_DEST_DIR}/nats.key && \
       sudo chmod 644 ${CERT_DEST_DIR}/ca.crt ${CERT_DEST_DIR}/caddy.crt ${CERT_DEST_DIR}/nats.crt"; then
    echo "ERROR: ${host}: chmod failed"
    ERRORS=$((ERRORS + 1))
  fi

  echo "    OK: ${host}"
done

if [[ $ERRORS -gt 0 ]]; then
  echo "FAILED: ${ERRORS} host(s) reported errors"
  exit 1
fi

echo "OK: certs distributed to all hosts"

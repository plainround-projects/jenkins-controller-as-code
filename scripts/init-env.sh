#!/usr/bin/env bash
# Creates .env from .env.example with random secrets, unless .env exists. The secrets stay on this machine: .env is not
# tracked, and the controller reads them from its environment.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
require openssl

if [ -f "${ROOT}/.env" ]; then
  log ".env already exists"
  exit 0
fi
umask 077
sed -e "s/^ADMIN_PASSWORD=.*/ADMIN_PASSWORD=$(openssl rand -hex 16)/" \
    -e "s/^PUBLISH_TOKEN=.*/PUBLISH_TOKEN=$(openssl rand -hex 24)/" "${ROOT}/.env.example" > "${ROOT}/.env"
log "created .env with random secrets"

#!/bin/bash
# Runs Trivy in a container as the calling user (Jenkins), with:
#   - the workspace mounted at /src (so .trivyignore and reports/ are used)
#   - a persistent vulnerability-DB cache in ~/.cache/trivy
#   - the Docker socket, so `trivy image` can scan locally built images
# Usage: bash security/trivy.sh <trivy args...>
set -euo pipefail
WORKSPACE="${WORKSPACE:-$PWD}"
mkdir -p "$HOME/.cache/trivy"
exec docker run --rm -u "$(id -u):$(id -g)" -e HOME=/tmp -e TRIVY_SKIP_VERSION_CHECK=true \
  --group-add "$(stat -c %g /var/run/docker.sock)" \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$WORKSPACE":/src -v "$HOME/.cache/trivy":/cache -w /src \
  "${TRIVY_IMAGE:-aquasec/trivy:0.65.0}" \
  --cache-dir /cache --timeout 20m "$@"

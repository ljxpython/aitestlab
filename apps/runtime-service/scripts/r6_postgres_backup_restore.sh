#!/usr/bin/env bash
set -euo pipefail

SOURCE_CONTAINER="${R6_POSTGRES_CONTAINER:-runtime-service-post17-postgres-1}"
TEMP_CONTAINER="r6-postgres-restore-$RANDOM"
DUMP_FILE="$(mktemp "${TMPDIR:-/tmp}/r6-postgres.XXXXXX.dump")"
TEMP_PASSWORD="r6-restore-only-password"

cleanup() {
  docker rm --force "$TEMP_CONTAINER" >/dev/null 2>&1 || true
  rm -f "$DUMP_FILE"
}
trap cleanup EXIT

if ! docker inspect "$SOURCE_CONTAINER" >/dev/null 2>&1; then
  echo "source PostgreSQL container not found: $SOURCE_CONTAINER" >&2
  exit 2
fi

docker exec "$SOURCE_CONTAINER" pg_dump \
  -U "${R6_POSTGRES_USER:-runtime_service}" \
  -d "${R6_POSTGRES_DB:-runtime_service}" \
  --format=custom \
  --no-owner \
  --no-privileges >"$DUMP_FILE"

test -s "$DUMP_FILE"

docker run --detach --rm \
  --name "$TEMP_CONTAINER" \
  -e "POSTGRES_PASSWORD=$TEMP_PASSWORD" \
  -e "POSTGRES_DB=${R6_POSTGRES_DB:-runtime_service}" \
  pgvector/pgvector:pg16 >/dev/null

for _ in {1..60}; do
  if docker exec "$TEMP_CONTAINER" pg_isready \
    -U postgres -d "${R6_POSTGRES_DB:-runtime_service}" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

docker exec "$TEMP_CONTAINER" pg_isready \
  -U postgres -d "${R6_POSTGRES_DB:-runtime_service}" >/dev/null

docker exec -i "$TEMP_CONTAINER" pg_restore \
  -U postgres \
  -d "${R6_POSTGRES_DB:-runtime_service}" \
  --exit-on-error \
  --no-owner \
  --no-privileges <"$DUMP_FILE"

docker exec "$SOURCE_CONTAINER" psql \
  -U "${R6_POSTGRES_USER:-runtime_service}" \
  -d "${R6_POSTGRES_DB:-runtime_service}" \
  -Atqc "SELECT 1" >/dev/null
docker exec "$TEMP_CONTAINER" psql \
  -U postgres \
  -d "${R6_POSTGRES_DB:-runtime_service}" \
  -Atqc "SELECT 1" >/dev/null

printf '%s\n' '{"status":"passed","source":"isolated-postgres","restore":"temporary-pgvector-container","source_mutation":"none"}'

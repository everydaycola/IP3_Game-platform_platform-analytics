#!/usr/bin/env bash
set -euo pipefail

# ---- CONFIG ----
ELASTIC_URL="${ELASTIC_URL:-http://localhost:9200}"
KIBANA_URL="${KIBANA_URL:-http://localhost:5601}"

ELASTIC_USER="${ELASTIC_USER:-elastic}"
ELASTIC_PASS="${ELASTIC_PASS:-changeme}"
KIBANA_USER="${KIBANA_USER:-elastic}"
KIBANA_PASS="${KIBANA_PASS:-changeme}"

# Paths in your repo (edit if different)
DIR_ELASTIC="${DIR_ELASTIC:-./elastic}"
DIR_KIBANA="${DIR_KIBANA:-./kibana}"

# Templates (optional)
TEMPLATE_FILES=(
  # "$DIR_ELASTIC/templates/events_enriched_template.json"
  # "$DIR_ELASTIC/templates/retention_cohort_template.json"
)

# Saved objects export (Kibana)
KIBANA_EXPORT_FILE="${KIBANA_EXPORT_FILE:-$DIR_KIBANA/exports/user_engagement_retention.ndjson}"

# Transforms
TF_PLAYER_FIRST_SEEN_ID="${TF_PLAYER_FIRST_SEEN_ID:-player_first_seen}"
TF_PLAYER_FIRST_SEEN_FILE="${TF_PLAYER_FIRST_SEEN_FILE:-$DIR_ELASTIC/transforms/player_first_seen.json}"

TF_RETENTION_COHORT_ID="${TF_RETENTION_COHORT_ID:-retention_cohort}"
TF_RETENTION_COHORT_FILE="${TF_RETENTION_COHORT_FILE:-$DIR_ELASTIC/transforms/retention_cohort.json}"

# Enrich policy
ENRICH_POLICY_NAME="${ENRICH_POLICY_NAME:-player_first_seen_enrich_policy}"
ENRICH_POLICY_FILE="${ENRICH_POLICY_FILE:-$DIR_ELASTIC/enrich/player_first_seen_enrich_policy.json}"

# Ingest pipeline
PIPELINE_NAME="${PIPELINE_NAME:-player_cohort_enrich}"
PIPELINE_FILE="${PIPELINE_FILE:-$DIR_ELASTIC/ingest_pipelines/player_cohort_enrich.json}"

# If true, we delete & recreate resources (recommended for clean prod deploy)
RECREATE="${RECREATE:-true}"

# ---- HELPERS ----
auth_es=(-u "${ELASTIC_USER}:${ELASTIC_PASS}")
auth_kbn=(-u "${KIBANA_USER}:${KIBANA_PASS}")

hdr_json=(-H "Content-Type: application/json")
hdr_kbn=(-H "kbn-xsrf: true")

have_jq=false
command -v jq >/dev/null 2>&1 && have_jq=true

log() { echo -e "\n==> $*"; }
die() { echo "ERROR: $*" >&2; exit 1; }

http() {
  # http METHOD URL [DATA_FILE]
  local method="$1"; shift
  local url="$1"; shift
  local data_file="${1:-}"

  if [[ -n "$data_file" ]]; then
    curl -sS -X "$method" "${auth_es[@]}" "${hdr_json[@]}" "$url" --data-binary @"$data_file"
  else
    curl -sS -X "$method" "${auth_es[@]}" "$url"
  fi
}

http_kbn_import() {
  local file="$1"
  curl -sS -X POST "${auth_kbn[@]}" "${hdr_kbn[@]}" \
    -F file=@"$file" \
    "${KIBANA_URL}/api/saved_objects/_import?overwrite=true"
}

exists_es() {
  # exists_es URL -> 0/1
  local url="$1"
  local code
  code=$(curl -sS -o /dev/null -w "%{http_code}" "${auth_es[@]}" "$url" || true)
  [[ "$code" == "200" ]]
}

# ---- PRECHECKS ----
log "Prechecks"
command -v curl >/dev/null 2>&1 || die "curl is required"

[[ -f "$TF_PLAYER_FIRST_SEEN_FILE" ]] || die "Missing: $TF_PLAYER_FIRST_SEEN_FILE"
[[ -f "$TF_RETENTION_COHORT_FILE" ]] || die "Missing: $TF_RETENTION_COHORT_FILE"
[[ -f "$ENRICH_POLICY_FILE" ]] || die "Missing: $ENRICH_POLICY_FILE"
[[ -f "$PIPELINE_FILE" ]] || die "Missing: $PIPELINE_FILE"
[[ -f "$KIBANA_EXPORT_FILE" ]] || die "Missing: $KIBANA_EXPORT_FILE"

log "Elastic: $ELASTIC_URL"
log "Kibana : $KIBANA_URL"

# ---- 1) Templates (optional) ----
if [[ "${#TEMPLATE_FILES[@]}" -gt 0 ]]; then
  log "1) Installing index templates (optional)"
  for f in "${TEMPLATE_FILES[@]}"; do
    if [[ -f "$f" ]]; then
      name="$(basename "$f" .json)"
      log " - PUT _index_template/$name from $f"
      http PUT "${ELASTIC_URL}/_index_template/${name}" "$f" | ${have_jq:+jq .} || true
    else
      log " - (skip missing) $f"
    fi
  done
else
  log "1) No templates configured (skipping)"
fi

# ---- Utility: stop + delete transform if needed ----
stop_delete_transform() {
  local id="$1"
  if exists_es "${ELASTIC_URL}/_transform/${id}"; then
    log " - Transform exists: $id"
    if [[ "$RECREATE" == "true" ]]; then
      log "   stopping $id (if running) ..."
      curl -sS -X POST "${auth_es[@]}" "${ELASTIC_URL}/_transform/${id}/_stop?force=true" >/dev/null || true
      log "   deleting $id ..."
      curl -sS -X DELETE "${auth_es[@]}" "${ELASTIC_URL}/_transform/${id}?force=true" >/dev/null || true
    else
      log "   RECREATE=false -> keeping existing $id"
    fi
  fi
}

# ---- 5) Ingest pipeline create ----
log "5) Ingest pipeline: create/update ($PIPELINE_NAME)"
log " - PUT _ingest/pipeline/$PIPELINE_NAME"
http PUT "${ELASTIC_URL}/_ingest/pipeline/${PIPELINE_NAME}" "$PIPELINE_FILE" | ${have_jq:+jq .} || true

log "Waiting for events-enriched-* to exist..."
until curl -s "${ELASTIC_URL}/events-enriched-*/_count" | grep -q '"count"'; do
  sleep 5
done

# ---- 2) Create transforms ----
log "2) Transforms: create (player_first_seen, retention_cohort)"

stop_delete_transform "$TF_PLAYER_FIRST_SEEN_ID"
if ! exists_es "${ELASTIC_URL}/_transform/${TF_PLAYER_FIRST_SEEN_ID}"; then
  log " - PUT _transform/$TF_PLAYER_FIRST_SEEN_ID"
  http PUT "${ELASTIC_URL}/_transform/${TF_PLAYER_FIRST_SEEN_ID}" "$TF_PLAYER_FIRST_SEEN_FILE" | ${have_jq:+jq .} || true
fi

stop_delete_transform "$TF_RETENTION_COHORT_ID"
if ! exists_es "${ELASTIC_URL}/_transform/${TF_RETENTION_COHORT_ID}"; then
  log " - PUT _transform/$TF_RETENTION_COHORT_ID"
  http PUT "${ELASTIC_URL}/_transform/${TF_RETENTION_COHORT_ID}" "$TF_RETENTION_COHORT_FILE" | ${have_jq:+jq .} || true
fi

# ---- 3) Start transforms (player_first_seen first) ----
log "3) Start transforms"
log " - POST _transform/$TF_PLAYER_FIRST_SEEN_ID/_start"
curl -sS -X POST "${auth_es[@]}" "${ELASTIC_URL}/_transform/${TF_PLAYER_FIRST_SEEN_ID}/_start" | ${have_jq:+jq .} || true

# Wait until player_first_seen has produced at least 1 checkpoint OR documents
log "   waiting for $TF_PLAYER_FIRST_SEEN_ID to produce data (needed for enrich execute)..."
for i in {1..30}; do
  stats="$(curl -sS "${auth_es[@]}" "${ELASTIC_URL}/_transform/${TF_PLAYER_FIRST_SEEN_ID}/_stats" || true)"
  if $have_jq; then
    docs="$(echo "$stats" | jq -r '.transforms[0].stats.documents_indexed // 0')"
    ckpt="$(echo "$stats" | jq -r '.transforms[0].checkpointing.last.checkpoint // 0')"
    if [[ "$docs" -gt 0 ]] || [[ "$ckpt" -gt 0 ]]; then
      log "   ok: documents_indexed=$docs checkpoint=$ckpt"
      break
    fi
  fi
  sleep 2
done

# ---- 4) Enrich policy create + execute ----
log "4) Enrich policy: create + execute"

# Delete existing policy if recreating
if exists_es "${ELASTIC_URL}/_enrich/policy/${ENRICH_POLICY_NAME}"; then
  if [[ "$RECREATE" == "true" ]]; then
    log " - DELETE _enrich/policy/$ENRICH_POLICY_NAME"
    curl -sS -X DELETE "${auth_es[@]}" "${ELASTIC_URL}/_enrich/policy/${ENRICH_POLICY_NAME}" >/dev/null || true
  else
    log " - Enrich policy exists, RECREATE=false -> keeping"
  fi
fi

if ! exists_es "${ELASTIC_URL}/_enrich/policy/${ENRICH_POLICY_NAME}"; then
  log " - PUT _enrich/policy/$ENRICH_POLICY_NAME"
  http PUT "${ELASTIC_URL}/_enrich/policy/${ENRICH_POLICY_NAME}" "$ENRICH_POLICY_FILE" | ${have_jq:+jq .} || true
fi

log " - POST _enrich/policy/$ENRICH_POLICY_NAME/_execute"
curl -sS -X POST "${auth_es[@]}" "${ELASTIC_URL}/_enrich/policy/${ENRICH_POLICY_NAME}/_execute" | ${have_jq:+jq .} || true

# ---- 6) Start retention_cohort transform ----
log "6) Start retention_cohort transform"
log " - POST _transform/$TF_RETENTION_COHORT_ID/_start"
curl -sS -X POST "${auth_es[@]}" "${ELASTIC_URL}/_transform/${TF_RETENTION_COHORT_ID}/_start" | ${have_jq:+jq .} || true

# ---- 7) Skip Kibana import (dashboard created via Python script) ----
log "7) Skip Kibana .ndjson import (dashboard will be created via Python script)"
echo "   Note: The User Engagement & Retention dashboard will be created by"
echo "   scripts/create_retention_engagement_dashboard.py with the latest KPI definitions"

log "DONE ✅"
echo "Tip: If you use Logstash, make sure it routes platform-events-* into events-enriched-* using ingest pipeline: $PIPELINE_NAME"

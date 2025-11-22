#!/usr/bin/env bash

set -eu
set -o pipefail

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

# --------------------------------------------------------
# Users declarations

declare -A users_passwords
users_passwords=(
	[logstash_internal]="${LOGSTASH_INTERNAL_PASSWORD:-}"
	[kibana_system]="${KIBANA_SYSTEM_PASSWORD:-}"
)

declare -A users_roles
users_roles=(
	[logstash_internal]='logstash_writer'
)

# --------------------------------------------------------
# Roles declarations

declare -A roles_files
roles_files=(
	[logstash_writer]='logstash_writer.json'
)

# --------------------------------------------------------

log 'Waiting for availability of Elasticsearch'
wait_for_elasticsearch

log 'Setting kibana_system password'
set_user_password 'kibana_system' "${KIBANA_SYSTEM_PASSWORD}"

log 'Setting logstash_internal password'
set_user_password 'logstash_internal' "${LOGSTASH_INTERNAL_PASSWORD}"

log 'Creating logstash_writer role'
create_role 'logstash_writer' "${roles_files[logstash_writer]}"

log 'Setup complete'

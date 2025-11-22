#!/usr/bin/env bash

# Log a message
function log {
	echo "[+] $1"
}

# Wait for Elasticsearch availability
function wait_for_elasticsearch {
	local elasticsearch_host="${ELASTICSEARCH_HOST:-elasticsearch}"

	local -a args=( '-s' '-D-' '-m15' '-w' '%{http_code}' "http://${elasticsearch_host}:9200/" )

	if [[ -n "${ELASTIC_PASSWORD:-}" ]]; then
		args+=( '-u' "elastic:${ELASTIC_PASSWORD}" )
	fi

	local -i result=1
	local output

	# retry for max 300s (60*5s)
	for _ in $(seq 1 60); do
		local -i exit_code=0
		output="$(curl "${args[@]}")" || exit_code=$?

		if [[${exit_code} -eq 0 ]]; then
			if [[ "${output: -3}" -eq 200 ]]; then
				result=0
				break
			fi
		fi

		sleep 5
	done

	if [[ ${result} -eq 1 ]]; then
		echo -e "\n\nERROR: Elasticsearch is not running\n\n" >&2
		exit 1
	fi

	echo "${output::-3}"
}

# Set a user password
function set_user_password {
	local user="${1}"
	local password="${2}"

	local elasticsearch_host="${ELASTICSEARCH_HOST:-elasticsearch}"

	local -a args=( '-s' '-D-' '-m15' )

	args+=( '-X' 'POST' )
	args+=( '-H' 'Content-Type: application/json' )
	args+=( '-d' "{\"password\" : \"${password}\"}" )

	if [[ -n "${ELASTIC_PASSWORD:-}" ]]; then
		args+=( '-u' "elastic:${ELASTIC_PASSWORD}" )
	fi

	args+=( "http://${elasticsearch_host}:9200/_security/user/${user}/_password" )

	curl "${args[@]}"
}

# Create a role
function create_role {
	local role="${1}"
	local body="${2}"

	local elasticsearch_host="${ELASTICSEARCH_HOST:-elasticsearch}"

	local -a args=( '-s' '-D-' '-m15' )

	args+=( '-X' 'PUT' )
	args+=( '-H' 'Content-Type: application/json' )
	args+=( '-d' "@roles/${body}" )

	if [[ -n "${ELASTIC_PASSWORD:-}" ]]; then
		args+=( '-u' "elastic:${ELASTIC_PASSWORD}" )
	fi

	args+=( "http://${elasticsearch_host}:9200/_security/role/${role}" )

	curl "${args[@]}"
}

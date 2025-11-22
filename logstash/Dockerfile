ARG ELASTIC_VERSION

# https://www.docker.elastic.co/
FROM docker.elastic.co/logstash/logstash:${ELASTIC_VERSION:-8.15.3}

# RabbitMQ plugin is already included via logstash-integration-rabbitmq
# No additional installation needed for Logstash 8.15+

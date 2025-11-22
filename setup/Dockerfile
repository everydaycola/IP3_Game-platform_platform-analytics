ARG ELASTIC_VERSION
FROM docker.elastic.co/elasticsearch/elasticsearch:${ELASTIC_VERSION}

USER root
RUN apt-get update && apt-get install -y jq curl && rm -rf /var/lib/apt/lists/*
USER elasticsearch

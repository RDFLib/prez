FROM ghcr.io/aiworkerjohns/fuseki-ai:6.1.0-snapshot

WORKDIR /fuseki

COPY config.ttl ./config.ttl

ENTRYPOINT ["java", "-jar", "jena-fuseki-server.jar", "--config", "config.ttl"]

FROM ghcr.io/kurrawong/fuseki-lucene-shacl:sha-e2f4b0d

# The image's own entrypoint starts the server with the JVM flags Lucene needs
# (--add-modules jdk.incubator.vector, --enable-native-access ALL-UNNAMED) and
# reads its configuration from /config.ttl, so the config goes there rather than
# the entrypoint being overridden and those flags dropped.
#
# The image sets WORKDIR /fuseki, which is what the config's relative
# `text:directory <file:Lucene>` resolves against.
COPY config.ttl /config.ttl

import re

from rdflib import URIRef

# Define the regex based on the SPARQL ABNF definition for IRIREF, WITHOUT the leading and trailing < >
# ^                     : Start of the string
# <                     : Literal '<'
# [^"{}|^`\\\x00-\x20] : Match any character NOT in the specified set:
#                         " { } | ^ ` \ (note the double escape \\ for literal \)
#                         and the range U+0000 to U+0020 (\x00-\x20)
# * : Match the preceding character class zero or more times
# >                     : Literal '>'
# $                     : End of the string
# Compile the regex for efficiency if used repeatedly
sparql_iri_pattern_str = r'^[^<>"{}|^`\\\x00-\x20]*$'
sparql_iri_re = re.compile(sparql_iri_pattern_str)


def validate_iri(iri: str | URIRef):
    if isinstance(iri, URIRef):
        iri = str(iri)
    return bool(sparql_iri_re.fullmatch(iri))

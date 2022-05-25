# from connegp import Profile, RDF_MEDIATYPES
#
# dd = Profile(
#     uri="https://w3id.org/profile/dd",
#     id="dd",
#     label="Drop-Down List",
#     comment="A simple data model to provide items for form drop-down lists. The basic information is an ID & name tuple "
#     "and the optional extra value is an item's parent. For vocabularies, this is then URI, prefLabel or URI, "
#     "prefLabel & broader Concept",
#     mediatypes=["application/json"],
#     default_mediatype="application/json",
#     languages=["en"],
#     default_language="en",
# )
#
# dcat = Profile(
#     uri="https://www.w3.org/TR/vocab-dcat/",
#     id="dcat",
#     label="DCAT",
#     comment="Dataset Catalogue Vocabulary (DCAT) is a W3C-authored RDF vocabulary designed to "
#     "facilitate interoperability between data catalogs "
#     "published on the Web.",
#     mediatypes=["text/html"] + RDF_MEDIATYPES,
#     default_mediatype="text/html",
#     languages=["en"],
#     default_language="en",
# )
#
# geo = Profile(
#     uri="http://www.opengis.net/ont/geosparql",
#     id="geo",
#     label="GeoSPARQL",
#     comment="An RDF/OWL vocabulary for representing spatial information",
#     mediatypes=RDF_MEDIATYPES,
#     default_mediatype="text/turtle",
#     languages=["en"],
#     default_language="en",
# )
#
# oai = Profile(
#     uri="http://www.opengis.net/spec/ogcapi-features-1/1.0/req/oas30",
#     id="oai",
#     label="OpenAPI 3.0",
#     comment="The OpenAPI Specification (OAS) defines a standard, language-agnostic interface to RESTful APIs which allows both humans and computers to discover and understand the capabilities of the service without access to source code, documentation, or through network traffic inspection.",
#     mediatypes=["text/html", "application/json", "application/geo+json"],
#     default_mediatype="text/html",
#     languages=["en"],
#     default_language="en",
# )
#
# gas = Profile(
#     uri="https://w3id.org/profile/ga-spaceprez",
#     id="gas",
#     label="Geoscience Australia Samples profile",
#     comment="A profile to implement Geoscience Australia specific views of objects",
#     mediatypes=["text/html", "application/json", "application/geo+json"],
#     default_mediatype="text/html",
#     languages=["en"],
#     default_language="en",
# )

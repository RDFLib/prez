from connegp import Profile, RDF_MEDIATYPES


vocpub = Profile(
    uri="https://w3id.org/profile/vocpub",
    id="vocpub",
    label="VocPub",
    comment="A profile of SKOS for the publication of Vocabularies. This profile mandates the use of one Concept "
    "Scheme per vocabulary",
    mediatypes=["text/html"] + RDF_MEDIATYPES,
    default_mediatype="text/turtle",
    languages=["en"],
    default_language="en",
)

vocpub_supplied = Profile(
    uri="https://w3id.org/profile/vocpub",
    id="vocpub_supplied",
    label="VocPub Supplied",
    comment="A profile of SKOS for the publication of Vocabularies. This profile excludes inferred data.",
    mediatypes=RDF_MEDIATYPES,
    default_mediatype="text/turtle",
    languages=["en"],
    default_language="en",
)

skos = Profile(
    uri="https://www.w3.org/TR/skos-reference/",
    id="skos",
    label="SKOS",
    comment="Simple Knowledge Organization System (SKOS) is a W3C-authored, common data model for sharing "
    "and linking knowledge organization systems "
    "via the Web.",
    mediatypes=RDF_MEDIATYPES,
    default_mediatype="text/turtle",
    languages=["en"],
    default_language="en",
)

sdo = Profile(
    uri="https://schema.org",
    id="sdo",
    label="schema.org",
    comment="Schema.org is a collaborative, community activity with a mission to create, maintain, and promote schemas "
    "for structured data on the Internet, on web pages, in email messages, and beyond.",
    mediatypes=RDF_MEDIATYPES,
    default_mediatype="text/turtle",
    languages=["en"],
    default_language="en",
)

dd = Profile(
    uri="https://w3id.org/profile/dd",
    id="dd",
    label="Drop-Down List",
    comment="A simple data model to provide items for form drop-down lists. The basic information is an ID & name tuple "
    "and the optional extra value is an item's parent. For vocabularies, this is then URI, prefLabel or URI, "
    "prefLabel & broader Concept",
    mediatypes=["application/json"],
    default_mediatype="application/json",
    languages=["en"],
    default_language="en",
)

dcat = Profile(
    uri="https://www.w3.org/TR/vocab-dcat/",
    id="dcat",
    label="DCAT",
    comment="Dataset Catalogue Vocabulary (DCAT) is a W3C-authored RDF vocabulary designed to "
    "facilitate interoperability between data catalogs "
    "published on the Web.",
    mediatypes=["text/html"] + RDF_MEDIATYPES,
    default_mediatype="text/html",
    languages=["en"],
    default_language="en",
)

alt = Profile(
    uri="http://www.w3.org/ns/dx/conneg/altr",
    id="alt",
    label="Alternate Representations",
    comment="The representation of the resource that lists all other representations (profiles and Media Types)",
    mediatypes=["text/html"] + RDF_MEDIATYPES,
    default_mediatype="text/html",
    languages=["en"],
    default_language="en",
)

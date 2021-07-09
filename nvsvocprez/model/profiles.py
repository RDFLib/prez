from nvsvocprez.pyldapi.profile import Profile
from nvsvocprez.pyldapi.renderer import RDF_MEDIATYPES

skos = Profile(
    uri="https://www.w3.org/TR/skos-reference/",
    id="skos",
    label="SKOS",
    comment="Simple Knowledge Organization System (SKOS)is a W3C-authored, common data model for sharing "
    "and linking knowledge organization systems "
    "via the Web.",
    mediatypes=RDF_MEDIATYPES,
    default_mediatype="text/turtle",
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

void = Profile(
    uri="https://www.w3.org/TR/vocab-dcat/",
    id="void",
    label="VoID",
    comment="The Vocabulary of Interlinked Datasets (VoID) is an RDF Schema vocabulary for expressing metadata about "
            "RDF datasets.",
    mediatypes=RDF_MEDIATYPES,
    default_mediatype="text/turtle",
    languages=["en"],
    default_language="en",
)

ckan = Profile(
    uri="https://ckan.org/",
    id="ckan",
    label="CKAN",
    comment="The Comprehensive Knowledge Archive Network (CKAN) is a web-based open-source management system for "
    "the storage and distribution of open data. This profile it it's native data model",
    mediatypes=["application/json"],
    default_mediatype="application/json",
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

nvs = Profile(
    uri="https://w3id.org/profile/nvs-col",
    id="nvs",
    label="NVS Collections List Profile",
    comment="The NERC Vocabulary Server's profile of SKOS that include Provenance Ontology (PROV) and Registry Ontology"
            "relationships for term governance.",
    mediatypes=["text/html"] + RDF_MEDIATYPES,
    default_mediatype="text/html",
    languages=["en"],
    default_language="en",
)

vocpub = Profile(
    uri="https://w3id.org/profile/vocpub",
    id="vocpub",
    label="VocPub",
    comment="A profile of SKOS for the publication of Vocabularies. This profile mandates the use of one Concept "
            "Scheme per vocabulary",
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
    mediatypes=["text/html"] + RDF_MEDIATYPES,
    default_mediatype="text/html",
    languages=["en"],
    default_language="en",
)

puv = Profile(
    uri="https://w3id.org/env/puv",
    id="puv",
    label="Parameter Use Vocabulary",
    comment="A simple ontology which implements the Parameter Usage Vocabulary semantic model, as described at "
            "https://github.com/nvs-vocabs/P01",
    mediatypes=["text/html"] + RDF_MEDIATYPES,
    default_mediatype="text/html",
    languages=["en"],
    default_language="en",
)

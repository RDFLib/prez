from connegp import Connegp, Profile, RDF_MEDIATYPES

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

profiles = {
    "dcat": dcat,
    "skos": skos
}

request = {
    "headers": {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Profile": "<https://www.w3.org/TR/vocab-dcat/>;q=1.0,<https://www.w3.org/TR/skos-reference/>;q=0.8",
        "Link": '<https://www.w3.org/TR/vocab-dcat/>; rel="profile"',
    },
    "query_params": {
        "_profile": "dcat",
        # "_profile": '<https://www.w3.org/TR/skos-reference/>;q=1.0,<https://www.w3.org/TR/vocab-dcat/>;q=0.8',
        "_mediatype": "text/turtle"
    }
}

c = Connegp(request, profiles, "dcat")

print(c.profile)
print(c.mediatype)
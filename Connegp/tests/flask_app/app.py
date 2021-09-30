from flask import Flask, request, Request

from connegp import Connegp, Profile, RDF_MEDIATYPES

app = Flask(__name__)

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


@app.route("/")
def hello_world():
    # insert new headers & create new request object for testing
    new_environ = request.environ
    new_environ.update(
        HTTP_ACCEPT="text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        HTTP_ACCEPT_PROFILE="<https://www.w3.org/TR/skos-reference/>;q=1.0,<https://www.w3.org/TR/vocab-dcat/>;q=0.8",
        HTTP_LINK='<https://www.w3.org/TR/skos-reference/>; rel="profile"',
    )
    new_request = Request(new_environ)
    c = Connegp(new_request, {"dcat": dcat, "skos": skos}, "dcat")
    print(f"Profile: {c.profile}, mediatype: {c.mediatype}")
    return "<p>Hello, World!</p>"

from pathlib import Path
from string import Template

from rdflib import Graph, RDF, DCTERMS, Literal, RDFS

from prez.cache import search_methods
from prez.models import SearchMethod
from prez.reference_data.prez_ns import PREZ


async def generate_search_methods():
    for f in (Path(__file__).parent.parent / "reference_data/search_methods").glob(
        "*.ttl"
    ):
        g = Graph().parse(f, format="ttl")
        uri = g.value(None, RDF.type, PREZ.SearchMethod)
        identifier = g.value(uri, DCTERMS.identifier, None)
        title: Literal = g.value(uri, RDFS.label, None)
        template_query = Template(g.value(uri, RDF.value, None))
        sm = SearchMethod(
            uri=uri, identifier=identifier, title=title, template_query=template_query
        )
        search_methods.update({identifier: sm})

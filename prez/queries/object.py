from textwrap import dedent

from jinja2 import Template


def object_inbound_query(iri: str, predicate: str) -> str:
    query = Template(
        """
        SELECT (COUNT(?iri) as ?count)
        WHERE {
        BIND(<{{ iri }}> as ?iri)
        
        ?other <{{ predicate }}> ?iri .
        }
    """
    ).render(iri=iri, predicate=predicate)

    return dedent(query)


def object_outbound_query(iri: str, predicate: str) -> str:
    query = Template(
        """
        SELECT (COUNT(?iri) as ?count)
        WHERE {
        BIND(<{{ iri }}> as ?iri)
        
        ?iri <{{ predicate }}> ?other .
        }
    """
    ).render(iri=iri, predicate=predicate)

    return dedent(query)

from textwrap import dedent

from jinja2 import Template


def get_foaf_homepage_query(iri: str) -> str:
    query = Template(
        """
        PREFIX foaf: <http://xmlns.com/foaf/0.1/>
        
        SELECT DISTINCT ?url
        WHERE {
            <{{ iri }}> foaf:homepage ?url . 
        }
    """
    ).render(iri=iri)

    return dedent(query)

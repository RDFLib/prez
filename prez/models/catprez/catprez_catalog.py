from typing import List, Dict, Optional

from prez.config import *
from prez.models import PrezModel


class CatPrezCatalog(PrezModel):
    # class attributes for property grouping & order
    main_props = [
        str(DCTERMS.identifier),
        str(DCTERMS.creator),
        str(DCTERMS.publisher),
        str(DCTERMS.created),
        str(DCTERMS.modified),
        str(DCTERMS.hasPart)
    ]
    hidden_props = [
        str(DCTERMS.description),
        str(RDFS.label),
        str(RDF.type)
    ]

    def __init__(
        self, graph: Graph, id: Optional[str] = None, uri: Optional[str] = None
    ) -> None:
        super().__init__(graph)

        if id is None and uri is None:
            raise ValueError("Either an ID or a URI must be provided")

        query_by_id = f"""
                ?cs dcterms:identifier "{id}"^^xsd:token .
                BIND("{id}" AS ?id)
        """

        query_by_uri = f"""
                BIND (<{uri}> as ?cs)
                ?cs dcterms:identifier ?id .
        """

        qx = f"""
            PREFIX dcterms: <{DCTERMS}>
            PREFIX rdfs: <{RDFS}>
            PREFIX xsd: <{XSD}>
            
            SELECT *
            WHERE {{
                {query_by_id if id is not None else query_by_uri}
                
                ?c
                    a dcat:Catalog ;
                    dcterms:title ?title ;
                    dcterms:description ?desc .
            }}
            """

        r = self.graph.query(qx)

        result = r.bindings[0]
        self.uri = result["c"]
        self.id = result["id"]
        self.title = result["title"]
        self.description = result["desc"]

    # override
    def to_dict(self) -> Dict:
        return {
            "uri": self.uri,
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "properties": self._get_properties(),
        }

    # override
    def _get_properties(self) -> List[Dict]:
        props_dict = self._get_props()

        # group props in order, filtering out hidden props
        properties = []
        main_props = []
        other_props = []

        for prop in props_dict:
            if prop["value"] in CatPrezCatalog.hidden_props:
                continue
            elif prop["value"] in CatPrezCatalog.main_props:
                main_props.append(prop)
            else:
                other_props.append(prop)

        # sorts & combines into a single list
        properties.extend(
            sorted(
                main_props,
                key=lambda p: self._sort_within_list(p, CatPrezCatalog.main_props),
            )
        )
        properties.extend(other_props)

        return properties

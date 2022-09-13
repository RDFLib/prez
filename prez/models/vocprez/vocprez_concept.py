from typing import List, Dict, Optional

from prez.config import *
from prez.models import PrezModel


class VocPrezConcept(PrezModel):
    # class attributes for property grouping & order
    main_props = [
        # str(SKOS.definition),
    ]

    hidden_props = [
        str(SKOS.semanticRelation),
        str(SKOS.broaderTransitive),
        str(SKOS.narrowerTransitive),
        str(DCTERMS.identifier),
        str(SDO.identifier),
        str(SKOS.inScheme),
        str(SKOS.topConceptOf),
        str(SKOS.broader),
        str(SKOS.narrower),
        str(SKOS.definition),
    ]

    def __init__(
        self, graph: Graph, id: Optional[str] = None, uri: Optional[str] = None
    ) -> None:
        super().__init__(graph)

        if id is None and uri is None:
            raise ValueError("Either an ID or a URI must be provided")

        query_by_id = f"""
                ?c dcterms:identifier "{id}"^^xsd:token .     
                BIND("{id}" AS ?id)
        """

        query_by_uri = f"""
                BIND (<{uri}> as ?c)
                ?c dcterms:identifier ?id .
        """

        qx = f"""
            PREFIX dcterms: <{DCTERMS}>
            PREFIX rdfs: <{RDFS}>
            PREFIX skos: <{SKOS}>
            PREFIX xsd: <{XSD}>
            
            SELECT DISTINCT *
            WHERE {{
                {query_by_id if id is not None else query_by_uri}

                ?cs dcterms:identifier ?cs_id ;
                    skos:prefLabel ?cs_label .
                    
                FILTER(lang(?cs_label) = "" || lang(?cs_label) = "en")
                
                ?c a skos:Concept ;
                    skos:prefLabel ?title ;
                    skos:definition ?desc ;
                    skos:inScheme ?cs .
                    
                FILTER(lang(?title) = "" || lang(?title) = "en")                
            }}
            """

        r = self.graph.query(qx)

        result = r.bindings[0]
        self.uri = result["c"]
        self.id = result["id"]
        self.title = result["title"]
        self.description = result["desc"]
        self.scheme = {
            "uri": result["cs"],
            "id": result["cs_id"],
            "title": result["cs_label"],
        }

    # override
    def to_dict(self) -> Dict:
        return {
            "uri": self.uri,
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "properties": self._get_properties(),
            "scheme": self.scheme,
            "broader": self._get_broader_concepts(),
            "narrower": self._get_narrower_concepts(),
        }

    # override
    def _get_properties(self) -> List[Dict]:
        props_dict = self._get_props()

        # group props in order, filtering out hidden props
        properties = []
        main_props = []
        other_props = []

        for prop in props_dict:
            if prop["value"] in VocPrezConcept.hidden_props:
                continue
            elif prop["value"] in VocPrezConcept.main_props:
                main_props.append(prop)
            else:
                other_props.append(prop)

        # sorts & combines into a single list
        properties.extend(main_props)
        properties.extend(other_props)

        return properties

    def _get_broader_concepts(self) -> List[Dict]:
        broader = []
        r = self.graph.query(
            f"""
            PREFIX skos: <{SKOS}>
            
            SELECT DISTINCT *
            WHERE {{
                <{self.uri}> skos:broader ?broader .
                ?broader dcterms:identifier ?id ;
                    skos:prefLabel ?label ;
                    skos:inScheme/dcterms:identifier ?cs_id .
                    
                FILTER(lang(?label) = "" || lang(?label) = "en" || lang(?label) = "en-AU")
            }}
        """
        )

        for result in r.bindings:
            broader.append(
                {
                    "uri": result["broader"],
                    "label": result["label"],
                    "id": result["id"],
                    "scheme_id": result["cs_id"],
                }
            )
        return sorted(broader, key=lambda c: c["label"])

    def _get_narrower_concepts(self) -> List[Dict]:
        narrower = []
        r = self.graph.query(
            f"""
            PREFIX skos: <{SKOS}>
            
            SELECT DISTINCT *
            WHERE {{
                <{self.uri}> skos:narrower ?narrower .
                ?narrower dcterms:identifier ?id ;
                    skos:prefLabel ?label ;
                    skos:inScheme/dcterms:identifier ?cs_id .
                    
                FILTER(lang(?label) = "" || lang(?label) = "en" || lang(?label) = "en-AU")
            }}
        """
        )

        for result in r.bindings:
            narrower.append(
                {
                    "uri": result["narrower"],
                    "label": result["label"],
                    "id": result["id"],
                    "scheme_id": result["cs_id"],
                }
            )
        return sorted(narrower, key=lambda c: c["label"])

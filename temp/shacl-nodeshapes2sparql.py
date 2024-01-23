from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel
from rdflib import URIRef
from rdflib.namespace import SH

from temp.grammar import IRI


class SHACL(BaseModel):
    class Config:
        arbitrary_types_allowed = True

    def from_graph(self, graph):
        raise NotImplementedError("Subclasses must implement this method.")

    def to_grammar(self):
        raise NotImplementedError("Subclasses must implement this method.")


    class NodeShape(SHACL):
        uri: URIRef
        nodeTarget: Optional[URIRef]
        classTarget: Optional[List[URIRef]]
        subjectsOfTarget: Optional[URIRef]
        objectsOfTarget: Optional[URIRef]
        propertyShapes: Optional[List[PropertyShape]]

        def from_graph(self, graph):
            self.nodeTarget = next(graph.objects(self.uri, SH.targetNode), None)
            self.classTarget = list(graph.objects(self.uri, SH.targetClass))
            self.subjectsOfTarget = next(graph.value(self.uri, SH.targetSubjectsOf), None)
            self.objectsOfTarget = next(graph.objects(self.uri, SH.targetObjectsOf), None)
            self.propertyShapes = list(graph.objects(self.uri, SH.property))

        def to_grammar(self):
            if self.nodeTarget:
                pass  # do not need to add any specific triples or the like
            if self.classTarget:
                pass
            if self.subjectsOfTarget:
                pass
            if self.objectsOfTarget:
                pass
            if self.propertyShapes:
                pass

        def _process_node_target(self):
            target_uri = IRI(value=self.nodeTarget)

        def _process_property_shapes(self, property_shapes):
            pass


class PropertyShape(SHACL):
    uri: URIRef

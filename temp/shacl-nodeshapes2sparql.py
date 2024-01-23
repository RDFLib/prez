from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel
from rdflib import URIRef
from rdflib.namespace import SH, RDF

from temp.grammar import IRI, SimplifiedTriple, TriplesBlock


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
    _triples: Optional[List[SimplifiedTriple]]

    def from_graph(self, graph):
        self.nodeTarget = next(graph.objects(self.uri, SH.targetNode), None)
        self.classTarget = list(graph.objects(self.uri, SH.targetClass))
        self.subjectsOfTarget = next(graph.value(self.uri, SH.targetSubjectsOf), None)
        self.objectsOfTarget = next(graph.objects(self.uri, SH.targetObjectsOf), None)
        self.propertyShapes = list(graph.objects(self.uri, SH.property))

    def to_grammar(self) -> TriplesBlock:
        if self.nodeTarget:
            pass  # do not need to add any specific triples or the like
        if self.classTarget:
            self._process_class_target()
        if self.subjectsOfTarget:
            pass
        if self.objectsOfTarget:
            pass
        if self.propertyShapes:
            pass

    def _process_class_target(self):
        for klass in self.classTarget:
            self._triples.append(
                SimplifiedTriple(
                    subject=self.focus_node,
                    predicate=IRI(value=RDF.type),
                    object=klass,
                )
            )

    def _process_property_shapes(self, property_shapes):
        pass


class PropertyShape(SHACL):
    uri: URIRef

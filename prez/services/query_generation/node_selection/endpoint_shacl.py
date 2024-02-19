from __future__ import annotations

from string import Template
from typing import List, Optional, Union, Any, Dict

from pydantic import BaseModel
from rdflib import URIRef, BNode, Graph
from rdflib.collection import Collection
from rdflib.namespace import SH, RDF
from rdflib.term import Node

from prez.reference_data.prez_ns import ONT
from temp.grammar import *


class Shape(BaseModel):
    class Config:
        arbitrary_types_allowed = True

    def __init__(self, **data: Any):
        super().__init__(**data)
        self.triples_list = []
        self.gpnt_list = []
        self.from_graph()
        self.to_grammar()

    def from_graph(self):
        raise NotImplementedError("Subclasses must implement this method.")

    def to_grammar(self):
        raise NotImplementedError("Subclasses must implement this method.")


class NodeShape(Shape):
    uri: URIRef
    graph: Graph
    focus_node: Var | IRI = Var(value="focus_node")
    targetNode: Optional[URIRef] = None
    targetClasses: Optional[List[Node]] = []
    propertyShapesURIs: Optional[List[Node]] = []
    target: Optional[Node] = None
    rules: Optional[List[Node]] = []
    propertyShapes: Optional[List[PropertyShape]] = []
    triples_list: Optional[List[SimplifiedTriple]] = []
    gpnt_list: Optional[List[GraphPatternNotTriples]] = []
    path_nodes: Optional[Dict[str, Var | IRI]] = {}
    classes_at_len: Optional[Dict[str, List[URIRef]]] = {}
    hierarchy_level: Optional[int] = None
    select_template: Optional[str] = None

    def from_graph(self):  # TODO this can be a SPARQL select against the system graph.
        self.targetNode = next(self.graph.objects(self.uri, SH.targetNode), None)
        self.targetClasses = list(self.graph.objects(self.uri, SH.targetClass))
        self.propertyShapesURIs = list(self.graph.objects(self.uri, SH.property))
        self.target = next(self.graph.objects(self.uri, SH.target), None)
        self.rules = list(self.graph.objects(self.uri, SH.rule))
        self.propertyShapes = [
            PropertyShape(
                uri=ps_uri,
                graph=self.graph,
                focus_node=self.focus_node,
                path_nodes=self.path_nodes,
            )
            for ps_uri in self.propertyShapesURIs
        ]
        self.hierarchy_level = next(
            self.graph.objects(self.uri, ONT.hierarchyLevel), None
        )
        if not self.hierarchy_level:
            raise ValueError("No hierarchy level found")

    def to_grammar(self):
        if self.targetNode:
            pass  # do not need to add any specific triples or the like
        if self.targetClasses:
            self._process_class_targets()
        if self.propertyShapes:
            self._process_property_shapes()
        if self.target:
            self._process_target()
            # rules used to construct triples only in the context of sh:target/sh:sparql at present.
            if self.rules:
                self._process_rules()

    def _process_class_targets(self):
        if len(self.targetClasses) == 1:
            self.triples_list.append(
                SimplifiedTriple(
                    subject=self.focus_node,
                    predicate=IRI(value=RDF.type),
                    object=IRI(value=self.targetClasses[0]),
                )
            )
        elif len(self.targetClasses) > 1:
            self.triples_list.append(
                SimplifiedTriple(
                    subject=self.focus_node,
                    predicate=IRI(value=RDF.type),
                    object=Var(value=f"focus_classes"),
                )
            )
            dbvs = [
                DataBlockValue(value=IRI(value=klass)) for klass in self.targetClasses
            ]
            self.gpnt_list.append(
                GraphPatternNotTriples(
                    content=InlineData(
                        data_block=DataBlock(
                            block=InlineDataOneVar(
                                variable=Var(value=f"focus_classes"),
                                datablockvalues=dbvs,
                            )
                        )
                    )
                )
            )
        else:
            raise ValueError("No target classes found")

    def _process_property_shapes(self):
        for shape in self.propertyShapes:
            self.triples_list.extend(shape.triples_list)
            self.gpnt_list.extend(shape.gpnt_list)
            self.path_nodes = self.path_nodes | shape.path_nodes
            self.classes_at_len = self.classes_at_len | shape.classes_at_len
        # deduplicate
        self.triples_list = list(set(self.triples_list))

    def _process_target(self):
        self.select_statement = Template(
            str(self.endpoint_graph.value(self.target, SH.select, default=None))
        )

    def _process_rules(self):
        pass


class PropertyShape(Shape):
    uri: URIRef | BNode  # URI of the shape
    graph: Graph
    focus_node: IRI | Var = Var(value="focus_node")
    # inputs
    property_paths: Optional[List[PropertyPath]] = None
    or_klasses: Optional[List[URIRef]] = None
    # outputs
    grammar: Optional[GroupGraphPatternSub] = None
    triples_list: Optional[List[SimplifiedTriple]] = None
    gpnt_list: Optional[List[GraphPatternNotTriples]] = None
    path_nodes: Optional[Dict[str, Var | IRI]] = {}
    classes_at_len: Optional[Dict[str, List[URIRef]]] = {}
    _select_vars: Optional[List[Var]] = None

    def from_graph(self):
        self.property_paths = []
        _single_class = next(self.graph.objects(self.uri, SH["class"]), None)
        if _single_class:
            self.or_klasses = [URIRef(_single_class)]

        # look for sh:or statements and process classes from these NB only sh:or / sh:class is handled at present.
        or_classes = next(self.graph.objects(self.uri, SH["or"]), None)
        if or_classes:
            or_bns = list(Collection(self.graph, or_classes))
            or_triples = list(self.graph.triples_choices((or_bns, SH["class"], None)))
            self.or_klasses = [URIRef(klass) for _, _, klass in or_triples]

        pp = next(self.graph.objects(self.uri, SH.path))
        if isinstance(pp, URIRef):
            self.property_paths.append(Path(value=pp))
        elif isinstance(pp, BNode):
            self._process_property_path(pp, self.graph)

    def _process_property_path(self, pp, graph):
        if isinstance(pp, BNode):
            pred_objects_gen = graph.predicate_objects(subject=pp)
            bn_pred, bn_obj = next(pred_objects_gen, (None, None))
            if bn_obj == SH.union:
                pass
            elif bn_pred == SH.inversePath:
                self.property_paths.append(InversePath(value=bn_obj))
            # elif bn_pred == SH.alternativePath:
            #     predicates.extend(list(Collection(self.profile_graph, bn_obj)))
            else:  # sequence paths
                paths = list(Collection(graph, pp))
                for path in paths:
                    self._process_property_path(path, graph)

    def to_grammar(self):

        # set up the path nodes - either from supplied values or set as variables
        for i, property_path in enumerate(self.property_paths):
            path_node_str = f"path_node_{i+1}"
            if path_node_str not in self.path_nodes:
                self.path_nodes[path_node_str] = Var(value=path_node_str)

        self.triples_list = []
        len_pp = len(self.property_paths)
        # sh:class applies to the end of sequence paths
        path_node_term = self.path_nodes[f"path_node_{len_pp}"]

        # useful for determining which endpoint property shape should be used when a request comes in on endpoint
        self.classes_at_len[f"path_node_{len_pp}"] = self.or_klasses

        if self.or_klasses:
            if len(self.or_klasses) == 1:
                self.triples_list.append(
                    SimplifiedTriple(
                        subject=path_node_term,
                        predicate=IRI(value=RDF.type),
                        object=IRI(value=self.or_klasses[0]),
                    )
                )
            else:
                self.triples_list.append(
                    SimplifiedTriple(
                        subject=path_node_term,
                        predicate=IRI(value=RDF.type),
                        object=Var(value=f"path_node_classes_{len_pp}"),
                    )
                )
                dbvs = [
                    DataBlockValue(value=IRI(value=klass)) for klass in self.or_klasses
                ]
                self.gpnt_list.append(
                    GraphPatternNotTriples(
                        content=InlineData(
                            data_block=DataBlock(
                                block=InlineDataOneVar(
                                    variable=Var(value=f"path_node_classes_{len_pp}"),
                                    datablockvalues=dbvs,
                                )
                            )
                        )
                    )
                )

        if self.property_paths:
            for i, property_path in enumerate(self.property_paths):

                path_node_var = self.path_nodes[f"path_node_{i + 1}"]
                if i == 0:
                    focus_or_path_node = self.focus_node
                else:
                    focus_or_path_node = self.path_nodes[f"path_node_{i}"]
                if isinstance(property_path, Path):
                    # vanilla property path
                    self.triples_list.append(
                        SimplifiedTriple(
                            subject=focus_or_path_node,
                            predicate=IRI(value=property_path.value),
                            object=path_node_var,
                        )
                    )
                elif isinstance(property_path, InversePath):
                    self.triples_list.append(
                        SimplifiedTriple(
                            subject=path_node_var,
                            predicate=IRI(value=property_path.value),
                            object=focus_or_path_node,
                        )
                    )


class PropertyPath(BaseModel):
    class Config:
        arbitrary_types_allowed = True

    uri: Optional[URIRef] = None


class Path(PropertyPath):
    value: URIRef


class SequencePath(PropertyPath):
    value: List[PropertyPath]


class InversePath(PropertyPath):
    value: URIRef

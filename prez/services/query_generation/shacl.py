from __future__ import annotations

from string import Template
from typing import List, Optional, Any, Dict, Literal as TypingLiteral, Union

from pydantic import BaseModel
from rdflib import URIRef, BNode, Graph
from rdflib.collection import Collection
from rdflib.namespace import SH, RDF
from rdflib.term import Node

from prez.reference_data.prez_ns import ONT, SHEXT
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
    kind: TypingLiteral["endpoint", "profile"]
    focus_node: Union[Var, IRI]
    targetNode: Optional[URIRef] = None
    targetClasses: Optional[List[Node]] = []
    propertyShapesURIs: Optional[List[Node]] = []
    target: Optional[Node] = None
    rules: Optional[List[Node]] = []
    propertyShapes: Optional[List[PropertyShape]] = []
    triples_list: Optional[List[SimplifiedTriple]] = []
    gpnt_list: Optional[List[GraphPatternNotTriples]] = []
    rule_triples: Optional[List[SimplifiedTriple]] = []
    path_nodes: Optional[Dict[str, Var | IRI]] = {}
    classes_at_len: Optional[Dict[str, List[URIRef]]] = {}
    hierarchy_level: Optional[int] = None
    select_template: Optional[Template] = None
    bnode_depth: Optional[int] = None

    def from_graph(self):  # TODO this can be a SPARQL select against the system graph.
        self.bnode_depth = next(
            self.graph.objects(self.uri, SHEXT["bnode-depth"]), None
        )
        self.targetNode = next(self.graph.objects(self.uri, SH.targetNode), None)
        self.targetClasses = list(self.graph.objects(self.uri, SH.targetClass))
        self.propertyShapesURIs = list(self.graph.objects(self.uri, SH.property))
        self.target = next(self.graph.objects(self.uri, SH.target), None)
        self.rules = list(self.graph.objects(self.uri, SH.rule))
        self.propertyShapes = [
            PropertyShape(
                uri=ps_uri,
                graph=self.graph,
                kind=self.kind,
                focus_node=self.focus_node,
                path_nodes=self.path_nodes,
            )
            for ps_uri in self.propertyShapesURIs
        ]
        self.hierarchy_level = next(
            self.graph.objects(self.uri, ONT.hierarchyLevel), None
        )
        if not self.hierarchy_level and self.kind == "endpoint":
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
        if self.bnode_depth:
            self._build_bnode_blocks()

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

    def _process_target(self):
        self.select_template = Template(
            str(self.endpoint_graph.value(self.target, SH.select, default=None))
        )

    def _process_rules(self):
        for rule_node in self.rule_nodes:
            subject = self.graph.value(subject=rule_node, predicate=SH.subject)
            predicate = self.graph.value(subject=rule_node, predicate=SH.predicate)
            object = self.graph.value(subject=rule_node, predicate=SH.object)
            if subject == SH.this:
                subject = self.focus_node
            subject, predicate, object = self.sh_rule_type_conversion(
                [subject, predicate, object]
            )
            self.rule_triples.append(
                SimplifiedTriple(subject=subject, predicate=predicate, object=object)
            )

    def _process_property_shapes(self):
        for shape in self.propertyShapes:
            self.triples_list.extend(shape.triples_list)
            self.gpnt_list.extend(shape.gpnt_list)
            self.path_nodes = self.path_nodes | shape.path_nodes
            self.classes_at_len = self.classes_at_len | shape.classes_at_len
        # deduplicate
        self.triples_list = list(set(self.triples_list))

    def _build_bnode_blocks(self):
        max_depth = int(self.bnode_depth)

        def optional_gpnt(depth):
            # graph pattern or triples block list, which will contain the filter, and any nested optional blocks
            gpotb = [
                GraphPatternNotTriples(
                    content=Filter(
                        constraint=Constraint(
                            content=BuiltInCall.create_with_one_expr(
                                "isBLANK",
                                PrimaryExpression(content=Var(value=f"bn_o_{depth}")),
                            )
                        )
                    )
                ),
            ]

            # recursive call to build nested optional blocks
            if depth < max_depth:
                gpotb.append(optional_gpnt(depth + 1))

            # triples to go inside the optional block
            triples = []
            if depth == 1:
                triples.append(
                    SimplifiedTriple(
                        subject=self.focus_node,
                        predicate=Var(value=f"bn_p_{depth}"),
                        object=Var(value=f"bn_o_{depth}"),
                    )
                )
            triples.append(
                SimplifiedTriple(
                    subject=Var(value=f"bn_o_{depth}"),
                    predicate=Var(value=f"bn_p_{depth + 1}"),
                    object=Var(value=f"bn_o_{depth + 1}"),
                )
            )

            # optional block containing triples
            opt_gpnt = GraphPatternNotTriples(
                content=OptionalGraphPattern(
                    group_graph_pattern=GroupGraphPattern(
                        content=GroupGraphPatternSub(
                            triples_block=TriplesBlock(triples=triples),
                            graph_patterns_or_triples_blocks=gpotb,
                        )
                    )
                )
            )
            return opt_gpnt

        nested_ogp = optional_gpnt(depth=1)
        self.gpnt_list.append(nested_ogp)


class PropertyShape(Shape):
    uri: URIRef | BNode  # URI of the shape
    graph: Graph
    kind: TypingLiteral["endpoint", "profile"]
    focus_node: Union[IRI, Var]
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

    @property
    def minCount(self):
        minc = next(self.graph.objects(self.uri, SH.minCount), None)
        if minc is not None:
            return int(minc)

    @property
    def maxCount(self):
        maxc = next(self.graph.objects(self.uri, SH.maxCount), None)
        if maxc is not None:
            return int(maxc)

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

        pps = list(self.graph.objects(self.uri, SH.path))
        for pp in pps:
            self._process_property_path(pp)
        # get the longest property path first - for endpoints this will be the path any path_nodes apply to
        self.property_paths = sorted(
            self.property_paths, key=lambda x: len(x), reverse=True
        )

    def _process_property_path(self, pp):
        if isinstance(pp, URIRef):
            self.property_paths.append(Path(value=pp))
        elif isinstance(pp, BNode):
            pred_objects_gen = self.graph.predicate_objects(subject=pp)
            bn_pred, bn_obj = next(pred_objects_gen, (None, None))
            if bn_obj == SH.union:
                union_list = list(Collection(self.graph, pp))
                if union_list != [SH.union]:
                    union_list_bnode = union_list[1]
                union_items = list(Collection(self.graph, union_list_bnode))
                for item in union_items:
                    self._process_property_path(item)
            elif bn_pred == SH.inversePath:
                self.property_paths.append(InversePath(value=bn_obj))
            # elif bn_pred == SH.alternativePath:
            #     predicates.extend(list(Collection(self.profile_graph, bn_obj)))
            else:  # sequence paths
                paths = list(Collection(self.graph, pp))
                sp_list = []
                for path in paths:
                    if isinstance(path, BNode):
                        pred_objects_gen = self.graph.predicate_objects(subject=path)
                        bn_pred, bn_obj = next(pred_objects_gen, (None, None))
                        if bn_pred == SH.inversePath:
                            sp_list.append(InversePath(value=bn_obj))
                    elif isinstance(path, URIRef):
                        sp_list.append(Path(value=path))
                self.property_paths.append(SequencePath(value=sp_list))

    def to_grammar(self):
        # label nodes in the inner select and profile part of the query differently for clarity.
        if self.kind == "endpoint":
            path_or_prop = "path"
        elif self.kind == "profile":
            path_or_prop = "prof"

        # set up the path nodes - either from supplied values or set as variables
        total_individual_nodes = sum([len(i) for i in self.property_paths])
        for i in range(total_individual_nodes):
            path_node_str = f"{path_or_prop}_node_{i + 1}"
            if path_node_str not in self.path_nodes:
                self.path_nodes[path_node_str] = Var(value=path_node_str)

        self.triples_list = []
        len_pp = max([len(i) for i in self.property_paths])
        # sh:class applies to the end of sequence paths
        if f"{path_or_prop}_node_{len_pp}" in self.path_nodes:
            path_node_term = self.path_nodes[f"{path_or_prop}_node_{len_pp}"]
        else:
            path_node_term = Var(value=f"{path_or_prop}_node_{len_pp}")

        # useful for determining which endpoint property shape should be used when a request comes in on endpoint
        self.classes_at_len[f"{path_or_prop}_node_{len_pp}"] = self.or_klasses

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
                        object=Var(value=f"{path_or_prop}_node_classes_{len_pp}"),
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
                                    variable=Var(
                                        value=f"{path_or_prop}_node_classes_{len_pp}"
                                    ),
                                    datablockvalues=dbvs,
                                )
                            )
                        )
                    )
                )

        if self.property_paths:
            i = 0
            for property_path in self.property_paths:
                if f"{path_or_prop}_node_{i + 1}" in self.path_nodes:
                    path_node_1 = self.path_nodes[f"{path_or_prop}_node_{i + 1}"]
                else:
                    path_node_1 = Var(value=f"{path_or_prop}_node_{i + 1}")
                # for sequence paths up to length two:
                if f"{path_or_prop}_node_{i + 2}" in self.path_nodes:
                    path_node_2 = self.path_nodes[f"{path_or_prop}_node_{i + 2}"]
                else:
                    path_node_2 = Var(value=f"{path_or_prop}_node_{i + 2}")

                if isinstance(property_path, Path):
                    if property_path.value == SHEXT.allPredicateValues:
                        pred = Var(value="preds")
                    else:
                        pred = IRI(value=property_path.value)
                    # vanilla property path
                    self.triples_list.append(
                        SimplifiedTriple(
                            subject=self.focus_node,
                            predicate=pred,
                            object=path_node_1,
                        )
                    )
                    i += 1

                elif isinstance(property_path, InversePath):
                    self.triples_list.append(
                        SimplifiedTriple(
                            subject=path_node_1,
                            predicate=IRI(value=property_path.value),
                            object=self.focus_node,
                        )
                    )
                    i += 1

                elif isinstance(property_path, SequencePath):
                    for j, path in enumerate(property_path.value):
                        if isinstance(path, Path):
                            if j == 0:
                                self.triples_list.append(
                                    SimplifiedTriple(
                                        subject=self.focus_node,
                                        predicate=IRI(value=path.value),
                                        object=path_node_1,
                                    )
                                )
                            else:
                                self.triples_list.append(
                                    SimplifiedTriple(
                                        subject=path_node_1,
                                        predicate=IRI(value=path.value),
                                        object=path_node_2,
                                    )
                                )
                        elif isinstance(path, InversePath):
                            if j == 0:
                                self.triples_list.append(
                                    SimplifiedTriple(
                                        subject=path_node_1,
                                        predicate=IRI(value=path.value),
                                        object=self.focus_node,
                                    )
                                )
                            else:
                                self.triples_list.append(
                                    SimplifiedTriple(
                                        subject=path_node_2,
                                        predicate=IRI(value=path.value),
                                        object=path_node_1,
                                    )
                                )
                    i += len(property_path)

        if self.minCount == 0:
            # triples = self.triples_list.copy()
            self.gpnt_list.append(
                GraphPatternNotTriples(
                    content=OptionalGraphPattern(
                        group_graph_pattern=GroupGraphPattern(
                            content=GroupGraphPatternSub(
                                triples_block=TriplesBlock(triples=self.triples_list)
                            )
                        )
                    )
                )
            )
            self.triples_list = []

        if self.maxCount == 0:
            for p in self.property_paths:
                assert isinstance(p, Path)  # only support filtering direct predicates

            # reset the triples list
            self.triples_list = [
                SimplifiedTriple(
                    subject=path_node_term,
                    predicate=Var(value="excluded_props"),
                    object=Var(value="excluded_prop_vals"),
                )
            ]

            values = [
                PrimaryExpression(content=IRIOrFunction(iri=IRI(value=p.value)))
                for p in self.property_paths
            ]
            gpnt = GraphPatternNotTriples(
                content=Filter.filter_relational(
                    focus=PrimaryExpression(content=Var(value="excluded_props")),
                    comparators=values,
                    operator="NOT IN",
                )
            )
            self.gpnt_list.append(gpnt)


class PropertyPath(BaseModel):
    class Config:
        arbitrary_types_allowed = True

    uri: Optional[URIRef] = None


class Path(PropertyPath):
    value: URIRef

    def __len__(self):
        return 1


class SequencePath(PropertyPath):
    value: List[PropertyPath]

    def __len__(self):
        return len(self.value)


class InversePath(PropertyPath):
    value: URIRef

    def __len__(self):
        return 1

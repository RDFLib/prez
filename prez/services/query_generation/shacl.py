from __future__ import annotations

import logging
from string import Template
from typing import Any, Dict, List
from typing import Literal as TypingLiteral
from typing import Optional, Tuple, Type, Union

from pydantic import BaseModel
from rdflib import RDFS, BNode, Graph, URIRef
from rdflib.collection import Collection
from rdflib.namespace import RDF, SH
from rdflib.term import Node, Literal
from sparql_grammar_pydantic import (
    IRI,
    BuiltInCall,
    Constraint,
    DataBlock,
    DataBlockValue,
    Filter,
    GraphNodePath,
    GraphPatternNotTriples,
    GraphTerm,
    GroupGraphPattern,
    GroupGraphPatternSub,
    GroupOrUnionGraphPattern,
    InlineData,
    InlineDataOneVar,
    IRIOrFunction,
    ObjectListPath,
    ObjectPath,
    OptionalGraphPattern,
    PathAlternative,
    PathElt,
    PathEltOrInverse,
    PathMod,
    PathPrimary,
    PathSequence,
    PrimaryExpression,
    PropertyListPathNotEmpty,
    SG_Path,
    TriplesBlock,
    TriplesSameSubject,
    TriplesSameSubjectPath,
    Var,
    VarOrTerm,
    VerbPath,
)

from prez.reference_data.prez_ns import ONT, SHEXT

log = logging.getLogger(__name__)


class Shape(BaseModel):
    class Config:
        arbitrary_types_allowed = True

    def __init__(self, **data: Any):
        super().__init__(**data)
        self.tss_list = []
        self.tssp_list = []
        self.gpnt_list = []
        self.from_graph()
        self.to_grammar()

    def add_triple_to_tss_and_tssp(self, triple: Tuple):
        self.tss_list.append(TriplesSameSubject.from_spo(*triple))
        self.tssp_list.append(TriplesSameSubjectPath.from_spo(*triple))

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
    tss_list: Optional[List[TriplesSameSubject]] = []
    tssp_list: Optional[List[TriplesSameSubjectPath]] = []
    gpnt_list: Optional[List[GraphPatternNotTriples]] = []
    rule_triples: Optional[TriplesSameSubjectPath] = []
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
                shape_number=i,
            )
            for i, ps_uri in enumerate(self.propertyShapesURIs)
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

    def _process_class_targets(self):
        if len(self.targetClasses) == 1:
            if self.targetClasses == [RDFS.Resource]:
                pass
            else:
                self.add_triple_to_tss_and_tssp(
                    (
                        self.focus_node,
                        IRI(value=RDF.type),
                        IRI(value=self.targetClasses[0]),
                    )
                )
        elif len(self.targetClasses) > 1:
            self.add_triple_to_tss_and_tssp(
                (self.focus_node, IRI(value=RDF.type), Var(value="focus_classes"))
            )
            dbvs = [
                DataBlockValue(value=IRI(value=klass)) for klass in self.targetClasses
            ]
            self.gpnt_list.append(
                GraphPatternNotTriples(
                    content=InlineData(
                        data_block=DataBlock(
                            block=InlineDataOneVar(
                                variable=Var(value="focus_classes"),
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
            self.rule_triples.append((subject, predicate, object))

    def _process_property_shapes(self):
        for shape in self.propertyShapes:
            self.tssp_list.extend(shape.tssp_list)
            self.tss_list.extend(shape.tss_list)
            self.gpnt_list.extend(shape.gpnt_list)
            self.path_nodes = self.path_nodes | shape.path_nodes
            self.classes_at_len = self.classes_at_len | shape.classes_at_len
        # deduplicate
        # self.tssp_list = list(set(self.tssp_list))  #TODO requires re implementation of hash functions for classes


class PropertyShape(Shape):
    uri: URIRef | BNode  # URI of the shape
    graph: Graph
    kind: TypingLiteral["endpoint", "profile", "fts"]
    focus_node: Union[IRI, Var]
    # inputs
    shape_number: int = 0
    and_property_paths: Optional[List[PropertyPath]] = None
    union_property_paths: Optional[List[PropertyPath]] = None
    or_klasses: Optional[List[URIRef]] = None
    # outputs
    grammar: Optional[GroupGraphPatternSub] = None
    tss_list: Optional[List[TriplesSameSubject]] = []
    tssp_list: Optional[List[TriplesSameSubjectPath]] = []
    gpnt_list: Optional[List[GraphPatternNotTriples]] = None
    path_nodes: Optional[Dict[str, Var | IRI]] = {}
    classes_at_len: Optional[Dict[str, List[URIRef]]] = {}
    _select_vars: Optional[List[Var]] = None
    bnode_depth: Optional[int] = None

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
        self.and_property_paths = []
        self.union_property_paths = []
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
        self.and_property_paths = sorted(
            self.and_property_paths, key=lambda x: len(x), reverse=True
        )

    def _parse_property_path(self, pp: Node) -> PropertyPath:
        """Recursively parses a SHACL path node (URIRef or BNode) into a PropertyPath object."""
        if isinstance(pp, URIRef):
            return Path(value=pp)
        elif isinstance(pp, BNode):
            # Check for sequence first (RDF list structure)
            if self.graph.value(pp, RDF.first):
                path_elements = []
                current = pp
                while current != RDF.nil:
                    first = self.graph.value(current, RDF.first)
                    if first:
                        path_elements.append(self._parse_property_path(first))
                    else:
                        raise ValueError(f"Malformed RDF list structure at {current}")
                    current = self.graph.value(current, RDF.rest)
                    if not current:
                        raise ValueError(f"Malformed RDF list structure: missing rdf:rest from {pp}")
                return SequencePath(value=path_elements)

            # If not a sequence, check for other SHACL path constructs
            pred_objects = list(self.graph.predicate_objects(subject=pp))
            if not pred_objects:
                raise ValueError(f"BNode {pp} has no predicate-objects in SHACL path.")

            if len(pred_objects) == 1:
                bn_pred, bn_obj = pred_objects[0]

                if bn_pred == SH.union:
                    # Handle sh:union - process each item and add to union paths
                    # Note: This path itself doesn't return a single PropertyPath object,
                    # instead it triggers processing of its members which are added via _add_path.
                    # We return None here to signal that _process_property_path should not call _add_path for the sh:union BNode itself.
                    union_list = list(Collection(self.graph, bn_obj))
                    for item in union_list:
                        self._process_property_path(item, union=True) # Force union=True
                    return None # Signal that the union BNode itself doesn't represent a single path to add
                elif bn_pred == SH.alternativePath:
                    alt_list = list(Collection(self.graph, bn_obj))
                    return AlternativePath(value=[self._parse_property_path(item) for item in alt_list])
                elif bn_pred in PRED_TO_PATH_CLASS:
                    path_class = PRED_TO_PATH_CLASS[bn_pred]
                    if path_class == BNodeDepth:
                        return BNodeDepth(value=bn_obj) # Assumes bn_obj is Literal
                    elif path_class in [InversePath, ZeroOrMorePath, OneOrMorePath, ZeroOrOnePath]:
                        # These take another path as their value
                        inner_path = self._parse_property_path(bn_obj)
                        return path_class(value=inner_path)
                    else:
                        raise ValueError(f"Unhandled path class {path_class} for predicate {bn_pred}")
                else:
                    raise ValueError(f"Unsupported SHACL path construct for BNode {pp} with predicate {bn_pred}")
            else:
                raise ValueError(f"BNode {pp} has multiple predicate-objects in SHACL path context.")
        else:
            raise ValueError(f"Unexpected node type in SHACL path: {type(pp)}")

    def _process_property_path(self, pp: Node, union: bool = False):
        """Processes a SHACL path node by parsing it and adding it to the appropriate list."""
        try:
            path_object = self._parse_property_path(pp)
            # Check if path_object is None (e.g., handled by sh:union) before adding
            if path_object is not None:
                 self._add_path(path_object, union)
        except ValueError as e:
            # Log or handle parsing errors appropriately
            log.debug(f"Could not parse property path {pp}. Error: {e}")
            # Decide if you want to skip this path or raise the error further

    def _add_path(self, path: PropertyPath, union: bool):
        """Adds a parsed PropertyPath object to the appropriate list."""
        if union:
            self.union_property_paths.append(path)
        else:
            self.and_property_paths.append(path)

    def to_grammar(self):
        # label nodes in the inner select and profile part of the query differently for clarity.
        if self.kind == "endpoint":
            path_or_prop = "path"
        elif (self.kind == "profile") or (self.kind == "fts"):
            path_or_prop = f"prof_{self.shape_number + 1}"

        # set up the path nodes - either from supplied values or set as variables
        total_individual_nodes = sum([len(i) for i in self.and_property_paths])
        for i in range(total_individual_nodes):
            path_node_str = f"{path_or_prop}_node_{i + 1}"
            if path_node_str not in self.path_nodes:
                self.path_nodes[path_node_str] = Var(value=path_node_str)

        self.tssp_list = []
        if path_or_prop == "path":
            len_pp = max([len(i) for i in self.and_property_paths])
            # sh:class applies to the end of sequence paths
            if f"{path_or_prop}_node_{len_pp}" in self.path_nodes:
                path_node_term = self.path_nodes[f"{path_or_prop}_node_{len_pp}"]
            else:
                path_node_term = Var(value=f"{path_or_prop}_node_{len_pp}")

            # useful for determining which endpoint property shape should be used when a request comes in on endpoint
            self.classes_at_len[f"{path_or_prop}_node_{len_pp}"] = self.or_klasses

            if self.or_klasses:
                if len(self.or_klasses) == 1:
                    self.add_triple_to_tss_and_tssp(
                        (
                            path_node_term,
                            IRI(value=RDF.type),
                            IRI(value=self.or_klasses[0]),
                        )
                    )
                else:
                    self.add_triple_to_tss_and_tssp(
                        (
                            path_node_term,
                            IRI(value=RDF.type),
                            Var(value=f"{path_or_prop}_node_classes_{len_pp}"),
                        )
                    )
                    dbvs = [
                        DataBlockValue(value=IRI(value=klass))
                        for klass in self.or_klasses
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

        pp_i = 0
        tssp_list_for_and = []
        tssp_list_for_union = []
        if self.and_property_paths:
            self.process_property_paths(
                self.and_property_paths, path_or_prop, tssp_list_for_and, pp_i
            )
        for inner_list in tssp_list_for_and:
            self.tssp_list.extend(inner_list)
        if self.union_property_paths:
            self.process_property_paths(
                self.union_property_paths, path_or_prop, tssp_list_for_union, pp_i
            )
            ggp_list = []
            for inner_list in tssp_list_for_union:
                ggp_list.append(
                    GroupGraphPattern(
                        content=GroupGraphPatternSub(
                            triples_block=TriplesBlock.from_tssp_list(inner_list)
                        )
                    )
                )
            if self.bnode_depth:
                ggp_list.extend(self._build_bnode_blocks())
            self.gpnt_list.append(
                GraphPatternNotTriples(
                    content=GroupOrUnionGraphPattern(group_graph_patterns=ggp_list)
                )
            )

        if self.bnode_depth and not self.union_property_paths:
            self.gpnt_list.append(
                GraphPatternNotTriples(
                    content=GroupOrUnionGraphPattern(group_graph_patterns=self._build_bnode_blocks())
                )
            )

        if self.minCount == 0:
            self.gpnt_list.append(
                GraphPatternNotTriples(
                    content=OptionalGraphPattern(
                        group_graph_pattern=GroupGraphPattern(
                            content=GroupGraphPatternSub(
                                triples_block=TriplesBlock.from_tssp_list(
                                    self.tssp_list
                                )
                            )
                        )
                    )
                )
            )
            self.tssp_list = []

        if self.maxCount == 0:
            for p in self.and_property_paths:
                assert isinstance(p, Path)  # only support filtering direct predicates

            # reset the triples list
            self.tssp_list = [
                TriplesSameSubjectPath.from_spo(
                    subject=self.focus_node,
                    predicate=Var(value="preds"),
                    object=Var(value="excluded_pred_vals"),
                )
            ]

            values = [
                PrimaryExpression(content=IRIOrFunction(iri=IRI(value=p.value)))
                for p in self.and_property_paths
            ]
            gpnt = GraphPatternNotTriples(
                content=Filter.filter_relational(
                    focus=PrimaryExpression(content=Var(value="preds")),
                    comparators=values,
                    operator="NOT IN",
                )
            )
            self.gpnt_list.append(gpnt)

    def process_property_paths(self, property_paths, path_or_prop, tssp_list, pp_i):
        for property_path in property_paths:
            # Always create path_node_1 as it's needed everywhere
            if f"{path_or_prop}_node_{pp_i + 1}" in self.path_nodes:
                path_node_1 = self.path_nodes[f"{path_or_prop}_node_{pp_i + 1}"]
            else:
                path_node_1 = Var(value=f"{path_or_prop}_node_{pp_i + 1}")

            # Create additional nodes only if we have a sequence path
            path_nodes = {0: path_node_1}  # Start with path_node_1
            if isinstance(property_path, SequencePath):
                seq_path_len = len(property_path.value)
                for i in range(1, seq_path_len):
                    node_key = f"{path_or_prop}_node_{pp_i + i + 1}"
                    if node_key in self.path_nodes:
                        path_nodes[i] = self.path_nodes[node_key]
                    else:
                        path_nodes[i] = Var(value=node_key)

            current_tssp = []

            if isinstance(property_path, Path):
                if property_path.value == SHEXT.allPredicateValues:
                    pred = Var(value="preds")
                    obj = Var(value="vals")
                else:
                    pred = IRI(value=property_path.value)
                    obj = path_node_1
                if self.kind == "fts":
                    triple = (self.focus_node, pred, Var(value="fts_search_node"))
                else:
                    triple = (self.focus_node, pred, obj)
                self.tss_list.append(TriplesSameSubject.from_spo(*triple))
                current_tssp.append(TriplesSameSubjectPath.from_spo(*triple))
                pp_i += 1

            elif isinstance(property_path, BNodeDepth):
                self.bnode_depth = int(property_path.value)

            elif isinstance(property_path, AlternativePath):
                # Handle AlternativePath - generate SPARQL using '|'
                tssp = _tssp_for_alternative(
                    self.focus_node,
                    property_path.value, # List of paths
                    path_node_1
                )
                current_tssp.append(tssp)
                pp_i += 1 # Increment once for the whole alternative path

            elif isinstance(property_path, InversePath):
                if self.kind == "fts":
                    triple = (
                        Var(value="fts_search_node"),
                        IRI(value=property_path.value.value),
                        self.focus_node,
                    )
                elif property_path.value.value == SHEXT.allPredicateValues:
                    triple = (
                        path_node_1,
                        Var(value="inbound_props"),
                        self.focus_node,
                    )
                else:
                    triple = (
                        path_node_1,
                        IRI(value=property_path.value.value),
                        self.focus_node,
                    )
                self.tss_list.append(TriplesSameSubject.from_spo(*triple))
                current_tssp.append(TriplesSameSubjectPath.from_spo(*triple))
                pp_i += 1

            elif isinstance(
                    property_path, Union[ZeroOrMorePath, OneOrMorePath, ZeroOrOnePath]
            ):
                self.tssp_list.append(
                    _tssp_for_pathmods(
                        self.focus_node,
                        IRI(value=property_path.value.value),
                        path_node_1,
                        property_path.operand,
                    )
                )
                pp_i += 1

            elif isinstance(property_path, SequencePath):
                preds_pathmods_inverse = []
                seq_path_len = len(property_path.value)
                inner_path_type = None
                for j, path in enumerate(property_path.value):
                    if isinstance(path, Path):
                        inner_path_type = "path"
                        if self.kind == "endpoint":
                            preds_pathmods_inverse.append(
                                (IRI(value=path.value), None, False)
                            )
                        elif (self.kind == "profile") or (self.kind == "fts"):
                            if j == 0:
                                triple = (
                                    self.focus_node,
                                    IRI(value=path.value),
                                    path_nodes[0],  # This is path_node_1
                                )
                            else:
                                if path.value == SHEXT.allPredicateValues:
                                    triple = (
                                        path_nodes[j - 1],  # Previous node
                                        Var(value="sequence_all_preds"),
                                        path_nodes[j],
                                    )
                                else:
                                    triple = (
                                        path_nodes[j - 1],  # Previous node
                                        IRI(value=path.value),
                                        path_nodes[j],  # Current node
                                    )
                    elif isinstance(path, InversePath):
                        inner_path_type = "inverse"
                        if self.kind == "endpoint":
                            preds_pathmods_inverse.append(
                                (IRI(value=path.value.value), None, True)
                            )
                        elif (self.kind == "profile") or (self.kind == "fts"):
                            if j == 0:
                                triple = (
                                    path_nodes[0],  # path_node_1
                                    IRI(value=path.value.value),
                                    self.focus_node,
                                )
                            else:
                                triple = (
                                    path_nodes[j],  # Current node
                                    IRI(value=path.value.value),
                                    path_nodes[j - 1],  # Previous node
                                )
                    elif isinstance(
                            path, Union[ZeroOrMorePath, OneOrMorePath, ZeroOrOnePath]
                    ):
                        inner_path_type = "zero_one_more"
                        if isinstance(path.value, Path):
                            preds_pathmods_inverse.append(
                                (IRI(value=path.value.value), path.operand, False)
                            )
                        elif isinstance(path.value, InversePath):
                            preds_pathmods_inverse.append(
                                (IRI(value=path.value.value.value), path.operand, True)
                            )
                    if self.kind == "profile":
                        self.tss_list.append(TriplesSameSubject.from_spo(*triple))
                        current_tssp.append(TriplesSameSubjectPath.from_spo(*triple))
                    elif self.kind == "fts":
                        if (
                                j == seq_path_len - 1
                        ):  # we're at the end of the sequence path
                            if inner_path_type != "inverse":
                                new_triple = triple[:2] + (
                                    Var(value="fts_search_node"),
                                )
                            else:
                                new_triple = (Var(value="fts_search_node"),) + triple[
                                                                               1:
                                                                               ]
                            self.tss_list.append(
                                TriplesSameSubject.from_spo(*new_triple)
                            )
                            current_tssp.append(
                                TriplesSameSubjectPath.from_spo(*new_triple)
                            )
                        else:
                            self.tss_list.append(TriplesSameSubject.from_spo(*triple))
                            current_tssp.append(
                                TriplesSameSubjectPath.from_spo(*triple)
                            )
                pp_i += len(property_path.value)
                if self.kind == "endpoint":
                    tssp = _tssp_for_sequence(
                        self.focus_node,
                        preds_pathmods_inverse,
                        path_nodes[seq_path_len - 1],  # Last node
                    )
                    current_tssp.append(tssp)

            if current_tssp:
                tssp_list.append(current_tssp)

        return pp_i

    def _build_bnode_blocks(self):
        """
        Build separate blocks for each depth level up to max_depth.
        These blocks will be combined with UNION in the calling code.
        Each block represents a path of increasing depth through blank nodes.
        """
        # List to collect all the graph pattern not triples
        bn_ggp_list = []

        for depth in range(1, self.bnode_depth + 1):
            # Create a block for the current depth
            ggp = self._create_depth_block(depth)
            bn_ggp_list.append(ggp)
        return bn_ggp_list


    def _create_depth_block(self, max_depth):
        """
        Create a single block that captures paths up to the given depth.
        """
        # Collect all triples for this depth
        all_triples = []
        # Collect all filters for this depth
        all_filters = []

        # Add the first triple with the focus node
        all_triples.append(
            (
                self.focus_node,
                Var(value=f"bn_p_1"),
                Var(value=f"bn_o_1"),
            )
        )

        # Add subsequent triples and filters for each level of depth
        for depth in range(1, max_depth + 1):
            # Add filter for the current depth
            all_filters.append(
                GraphPatternNotTriples(
                    content=Filter(
                        constraint=Constraint(
                            content=BuiltInCall.create_with_one_expr(
                                "isBLANK",
                                PrimaryExpression(content=Var(value=f"bn_o_{depth}")),
                            )
                        )
                    )
                )
            )

            # Add the next triple in the chain (except for the first one which was already added)
            all_triples.append(
                (
                    Var(value=f"bn_o_{depth}"),
                    Var(value=f"bn_p_{depth + 1}"),
                    Var(value=f"bn_o_{depth + 1}"),
                )
            )

        # Create Triples Same Subject Path for WHERE clause
        tssp_list = [TriplesSameSubjectPath.from_spo(*triple) for triple in all_triples[::-1]]

        # Create Triples Same Subject for CONSTRUCT TRIPLES clause
        tss_list = [TriplesSameSubject.from_spo(*triple) for triple in all_triples[::-1]]
        self.tss_list.extend(tss_list)

        # Create the group graph pattern with all triples and filters
        ggp = GroupGraphPattern(
                        content=GroupGraphPatternSub(
                            triples_block=TriplesBlock.from_tssp_list(tssp_list),
                            graph_patterns_or_triples_blocks=all_filters,
                        )
                    )
        return ggp


def _tssp_for_pathmods(focus_node: IRI | Var, pred, obj, pathmod):
    """
    Creates path modifier TriplesSameSubjectPath objects.
    """
    if isinstance(focus_node, IRI):
        focus_node = GraphTerm(content=focus_node)
    return TriplesSameSubjectPath(
        content=(
            VarOrTerm(varorterm=focus_node),
            PropertyListPathNotEmpty(
                first_pair=(
                    VerbPath(
                        path=SG_Path(
                            path_alternative=PathAlternative(
                                sequence_paths=[
                                    PathSequence(
                                        list_path_elt_or_inverse=[
                                            PathEltOrInverse(
                                                path_elt=PathElt(
                                                    path_primary=PathPrimary(
                                                        value=pred,
                                                    ),
                                                    path_mod=PathMod(pathmod=pathmod),
                                                )
                                            )
                                        ]
                                    )
                                ]
                            )
                        )
                    ),
                    ObjectListPath(
                        object_paths=[
                            ObjectPath(
                                graph_node_path=GraphNodePath(
                                    varorterm_or_triplesnodepath=VarOrTerm(
                                        varorterm=obj
                                    )
                                )
                            )
                        ]
                    ),
                )
            ),
        )
    )


def _build_path_elt_or_inverse(path_item: PropertyPath) -> PathEltOrInverse:
    """Helper function to build PathEltOrInverse from different PropertyPath types."""
    inverse = False
    path_mod = None
    primary_value = None

    if isinstance(path_item, InversePath):
        inverse = True
        # Unwrap the InversePath to get the actual path element
        path_item = path_item.value

    if isinstance(path_item, (ZeroOrMorePath, OneOrMorePath, ZeroOrOnePath)):
        path_mod = PathMod(pathmod=path_item.operand)
        # Unwrap to get the base path
        path_item = path_item.value

    if isinstance(path_item, Path):
        primary_value = IRI(value=path_item.value)
    # Add handling for other potential path types if necessary

    if primary_value is None:
        # This case should ideally be handled based on expected path structures
        # For now, raise an error or handle default case
        raise ValueError(f"Unsupported path type in alternative/sequence: {type(path_item)}")

    return PathEltOrInverse(
        path_elt=PathElt(
            path_primary=PathPrimary(value=primary_value),
            path_mod=path_mod,
        ),
        inverse=inverse,
    )


def _tssp_for_alternative(focus_node, alternative_paths: list[PropertyPath], obj):
    """Creates TSSP for Alternative Paths using '|'."""
    if isinstance(focus_node, IRI):
        focus_node = GraphTerm(content=focus_node)
    if isinstance(obj, IRI):
        obj = GraphTerm(content=obj)

    sequence_paths = []
    for alt_path in alternative_paths:
        # Each alternative is treated as a sequence of one element for PathAlternative structure
        # We need to handle potentially complex paths within each alternative
        # Using _build_path_elt_or_inverse helps encapsulate this logic
        list_path_elt_or_inverse = [_build_path_elt_or_inverse(alt_path)]
        sequence_paths.append(PathSequence(list_path_elt_or_inverse=list_path_elt_or_inverse))

    return TriplesSameSubjectPath(
        content=(
            VarOrTerm(varorterm=focus_node),
            PropertyListPathNotEmpty(
                first_pair=(
                    VerbPath(
                        path=SG_Path(
                            path_alternative=PathAlternative(
                                sequence_paths=sequence_paths # This creates the path1 | path2 structure
                            )
                        )
                    ),
                    ObjectListPath(
                        object_paths=[
                            ObjectPath(
                                graph_node_path=GraphNodePath(
                                    varorterm_or_triplesnodepath=VarOrTerm(
                                        varorterm=obj
                                    )
                                )
                            )
                        ]
                    ),
                )
            ),
        )
    )


def _tssp_for_sequence(
        focus_node, preds_pathmods_inverse: list[tuple[IRI, str | None, bool]], obj
):
    """
    Creates TSSP for Sequence Paths, supporting *?+ pathmods and inverse paths TriplesSameSubjectPath objects.
    """
    if isinstance(focus_node, IRI):
        focus_node = GraphTerm(content=focus_node)
    if isinstance(obj, IRI):
        obj = GraphTerm(content=obj)
    # Refactored to use the helper function _build_path_elt_or_inverse
    list_path_elt_or_inverse = []
    # The input format preds_pathmods_inverse needs to be adapted or the helper used differently.
    # Assuming preds_pathmods_inverse provides enough info to construct PropertyPath objects or similar structure.
    # This part requires careful adaptation based on how preds_pathmods_inverse is populated.
    # For demonstration, let's assume we can map it:
    for pred_iri, pathmod_operand, inverse_flag in preds_pathmods_inverse:
        # Construct a temporary simple Path or modified path based on input
        # This is a simplification; the actual structure might be more complex
        base_path = Path(value=pred_iri.value) # Assuming pred is IRI here
        current_path = base_path
        if pathmod_operand == "*":
            current_path = ZeroOrMorePath(value=base_path)
        elif pathmod_operand == "+":
            current_path = OneOrMorePath(value=base_path)
        elif pathmod_operand == "?":
            current_path = ZeroOrOnePath(value=base_path)

        if inverse_flag:
            current_path = InversePath(value=current_path)

        list_path_elt_or_inverse.append(_build_path_elt_or_inverse(current_path))

    return TriplesSameSubjectPath(
        content=(
            VarOrTerm(varorterm=focus_node),
            PropertyListPathNotEmpty(
                first_pair=(
                    VerbPath(
                        path=SG_Path(
                            path_alternative=PathAlternative(
                                sequence_paths=[
                                    PathSequence(
                                        list_path_elt_or_inverse=list_path_elt_or_inverse
                                    )
                                ]
                            )
                        )
                    ),
                    ObjectListPath(
                        object_paths=[
                            ObjectPath(
                                graph_node_path=GraphNodePath(
                                    varorterm_or_triplesnodepath=VarOrTerm(
                                        varorterm=obj
                                    )
                                )
                            )
                        ]
                    ),
                )
            ),
        )
    )


class PropertyPath(BaseModel):
    class Config:
        arbitrary_types_allowed = True

    uri: Optional[URIRef] = None

    def __len__(self):
        return 1  # Default length for all PropertyPath subclasses


class Path(PropertyPath):
    value: URIRef


class SequencePath(PropertyPath):
    value: List[PropertyPath]

    def __len__(self):
        return len(self.value)  # Override to return the length of the sequence


class InversePath(PropertyPath):
    value: PropertyPath


class ZeroOrMorePath(PropertyPath):
    value: PropertyPath
    operand: str = "*"


class OneOrMorePath(PropertyPath):
    value: PropertyPath
    operand: str = "+"


class ZeroOrOnePath(PropertyPath):
    value: PropertyPath
    operand: str = "?"


class AlternativePath(PropertyPath):
    value: List[PropertyPath]

    def __len__(self):
        return len(self.value)


class BNodeDepth(PropertyPath):
    value: Literal

PRED_TO_PATH_CLASS: Dict[URIRef, Type[PropertyPath]] = {
    SH.inversePath: InversePath,
    SH.zeroOrMorePath: ZeroOrMorePath,
    SH.oneOrMorePath: OneOrMorePath,
    SH.zeroOrOnePath: ZeroOrOnePath,
    SH.alternativePath: AlternativePath,
    SHEXT.bNodeDepth: BNodeDepth,
}

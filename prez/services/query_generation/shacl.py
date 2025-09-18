from __future__ import annotations

import logging
from string import Template
from typing import Any, Dict, List
from typing import Literal as TypingLiteral
from typing import Optional, Tuple, Type, Union

from pydantic import BaseModel
from rdflib import RDFS, BNode, Graph, URIRef, XSD
from rdflib.collection import Collection
from rdflib.namespace import RDF, SH
from rdflib.term import Node, Literal
from sparql_grammar_pydantic import (
    IRI,
    Bind,
    BuiltInCall,
    Constraint,
    DataBlock,
    DataBlockValue,
    Expression,
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
    RDFLiteral,
    BooleanLiteral,
    NumericLiteral,
)

from prez.config import settings
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
    var_counter_offset: int = 0  # Offset for variable numbering to ensure uniqueness
    and_property_paths: Optional[List[PropertyPath]] = None
    union_property_paths: Optional[List[PropertyPath]] = None
    or_klasses: Optional[List[URIRef]] = None
    # outputs
    grammar: Optional[GroupGraphPatternSub] = None
    tss_list: Optional[List[TriplesSameSubject]] = []
    tssp_list: Optional[List[TriplesSameSubjectPath]] = []
    gpnt_list: Optional[List[GraphPatternNotTriples]] = []  # Initialize as list
    path_nodes: Optional[Dict[str, Var | IRI]] = {}
    classes_at_len: Optional[Dict[str, List[URIRef]]] = {}
    _select_vars: Optional[List[Var]] = None
    bnode_depth: Optional[int] = None
    union_tssps_binds: Optional[List[Dict[str, Any]]] = []  # New attribute
    all_predicate_values_counter: int = 0

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
        # Context Guard: Check if this PropertyShape is inside a sh:filterShape.
        # This checks for both direct and nested sh:property within the filter.
        parents = list(self.graph.subjects(SH.property, self.uri))
        for parent in parents:
            grandparents = list(self.graph.subjects(SH.filterShape, parent))
            if grandparents:
                return  # This is a direct child of a filter shape's property.
            great_grandparents = list(self.graph.subjects(SH.property, parent))
            for great_grandparent in great_grandparents:
                if list(self.graph.subjects(SH.filterShape, great_grandparent)):
                    return  # This is a nested child of a filter shape's property.

        self.and_property_paths = []
        self.union_property_paths = []
        _single_class = next(self.graph.objects(self.uri, SH["class"]), None)
        if _single_class:
            self.or_klasses = [URIRef(_single_class)]

        or_classes = next(self.graph.objects(self.uri, SH["or"]), None)
        if or_classes:
            or_bns = list(Collection(self.graph, or_classes))
            or_triples = list(self.graph.triples_choices((or_bns, SH["class"], None)))
            self.or_klasses = [URIRef(klass) for _, _, klass in or_triples]

        shape_level_path_alias = next(
            self.graph.objects(self.uri, SHEXT.pathAlias), None
        )

        filter_shape_uri = next(self.graph.objects(self.uri, SH.filterShape), None)
        filter_shape_tssp_list = []
        if filter_shape_uri:
            filter_shape_tssp_list = self._parse_filter_shape(filter_shape_uri)

        pps = list(self.graph.objects(self.uri, SH.path))
        for pp in pps:
            self._add_path_to_shape(
                pp,
                shape_level_alias=shape_level_path_alias,
                filter_shape_tssp_list=filter_shape_tssp_list,
            )

        self.and_property_paths = sorted(
            self.and_property_paths, key=lambda x: len(x), reverse=True
        )

    def _create_facet_binds(
        self, property_path: PropertyPath, value_var: Union[Var, IRI]
    ) -> List[GraphPatternNotTriples]:
        """Creates BIND clauses for facetName and facetValue based on path alias or simple path predicate."""
        binds = []
        facet_name_iri = None
        # Ensure value_var is wrapped correctly for Expression
        if isinstance(value_var, Var):
            facet_value_expr_content = value_var
        elif isinstance(value_var, IRI):
            facet_value_expr_content = IRIOrFunction(iri=value_var)
        else:  # Handle other potential types like Literal if needed, or raise error
            raise TypeError(
                f"Unsupported type for facet value variable: {type(value_var)}"
            )

        facet_value_expr = PrimaryExpression(content=facet_value_expr_content)

        if hasattr(property_path, "path_alias") and property_path.path_alias:
            facet_name_iri = IRI(value=property_path.path_alias)
        elif isinstance(property_path, Path):
            # Only create binds if it's a simple Path and no alias exists
            facet_name_iri = IRI(value=property_path.value)

        if facet_name_iri:
            # Bind for facetName
            bind_name_gpnt = GraphPatternNotTriples(
                content=Bind(
                    expression=Expression.from_primary_expression(
                        PrimaryExpression(content=IRIOrFunction(iri=facet_name_iri))
                    ),
                    var=Var(value="facetName"),
                )
            )
            binds.append(bind_name_gpnt)

            # Bind for facetValue
            bind_value_gpnt = GraphPatternNotTriples(
                content=Bind(
                    expression=Expression.from_primary_expression(facet_value_expr),
                    var=Var(value="facetValue"),
                )
            )
            binds.append(bind_value_gpnt)

        return binds

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
                        raise ValueError(
                            f"Malformed RDF list structure: missing rdf:rest from {pp}"
                        )
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
                        self._add_path_to_shape(item, union=True)  # Force union=True
                    return None  # Signal that the union BNode itself doesn't represent a single path to add
                elif bn_pred == SH.alternativePath:
                    alt_list = list(Collection(self.graph, bn_obj))
                    return AlternativePath(
                        value=[self._parse_property_path(item) for item in alt_list]
                    )
                elif bn_pred in PRED_TO_PATH_CLASS:
                    path_class = PRED_TO_PATH_CLASS[bn_pred]
                    if path_class == BNodeDepth:
                        return BNodeDepth(value=bn_obj)  # Assumes bn_obj is Literal
                    elif path_class in [
                        InversePath,
                        ZeroOrMorePath,
                        OneOrMorePath,
                        ZeroOrOnePath,
                    ]:
                        # These take another path as their value
                        inner_path = self._parse_property_path(bn_obj)
                        return path_class(value=inner_path)
                    else:
                        raise ValueError(
                            f"Unhandled path class {path_class} for predicate {bn_pred}"
                        )
                else:
                    raise ValueError(
                        f"Unsupported SHACL path construct for BNode {pp} with predicate {bn_pred}"
                    )
            else:
                raise ValueError(
                    f"BNode {pp} has multiple predicate-objects in SHACL path context."
                )
        else:
            raise ValueError(f"Unexpected node type in SHACL path: {type(pp)}")

    def _parse_filter_shape(
        self, filter_shape_uri: Node
    ) -> List[TriplesSameSubjectPath]:
        """
        Parses a sh:filterShape structure and returns the corresponding triple patterns.
        This is a narrow implementation based on the specific use case described in the documentation.
        """
        patterns = []
        # sh:filterShape -> sh:property
        prop_bnode = next(self.graph.objects(filter_shape_uri, SH.property))
        # sh:property -> sh:property (sibling)
        sibling_prop_bnode = next(self.graph.objects(prop_bnode, SH.property))
        # sibling sh:property -> sh:path
        sibling_path = next(self.graph.objects(sibling_prop_bnode, SH.path))
        # sibling sh:property -> sh:hasValue
        sibling_has_value = list(self.graph.objects(sibling_prop_bnode, SH.hasValue))
        if sibling_has_value:
            val = sibling_has_value[0]
            iri_or_lit = None
            if isinstance(val, URIRef):
                iri_or_lit = IRI(value=str(val))
            elif isinstance(val, Literal):
                if val.datatype:
                    if val.datatype == XSD.boolean:
                        iri_or_lit = BooleanLiteral(value=bool(val))
                    elif val.datatype in [XSD.integer, XSD.int]:
                        val = int(val)
                        iri_or_lit = NumericLiteral(value=val)
                    elif val.datatype in [XSD.decimal, XSD.double, XSD.float]:
                        val = float(val)
                        iri_or_lit = NumericLiteral(value=val)
                else:
                    iri_or_lit = RDFLiteral(value=str(val))
            patterns.append(
                TriplesSameSubjectPath.from_spo(
                    self.focus_node, IRI(value=str(sibling_path)), iri_or_lit
                )
            )
        else:  # check for sh:in
            sibling_in_bn = next(self.graph.objects(sibling_prop_bnode, SH["in"]))
            # sibling_in_vals = list(Collection(self.graph, sibling_in_bn))
            if sibling_in_bn:
                raise NotImplementedError()
            else:
                raise ValueError(
                    "Expected sh:hasValue or sh:in for the filterShape values."
                )
        return patterns

    def _add_path_to_shape(
        self,
        pp: Node,
        union: bool = False,
        shape_level_alias: Optional[URIRef] = None,
        filter_shape_tssp_list: Optional[List[TriplesSameSubjectPath]] = None,
    ):
        """Processes a SHACL path node by parsing it and adding it to the appropriate list."""
        path_to_parse = pp
        path_alias_value = shape_level_alias
        bnode_class = None
        final_filter_shape_tssp_list = filter_shape_tssp_list or []

        if isinstance(pp, BNode):
            bnode_alias = next(
                self.graph.objects(subject=pp, predicate=SHEXT.pathAlias), None
            )
            if bnode_alias:
                path_alias_value = bnode_alias

            bnode_class = next(
                self.graph.objects(subject=pp, predicate=SH["class"]), None
            )

            nested_path_node = next(
                self.graph.objects(subject=pp, predicate=SH.path), None
            )
            if nested_path_node:
                path_to_parse = nested_path_node

        try:
            path_object = self._parse_property_path(path_to_parse)
            if path_object is not None:
                if path_alias_value:
                    path_object.path_alias = path_alias_value
                if bnode_class:
                    path_object.sh_class = bnode_class
                if final_filter_shape_tssp_list:
                    path_object.filter_shape_tssp_list = final_filter_shape_tssp_list
                self._add_path(path_object, union)
        except ValueError as e:
            log.warning(
                f"Could not parse property path {path_to_parse} (original node: {pp}). Error: {e}"
            )

    def _add_path(self, path: PropertyPath, union: bool):
        """Adds a parsed PropertyPath object to the appropriate list."""
        log.debug(
            f"Adding path to {'union' if union else 'and'} list: {path!r}, Current alias: {path.path_alias!r}"
        )
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
        # Process AND paths
        if self.and_property_paths:
            and_paths_data, pp_i = self._generate_sparql_for_paths(
                self.and_property_paths, path_or_prop, pp_i
            )
            for item in and_paths_data:
                self.tssp_list.extend(item["tssp_list"])

        # Process UNION paths
        if self.union_property_paths:
            union_paths_data, pp_i = self._generate_sparql_for_paths(
                self.union_property_paths, path_or_prop, pp_i
            )
            # Store the processed data (including TSSP lists and facet binds) for union paths
            self.union_tssps_binds = union_paths_data

            ggp_list = []  # Initialize list for patterns from union paths
            for item in union_paths_data:
                # Only add a group pattern if there are triples for it
                # This prevents adding {} for paths like bNodeDepth that don't generate direct triples here
                if item["tssp_list"]:
                    ggps_content = GroupGraphPatternSub(
                        triples_block=TriplesBlock.from_tssp_list(item["tssp_list"]),
                        # TODO: Incorporate facet binds if needed
                    )
                    ggp_list.append(GroupGraphPattern(content=ggps_content))

            # Add BNode blocks if bnode_depth was set (potentially by one of the union paths)
            if self.bnode_depth:
                bnode_blocks = self._build_bnode_blocks()
                if bnode_blocks:  # Ensure it's not empty
                    ggp_list.extend(bnode_blocks)

            # Only add the UNION if there are patterns to union
            if ggp_list:
                self.gpnt_list.append(
                    GraphPatternNotTriples(
                        content=GroupOrUnionGraphPattern(group_graph_patterns=ggp_list)
                    )
                )

        # Handle BNode depth separately if there were no union paths but bnode depth is set
        elif (
            self.bnode_depth
        ):  # Changed from 'if self.bnode_depth and not self.union_property_paths:'
            self.gpnt_list.append(
                GraphPatternNotTriples(
                    content=GroupOrUnionGraphPattern(
                        group_graph_patterns=self._build_bnode_blocks()
                    )
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

    def _generate_sparql_for_paths(
        self, property_paths, path_or_prop, start_pp_i
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Processes property paths, generating TSSP lists and facet binds."""
        processed_paths_data = []
        pp_i = start_pp_i
        for property_path in property_paths:
            # Determine if we should use the path alias for CONSTRUCT triples
            use_alias = (
                settings.use_path_aliases
                and hasattr(property_path, "path_alias")
                and property_path.path_alias
            )

            # Always create path_node_1 as it's needed everywhere
            if self.kind == "fts":
                if isinstance(property_path, SequencePath):
                    # For FTS sequence paths, intermediate nodes are numbered, final node is fts_search_node
                    path_node_1 = Var(value=f"fts_search_node_{pp_i + 1}")
                else:
                    path_node_1 = Var(value="fts_search_node")
            elif (
                f"{path_or_prop}_node_{pp_i + 1 + self.var_counter_offset}"
                in self.path_nodes
            ):
                path_node_1 = self.path_nodes[
                    f"{path_or_prop}_node_{pp_i + 1 + self.var_counter_offset}"
                ]
            else:
                path_node_1 = Var(
                    value=f"{path_or_prop}_node_{pp_i + 1 + self.var_counter_offset}"
                )

            # Create additional nodes only if we have a sequence path
            path_nodes = {0: path_node_1}  # Start with path_node_1
            obj_node = (
                path_node_1  # Default object node for simple paths, inverse, etc.
            )
            if isinstance(property_path, SequencePath):
                seq_path_len = len(property_path.value)
                for i in range(1, seq_path_len):
                    if self.kind == "fts":
                        # For FTS sequence paths: intermediate nodes are numbered, final node is fts_search_node
                        if i == seq_path_len - 1:  # Last node in sequence
                            path_nodes[i] = Var(value="fts_search_node")
                        else:  # Intermediate nodes
                            path_nodes[i] = Var(value=f"fts_search_node_{pp_i + i + 1}")
                    else:
                        node_key = f"{path_or_prop}_node_{pp_i + i + 1}"
                        if node_key in self.path_nodes:
                            path_nodes[i] = self.path_nodes[node_key]
                        else:
                            path_nodes[i] = Var(value=node_key)
                obj_node = path_nodes[
                    seq_path_len - 1
                ]  # Object node is the last in sequence
            elif isinstance(property_path, BNodeDepth):
                obj_node = (
                    None  # BNodeDepth doesn't have a specific object node for binding
                )

            current_tssp = []
            current_facet_binds = []
            if obj_node:  # Only create binds if we have a valid object node
                current_facet_binds = self._create_facet_binds(property_path, obj_node)

            if property_path.filter_shape_tssp_list:
                current_tssp.extend(property_path.filter_shape_tssp_list)

            if isinstance(property_path, Path):
                if property_path.value == SHEXT.allPredicateValues:
                    pred = Var(value="preds")
                    obj = Var(value="vals")
                else:
                    pred = IRI(value=property_path.value)
                    obj = path_node_1
                # WHERE clause triple (always added)
                where_triple = (self.focus_node, pred, obj)
                current_tssp.append(TriplesSameSubjectPath.from_spo(*where_triple))

                # CONSTRUCT clause triple (conditional on alias)
                if not use_alias:
                    if self.kind == "fts":
                        construct_triple = (
                            self.focus_node,
                            pred,
                            Var(value="fts_search_node"),
                        )
                    else:
                        construct_triple = (self.focus_node, pred, obj)
                    self.tss_list.append(TriplesSameSubject.from_spo(*construct_triple))
                # pp_i increment and alias handling happens at the end or in the 'if use_alias:' block

                # check for sh:class
                if property_path.sh_class:
                    type_triple = (
                        path_node_1,
                        IRI(value=RDF.type),
                        IRI(value=property_path.sh_class),
                    )
                    # Add to WHERE and CONSTRUCT clauses
                    current_tssp.append(TriplesSameSubjectPath.from_spo(*type_triple))
                    self.tss_list.append(TriplesSameSubject.from_spo(*type_triple))

            elif isinstance(property_path, BNodeDepth):
                # BNodeDepth doesn't directly generate triples here, just sets the depth
                # Alias logic (if use_alias is True) will handle pp_i increment and continue below
                self.bnode_depth = int(property_path.value)

            elif isinstance(property_path, AlternativePath):
                # Handle AlternativePath - generate SPARQL using '|'
                tssp = _tssp_for_alternative(
                    self.focus_node, property_path.value, path_node_1  # List of paths
                )
                current_tssp.append(tssp)
                # pp_i increment and alias handling happens at the end or in the 'if use_alias:' block

            elif isinstance(property_path, InversePath):
                # Determine subject and object for WHERE clause triple
                if property_path.value.value == SHEXT.allPredicateValues:
                    subj = path_node_1
                    pred = Var(value="inbound_props")
                    obj = self.focus_node
                else:
                    subj = path_node_1
                    pred = IRI(value=property_path.value.value)
                    obj = self.focus_node

                # WHERE clause triple (always added)
                where_triple = (subj, pred, obj)
                current_tssp.append(TriplesSameSubjectPath.from_spo(*where_triple))

                # CONSTRUCT clause triple (conditional on alias)
                if not use_alias:
                    if self.kind == "fts":
                        # FTS replaces the focus node in the construct triple
                        construct_triple = (subj, pred, Var(value="fts_search_node"))
                    else:
                        construct_triple = where_triple  # Use the same triple structure
                    self.tss_list.append(TriplesSameSubject.from_spo(*construct_triple))
                # pp_i increment and alias handling happens at the end or in the 'if use_alias:' block

            elif isinstance(
                property_path, Union[ZeroOrMorePath, OneOrMorePath, ZeroOrOnePath]
            ):
                # WHERE clause uses path mods (always added)
                tssp = _tssp_for_pathmods(
                    self.focus_node,
                    IRI(value=property_path.value.value),
                    path_node_1,
                    property_path.operand,
                )
                self.tssp_list.append(
                    tssp
                )  # Note: Appends directly to self.tssp_list, not current_tssp
                # CONSTRUCT clause triple (conditional on alias) - Path mods usually don't add simple TSS triples directly,
                # but if an alias exists, we add the simplified alias triple. This is handled by the 'if use_alias:' block.
                # pp_i increment and alias handling happens at the end or in the 'if use_alias:' block

            elif isinstance(property_path, SequencePath):
                seq_path_len = len(property_path.value)

                if self.kind == "endpoint":
                    # For endpoints, the entire sequence is treated as one complex path.
                    # We collect all PropertyPath objects that make up the sequence.
                    sequence_elements_for_endpoint: list[PropertyPath] = []
                    for (
                        path_segment
                    ) in (
                        property_path.value
                    ):  # Iterate through the actual PropertyPath objects
                        sequence_elements_for_endpoint.append(path_segment)

                    # Generate the single TSSP for the entire sequence.
                    # The object of this sequence is the last node allocated for this sequence.
                    final_sequence_obj_node = path_nodes[seq_path_len - 1]
                    tssp_seq = _tssp_for_sequence(
                        self.focus_node,
                        sequence_elements_for_endpoint,
                        final_sequence_obj_node,
                    )
                    # This single TSSP represents the whole sequence path for the WHERE clause.
                    current_tssp = [tssp_seq]
                    # CONSTRUCT logic for endpoints with SequencePath is typically handled by aliases
                    # or by the general alias logic later if `use_alias` is true.
                    # If not using an alias, the CONSTRUCT part for a complex sequence path
                    # doesn't usually add individual simple triples from the sequence here.
                else:  # self.kind == "profile" or self.kind == "fts"
                    # For profile/fts, process each segment of the sequence individually.
                    # `current_tssp` will accumulate TSSP for each segment.
                    for j, path_segment in enumerate(property_path.value):
                        triple = None  # Reset for each segment; used for simple (s,p,o) generation
                        inner_path_type = None  # To track segment type for FTS handling

                        # Determine subject and object for the current segment
                        segment_subject_node = (
                            self.focus_node if j == 0 else path_nodes[j - 1]
                        )
                        # The object of the current segment is path_nodes[j]
                        # (path_nodes[0] is path_node_1, path_nodes[1] is path_node_2, etc.)
                        segment_object_node = path_nodes[j]

                        if isinstance(path_segment, Path):
                            inner_path_type = "path"
                            if path_segment.value == SHEXT.allPredicateValues:
                                var_name = f"sequence_all_preds_{self.all_predicate_values_counter}"
                                self.all_predicate_values_counter += 1
                                triple = (
                                    segment_subject_node,
                                    Var(value=var_name),
                                    segment_object_node,
                                )
                            else:
                                triple = (
                                    segment_subject_node,
                                    IRI(value=path_segment.value),
                                    segment_object_node,
                                )

                        elif isinstance(path_segment, InversePath):
                            inner_path_type = "inverse"
                            # For inverse, subject and object are swapped in the triple
                            triple = (
                                segment_object_node,
                                IRI(value=path_segment.value.value),
                                segment_subject_node,
                            )

                        elif isinstance(
                            path_segment, (ZeroOrMorePath, OneOrMorePath, ZeroOrOnePath)
                        ):
                            inner_path_type = "zero_one_more"
                            # For profile/fts, complex path modifiers in a sequence are tricky.
                            # If the inner value is a simple Path, we can attempt a modified TSSP.
                            # Otherwise, it's too complex for simple triple generation here.
                            if isinstance(path_segment.value, Path):
                                tssp_mod_segment = _tssp_for_pathmods(
                                    segment_subject_node,
                                    IRI(value=path_segment.value.value),
                                    segment_object_node,
                                    path_segment.operand,
                                )
                                current_tssp.append(tssp_mod_segment)
                            # `triple` remains None, so no simple triple added to CONSTRUCT unless aliased.

                        elif isinstance(path_segment, AlternativePath):
                            inner_path_type = "alternative"
                            # For profile/fts, AlternativePath within a sequence needs to generate a UNION block.

                            group_graph_patterns_for_union = []
                            for alt_path_item in path_segment.value:
                                # Each alt_path_item is a PropertyPath (e.g., Path, InversePath)
                                # We need to generate a simple TSSP for it.
                                tssp_for_alt = _tssp_for_path_segment(
                                    segment_subject_node,
                                    alt_path_item,
                                    segment_object_node,
                                )
                                group_graph_patterns_for_union.append(
                                    GroupGraphPattern(
                                        content=GroupGraphPatternSub(
                                            triples_block=TriplesBlock.from_tssp_list(
                                                [tssp_for_alt]
                                            )
                                        )
                                    )
                                )
                                # For CONSTRUCT, add individual triples for each alternative if not aliased
                                if not use_alias:
                                    # Need to get the correct predicate for the CONSTRUCT
                                    construct_pred_iri = None
                                    construct_subj = segment_subject_node
                                    construct_obj = segment_object_node
                                    if isinstance(alt_path_item, Path):
                                        construct_pred_iri = IRI(
                                            value=alt_path_item.value
                                        )
                                    elif isinstance(
                                        alt_path_item, InversePath
                                    ) and isinstance(alt_path_item.value, Path):
                                        construct_pred_iri = IRI(
                                            value=alt_path_item.value.value
                                        )
                                        construct_subj, construct_obj = (
                                            construct_obj,
                                            construct_subj,
                                        )  # Swap for inverse
                                    elif isinstance(
                                        alt_path_item,
                                        (ZeroOrMorePath, OneOrMorePath, ZeroOrOnePath),
                                    ) and isinstance(alt_path_item.value, Path):
                                        construct_pred_iri = IRI(
                                            value=alt_path_item.value.value
                                        )  # Use base predicate for construct

                                    if construct_pred_iri:
                                        self.tss_list.append(
                                            TriplesSameSubject.from_spo(
                                                construct_subj,
                                                construct_pred_iri,
                                                construct_obj,
                                            )
                                        )

                            if group_graph_patterns_for_union:
                                union_gpnt = GraphPatternNotTriples(
                                    content=GroupOrUnionGraphPattern(
                                        group_graph_patterns=[
                                            GroupGraphPattern(
                                                content=GroupGraphPatternSub(
                                                    graph_patterns_or_triples_blocks=[
                                                        GraphPatternNotTriples(
                                                            content=GroupOrUnionGraphPattern(
                                                                group_graph_patterns=group_graph_patterns_for_union
                                                            )
                                                        )
                                                    ]
                                                )
                                            )
                                        ]
                                    )
                                )
                                self.gpnt_list.append(union_gpnt)
                            # `triple` remains None, as it's handled by the union_gp and tss_list additions.

                        # Process the generated simple triple (if any) for this segment (profile/fts)
                        # This block is for simple Path, InversePath, and ZeroOrOneMorePath that result in a 'triple'
                        if triple:
                            # Adjust object for FTS if it's the last segment
                            if j == seq_path_len - 1 and self.kind == "fts":
                                # Use the actual final segment object node variable name for FTS
                                final_fts_var = segment_object_node
                                if (
                                    inner_path_type != "inverse"
                                ):  # s P o -> s P fts_node
                                    where_triple = triple[:2] + (final_fts_var,)
                                else:  # o P s -> fts_node P s (subject of inverse is fts_node)
                                    where_triple = (final_fts_var,) + triple[1:]
                            else:
                                where_triple = triple

                            current_tssp.append(
                                TriplesSameSubjectPath.from_spo(*where_triple)
                            )
                            # Add to CONSTRUCT only if the entire SequencePath is NOT aliased
                            if not use_alias:
                                self.tss_list.append(
                                    TriplesSameSubject.from_spo(*where_triple)
                                )

                    # After processing all segments, handle sh:class if present on the *entire* SequencePath
                    if (
                        property_path.sh_class
                    ):  # property_path is the SequencePath itself
                        # sh:class applies to the object of the last segment of the sequence
                        final_segment_object_node = path_nodes[seq_path_len - 1]
                        type_triple_for_seq_class = (
                            final_segment_object_node,
                            IRI(value=RDF.type),
                            IRI(value=property_path.sh_class),
                        )
                        current_tssp.append(
                            TriplesSameSubjectPath.from_spo(*type_triple_for_seq_class)
                        )
                        if not use_alias:  # Add to CONSTRUCT if not aliased
                            self.tss_list.append(
                                TriplesSameSubject.from_spo(*type_triple_for_seq_class)
                            )
                # End of SequencePath specific logic

            # --- Alias Handling and pp_i Increment ---
            if use_alias:
                # Determine the correct object node for the alias triple
                if isinstance(property_path, SequencePath):
                    seq_path_len = len(property_path.value)
                    # The final node is the last one in the sequence path's node dictionary
                    obj_node = path_nodes[seq_path_len - 1]
                elif isinstance(property_path, BNodeDepth):
                    # BNodeDepth doesn't map to a specific node, skip alias TSS generation
                    obj_node = None  # Signal to skip adding triple
                else:
                    # For Path, InversePath, AlternativePath, Modifiers - use path_node_1
                    obj_node = path_node_1

                # Add the simplified alias triple to TSS list if obj_node is valid
                if obj_node:
                    alias_triple = (
                        self.focus_node,
                        IRI(value=property_path.path_alias),
                        obj_node,
                    )
                    self.tss_list.append(TriplesSameSubject.from_spo(*alias_triple))

                # Increment pp_i based on the path length and continue
                if isinstance(property_path, SequencePath):
                    pp_i += len(property_path.value)
                elif isinstance(property_path, BNodeDepth):
                    pass  # BNodeDepth doesn't consume a node index
                else:
                    pp_i += 1  # Increment by 1 for other path types
                # Continue to the next property_path, skipping original TSS logic below this point
                # (Note: WHERE clause TSSP logic above this point was already executed)
                # REMOVED continue statement to ensure tssp_list is always appended below

            else:
                # If not using alias, increment pp_i based on the path type processed by original logic
                if isinstance(property_path, SequencePath):
                    pp_i += len(property_path.value)
                elif isinstance(property_path, BNodeDepth):
                    pass  # BNodeDepth doesn't consume a node index
                else:
                    pp_i += 1  # Increment by 1 for other path types

            # Add the collected WHERE clause triples and facet binds for this path
            # Determine the value for path_alias_or_path
            path_alias_or_path_value = None
            if property_path.path_alias:
                path_alias_or_path_value = property_path.path_alias
            elif isinstance(property_path, Path):
                path_alias_or_path_value = property_path.value

            processed_paths_data.append(
                {
                    "tssp_list": current_tssp,
                    "facet_binds": current_facet_binds,
                    "path_alias_or_path": path_alias_or_path_value,
                }
            )

        return processed_paths_data, pp_i

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
        tssp_list = [
            TriplesSameSubjectPath.from_spo(*triple) for triple in all_triples[::-1]
        ]

        # Create Triples Same Subject for CONSTRUCT TRIPLES clause
        tss_list = [
            TriplesSameSubject.from_spo(*triple) for triple in all_triples[::-1]
        ]
        self.tss_list.extend(tss_list)

        # Create the group graph pattern with all triples and filters
        ggp = GroupGraphPattern(
            content=GroupGraphPatternSub(
                triples_block=TriplesBlock.from_tssp_list(tssp_list),
                graph_patterns_or_triples_blocks=all_filters,
            )
        )
        return ggp


def _get_base_predicate_iri(path_segment: PropertyPath) -> IRI:
    """Extracts the base IRI from a PropertyPath segment for use as a predicate."""
    if isinstance(path_segment, Path):
        if path_segment.value == SHEXT.allPredicateValues:
            # This case should ideally be handled before calling this,
            # as allPredicateValues doesn't map to a single IRI.
            raise ValueError(
                "Cannot get a single base IRI for SHEXT.allPredicateValues"
            )
        return IRI(value=path_segment.value)
    elif isinstance(
        path_segment, (InversePath, ZeroOrMorePath, OneOrMorePath, ZeroOrOnePath)
    ):
        # For these, the 'value' is another PropertyPath, so recursively get its base IRI
        return _get_base_predicate_iri(path_segment.value)
    # AlternativePath does not have a single base predicate.
    # SequencePath also does not have a single base predicate.
    else:
        raise ValueError(
            f"Unsupported PropertyPath type for base predicate extraction: {type(path_segment)}"
        )


def _tssp_for_path_segment(
    subject: Var | IRI | BNode, path_segment: PropertyPath, obj: Var | IRI | BNode
) -> TriplesSameSubjectPath:
    """
    Creates a TriplesSameSubjectPath for a single PropertyPath segment.
    Handles simple paths, inverse paths, and paths with cardinality modifiers.
    """
    # Ensure subject and obj are GraphTerm if they are IRIs for TriplesSameSubjectPath.from_spo
    # However, _tssp_for_pathmods handles this internally.
    # TriplesSameSubjectPath.from_spo also handles this.

    if isinstance(path_segment, Path):
        if path_segment.value == SHEXT.allPredicateValues:
            # This is a special case, from_spo expects Var or IRI for predicate
            return TriplesSameSubjectPath.from_spo(
                subject, Var(value="preds_seq_val"), obj
            )
        else:
            return TriplesSameSubjectPath.from_spo(
                subject, IRI(value=path_segment.value), obj
            )
    elif isinstance(path_segment, InversePath):
        # For inverse, subject and object are swapped in the triple
        # The predicate of the inverse path's value must be a simple Path.
        if not isinstance(path_segment.value, Path):
            raise ValueError(
                f"InversePath's value must be a Path, got {type(path_segment.value)}"
            )
        if path_segment.value.value == SHEXT.allPredicateValues:
            return TriplesSameSubjectPath.from_spo(
                obj, Var(value="preds_seq_inv_val"), subject
            )
        else:
            return TriplesSameSubjectPath.from_spo(
                obj, IRI(value=path_segment.value.value), subject
            )
    elif isinstance(path_segment, (ZeroOrMorePath, OneOrMorePath, ZeroOrOnePath)):
        # These use path modifiers in the TSSP
        # The predicate of the pathmod's value must be a simple Path.
        if not isinstance(path_segment.value, Path):
            raise ValueError(
                f"Path modifier's value must be a Path, got {type(path_segment.value)}"
            )
        return _tssp_for_pathmods(
            subject, IRI(value=path_segment.value.value), obj, path_segment.operand
        )
    # AlternativePath is handled by creating a UNION of GroupGraphPatterns, not a single TSSP.
    # SequencePath is handled by iterating its elements.
    else:
        raise ValueError(
            f"Unsupported PropertyPath type for _tssp_for_path_segment: {type(path_segment)}"
        )


def _tssp_for_pathmods(focus_node: IRI | Var, pred: IRI, obj: Var | IRI, pathmod: str):
    """
    Creates path modifier TriplesSameSubjectPath objects.
    """
    if isinstance(focus_node, IRI):
        focus_node = GraphTerm(content=focus_node)
    # Ensure obj is GraphTerm if it's an IRI for VarOrTerm
    if isinstance(obj, IRI):
        obj_term = GraphTerm(content=obj)
    else:
        obj_term = obj

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
                                                        value=pred,  # pred is already an IRI
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
                                        varorterm=obj_term  # Use the potentially wrapped obj_term
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
    """Helper function to build PathEltOrInverse from different PropertyPath types, including nested ones."""
    # Stage 1: Handle the outermost InversePath wrapper, if any.
    is_outer_inverse = False
    if isinstance(path_item, InversePath):
        is_outer_inverse = True
        path_item = path_item.value  # Unwrap

    # Stage 2: Handle the outermost PathMod wrapper, if any (applies to the potentially unwrapped path_item).
    outer_path_mod: Optional[PathMod] = None
    if isinstance(path_item, (ZeroOrMorePath, OneOrMorePath, ZeroOrOnePath)):
        outer_path_mod = PathMod(pathmod=path_item.operand)
        path_item = path_item.value  # Unwrap further

    # Stage 3: Now path_item is the "core" path.
    # It should be a simple Path (IRI), an AlternativePath, or a nested complex path
    # that needs to be braced.
    core_path_primary: PathPrimary

    if isinstance(path_item, Path):  # Base case: simple predicate
        core_path_primary = PathPrimary(value=IRI(value=path_item.value))
    elif isinstance(path_item, AlternativePath):  # Base case: ( path | path )
        alt_sg_path_sequences = []
        for alt_sub_path in path_item.value:
            # Each sub-path in an alternative is a sequence of one PathEltOrInverse.
            alt_sg_path_sequences.append(
                PathSequence(
                    list_path_elt_or_inverse=[
                        _build_path_elt_or_inverse(alt_sub_path)  # Recursive call
                    ]
                )
            )
        core_path_primary = PathPrimary(
            value=SG_Path(  # This creates the ( ... )
                path_alternative=PathAlternative(sequence_paths=alt_sg_path_sequences)
            )
        )
    elif isinstance(
        path_item, (InversePath, ZeroOrMorePath, OneOrMorePath, ZeroOrOnePath)
    ):
        # Nested complex path, e.g., ^(^p) or ^(p*).
        # The PathPrimary needs to be a braced path containing the result of a recursive call.
        core_path_primary = PathPrimary(
            value=SG_Path(  # This creates the ( ... )
                path_alternative=PathAlternative(
                    sequence_paths=[
                        PathSequence(
                            list_path_elt_or_inverse=[
                                _build_path_elt_or_inverse(
                                    path_item
                                )  # Recursive call for the nested structure
                            ]
                        )
                    ]
                )
            )
        )
    else:
        raise ValueError(
            f"Unsupported core path type '{type(path_item)}' in _build_path_elt_or_inverse."
        )

    return PathEltOrInverse(
        path_elt=PathElt(
            path_primary=core_path_primary,
            path_mod=outer_path_mod,  # Apply the extracted outermost path_mod here
        ),
        inverse=is_outer_inverse,  # Apply the extracted outermost inverse flag here
    )


def _tssp_for_alternative(focus_node, alternative_paths: list[PropertyPath], obj):
    """Creates TSSP for Alternative Paths using '|'."""
    if isinstance(focus_node, IRI):
        focus_node = GraphTerm(content=focus_node)
    if isinstance(obj, IRI):
        obj_term = GraphTerm(content=obj)
    else:
        obj_term = obj

    sequence_paths = []
    for alt_path in alternative_paths:
        # Each alternative is treated as a sequence of one element for PathAlternative structure
        # We need to handle potentially complex paths within each alternative
        # Using _build_path_elt_or_inverse helps encapsulate this logic
        list_path_elt_or_inverse = [_build_path_elt_or_inverse(alt_path)]
        sequence_paths.append(
            PathSequence(list_path_elt_or_inverse=list_path_elt_or_inverse)
        )

    return TriplesSameSubjectPath(
        content=(
            VarOrTerm(varorterm=focus_node),
            PropertyListPathNotEmpty(
                first_pair=(
                    VerbPath(
                        path=SG_Path(
                            path_alternative=PathAlternative(
                                sequence_paths=sequence_paths  # This creates the path1 | path2 structure
                            )
                        )
                    ),
                    ObjectListPath(
                        object_paths=[
                            ObjectPath(
                                graph_node_path=GraphNodePath(
                                    varorterm_or_triplesnodepath=VarOrTerm(
                                        varorterm=obj_term
                                    )
                                )
                            )
                        ]
                    ),
                )
            ),
        )
    )


def _tssp_for_sequence(focus_node, sequence_elements: list[PropertyPath], obj):
    """
    Creates TSSP for Sequence Paths from a list of PropertyPath objects.
    Supports simple paths, inverse paths, path modifiers, and alternative paths within the sequence.
    """
    if isinstance(focus_node, IRI):
        focus_node = GraphTerm(content=focus_node)
    if isinstance(obj, IRI):
        obj_term = GraphTerm(content=obj)
    else:
        obj_term = obj

    list_path_elt_or_inverse = []
    for path_element in sequence_elements:
        list_path_elt_or_inverse.append(_build_path_elt_or_inverse(path_element))

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
                                        varorterm=obj_term
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
    path_alias: Optional[URIRef] = None
    sh_class: Optional[URIRef] = None
    filter_shape_tssp_list: Optional[List[TriplesSameSubjectPath]] = []

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
        return 1


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

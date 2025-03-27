from typing import Optional

from rdflib import SKOS
from sparql_grammar_pydantic import (
    IRI,
    Bind,
    BuiltInCall,
    ConstructQuery,
    ConstructTemplate,
    ConstructTriples,
    ExistsFunc,
    Expression,
    GraphNodePath,
    GraphPatternNotTriples,
    GraphTerm,
    GroupGraphPattern,
    GroupGraphPatternSub,
    GroupOrUnionGraphPattern,
    LimitClause,
    LimitOffsetClauses,
    ObjectListPath,
    ObjectPath,
    OffsetClause,
    OrderClause,
    OrderCondition,
    PathAlternative,
    PathElt,
    PathEltOrInverse,
    PathPrimary,
    PathSequence,
    PrimaryExpression,
    PropertyListPathNotEmpty,
    SelectClause,
    SG_Path,
    SolutionModifier,
    SubSelect,
    TriplesBlock,
    TriplesSameSubject,
    TriplesSameSubjectPath,
    Var,
    VarOrTerm,
    VerbPath,
    WhereClause,
)

from prez.reference_data.prez_ns import PREZ


class ConceptHierarchyQuery(ConstructQuery):
    """
    CONSTRUCT {
      ?focus_node a ?class ;
                  prez:hasChildren ?hasChildren .
    }
    WHERE {
      ?focus_node a ?class
      {
        SELECT DISTINCT ?focus_node ?hasChildren
        WHERE {
            <http://example.org/ns#Concept-Scheme-A> <http://www.w3.org/2004/02/skos/core#hasTopConcept>|^<http://www.w3.org/2004/02/skos/core#isTopConceptOf> ?focus_node.
            ?focus_node <http://www.w3.org/2004/02/skos/core#prefLabel> ?label.
            BIND(EXISTS {?focus_node <http://www.w3.org/2004/02/skos/core#narrower>|^<http://www.w3.org/2004/02/skos/core#broader> ?grandChildren.} as ?hasChildren)
        }
        ORDER BY ?label
        OFFSET 0
        LIMIT 20
        }
    }
    """

    def __init__(
            self,
            parent_uri: IRI,
            parent_child_predicates: tuple[IRI, IRI],
            limit: int = 10,
            offset: int = 0,
            has_children_var: Var = Var(
                value="hasChildren"
            ),  # whether the focus nodes have children
            label_predicate: IRI = IRI(value=SKOS.prefLabel),
            child_grandchild_predicates: Optional[tuple[IRI, IRI]] = None,
            label_var=Var(value="label"),
    ):
        if not child_grandchild_predicates:
            child_grandchild_predicates = parent_child_predicates
        focus_node_var = Var(value="focus_node")
        grandchildren_var = Var(value="grandchildren")

        parent_child_alt = PathSequence(
            list_path_elt_or_inverse=[
                PathEltOrInverse(
                    path_elt=PathElt(
                        path_primary=PathPrimary(
                            value=parent_child_predicates[0],
                        )
                    )
                )
            ]
        )
        parent_child_sp_inverse = PathSequence(
            list_path_elt_or_inverse=[
                PathEltOrInverse(
                    path_elt=PathElt(
                        path_primary=PathPrimary(
                            value=parent_child_predicates[1],
                        )
                    ),
                    inverse=True,
                )
            ]
        )

        tssp1 = TriplesSameSubjectPath(
            content=(
                VarOrTerm(varorterm=GraphTerm(content=parent_uri)),
                PropertyListPathNotEmpty(
                    first_pair=(
                        VerbPath(
                            path=SG_Path(
                                path_alternative=PathAlternative(
                                    sequence_paths=[
                                        parent_child_alt,
                                        parent_child_sp_inverse,
                                    ]
                                )
                            )
                        ),
                        ObjectListPath(
                            object_paths=[
                                ObjectPath(
                                    graph_node_path=GraphNodePath(
                                        varorterm_or_triplesnodepath=VarOrTerm(
                                            varorterm=focus_node_var
                                        )
                                    )
                                )
                            ]
                        ),
                    )
                ),
            )
        )

        tb1 = TriplesBlock(triples=tssp1)

        child_grandchild_alt = PathSequence(
            list_path_elt_or_inverse=[
                PathEltOrInverse(
                    path_elt=PathElt(
                        path_primary=PathPrimary(
                            value=child_grandchild_predicates[0],
                        )
                    )
                )
            ]
        )
        child_grandchild_sp_inverse = PathSequence(
            list_path_elt_or_inverse=[
                PathEltOrInverse(
                    path_elt=PathElt(
                        path_primary=PathPrimary(
                            value=child_grandchild_predicates[1],
                        )
                    ),
                    inverse=True,
                )
            ]
        )

        tssp2 = TriplesSameSubjectPath(
            content=(
                VarOrTerm(varorterm=focus_node_var),
                PropertyListPathNotEmpty(
                    first_pair=(
                        VerbPath(
                            path=SG_Path(
                                path_alternative=PathAlternative(
                                    sequence_paths=[
                                        child_grandchild_alt,
                                        child_grandchild_sp_inverse,
                                    ]
                                )
                            )
                        ),
                        ObjectListPath(
                            object_paths=[
                                ObjectPath(
                                    graph_node_path=GraphNodePath(
                                        varorterm_or_triplesnodepath=VarOrTerm(
                                            varorterm=grandchildren_var
                                        )
                                    )
                                )
                            ]
                        ),
                    )
                ),
            )
        )
        bind_gpnt = GraphPatternNotTriples(
            content=Bind(
                expression=Expression.from_primary_expression(
                    PrimaryExpression(
                        content=BuiltInCall(
                            other_expressions=ExistsFunc(
                                group_graph_pattern=GroupGraphPattern(
                                    content=GroupGraphPatternSub(
                                        triples_block=TriplesBlock(triples=tssp2)
                                    )
                                )
                            )
                        )
                    )
                ),
                var=has_children_var,
            )
        )

        tb2 = TriplesBlock.from_tssp_list(
            [
                TriplesSameSubjectPath.from_spo(
                    Var(value="focus_node"),
                    label_predicate,
                    label_var
                )
            ]
        )
        tb1.triples_block = tb2

        sc = SelectClause(
            distinct=True,
            variables_or_all=[focus_node_var, has_children_var],
        )

        inner_wc = WhereClause(
            group_graph_pattern=GroupGraphPattern(
                content=GroupGraphPatternSub(
                    graph_patterns_or_triples_blocks=[tb1, bind_gpnt]
                )
            )
        )

        inner_sm = SolutionModifier(
            order_by=OrderClause(conditions=[OrderCondition(var=label_var)]),
            limit_offset=LimitOffsetClauses(
                limit_clause=LimitClause(limit=limit),
                offset_clause=OffsetClause(offset=offset),
            ),
        )

        outer_wc = WhereClause(
            group_graph_pattern=GroupGraphPattern(
                content=GroupGraphPatternSub(
                    graph_patterns_or_triples_blocks=[
                        GraphPatternNotTriples(
                            content=GroupOrUnionGraphPattern(
                                group_graph_patterns=[
                                    GroupGraphPattern(
                                        content=SubSelect(
                                            select_clause=sc,
                                            where_clause=inner_wc,
                                            solution_modifier=inner_sm,
                                        )
                                    )
                                ]
                            )
                        )
                    ]
                )
            )
        )

        ct = ConstructTemplate(
            construct_triples=ConstructTriples.from_tss_list(
                [
                    TriplesSameSubject.from_spo(
                        subject=focus_node_var,
                        predicate=IRI(value=PREZ.hasChildren),
                        object=has_children_var,
                    )
                ]
            )
        )

        super().__init__(
            construct_template=ct,
            where_clause=outer_wc,
            solution_modifier=SolutionModifier(),
        )

    @property
    def construct_triples(self):
        return self.construct_template.construct_triples

    @property
    def tss_list(self):
        return [self.construct_template.construct_triples.triples]

    @property
    def inner_select_vars(self):
        return (
            self.where_clause.group_graph_pattern.content.graph_patterns_or_triples_blocks[
                0
            ]
            .content.group_graph_patterns[0]
            .content.select_clause.variables_or_all
        )

    @property
    def inner_select_gpnt(self):
        return GraphPatternNotTriples(
            content=GroupOrUnionGraphPattern(
                group_graph_patterns=[
                    self.where_clause.group_graph_pattern.content.graph_patterns_or_triples_blocks[
                        0
                    ]
                    .content.group_graph_patterns[0]
                    .content.where_clause.group_graph_pattern
                ]
            )
        )

    @property
    def order_by(self):
        return (
            self.where_clause.group_graph_pattern.content.graph_patterns_or_triples_blocks[0]
            .content.group_graph_patterns[0].content.where_clause.group_graph_pattern.content.
            graph_patterns_or_triples_blocks[0].triples_block.triples.content[1].first_pair[0].path.path_alternative.
            sequence_paths[0].list_path_elt_or_inverse[0].path_elt.path_primary.value
        )

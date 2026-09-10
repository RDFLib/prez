from typing import Optional

from rdflib import SKOS
from sparql_grammar import (
    IRI,
    Bind,
    ConstructQuery,
    ConstructTemplate,
    ConstructTriples,
    ExistsFunc,
    Expression,
    GroupGraphPattern,
    GroupGraphPatternSub,
    GroupOrUnionGraphPattern,
    LimitOffsetClauses,
    OrderClause,
    OrderCondition,
    PathAlternative,
    PathElt,
    PathEltOrInverse,
    PathPrimary,
    SelectClause,
    SolutionModifier,
    SubSelect,
    TriplesBlock,
    TriplesSameSubject,
    TriplesSameSubjectPath,
    Var,
    WhereClause,
)

from prez.reference_data.prez_ns import PREZ


def _forward_or_inverse(forward: IRI, inverse: IRI) -> PathAlternative:
    """<forward>|^<inverse>"""
    return PathAlternative.alt(
        forward, PathEltOrInverse(PathElt(PathPrimary(inverse)), inverse=True)
    )


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

        # <parent> <child_pred>|^<parent_pred> ?focus_node .
        # ?focus_node <label_predicate> ?label .
        tb1 = TriplesBlock(
            [
                TriplesSameSubjectPath.from_spo(
                    parent_uri,
                    _forward_or_inverse(*parent_child_predicates),
                    focus_node_var,
                ),
                TriplesSameSubjectPath.from_spo(
                    focus_node_var, label_predicate, label_var
                ),
            ]
        )

        # BIND(EXISTS { ?focus_node <grandchild_pred>|^<child_pred> ?grandchildren } AS ?hasChildren)
        tssp2 = TriplesSameSubjectPath.from_spo(
            focus_node_var,
            _forward_or_inverse(*child_grandchild_predicates),
            grandchildren_var,
        )
        bind_gpnt = Bind(
            Expression.from_primary_expression(
                ExistsFunc(
                    GroupGraphPattern(GroupGraphPatternSub([TriplesBlock([tssp2])]))
                )
            ),
            has_children_var,
        )

        sc = SelectClause.create(focus_node_var, has_children_var, distinct=True)
        inner_wc = WhereClause(
            GroupGraphPattern(GroupGraphPatternSub([tb1, bind_gpnt]))
        )
        inner_sm = SolutionModifier(
            order_by=OrderClause([OrderCondition(label_var)]),
            limit_offset=LimitOffsetClauses.create(limit=limit, offset=offset),
        )
        outer_wc = WhereClause(
            GroupGraphPattern(
                GroupGraphPatternSub(
                    [
                        GroupOrUnionGraphPattern(
                            [
                                GroupGraphPattern(
                                    SubSelect(
                                        select_clause=sc,
                                        where_clause=inner_wc,
                                        solution_modifier=inner_sm,
                                    )
                                )
                            ]
                        )
                    ]
                )
            )
        )

        ct = ConstructTemplate(
            ConstructTriples(
                [
                    TriplesSameSubject.from_spo(
                        focus_node_var, IRI(value=PREZ.hasChildren), has_children_var
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
        return list(self.construct_template.construct_triples.triples)

    @property
    def _inner_subselect(self) -> SubSelect:
        return (
            self.where_clause.group_graph_pattern.content.patterns[0]
            .group_graph_patterns[0]
            .content
        )

    @property
    def inner_select_vars(self):
        return self._inner_subselect.select_clause.variables

    @property
    def inner_select_gpnt(self):
        return GroupOrUnionGraphPattern(
            [self._inner_subselect.where_clause.group_graph_pattern]
        )

    @property
    def order_by_val(self):
        return Var(value="label")

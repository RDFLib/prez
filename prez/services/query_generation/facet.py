from typing import List

from rdflib import Namespace
from rdflib import URIRef
from sparql_grammar_pydantic import (
    Aggregate,
    ConstructQuery,
    ConstructTemplate,
    ConstructTriples,
    Expression,
    GroupGraphPattern,
    PrimaryExpression,
    SelectClause,
    SolutionModifier,
    SubSelect,
    WhereClause,
    GroupClause,
    GroupCondition,
    BuiltInCall,
    GroupGraphPatternSub,
    GraphPatternNotTriples,
    GroupOrUnionGraphPattern,
    TriplesBlock,
    TriplesSameSubject,
    BlankNodePropertyList,
    PropertyListNotEmpty,
    Verb,
    ObjectList,
    VarOrTerm,
    IRI,
    Object,
    VarOrIri,
    GraphNode,
    Var,
    TriplesNode
)
from sparql_grammar_pydantic.grammar import PropertyList

from prez.reference_data.prez_ns import PREZ

# Use a proper namespace
TEXT = Namespace("http://example.org/text#")


class FacetQuery(ConstructQuery):
    """
    Generates a CONSTRUCT query to retrieve facet counts based on provided properties.

    CONSTRUCT {
        ?facet_bn <http://example.org/text#facetName> ?facetName ;
                  <http://example.org/text#facetValue> ?facetValue ;
                  <http://example.org/text#facetCount> ?facetCount .
    }
    WHERE {
        {
            SELECT ?facetName ?facetValue (COUNT(DISTINCT ?focus_node) AS ?facetCount)
            WHERE {
                # Core query logic to find relevant focus nodes
                {
                    # This subselect finds the relevant focus nodes
                    { <<< original_subselect >>> }

                    # This part binds the facet values and names (using UNION later)
                    {
                        # Minimal placeholder for facet binding logic
                        BIND("placeholder_name" AS ?facetName)
                        BIND("placeholder_value" AS ?facetValue)
                        # In reality, this block will be a UNION of patterns,
                        # each binding ?facetValue and ?facetName for a specific property.
                    }

            }
            GROUP BY ?facetName ?facetValue
        }
    }
    """

    def __init__(self, original_subselect: SubSelect, property_shape):
        # Define variables used
        focus_node_var = Var(value="focus_node")
        facet_name_var = Var(value="facetName")
        facet_name_iri = IRI(value=PREZ.facetName)
        facet_value_var = Var(value="facetValue")
        facet_value_iri = IRI(value=PREZ.facetValue)
        facet_count_var = Var(value="facetCount")
        facet_count_iri = IRI(value=PREZ.facetCount)

        inner_ss = SubSelect(
            select_clause=SelectClause(
                variables_or_all=[focus_node_var],
                distinct=True,
            ),
            where_clause=original_subselect.where_clause,
            solution_modifier=SolutionModifier()
        )

        count_expression = Expression.from_primary_expression(
            PrimaryExpression(
                content=BuiltInCall(
                    other_expressions=Aggregate(
                        function_name="COUNT",
                        expression=Expression.from_primary_expression(
                            PrimaryExpression(content=focus_node_var)
                        )
                    )
                )
            )
        )

        # inner subselect
        inner_gpnts_or_tb = [
            GraphPatternNotTriples(
                content=GroupOrUnionGraphPattern(
                    group_graph_patterns=
                    [GroupGraphPattern(content=inner_ss)
                     ]
                )
            )
        ]

        # union facet selection
        union_ggps = []
        if len(property_shape.union_tssps_binds) > 1:
            for utb in property_shape.union_tssps_binds:
                # generate a GGP.
                union_ggps.append(
                    GroupGraphPattern(
                        content=GroupGraphPatternSub(
                            triples_block=TriplesBlock.from_tssp_list(utb.get("tssp_list")),
                            graph_patterns_or_triples_blocks=utb.get("facet_binds")
                        )
                    )
                )
            if union_ggps:
                inner_gpnts_or_tb.append(
                    GraphPatternNotTriples(
                        content=GroupOrUnionGraphPattern(group_graph_patterns=union_ggps)
                    )
                )

        else:  # faceting on a single property
            utb = property_shape.union_tssps_binds[0]
            inner_gpnts_or_tb.append(TriplesBlock.from_tssp_list(utb.get("tssp_list")))
            inner_gpnts_or_tb.extend(utb.get("facet_binds"))

        # --- Outer WHERE Clause ---
        outer_where_clause = WhereClause(
            group_graph_pattern=GroupGraphPattern(
                content=SubSelect(
                    select_clause=SelectClause(
                        variables_or_all=[
                            facet_name_var,
                            facet_value_var,
                            (count_expression, facet_count_var)
                        ],
                    ),
                    where_clause=WhereClause(
                        group_graph_pattern=GroupGraphPattern(
                            content=GroupGraphPatternSub(
                                graph_patterns_or_triples_blocks=inner_gpnts_or_tb
                            )
                        )
                    ),
                    solution_modifier=SolutionModifier(
                        group_by=GroupClause(
                            group_conditions=[
                                GroupCondition(condition=facet_name_var),
                                GroupCondition(condition=facet_value_var)
                            ]
                        )
                    )
                )
            )
        )

        # --- Construct Template ---
        # Use a variable for the blank node subject to link the triples
        props_vals = [
            (facet_name_iri, facet_name_var),
            (facet_value_iri, facet_value_var),
            (facet_count_iri, facet_count_var),
        ]
        vol_list = []
        for prop, val in props_vals:
            verb_inner = Verb(varoriri=VarOrIri(
                varoriri=prop))
            object_list1_inner = ObjectList(
                list_object=[
                    Object(
                        graphnode=GraphNode(
                            varorterm_or_triplesnode=VarOrTerm(
                                varorterm=val
                            )
                        )
                    )
                ]
            )
            vol_list.append((verb_inner, object_list1_inner))

        tss = TriplesSameSubject(
            content=(
                TriplesNode(
                    coll_or_bnpl=BlankNodePropertyList(
                        plne=PropertyListNotEmpty(
                            verb_objectlist=vol_list
                        )
                    )
                ),
                PropertyList()
            )
        )

        construct_template = ConstructTemplate(
            construct_triples=ConstructTriples(triples=tss)
        )

        # Initialize the base ConstructQuery
        super().__init__(
            construct_template=construct_template,
            where_clause=outer_where_clause,
            solution_modifier=SolutionModifier()
        )

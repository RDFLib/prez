import copy

from rdflib import URIRef, Literal, DCTERMS, XSD
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
    TriplesNode,
)
from sparql_grammar_pydantic.grammar import PropertyList, IRIOrFunction, TriplesSameSubjectPath

from prez.cache import profiles_graph_cache
from prez.exceptions.model_exceptions import PrefixNotBoundException
from prez.reference_data.prez_ns import PREZ
from prez.services.curie_functions import get_uri_for_curie_id


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
                    In the case of faceting on objects, there is no subselect here.

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

    def __init__(
            self,
            original_subselect: SubSelect = None,
            property_shape=None,
            focus_node_uri=None,
            open_facet: bool = False,
    ):
        # Validate that exactly one of the three modes is specified
        modes_specified = sum([
            original_subselect is not None,
            focus_node_uri is not None,
            open_facet
        ])
        if modes_specified != 1:
            raise ValueError(
                "Exactly one of 'original_subselect', 'focus_node_uri', or 'open_facet=True' must be specified"
            )

        # Define variables used
        if focus_node_uri:
            focus_node_var_or_iri = IRI(value=focus_node_uri)
            focus_node_pe = PrimaryExpression(
                content=IRIOrFunction(iri=focus_node_var_or_iri)
            )
        else:
            focus_node_var_or_iri = Var(value="focus_node")
            focus_node_pe = PrimaryExpression(content=focus_node_var_or_iri)
        facet_name_var = Var(value="facetName")
        facet_name_iri = IRI(value=PREZ.facetName)
        facet_value_var = Var(value="facetValue")
        facet_value_iri = IRI(value=PREZ.facetValue)
        facet_count_var = Var(value="facetCount")
        facet_count_iri = IRI(value=PREZ.facetCount)

        count_expression = Expression.from_primary_expression(
            PrimaryExpression(
                content=BuiltInCall(
                    other_expressions=Aggregate(
                        function_name="COUNT",
                        expression=Expression.from_primary_expression(focus_node_pe),
                    )
                )
            )
        )

        # inner subselect or direct patterns
        inner_gpnts_or_tb = []

        if original_subselect is not None:
            # For listing queries with original subselect
            inner_ss = SubSelect(
                select_clause=SelectClause(
                    variables_or_all=[focus_node_var_or_iri],
                    distinct=True,
                ),
                where_clause=original_subselect.where_clause,
                solution_modifier=SolutionModifier(),
            )
            inner_gpnts_or_tb.append(
                GraphPatternNotTriples(
                    content=GroupOrUnionGraphPattern(
                        group_graph_patterns=[GroupGraphPattern(content=inner_ss)]
                    )
                )
            )
        elif open_facet:
            # For open facet queries - no subselect, just basic ?focus_node patterns
            inner_gpnts_or_tb.append(
                TriplesBlock.from_tssp_list(
                    [
                        TriplesSameSubjectPath.from_spo(
                            subject=Var(value="focus_node"),
                            predicate=IRI(value="http://www.w3.org/1999/02/22-rdf-syntax-ns#type"),
                            object=Var(value="type"),
                        )
                    ]
                )
            )

        # union facet selection
        union_ggps = []
        if len(property_shape.union_tssps_binds) > 1:
            for utb in property_shape.union_tssps_binds:
                # generate a GGP.
                union_ggps.append(
                    GroupGraphPattern(
                        content=GroupGraphPatternSub(
                            triples_block=TriplesBlock.from_tssp_list(
                                utb.get("tssp_list")
                            ),
                            graph_patterns_or_triples_blocks=utb.get("facet_binds"),
                        )
                    )
                )
            if union_ggps:
                inner_gpnts_or_tb.append(
                    GraphPatternNotTriples(
                        content=GroupOrUnionGraphPattern(
                            group_graph_patterns=union_ggps
                        )
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
                            (count_expression, facet_count_var),
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
                                GroupCondition(condition=facet_value_var),
                            ]
                        )
                    ),
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
            verb_inner = Verb(varoriri=VarOrIri(varoriri=prop))
            object_list1_inner = ObjectList(
                list_object=[
                    Object(
                        graphnode=GraphNode(
                            varorterm_or_triplesnode=VarOrTerm(varorterm=val)
                        )
                    )
                ]
            )
            vol_list.append((verb_inner, object_list1_inner))

        tss = TriplesSameSubject(
            content=(
                TriplesNode(
                    coll_or_bnpl=BlankNodePropertyList(
                        plne=PropertyListNotEmpty(verb_objectlist=vol_list)
                    )
                ),
                PropertyList(),
            )
        )

        construct_template = ConstructTemplate(
            construct_triples=ConstructTriples(triples=tss)
        )

        # Initialize the base ConstructQuery
        super().__init__(
            construct_template=construct_template,
            where_clause=outer_where_clause,
            solution_modifier=SolutionModifier(),
        )

    @staticmethod
    async def create_facets_query(main_query, query_params, focus_node_uri=None):
        """Create a facets query for either listing or object endpoints."""
        from prez.services.query_generation.shacl import NodeShape

        profile_uri = await get_facet_profile_uri_from_qsa(query_params.facet_profile)
        if not profile_uri:
            return None, None
        else:
            facet_nodeshape = NodeShape(
                uri=profile_uri,
                graph=profiles_graph_cache,
                kind="profile",
                focus_node=Var(value="focus_node"),
            )
            facet_property_shape = facet_nodeshape.propertyShapes[0]

            if focus_node_uri:
                # For object queries with known focus node URI
                facets_query = FacetQuery(
                    property_shape=facet_property_shape,
                    focus_node_uri=focus_node_uri,
                )
            elif main_query and hasattr(main_query, "inner_select"):
                # For listing queries with subselect
                subselect_for_faceting = copy.deepcopy(main_query.inner_select)
                facets_query = FacetQuery(
                    original_subselect=subselect_for_faceting,
                    property_shape=facet_property_shape,
                )
            else:
                # no subselect or focus node given - this is an "open" facet, add a type triple only.
                facets_query = FacetQuery(
                    property_shape=facet_property_shape,
                    open_facet=True,
                )
            return profile_uri, facets_query


async def get_facet_profile_uri_from_qsa(facet_profile_qsa):
    """Get facet profile URI from query string argument."""
    requested_facet_profile = facet_profile_qsa
    profile_uri = next(  # check if QSA is identifier
        profiles_graph_cache.subjects(
            predicate=DCTERMS.identifier, object=Literal(requested_facet_profile)
        ),
        None,
    ) or next(
        profiles_graph_cache.subjects(
            predicate=DCTERMS.identifier,
            object=Literal(requested_facet_profile, datatype=XSD.token),
        ),
        None,
    )
    if not profile_uri:  # check if QSA is uri
        try:
            uri_ref = URIRef(requested_facet_profile)
            # Check if this URI exists as a subject in any triple
            if (uri_ref, None, None) in profiles_graph_cache:
                profile_uri = uri_ref
        except ValueError:
            pass

    if not profile_uri:  # check if QSA is curie
        try:
            requested_facet_profile_uri = await get_uri_for_curie_id(
                requested_facet_profile
            )
            if requested_facet_profile_uri:
                if (requested_facet_profile_uri, None, None) in profiles_graph_cache:
                    profile_uri = requested_facet_profile_uri
        except PrefixNotBoundException:
            pass
    return profile_uri

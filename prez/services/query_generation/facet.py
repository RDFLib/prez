import copy
import json
import logging

from rdflib import RDF, URIRef, Literal, DCTERMS, XSD, Graph
from rdflib.collection import Collection
from sparql_grammar import (
    IRI,
    Aggregate,
    BlankNodePropertyList,
    ConstructQuery,
    ConstructTemplate,
    ConstructTriples,
    Expression,
    GroupClause,
    GroupGraphPattern,
    GroupGraphPatternSub,
    GroupOrUnionGraphPattern,
    IRIOrFunction,
    ObjectList,
    PropertyListNotEmpty,
    SelectClause,
    SolutionModifier,
    SubSelect,
    TriplesBlock,
    TriplesSameSubject,
    Var,
    WhereClause,
)

from prez.cache import profiles_graph_cache
from prez.exceptions.model_exceptions import PrefixNotBoundException
from prez.reference_data.prez_ns import LUC, PREZ
from prez.services.query_generation.grammar_helpers import triples_block
from prez.services.curie_functions import get_uri_for_curie_id

log = logging.getLogger(__name__)


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
    ):
        # Validate that exactly one of the two modes is specified
        modes_specified = sum(
            [original_subselect is not None, focus_node_uri is not None]
        )
        if modes_specified != 1:
            raise ValueError(
                "Exactly one of 'original_subselect' or 'focus_node_uri' must be specified"
            )

        # Define variables used
        if focus_node_uri:
            focus_node_var_or_iri = IRI(value=focus_node_uri)
            focus_node_pe = IRIOrFunction(iri=focus_node_var_or_iri)
        else:
            focus_node_var_or_iri = Var(value="focus_node")
            focus_node_pe = focus_node_var_or_iri
        facet_name_var = Var(value="facetName")
        facet_name_iri = IRI(value=PREZ.facetName)
        facet_value_var = Var(value="facetValue")
        facet_value_iri = IRI(value=PREZ.facetValue)
        facet_count_var = Var(value="facetCount")
        facet_count_iri = IRI(value=PREZ.facetCount)

        count_expression = Expression.from_primary_expression(
            Aggregate.count(focus_node_pe)
        )

        # inner subselect or direct patterns
        inner_gpnts_or_tb = []

        if original_subselect is not None:
            # For listing queries with original subselect
            inner_ss = SubSelect(
                select_clause=SelectClause.create(focus_node_var_or_iri, distinct=True),
                where_clause=original_subselect.where_clause,
                solution_modifier=SolutionModifier(),
            )
            inner_gpnts_or_tb.append(
                GroupOrUnionGraphPattern([GroupGraphPattern(inner_ss)])
            )

        # union facet selection
        union_ggps = []
        if len(property_shape.union_tssps_binds) > 1:
            for utb in property_shape.union_tssps_binds:
                # generate a GGP.
                tssp_list = utb.get("tssp_list") or []
                block = (
                    TriplesBlock(list(tssp_list))
                    if property_shape.kind == "profile"
                    else triples_block(tssp_list)
                )
                union_ggps.append(
                    GroupGraphPattern(
                        GroupGraphPatternSub([block, *(utb.get("facet_binds") or [])])
                    )
                )
            if union_ggps:
                inner_gpnts_or_tb.append(GroupOrUnionGraphPattern(union_ggps))

        else:  # faceting on a single property
            utb = property_shape.union_tssps_binds[0]
            tssp_list = utb.get("tssp_list") or []
            inner_gpnts_or_tb.append(
                TriplesBlock(list(tssp_list))
                if property_shape.kind == "profile"
                else triples_block(tssp_list)
            )
            inner_gpnts_or_tb.extend(utb.get("facet_binds") or [])

        # --- Outer WHERE Clause ---
        outer_where_clause = WhereClause(
            GroupGraphPattern(
                SubSelect(
                    select_clause=SelectClause(
                        [
                            facet_name_var,
                            facet_value_var,
                            (count_expression, facet_count_var),
                        ]
                    ),
                    where_clause=WhereClause(
                        GroupGraphPattern(GroupGraphPatternSub(inner_gpnts_or_tb))
                    ),
                    solution_modifier=SolutionModifier(
                        group_by=GroupClause.create(facet_name_var, facet_value_var)
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
        # [ prez:facetName ?facetName ; prez:facetValue ?facetValue ; prez:facetCount ?facetCount ]
        tss = TriplesSameSubject(
            BlankNodePropertyList(
                PropertyListNotEmpty(
                    [(prop, ObjectList.create(val)) for prop, val in props_vals]
                )
            )
        )

        construct_template = ConstructTemplate(ConstructTriples([tss]))

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
            focus_node = (
                IRI(value=focus_node_uri) if focus_node_uri else Var(value="focus_node")
            )
            facet_nodeshape = NodeShape(
                uri=profile_uri,
                graph=profiles_graph_cache,
                kind="profile",
                focus_node=focus_node,
            )
            facet_property_shape = facet_nodeshape.propertyShapes[0]

            if focus_node_uri:
                # For object queries with known focus node URI
                facets_query = FacetQuery(
                    property_shape=facet_property_shape,
                    focus_node_uri=focus_node_uri,
                )
            else:
                # For listing queries with subselect, or open facet queries
                subselect_for_faceting = copy.deepcopy(main_query.inner_select)
                facets_query = FacetQuery(
                    original_subselect=subselect_for_faceting,
                    property_shape=facet_property_shape,
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


def extract_lucene_facets_from_profile(
    profile_uri: URIRef, graph: Graph | None = None
) -> list | None:
    """Extract Lucene facet specs from a profile's luc:flatFacets / luc:rangeFacets.

    Returns a list suitable for SearchQueryJenaLucene._facets:
      - flat facets → field IRI strings
      - range facets → {"field": "<iri>", "ranges": [null, 20, 30, null]}

    Returns None if the profile has no Lucene facet predicates.
    """
    g = graph if graph is not None else profiles_graph_cache
    facets: list = []

    # luc:flatFacets — each object is a field IRI
    for field_iri in g.objects(profile_uri, LUC.flatFacets):
        if isinstance(field_iri, URIRef):
            facets.append(str(field_iri))

    # luc:rangeFacets — blank nodes with luc:field + luc:bucketBoundaries
    for range_node in g.objects(profile_uri, LUC.rangeFacets):
        field_iri = g.value(range_node, LUC.field)
        boundaries_literal = g.value(range_node, LUC.bucketBoundaries)
        if field_iri is None:
            log.warning(
                "luc:rangeFacets node %s is missing luc:field, skipping", range_node
            )
            continue
        range_spec: dict = {"field": str(field_iri)}
        if boundaries_literal is not None:
            try:
                range_spec["ranges"] = json.loads(str(boundaries_literal))
            except (json.JSONDecodeError, TypeError):
                log.warning(
                    "Could not parse luc:bucketBoundaries %r on %s, skipping ranges",
                    str(boundaries_literal),
                    range_node,
                )
        facets.append(range_spec)

    return facets if facets else None

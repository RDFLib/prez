"""
SPARQL Grammar Helper Functions

Reusable functions for constructing SPARQL grammar objects with sparql-grammar. Each
returns an ordinary grammar node (a ``Filter``, ``InlineData``,
``GroupOrUnionGraphPattern`` ...) that can be added to a ``GroupGraphPatternSub`` with
``add_pattern``.
"""

import logging
import re

from sparql_grammar import (
    IRI,
    BooleanLiteral,
    ConstructTriples,
    Expression,
    ExistsFunc,
    Filter,
    GroupGraphPattern,
    GroupGraphPatternSub,
    GroupOrUnionGraphPattern,
    InlineData,
    InlineDataOneVar,
    IRIOrFunction,
    NotExistsFunc,
    PathAlternative,
    PathElt,
    PathEltOrInverse,
    PathPrimary,
    RDFLiteral,
    TriplesBlock,
    TriplesSameSubjectPath,
    Var,
    numeric_literal,
    regex,
)

logger = logging.getLogger(__name__)

_DATATYPE_PATTERN = re.compile(r"(.*)\^\^<(\S+)>$")


def triples_block(tssp_list) -> TriplesBlock:
    """A ``TriplesBlock`` rendering the patterns in the order prez emits them.

    Prez accumulates triple patterns outward from the focus node, but emits a block
    in the opposite order: the most recently added pattern first. That is the order
    deployments have been running, and triple pattern order inside a basic graph
    pattern is an input to a query planner, so it is kept deliberately rather than
    left to whichever end of the list a builder happens to start from.

    Two kinds of list do not want reversing, and build a block directly instead:
    lists already in emission order (the sorted inner select, the link generation
    patterns), and profile-kind shape lists, which ``PropertyShape`` hands over
    focus-node first - see ``_tssp_list_for_triples_block``.
    """
    return TriplesBlock(list(reversed(tssp_list)) if tssp_list else [])


def construct_triples(tss_list) -> ConstructTriples:
    """A ``ConstructTemplate``'s triples, in the order prez emits them.

    Same order as :func:`triples_block`, for the same reason of keeping the emitted
    query stable, though a CONSTRUCT template's order only affects how the query
    reads: the graph it builds is a set either way.
    """
    return ConstructTriples(list(reversed(tss_list)) if tss_list else [])


def convert_value_to_rdf_term(val) -> IRI | RDFLiteral | BooleanLiteral:
    """Convert a Python value (typically from CQL JSON) to the appropriate RDF term.

    Strings are read by shape, as CQL gives no other way to tell an IRI from text:
    ``"..."^^<datatype>`` is a typed literal, anything starting with ``http`` is an
    IRI, and everything else is a plain literal. Literal text is escaped when the
    query is rendered, so no escaping is done here.
    """
    if isinstance(val, bool):
        return BooleanLiteral(value=val)
    if isinstance(val, (int, float)):
        return numeric_literal(val)

    # sanitize leading and trailing quotes
    val = val.strip("'\"")

    # check if it is a datatyped literal
    match = _DATATYPE_PATTERN.fullmatch(val)
    if match:
        value_str, datatype_str = match.groups()
        return RDFLiteral(
            value=value_str.strip("'\""), datatype=IRI(value=datatype_str)
        )

    # check if it is a uri
    if val.startswith("http"):
        return IRI(value=val)

    # just return a literal if nothing else matched
    return RDFLiteral(value=val)


def _as_primary(term):
    """An IRI in expression position is an ``iriOrFunction``; everything else is itself."""
    if isinstance(term, IRI):
        return IRIOrFunction(iri=term)
    return term


def create_regex_filter(variable: Var, pattern: str) -> Filter:
    """FILTER REGEX(STR(?variable), "pattern")"""
    return Filter(regex(variable, pattern))


def create_relational_filter(
    left_var: Var,
    operator: str,
    right_value: IRI | RDFLiteral | BooleanLiteral,
) -> Filter:
    """FILTER (?left_var <operator> <right_value>) for =, <, >, <=, >=, !="""
    return Filter(Expression.compare(left_var, operator, _as_primary(right_value)))


def create_values_constraint(variable: Var, values: list) -> InlineData:
    """VALUES ?variable { <val1> "val2" ... }"""
    return InlineData(
        InlineDataOneVar(variable, [convert_value_to_rdf_term(v) for v in values])
    )


_TEMPORAL_OPERATORS = ("=", "<=", ">=", "<", ">", "!=")


def _comparisons(comparisons) -> list[Expression]:
    expressions = []
    for left_comp, op, right_comp in comparisons:
        if op not in _TEMPORAL_OPERATORS:
            raise ValueError(f"Invalid operator: {op}")
        expressions.append(Expression.compare(left_comp, op, right_comp))
    return expressions


def create_temporal_or_gpnt(
    comparisons: list[tuple[Var | RDFLiteral, str, Var | RDFLiteral]], negated=False
) -> Filter:
    """
    FILTER ( comp1 op1 comp2 || comp3 op2 comp4 || ... )

    if negated:
    FILTER ( !(comp1 op1 comp2 || comp3 op2 comp4 || ...) )
    """
    disjunction = Expression.any_of(*_comparisons(comparisons))
    if negated:
        return Filter(Expression.negate(disjunction))
    return Filter(disjunction)


def create_filter_bool_gpnt(boolean: bool) -> Filter:
    """
    For filtering out all results in scenarios where the input arguments are valid but logically determine that the
    filter will filter out all results.

    generates FILTER(false) or FILTER(true)
    """
    return Filter(Expression.from_primary_expression(BooleanLiteral(value=boolean)))


def create_temporal_and_gpnt(
    comparisons: list[tuple[Var | RDFLiteral, str, Var | RDFLiteral]]
) -> Filter:
    """FILTER ( comp1 op1 comp2 && comp3 op2 comp4 && ... )"""
    return Filter(Expression.all_of(*_comparisons(comparisons)))


def create_tssp_alt_or_alt_inverse(
    subject: Var | IRI,
    first_pred: IRI,
    second_pred: IRI,
    obj: Var | IRI | RDFLiteral,
    inverse_second_prop: bool = False,
) -> TriplesSameSubjectPath:
    """
    with inverse_second_prop = False
    ?subject first_pred|second_pred ?obj
    or
    with inverse_second_prop = True
    ?subject first_pred|^second_pred ?obj
    """
    second = PathEltOrInverse(PathElt(PathPrimary(second_pred)), inverse_second_prop)
    return TriplesSameSubjectPath.from_spo(
        subject, PathAlternative.alt(first_pred, second), obj
    )


def create_tssp_sequence(
    subject: Var | IRI, pred_1: IRI, pred_2: IRI, obj: Var | IRI | RDFLiteral
) -> TriplesSameSubjectPath:
    """
    ?subject pred_1/pred_2 ?obj
    """
    return TriplesSameSubjectPath.from_spo(
        subject, PathAlternative.seq(pred_1, pred_2), obj
    )


def create_union_gpnt_from_tssps(
    tssps: list[TriplesSameSubjectPath],
) -> GroupOrUnionGraphPattern:
    """{ tssp1 } UNION { tssp2 } UNION ..."""
    return GroupOrUnionGraphPattern(
        [
            GroupGraphPattern(GroupGraphPatternSub([TriplesBlock([tssp])]))
            for tssp in tssps
        ]
    )


def create_filter_exists(patterns: GroupGraphPatternSub) -> Filter:
    """FILTER EXISTS { ... } around a group of patterns - improves query performance."""
    return Filter(ExistsFunc(GroupGraphPattern(patterns)))


def create_filter_not_exists(patterns: GroupGraphPatternSub) -> Filter:
    """FILTER NOT EXISTS { ... } around a group of patterns."""
    return Filter(NotExistsFunc(GroupGraphPattern(patterns)))


def create_filter_in(variable: Var, values: list[str] | str) -> Filter:
    """Create a FILTER(?var IN (...)) constraint.

    Args:
        variable: The SPARQL variable to filter
        values: Single value or list of values to match against

    Returns:
        Filter containing the FILTER IN constraint
    """
    # Normalize to list
    if not isinstance(values, list):
        values = [values]
    return Filter(
        Expression.in_(
            variable, [_as_primary(convert_value_to_rdf_term(v)) for v in values]
        )
    )

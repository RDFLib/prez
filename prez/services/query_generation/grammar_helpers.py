"""
SPARQL Grammar Helper Functions

This module contains reusable utility functions for constructing SPARQL grammar
objects using sparql-grammar-pydantic. These functions abstract away verbose
grammar construction patterns. The intention is to move these to the
sparql-grammar-pydantic library itself.
"""

import logging
import re

from rdflib import URIRef
from sparql_grammar_pydantic import (
    IRI,
    AdditiveExpression,
    BooleanLiteral,
    BrackettedExpression,
    BuiltInCall,
    ConditionalAndExpression,
    ConditionalOrExpression,
    Constraint,
    DataBlock,
    DataBlockValue,
    Expression,
    Filter,
    GraphNodePath,
    GraphPatternNotTriples,
    GroupGraphPattern,
    GroupGraphPatternSub,
    GroupOrUnionGraphPattern,
    InlineData,
    InlineDataOneVar,
    MultiplicativeExpression,
    NumericExpression,
    NumericLiteral,
    ObjectListPath,
    ObjectPath,
    PathAlternative,
    PathElt,
    PathEltOrInverse,
    PathPrimary,
    PathSequence,
    PrimaryExpression,
    PropertyListPathNotEmpty,
    RDFLiteral,
    RegexExpression,
    RelationalExpression,
    SG_Path,
    TriplesBlock,
    TriplesSameSubjectPath,
    UnaryExpression,
    ValueLogical,
    Var,
    VarOrTerm,
    VerbPath,
)

logger = logging.getLogger(__name__)


def convert_value_to_rdf_term(
    val,
) -> IRI | NumericLiteral | RDFLiteral | BooleanLiteral:
    """Convert a Python value to the appropriate RDF term."""
    # handle booleans
    if isinstance(val, bool):
        return BooleanLiteral(value=val)

    # handle numbers
    if isinstance(val, (int, float)):
        return NumericLiteral(value=val)

    # sanitize leading and trailing quotes
    val = val.strip("'\"")

    # check if it is a datatyped literal
    # search for a term or phrase enclosed in double quotes with an rdf style datatype declaration at the end
    datatype_pattern = r'(.*)\^\^<(\S+)>$'
    capture_groups = re.findall(datatype_pattern, val)
    if capture_groups and len(capture_groups) == 1:
        value_str, datatype_str = capture_groups[0]
        datatype_uri = URIRef(datatype_str)
        # sanitize leading and trailing quotes
        value_str = value_str.strip("'\"")
        try:
            datatype_uri.n3()
            datatype_iri = IRI(value=datatype_uri)
            return RDFLiteral(value=value_str, datatype=datatype_iri)
        except Exception as e:
            logger.warning(
                f"Exception during rdf_term conversion, provided datatype {datatype_str} is not a valid uri, "
                f"defaulting to RDFLiteral with no datatype"
                f"{e.args[0]}"
            )
            return RDFLiteral(value=val)

    # check if it is a uri
    elif val.startswith("http"):
        datatype_uri = URIRef(val)
        try:
            datatype_uri.n3()
            return IRI(value=datatype_uri)
        except Exception as e:
            logger.warning(
                f"Exception during rdf_term conversion, provided term {datatype_str} is not a valid uri, "
                f"defaulting to RDFLiteral with no datatype"
                f"{e.args[0]}"
            )
            return RDFLiteral(value=val)

    # just return a literal if nothing else matched
    return RDFLiteral(value=val)


def create_regex_filter(variable: Var, pattern: str) -> GraphPatternNotTriples:
    """Create a SPARQL FILTER with REGEX for pattern matching.

    Args:
        variable: The variable to test against
        pattern: The regex pattern to match

    Returns:
        GraphPatternNotTriples containing the FILTER with REGEX
    """
    return GraphPatternNotTriples(
        content=Filter(
            constraint=Constraint(
                content=BuiltInCall(
                    other_expressions=RegexExpression(
                        text_expression=Expression.from_primary_expression(
                            primary_expression=PrimaryExpression(content=variable)
                        ),
                        pattern_expression=Expression.from_primary_expression(
                            primary_expression=PrimaryExpression(
                                content=RDFLiteral(value=pattern)
                            )
                        ),
                    )
                )
            )
        )
    )


def create_relational_filter(
    left_var: Var,
    operator: str,
    right_value: IRI | NumericLiteral | RDFLiteral | BooleanLiteral,
) -> GraphPatternNotTriples:
    """Create a SPARQL FILTER with relational comparison.

    Args:
        left_var: The variable on the left side of the comparison
        operator: The comparison operator (=, <, >, <=, >=, !=)
        right_value: The value to compare against

    Returns:
        GraphPatternNotTriples containing the FILTER
    """
    from sparql_grammar_pydantic import IRIOrFunction

    object_pe = PrimaryExpression(content=left_var)

    # Handle IRI objects by wrapping them in IRIOrFunction
    if isinstance(right_value, IRI):
        value_content = IRIOrFunction(iri=right_value)
    else:
        value_content = right_value

    value_pe = PrimaryExpression(content=value_content)
    return GraphPatternNotTriples(
        content=Filter.filter_relational(
            focus=object_pe, comparators=value_pe, operator=operator
        )
    )


def create_values_constraint(variable: Var, values: list) -> GraphPatternNotTriples:
    """Create a SPARQL VALUES constraint for IN operations.

    Args:
        variable: The variable to constrain
        values: List of values (strings, numbers, URIs)

    Returns:
        GraphPatternNotTriples containing the VALUES constraint
    """
    # Convert values to appropriate RDF terms
    rdf_values = []
    for value in values:
        if isinstance(value, str) and value.startswith("http"):
            rdf_values.append(IRI(value=URIRef(value)))
        elif isinstance(value, (int, float)):
            rdf_values.append(NumericLiteral(value=value))
        else:
            rdf_values.append(RDFLiteral(value=str(value)))

    iri_db_vals = [DataBlockValue(value=p) for p in rdf_values]
    ildov = InlineDataOneVar(variable=variable, datablockvalues=iri_db_vals)

    return GraphPatternNotTriples(content=InlineData(data_block=DataBlock(block=ildov)))


def create_temporal_or_gpnt(
    comparisons: list[tuple[Var | RDFLiteral, str, Var | RDFLiteral]], negated=False
) -> GraphPatternNotTriples:
    """
    Create a FILTER with multiple conditions joined by OR (||).

    Format: FILTER ( comp1 op1 comp2 || comp3 op2 comp4 || ... )

    if negated:
    Format: FILTER (! (comp1 op1 comp2 || comp3 op2 comp4 || ...) )
    """
    _and_expressions = []
    for left_comp, op, right_comp in comparisons:
        if op not in ["=", "<=", ">=", "<", ">", "!="]:
            raise ValueError(f"Invalid operator: {op}")
        _and_expressions.append(
            ConditionalAndExpression(
                value_logicals=[
                    ValueLogical(
                        relational_expression=RelationalExpression(
                            left=NumericExpression(
                                additive_expression=AdditiveExpression(
                                    base_expression=MultiplicativeExpression(
                                        base_expression=UnaryExpression(
                                            primary_expression=PrimaryExpression(
                                                content=left_comp
                                            )
                                        )
                                    )
                                )
                            ),
                            operator=op,
                            right=NumericExpression(
                                additive_expression=AdditiveExpression(
                                    base_expression=MultiplicativeExpression(
                                        base_expression=UnaryExpression(
                                            primary_expression=PrimaryExpression(
                                                content=right_comp
                                            )
                                        )
                                    )
                                )
                            ),
                        )
                    )
                ]
            )
        )
    if not negated:
        return GraphPatternNotTriples(
            content=Filter(
                constraint=Constraint(
                    content=BrackettedExpression(
                        expression=Expression(
                            conditional_or_expression=ConditionalOrExpression(
                                conditional_and_expressions=_and_expressions
                            )
                        )
                    )
                )
            )
        )
    else:
        return GraphPatternNotTriples(
            content=Filter(
                constraint=Constraint(
                    content=BrackettedExpression(
                        expression=Expression(
                            conditional_or_expression=ConditionalOrExpression(
                                conditional_and_expressions=[
                                    ConditionalAndExpression(
                                        value_logicals=[
                                            ValueLogical(
                                                relational_expression=RelationalExpression(
                                                    left=NumericExpression(
                                                        additive_expression=AdditiveExpression(
                                                            base_expression=MultiplicativeExpression(
                                                                base_expression=UnaryExpression(
                                                                    operator="!",
                                                                    primary_expression=PrimaryExpression(
                                                                        content=BrackettedExpression(
                                                                            expression=Expression(
                                                                                conditional_or_expression=ConditionalOrExpression(
                                                                                    conditional_and_expressions=_and_expressions
                                                                                )
                                                                            )
                                                                        )
                                                                    ),
                                                                )
                                                            )
                                                        )
                                                    )
                                                )
                                            )
                                        ]
                                    )
                                ]
                            )
                        )
                    )
                )
            )
        )


def create_filter_bool_gpnt(boolean: bool) -> GraphPatternNotTriples:
    """
    For filtering out all results in scenarios where the input arguments are valid but logically determine that the
    filter will filter out all results.

    generates FILTER(false) or FILTER(true)
    """
    return GraphPatternNotTriples(
        content=Filter(
            constraint=Constraint(
                content=BrackettedExpression(
                    expression=Expression.from_primary_expression(
                        primary_expression=PrimaryExpression(
                            content=BooleanLiteral(value=boolean)
                        )
                    )
                )
            )
        )
    )


def create_temporal_and_gpnt(
    comparisons: list[tuple[Var | RDFLiteral, str, Var | RDFLiteral]]
) -> GraphPatternNotTriples:
    """
    Create a FILTER with multiple conditions joined by AND.

    :param comparisons: List of tuples, each containing (left_comp, operator, right_comp)
    :return: GraphPatternNotTriples

    Format:
    FILTER ( comp1 op1 comp2 && comp3 op2 comp4 && ... )
    """
    _vl_expressions = []

    for left_comp, op, right_comp in comparisons:
        if op not in ["=", "<=", ">=", "<", ">", "!="]:
            raise ValueError(f"Invalid operator: {op}")

        _vl_expressions.append(
            ValueLogical(
                relational_expression=RelationalExpression(
                    left=NumericExpression(
                        additive_expression=AdditiveExpression(
                            base_expression=MultiplicativeExpression(
                                base_expression=UnaryExpression(
                                    primary_expression=PrimaryExpression(
                                        content=left_comp
                                    )
                                )
                            )
                        )
                    ),
                    operator=op,
                    right=NumericExpression(
                        additive_expression=AdditiveExpression(
                            base_expression=MultiplicativeExpression(
                                base_expression=UnaryExpression(
                                    primary_expression=PrimaryExpression(
                                        content=right_comp
                                    )
                                )
                            )
                        )
                    ),
                )
            )
        )

    return GraphPatternNotTriples(
        content=Filter(
            constraint=Constraint(
                content=BrackettedExpression(
                    expression=Expression(
                        conditional_or_expression=ConditionalOrExpression(
                            conditional_and_expressions=[
                                ConditionalAndExpression(value_logicals=_vl_expressions)
                            ]
                        )
                    )
                )
            )
        )
    )


def create_tssp_alt_or_alt_inverse(
    subject: VarOrTerm,
    first_pred: IRI,
    second_pred: IRI,
    obj: VarOrTerm,
    inverse_second_prop: bool = False,
) -> TriplesSameSubjectPath:
    """
    with inverse_second_prop = False
    ?subject first_pred|second_pred ?obj
    or
    with inverse_second_prop = True
    ?subject first_pred|^second_pred ?obj
    """
    return TriplesSameSubjectPath(
        content=(
            subject,
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
                                                        value=first_pred,
                                                    )
                                                )
                                            )
                                        ]
                                    ),
                                    PathSequence(
                                        list_path_elt_or_inverse=[
                                            PathEltOrInverse(
                                                path_elt=PathElt(
                                                    path_primary=PathPrimary(
                                                        value=second_pred,
                                                    )
                                                ),
                                                inverse=inverse_second_prop,
                                            )
                                        ]
                                    ),
                                ]
                            )
                        )
                    ),
                    ObjectListPath(
                        object_paths=[
                            ObjectPath(
                                graph_node_path=GraphNodePath(
                                    varorterm_or_triplesnodepath=obj
                                )
                            )
                        ]
                    ),
                )
            ),
        )
    )


def create_tssp_sequence(
    subject: VarOrTerm, pred_1: IRI, pred_2: IRI, obj: VarOrTerm
) -> TriplesSameSubjectPath:
    """
    ?subject pred_1/pred_2 ?obj
    """
    return TriplesSameSubjectPath(
        content=(
            subject,
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
                                                        value=pred_1,
                                                    )
                                                )
                                            ),
                                            PathEltOrInverse(
                                                path_elt=PathElt(
                                                    path_primary=PathPrimary(
                                                        value=pred_2,
                                                    )
                                                )
                                            ),
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
                                    varorterm_or_triplesnodepath=obj
                                )
                            )
                        ]
                    ),
                )
            ),
        )
    )


def create_union_gpnt_from_tssps(
    tssps: list[TriplesSameSubjectPath],
) -> GraphPatternNotTriples:
    return GraphPatternNotTriples(
        content=GroupOrUnionGraphPattern(
            group_graph_patterns=[
                GroupGraphPattern(
                    content=GroupGraphPatternSub(
                        triples_block=TriplesBlock.from_tssp_list([tssp])
                    )
                )
                for tssp in tssps
            ]
        )
    )

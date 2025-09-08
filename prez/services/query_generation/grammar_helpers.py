"""
SPARQL Grammar Helper Functions

This module contains reusable utility functions for constructing SPARQL grammar
objects using sparql-grammar-pydantic. These functions abstract away verbose
grammar construction patterns. The intention is to move these to the
sparql-grammar-pydantic library itself.
"""

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
    ExistsFunc,
    Expression,
    Filter,
    GraphPatternNotTriples,
    GroupGraphPattern,
    GroupGraphPatternSub,
    InlineData,
    InlineDataOneVar,
    MultiplicativeExpression,
    NumericExpression,
    NumericLiteral,
    PrimaryExpression,
    RDFLiteral,
    RegexExpression,
    RelationalExpression,
    UnaryExpression,
    ValueLogical,
    Var, NotExistsFunc,
)


def convert_value_to_rdf_term(val) -> IRI | NumericLiteral | RDFLiteral:
    """Convert a Python value to the appropriate RDF term."""
    if isinstance(val, str) and val.startswith("http"):
        return IRI(value=val)
    elif isinstance(val, (int, float)):
        return NumericLiteral(value=val)
    else:
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
    left_var: Var, operator: str, right_value: IRI | NumericLiteral | RDFLiteral
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


def create_filter_exists(patterns: GroupGraphPatternSub) -> GraphPatternNotTriples:
    """Create a FILTER EXISTS wrapper around a group of patterns.
    
    This wraps the given patterns in FILTER EXISTS { ... } which improves
    query performance.
    
    Args:
        patterns: The GroupGraphPatternSub containing all patterns to wrap
        
    Returns:
        GraphPatternNotTriples containing the FILTER EXISTS
    """
    return GraphPatternNotTriples(
        content=Filter(
            constraint=Constraint(
                content=BuiltInCall(
                    other_expressions=ExistsFunc(
                        group_graph_pattern=GroupGraphPattern(content=patterns)
                    )
                )
            )
        )
    )


def create_filter_not_exists(patterns: GroupGraphPatternSub) -> GraphPatternNotTriples:
    """Create a FILTER NOT EXISTS wrapper around a group of patterns.

    This wraps the given patterns in FILTER NOT EXISTS { ... } which improves
    query performance.

    Args:
        patterns: The GroupGraphPatternSub containing all patterns to wrap

    Returns:
        GraphPatternNotTriples containing the FILTER NOT EXISTS
    """
    return GraphPatternNotTriples(
        content=Filter(
            constraint=Constraint(
                content=BuiltInCall(
                    other_expressions=NotExistsFunc(
                        group_graph_pattern=GroupGraphPattern(content=patterns)
                    )
                )
            )
        )
    )


def _create_filter_in(variable: Var, values: list) -> GraphPatternNotTriples:
    """Create a FILTER(?var IN (<val1>, "val2", ...)) constraint."""
    # Convert values to appropriate RDF terms and wrap in PrimaryExpression
    right_primary_expressions = []
    for value in values:
        rdf_term = convert_value_to_rdf_term(value)
        right_primary_expressions.append(
            PrimaryExpression(content=rdf_term)
        )

    in_expr = Expression.create_in_expression(
        left_primary_expression=PrimaryExpression(content=variable),
        operator="IN",
        right_primary_expressions=right_primary_expressions,
    )

    return GraphPatternNotTriples(
        content=Filter(
            constraint=Constraint(
                content=BrackettedExpression(expression=in_expr)
            )
        )
    )

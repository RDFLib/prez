from __future__ import annotations

import logging
from decimal import Decimal
from typing import List, Union, Optional, Generator, Tuple

from pydantic import BaseModel, field_validator
from rdflib import URIRef, Variable
from rdflib.plugins.sparql import prepareQuery
from rdflib.plugins.sparql.algebra import translateAlgebra

log = logging.getLogger(__name__)


class SPARQLGrammarBase(BaseModel):
    indent_level: int = 0

    class Config:
        arbitrary_types_allowed = True

    def __str__(self):
        return "".join(part for part in self.render())

    def __repr__(self):
        return f"{self.__class__.__name__} ({self})"

    def render(self):
        raise NotImplementedError("Subclasses must implement this method.")

    def to_string(self):
        return self.__str__()

    def collect_triples(self) -> List[SimplifiedTriple]:
        """
        Recursively collect SimplifiedTriple instances from this object.
        """
        triples = []

        # Iterate through all attributes of the object
        for attribute_name in self.model_fields:
            attribute_value = getattr(self, attribute_name)

            # Check if the attribute is a SimplifiedTriple and collect it
            if isinstance(attribute_value, SimplifiedTriple):
                triples.append(attribute_value)

            # If the attribute is a list, iterate through it and collect SimplifiedTriples
            elif isinstance(attribute_value, list):
                for item in attribute_value:
                    if isinstance(item, SimplifiedTriple):
                        triples.append(item)
                    # If the item is an instance of BaseClass, recurse into it
                    elif isinstance(item, SPARQLGrammarBase):
                        triples.extend(item.collect_triples())

            # If the attribute is an instance of BaseClass, recurse into it
            elif isinstance(attribute_value, SPARQLGrammarBase):
                triples.extend(attribute_value.collect_triples())

        # deduplicate
        triples = list(set(triples))
        return triples


class BlankNodeLabel(SPARQLGrammarBase):
    """
    BLANK_NODE_LABEL	  ::=  	'_:' ( PN_CHARS_U | [0-9] ) ((PN_CHARS|'.')* PN_CHARS)?
    """

    part_1: str
    part_2: Optional[str] = None

    def render(self):
        yield "_:"
        yield self.part_1
        if self.part_2:
            yield self.part_2


class Anon:
    """
    ANON	  ::=  	'[' WS* ']'
    https://www.w3.org/TR/sparql11-query/#rANON
    """

    def render(self):
        yield "[]"


class Var(SPARQLGrammarBase):
    value: str

    def render(self) -> Generator[str, None, None]:
        yield Variable(self.value).n3()

    def __hash__(self):
        return hash(self.value)


class IRI(SPARQLGrammarBase):
    """
    Represents a SPARQL iri.
    iri ::= IRIREF | PrefixedName
    """

    value: Union[URIRef, str]

    def render(self) -> Generator[str, None, None]:
        if isinstance(self.value, URIRef):
            yield self.value.n3()
        else:
            yield "<"
            yield self.value
            yield ">"

    def __hash__(self):
        return hash(self.value)


class BlankNode(SPARQLGrammarBase):
    """
    BlankNode	  ::=  	BLANK_NODE_LABEL | ANON
    """

    value: Union[BlankNodeLabel, Anon]

    def render(self):
        yield from self.value.render()

    def __hash__(self):
        return hash(self.value)


class RDFLiteral(SPARQLGrammarBase):
    """
    RDFLiteral	  ::=  	String ( LANGTAG | ( '^^' iri ) )?
    """

    value: str
    langtag: Optional[LANGTAG] = None
    datatype: Optional[IRI] = None

    def render(self) -> Generator[str, None, None]:
        yield f'"{self.value}"'
        if self.langtag:
            yield from self.langtag.render()
        elif self.datatype:
            yield "^^"
            yield from self.datatype.render()

    def __hash__(self):
        return hash(self.value)


class LANGTAG(SPARQLGrammarBase):
    """
    LANGTAG	  ::=  	'@' [a-zA-Z]+ ('-' [a-zA-Z0-9]+)*
    """

    tag: str
    subtag: Optional[str] = None

    def render(self) -> Generator[str, None, None]:
        yield f"@{self.tag}"
        if self.subtag:
            yield f"-{self.subtag}"


class NIL(SPARQLGrammarBase):
    """
    Represents a SPARQL NIL.
    NIL	  ::=  	'(' WS* ')'
    """

    def render(self) -> Generator[str, None, None]:
        yield "()"


class NumericLiteral(SPARQLGrammarBase):
    """
    not implemented properly - only does integer literals
    """

    value: Union[float, int, Decimal]

    def render(self) -> Generator[str, None, None]:
        yield str(self.value)

    def __hash__(self):
        return hash(self.value)


class SimplifiedTriple(SPARQLGrammarBase):
    """A simplified implmementation the triple pattern matches in the SPARQL grammar, to avoid implementing many classes
    such as TriplesSameSubjectPath"""

    subject: Union[IRI, Var, BlankNode]
    predicate: Union[IRI, Var]
    object: Union[IRI, RDFLiteral, Var, BlankNode, NumericLiteral]

    def render(self) -> Generator[str, None, None]:
        yield from self.subject.render()
        yield " "
        yield from self.predicate.render()
        yield " "
        yield from self.object.render()
        yield " ."

    def __hash__(self):
        return hash((self.subject, self.predicate, self.object))


class TriplesBlock(SPARQLGrammarBase):
    triples: List[SimplifiedTriple] = []

    def render(self) -> Generator[str, None, None]:
        for i, triple in enumerate(self.triples):
            yield from triple.render()
            # if i < len(self.triples) - 1:  # Check if it's not the last triple
            yield "\n"


class PrimaryExpression(SPARQLGrammarBase):
    """
    PrimaryExpression	  ::=  	BrackettedExpression | BuiltInCall | iriOrFunction | RDFLiteral | NumericLiteral | BooleanLiteral | Var
    """

    content: Union[
        BrackettedExpression,
        BuiltInCall,
        IRIOrFunction,
        RDFLiteral,
        NumericLiteral,
        BooleanLiteral,
        Var,
    ]

    def render(self) -> Generator[str, None, None]:
        yield from self.content.render()


class UnaryExpression(SPARQLGrammarBase):
    operator: Optional[str] = None  # '!', '+', or '-'
    primary_expression: PrimaryExpression

    def render(self) -> Generator[str, None, None]:
        if self.operator:
            yield f"{self.operator} "
        yield from self.primary_expression.render()


class MultiplicativeExpression(SPARQLGrammarBase):
    base_expression: UnaryExpression
    additional_expressions: Optional[List[Tuple[str, UnaryExpression]]] = []

    @field_validator("additional_expressions")
    def validate_additional_expressions(cls, v):
        if v[0] not in ["*", "/"]:
            raise ValueError("Operator must be '*' or '/'")
        return v

    def render(self) -> Generator[str, None, None]:
        yield from self.base_expression.render()
        for operator, expression in self.additional_expressions:
            yield f" {operator} "
            yield from expression.render()


class AdditiveExpression(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rAdditiveExpression
    AdditiveExpression	  ::=  	MultiplicativeExpression ( '+' MultiplicativeExpression | '-' MultiplicativeExpression | ( NumericLiteralPositive | NumericLiteralNegative ) ( ( '*' UnaryExpression ) | ( '/' UnaryExpression ) )* )*
    #TODO implement NumericLiteralPositive, NumericLiteralNegative - these should be options in the additional expressions
    """

    base_expression: "MultiplicativeExpression"
    additional_expressions: Optional[
        List[Tuple[str, Union[MultiplicativeExpression, UnaryExpression]]]
    ] = []

    @field_validator("additional_expressions")
    def validate_additional_expressions(cls, v):
        if v[0] not in ["+", "-", "*", "/"]:
            raise ValueError("Operator must be one of '+', '-', '*', or '/'")
        return v

    def render(self) -> Generator[str, None, None]:
        yield from self.base_expression.render()
        for operator, expression in self.additional_expressions:
            yield f" {operator} "
            yield from expression.render()


class NumericExpression(SPARQLGrammarBase):
    additive_expression: AdditiveExpression

    def render(self) -> Generator[str, None, None]:
        yield from self.additive_expression.render()


class RelationalExpression(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rRelationalExpression
    RelationalExpression	  ::=  	NumericExpression ( '=' NumericExpression | '!=' NumericExpression | '<' NumericExpression | '>' NumericExpression | '<=' NumericExpression | '>=' NumericExpression | 'IN' ExpressionList | 'NOT' 'IN' ExpressionList )?
    """

    left: NumericExpression
    operator: Optional[str] = None  # '=', '!=', '<', '>', '<=', '>=', 'IN' and 'NOT IN'
    right: Optional[Union[NumericExpression, ExpressionList]] = None

    def render(self) -> Generator[str, None, None]:
        yield from self.left.render()
        if self.operator:
            yield f" {self.operator} "
            if self.right:
                yield from self.right.render()


class ValueLogical(SPARQLGrammarBase):
    relational_expression: RelationalExpression

    def render(self) -> Generator[str, None, None]:
        yield from self.relational_expression.render()


class ConditionalAndExpression(SPARQLGrammarBase):
    """
    ConditionalAndExpression	  ::=  	ValueLogical ( '&&' ValueLogical )*
    """

    value_logicals: List[ValueLogical]

    def render(self) -> Generator[str, None, None]:
        for i, value_logical in enumerate(self.value_logicals):
            yield from value_logical.render()
            if i < len(self.value_logicals) - 1:
                yield " && "


class ConditionalOrExpression(SPARQLGrammarBase):
    """
    ConditionalOrExpression	  ::=  	ConditionalAndExpression ( '||' ConditionalAndExpression )*
    """

    conditional_and_expressions: List[ConditionalAndExpression]

    def render(self) -> Generator[str, None, None]:
        for i, conditional_and_expression in enumerate(
            self.conditional_and_expressions
        ):
            yield from conditional_and_expression.render()
            if i < len(self.conditional_and_expressions) - 1:
                yield " || "


class Expression(SPARQLGrammarBase):
    """
    Expression	  ::=  	ConditionalOrExpression
    """

    conditional_or_expression: ConditionalOrExpression

    def render(self) -> Generator[str, None, None]:
        yield from self.conditional_or_expression.render()

    @classmethod
    def from_primary_expr(cls, primary_expression: PrimaryExpression) -> Expression:
        """
        Convenience method to create an Expression directly from a Var, wrapped in a PrimaryExpression.
        """
        return cls(
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
                                                    primary_expression=primary_expression
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

    @classmethod
    def create_in_expression(
        cls,
        left_primary_expression: PrimaryExpression,
        operator: str,  # "IN" or "NOT IN"
        right_primary_expressions: List[PrimaryExpression],
    ) -> Expression:
        """ """
        return cls(
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
                                                    primary_expression=left_primary_expression
                                                )
                                            )
                                        )
                                    ),
                                    operator=operator,
                                    right=ExpressionList(
                                        expressions=[
                                            Expression.from_primary_expr(expr)
                                            for expr in right_primary_expressions
                                        ]
                                    ),
                                )
                            )
                        ]
                    )
                ]
            )
        )


class BrackettedExpression(SPARQLGrammarBase):
    expression: Expression

    def render(self) -> Generator[str, None, None]:
        yield "("
        yield from self.expression.render()
        yield ")"


class InlineDataOneVar(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rInlineDataOneVar
    InlineDataOneVar	  ::=  	Var '{' DataBlockValue* '}'
    """

    variable: Var
    datablockvalues: List[Union[DataBlockValue]]

    def render(self) -> Generator[str, None, None]:
        yield from self.variable.render()
        yield "{ "
        for value in self.datablockvalues:
            yield from value.render()
            yield " "
        yield " }"


class DataBlockValue(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rDataBlockValue
    DataBlockValue	  ::=  	iri | RDFLiteral | NumericLiteral | BooleanLiteral | 'UNDEF'
    """

    value: Union[IRI, RDFLiteral, NumericLiteral, BooleanLiteral, str]

    @field_validator("value")
    def check_string_is_undef(cls, v):
        if isinstance(v, str) and v != "UNDEF":
            raise ValueError("Only permitted string value is 'UNDEF'")
        return v

    def render(self) -> Generator[str, None, None]:
        if isinstance(self.value, str):
            yield self.value
        else:
            yield from self.value.render()


class InlineDataFull(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rInlineDataFull
    ( NIL | '(' Var* ')' ) '{' ( '(' DataBlockValue* ')' | NIL )* '}'
    """

    vars: Union[NIL, List[Var]]
    datablocks: List[Union[List[DataBlockValue], NIL]]

    def render(self) -> Generator[str, None, None]:
        if self.vars:
            yield "("
            for var in self.vars:
                yield from var.render()
                yield " "
            yield ") {"
        else:
            yield "{"

        if self.datablocks is None:
            yield "()"
        else:
            for data_block in self.datablocks:
                if data_block:
                    yield "("
                    for value in data_block:
                        yield from value.render()
                        yield " "
                    yield ")"
                    yield "\n"
                else:
                    yield "()"
        yield "}"


class DataBlock(SPARQLGrammarBase):
    block: Union[InlineDataOneVar, InlineDataFull]

    def render(self) -> Generator[str, None, None]:
        yield from self.block.render()


class InlineData(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rInlineData
    InlineData	  ::=  	'VALUES' DataBlock
    """

    data_block: DataBlock

    def render(self) -> Generator[str, None, None]:
        yield "\n\tVALUES "
        yield from self.data_block.render()


class ValuesClause(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rValuesClause
    ValuesClause	  ::=  	( 'VALUES' DataBlock )?
    """

    data_block: Optional[DataBlock]

    def render(self) -> Generator[str, None, None]:
        if self.data_block:
            yield "\n\tVALUES "
            yield from self.data_block.render()


class GraphPatternNotTriples(SPARQLGrammarBase):
    """
    Partially implemented
    https://www.w3.org/TR/sparql11-query/#rGraphPatternNotTriples
    GraphPatternNotTriples	  ::=  	GroupOrUnionGraphPattern | OptionalGraphPattern | MinusGraphPattern | GraphGraphPattern | ServiceGraphPattern | Filter | Bind | InlineData
    """

    content: Union[
        GroupOrUnionGraphPattern, OptionalGraphPattern, Filter, Bind, InlineData
    ]

    def render(self) -> Generator[str, None, None]:
        yield from self.content.render()


class GroupGraphPatternSub(SPARQLGrammarBase):
    """
    GraphPatternNotTriples partially implemented
    https://www.w3.org/TR/sparql11-query/#rGroupGraphPatternSub
    GroupGraphPatternSub	  ::=  	TriplesBlock? ( GraphPatternNotTriples '.'? TriplesBlock? )*
    """

    triples_block: Optional[TriplesBlock] = None
    graph_patterns_or_triples_blocks: Optional[
        List[Union[GraphPatternNotTriples, TriplesBlock]]
    ] = None

    def render(self) -> Generator[str, None, None]:
        if self.triples_block:
            yield from self.triples_block.render()
        if self.graph_patterns_or_triples_blocks:
            for item in self.graph_patterns_or_triples_blocks:
                yield from item.render()

    def add_pattern(self, pattern, prepend=False):
        if not isinstance(pattern, (TriplesBlock, GraphPatternNotTriples)):
            raise TypeError(
                "Pattern must be an instance of TriplesBlock or GraphPatternNotTriples."
            )
        if self.graph_patterns_or_triples_blocks is None:
            self.graph_patterns_or_triples_blocks = []
        if prepend:
            self.graph_patterns_or_triples_blocks.insert(0, pattern)
        else:
            self.graph_patterns_or_triples_blocks.append(pattern)

    def add_triple(self, triple):
        if not isinstance(triple, SimplifiedTriple):
            raise TypeError("Triple must be an instance of SimplifiedTriple.")
        if self.triples_block is None:
            self.triples_block = TriplesBlock()
            # prevent duplicates
        if triple not in self.triples_block.triples:
            self.triples_block.triples.append(triple)


# TODO future implementation below simplifies things to a single list, needs to be tested:

# class GroupGraphPatternSub(SPARQLGrammarBase):
#     """
#     GroupGraphPatternSub ::= TriplesBlock? (GraphPatternNotTriples '.'? TriplesBlock?)*
#     """
#     patterns: Optional[List[Union[TriplesBlock, GraphPatternNotTriples]]] = None
#
#     def render(self) -> Generator[str, None, None]:
#         for pattern in self.patterns:
#             yield from pattern.render()
#
#     def append_triples(self, triples: TriplesBlock):
#         # If the last item in the list is a TriplesBlock, append the triples to it
#         if not self.patterns:
#             self.patterns = []
#         if self.patterns and isinstance(self.patterns[-1], TriplesBlock):
#             self.patterns[-1].append(triples)
#         else:
#             # Otherwise, add a new TriplesBlock to the list
#             self.patterns.append(triples)


class SelectClause(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rSelectClause
    SelectClause	  ::=  	'SELECT' ( 'DISTINCT' | 'REDUCED' )? ( ( Var | ( '(' Expression 'AS' Var ')' ) )+ | '*' )
    """

    distinct: Optional[bool] = None
    reduced: Optional[bool] = None
    variables_or_all: Union[List[Union[Var, Tuple[Expression, Var]]], str]

    def render(self):
        yield "SELECT"
        if self.distinct:
            yield " DISTINCT"
        elif self.reduced:
            yield " REDUCED"
        if isinstance(self.variables_or_all, str):
            yield " *"
        else:
            for item in self.variables_or_all:
                if isinstance(item, Var):
                    yield " "
                    yield from item.render()
                elif isinstance(item, Tuple):
                    expression, as_var = item
                    yield " ("
                    yield from expression.render()
                    yield " AS "
                    yield from as_var.render()
                    yield ")"


class SubSelect(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rSubSelect
    SubSelect	  ::=  	SelectClause WhereClause SolutionModifier ValuesClause
    """

    select_clause: SelectClause
    where_clause: WhereClause
    solution_modifier: Optional[SolutionModifier] = None
    values_clause: Optional[ValuesClause] = None

    def render(self):
        yield from self.select_clause.render()
        yield from self.where_clause.render()
        if self.solution_modifier:
            yield from self.solution_modifier.render()
        if self.values_clause:
            yield from self.values_clause.render()


class SubSelectString(SubSelect):
    """Inherits from the SubSelect class such that it can be used as a drop in replacement where a subselect is provided
    as text, such as via sh:target / sh:select. NB by providing a subquery this way, the query cannot be validated. Use
    of translateAlgebra will to some extent "validate" the query though, and will expand any prefixes known to RDFLib."""

    select_clause: Optional[str] = None
    where_clause: Optional[str] = None
    solution_modifier: Optional[SolutionModifier] = None
    select_string: str

    @field_validator("select_string")
    def validate_and_transform_select_string(cls, v):
        try:
            translateAlgebra(prepareQuery(translateAlgebra(prepareQuery(v))))
            return translateAlgebra(prepareQuery(v))
        except Exception as e:
            log.error(msg=f'Potential query issue, or RDFLib bug: "{str(e)}"')
            return v

    def render(self):
        yield self.select_string
        if self.solution_modifier:
            yield from self.solution_modifier.render()


class GroupGraphPattern(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rGroupGraphPattern
    GroupGraphPattern	  ::=  	'{' ( SubSelect | GroupGraphPatternSub ) '}'
    """

    content: Union[SubSelect, GroupGraphPatternSub]

    def render(self) -> Generator[str, None, None]:
        yield "{\n"
        yield from self.content.render()
        yield "\n}"


class Filter(SPARQLGrammarBase):
    """
    Represents a SPARQL FILTER clause.
    Filter ::= 'FILTER' Constraint
    """

    constraint: Constraint

    def render(self) -> Generator[str, None, None]:
        yield "FILTER "
        yield from self.constraint.render()

    @classmethod
    def filter_relational(
        cls,
        focus: PrimaryExpression,
        comparators: Union[PrimaryExpression, List[PrimaryExpression]],
        operator: str,
    ) -> Filter:
        """
        Convenience method to create a FILTER clause to compare the focus node to comparators.
        """
        # Wrap the focus in an NumericExpression
        numeric_left = NumericExpression(
            additive_expression=AdditiveExpression(
                base_expression=MultiplicativeExpression(
                    base_expression=UnaryExpression(primary_expression=focus)
                )
            )
        )
        # for operators in '=', '!=', '<', '>', '<=', '>='
        if isinstance(comparators, PrimaryExpression):
            assert operator not in [
                "IN",
                "NOT IN",
            ], "an ExpressionList must be supplied for 'IN' or 'NOT IN'"
            expression_rhs = NumericExpression(
                additive_expression=AdditiveExpression(
                    base_expression=MultiplicativeExpression(
                        base_expression=UnaryExpression(primary_expression=comparators)
                    )
                )
            )
        else:  # for operators 'IN' and 'NOT IN'
            # Wrap each comparator in an Expression
            assert operator in ["IN", "NOT IN"]
            comparator_exprs = [
                Expression.from_primary_expr(comp) for comp in comparators
            ]
            expression_rhs = ExpressionList(expressions=comparator_exprs)
        # Build the RelationalExpression
        relational_expr = RelationalExpression(
            left=numeric_left, operator=operator, right=expression_rhs
        )
        # Build the ValueLogical to wrap the RelationalExpression
        value_logical = ValueLogical(relational_expression=relational_expr)
        # Build the ConditionalAndExpression to wrap the ValueLogical
        conditional_and_expr = ConditionalAndExpression(value_logicals=[value_logical])
        # Build the ConditionalOrExpression to wrap the ConditionalAndExpression
        conditional_or_expr = ConditionalOrExpression(
            conditional_and_expressions=[conditional_and_expr]
        )
        expression = Expression(conditional_or_expression=conditional_or_expr)
        # Create and return the Filter
        bracketted_expr = BrackettedExpression(expression=expression)
        return cls(constraint=Constraint(content=bracketted_expr))


class Constraint(SPARQLGrammarBase):
    """
    Represents a SPARQL Constraint.
    Constraint ::= BrackettedExpression | BuiltInCall | FunctionCall
    """

    content: Union[BrackettedExpression, BuiltInCall, FunctionCall]

    def render(self) -> Generator[str, None, None]:
        yield from self.content.render()


class FunctionCall(SPARQLGrammarBase):
    """
    FunctionCall	  ::=  	iri ArgList
    Represents a SPARQL FunctionCall.
    FunctionCall ::= iri ArgList
    """

    iri: IRI
    arg_list: ArgList

    def render(self) -> Generator[str, None, None]:
        yield from self.iri.render()
        yield from self.arg_list.render()


class ArgList(SPARQLGrammarBase):
    """
    Represents a SPARQL ArgList.
    ArgList ::= NIL | '(' 'DISTINCT'? Expression ( ',' Expression )* ')'
    """

    expressions: Optional[Union[NIL, List[Expression]]]
    distinct: bool = False

    def render(self) -> Generator[str, None, None]:
        if isinstance(self.expressions, NIL):
            yield from self.expressions.render()
        else:
            if self.distinct:
                yield "DISTINCT "
            yield "("
            for i, expr in enumerate(self.expressions):
                yield from expr.render()
                if i < len(self.expressions) - 1:
                    yield ", "
            yield ")"


class Bind(SPARQLGrammarBase):
    """
    Bind	  ::=  	'BIND' '(' Expression 'AS' Var ')'
    https://www.w3.org/TR/sparql11-query/#rBind
    """

    expression: Expression
    var: Var

    def render(self) -> Generator[str, None, None]:
        yield f"BIND("
        yield from self.expression.render()
        yield f" AS"
        yield from self.var.render()
        yield ")"


class OptionalGraphPattern(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rOptionalGraphPattern
    OptionalGraphPattern	  ::=  	'OPTIONAL' GroupGraphPattern
    """

    group_graph_pattern: GroupGraphPattern

    def render(self) -> Generator[str, None, None]:
        yield "\nOPTIONAL "
        yield from self.group_graph_pattern.render()


class GroupOrUnionGraphPattern(SPARQLGrammarBase):
    """
    For UNION statements
    https://www.w3.org/TR/sparql11-query/#rGroupOrUnionGraphPattern
    GroupOrUnionGraphPattern	  ::=  	GroupGraphPattern ( 'UNION' GroupGraphPattern )*
    """

    group_graph_patterns: List[GroupGraphPattern]

    def render(self) -> Generator[str, None, None]:
        ggps_iter = iter(self.group_graph_patterns)
        first_ggp = next(ggps_iter)

        yield "\n"
        yield from first_ggp.render()
        for ggp in ggps_iter:  # UNION goes between 2:N group graph patterns
            yield "\nUNION\n"
            yield from ggp.render()


class LimitClause(SPARQLGrammarBase):
    limit: int

    def render(self) -> Generator[str, None, None]:
        yield f"LIMIT {self.limit}"


class OffsetClause(SPARQLGrammarBase):
    offset: int

    def render(self) -> Generator[str, None, None]:
        yield f"OFFSET {self.offset}"


class OrderCondition(SPARQLGrammarBase):
    """
    Default direction is ASC if not specified
    """

    var: Var
    direction: Optional[str] = None

    def render(self):
        if self.direction:
            yield f"{self.direction}("
            yield from self.var.render()
            yield ")"
        else:
            yield from self.var.render()


class OrderClause(SPARQLGrammarBase):
    conditions: List[OrderCondition]

    def render(self):
        yield "\nORDER BY "
        yield " ".join(
            part for condition in self.conditions for part in condition.render()
        )


class LimitOffsetClauses(SPARQLGrammarBase):
    """
    Represents the LIMIT and OFFSET clauses in SPARQL queries.
    According to the SPARQL grammar:
    LimitOffsetClauses ::= LimitClause OffsetClause? | OffsetClause LimitClause?
    """

    limit_clause: Optional[LimitClause] = None
    offset_clause: Optional[OffsetClause] = None

    def render(self) -> Generator[str, None, None]:
        if self.limit_clause:
            yield from self.limit_clause.render()
        if self.offset_clause:
            if self.limit_clause:
                yield "\n"
            yield from self.offset_clause.render()


class SolutionModifier(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rSolutionModifier
    SolutionModifier	  ::=  	GroupClause? HavingClause? OrderClause? LimitOffsetClauses?
    """

    order_by: Optional[OrderClause] = None
    limit_offset: Optional[LimitOffsetClauses] = None
    # having: Optional[HavingClause]
    group_by: Optional["GroupClause"] = None

    def render(self) -> str:
        if self.order_by:
            yield from self.order_by.render()
        if self.limit_offset:
            if self.order_by:
                yield "\n"
            yield from self.limit_offset.render()
        if self.group_by:
            yield from self.group_by.render()


class GroupClause(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rGroupClause
    GroupClause ::= 'GROUP' 'BY' GroupCondition+
    """

    group_conditions: List["GroupCondition"]

    def render(self) -> Generator[str, None, None]:
        yield "\nGROUP BY "
        for i, condition in enumerate(self.group_conditions):
            yield from condition.render()
            if i < len(self.group_conditions) - 1:  # Check if it's not the last triple
                yield " "


class GroupCondition(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rGroupCondition
    GroupCondition ::= BuiltInCall | FunctionCall | '(' Expression ( 'AS' Var )? ')' | Var
    """

    condition: Union[BuiltInCall, FunctionCall, Tuple[Expression, Var], Var]

    def render(self) -> Generator[str, None, None]:
        if isinstance(self.condition, Tuple):
            yield "("
            yield from self.condition[0].render()
            yield " AS "
            yield from self.condition[1].render()
            yield ")"
        else:
            yield from self.condition.render()


class ConstructTriples(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rConstructTriples
    ConstructTriples	  ::=  	TriplesSameSubject ( '.' ConstructTriples? )?

    Simplified implementation that only accepts a list of SimplifiedTriples - avoids implementing the classes associated
    with ; and , for TriplesSameSubject etc. in the SPARQL Grammar
    """

    triples: List[SimplifiedTriple]

    def render(self) -> Generator[str, None, None]:
        for i, triple in enumerate(self.triples):
            yield from triple.render()
            if i < len(self.triples) - 1:  # Check if it's not the last triple
                yield "\n"


class ConstructTemplate(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rConstructTemplate
    ConstructTemplate	  ::=  	'{' ConstructTriples? '}'
    """

    construct_triples: ConstructTriples

    def render(self) -> Generator[str, None, None]:
        yield "{\n"
        yield from self.construct_triples.render()
        yield "\n}"


class WhereClause(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rWhereClause
    WhereClause	  ::=  	'WHERE'? GroupGraphPattern
    """

    group_graph_pattern: GroupGraphPattern

    def render(self) -> Generator[str, None, None]:
        yield "\nWHERE "
        yield from self.group_graph_pattern.render()


class ConstructQuery(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rConstructQuery
    ConstructQuery	  ::=  	'CONSTRUCT' ( ConstructTemplate DatasetClause* WhereClause SolutionModifier | DatasetClause* 'WHERE' '{' TriplesTemplate? '}' SolutionModifier )

    Currently simplified to only accept a ConstructTemplate, WhereClause, and SolutionModifier.
    """

    construct_template: ConstructTemplate
    where_clause: WhereClause
    solution_modifier: SolutionModifier

    def render(self) -> Generator[str, None, None]:
        yield "CONSTRUCT "
        yield from self.construct_template.render()
        yield from self.where_clause.render()
        yield from self.solution_modifier.render()


class BuiltInCall(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rBuiltInCall
    """

    other_expressions: Optional[Union[Aggregate, RegexExpression]] = None
    function_name: Optional[str] = None
    arguments: Optional[
        List[Union[Expression, Tuple[Expression], ExpressionList, Var, NIL]]
    ] = None

    @field_validator("function_name")
    def validate_function_name(cls, v):
        implemented = [
            "URI",
            "STR",
            "CONCAT",
            "SHA256",
            "LCASE",
            "isBLANK",
            "LANG",
            "LANGMATCHES",
        ]
        if v not in implemented:
            raise ValueError(
                f"{v} is not a valid SPARQL built-in function or it is not implemented yet"
            )
        return v

    def render(self) -> Generator[str, None, None]:
        if self.other_expressions:
            yield from self.other_expressions.render()
        else:
            yield f"{self.function_name}("
            if self.arguments:
                for i, arg in enumerate(self.arguments):
                    yield from arg.render()
                    if i < len(self.arguments) - 1:
                        yield ", "
            yield ")"

    @classmethod
    def create_with_one_expr(
        cls, function_name: str, expression: PrimaryExpression
    ) -> "BuiltInCall":
        """
        Convenience method for functions that take a single PrimaryExpression as an argument.
        Uses create_with_expression_list for consistency in handling expressions.
        """
        return cls.create_with_n_expr(function_name, [expression])

    @classmethod
    def create_with_n_expr(
        cls, function_name: str, expressions: List[PrimaryExpression]
    ) -> BuiltInCall:
        """
        Convenience method for functions that take a list of PrimaryExpressions as arguments.
        Wraps each PrimaryExpression in an Expression.
        """
        wrapped_expressions = [Expression.from_primary_expr(pe) for pe in expressions]

        # Create a BuiltInCall instance for the specified function with the list of wrapped expressions
        return cls(function_name=function_name, arguments=wrapped_expressions)


class BooleanLiteral(SPARQLGrammarBase):
    value: bool

    def render(self) -> Generator[str, None, None]:
        yield "true" if self.value else "false"


class GraphTerm(SPARQLGrammarBase):
    """
    Represents a SPARQL GraphTerm.
    GraphTerm ::= iri | RDFLiteral | NumericLiteral | BooleanLiteral | BlankNode | NIL
    """

    content: Union[IRI, RDFLiteral, NumericLiteral, BooleanLiteral, BlankNode, NIL]

    def render(self) -> Generator[str, None, None]:
        yield from self.content.render()


class IRIOrFunction(SPARQLGrammarBase):
    """
    iriOrFunction	  ::=  	iri ArgList?
    """

    iri: IRI
    arg_list: Optional[ArgList] = None

    def render(self) -> Generator[str, None, None]:
        yield from self.iri.render()
        if self.arg_list:
            yield "("
            yield from self.arg_list.render()
            yield ")"


class ExpressionList(SPARQLGrammarBase):
    expressions: Optional[List[Expression]] = []

    def render(self) -> Generator[str, None, None]:
        if not self.expressions:
            yield "()"
        else:
            yield "("
            for i, expression in enumerate(self.expressions):
                yield from expression.render()
                if i < len(self.expressions) - 1:
                    yield ", "
            yield ")"


class Aggregate(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rAggregate
    Aggregate	  ::=  	  'COUNT' '(' 'DISTINCT'? ( '*' | Expression ) ')'
    | 'SUM' '(' 'DISTINCT'? Expression ')'
    | 'MIN' '(' 'DISTINCT'? Expression ')'
    | 'MAX' '(' 'DISTINCT'? Expression ')'
    | 'AVG' '(' 'DISTINCT'? Expression ')'
    | 'SAMPLE' '(' 'DISTINCT'? Expression ')'
    | 'GROUP_CONCAT' '(' 'DISTINCT'? Expression ( ';' 'SEPARATOR' '=' String )? ')'
    """

    function_name: str  # One of 'COUNT', 'SUM', 'MIN', 'MAX', 'AVG', 'SAMPLE', 'GROUP_CONCAT'
    distinct: Optional[bool] = None
    expression: Optional[
        Union[str, Expression]
    ] = None  # '*' for COUNT, else Expression
    separator: Optional[str] = None  # Only used for GROUP_CONCAT

    @field_validator("function_name")
    def validate_function_name(cls, v):
        if v not in ["COUNT", "SUM", "MIN", "MAX", "AVG", "SAMPLE", "GROUP_CONCAT"]:
            raise ValueError(
                "Function name must be one of 'COUNT', 'SUM', 'MIN', 'MAX', 'AVG', 'SAMPLE', 'GROUP_CONCAT'"
            )
        return v

    @field_validator("expression")
    def validate_expression(cls, v):
        if v == "*" and cls.function_name != "COUNT":
            raise ValueError("'*' can only be used for COUNT")
        return v

    @field_validator("separator")
    def validate_separator(cls, v):
        if cls.function_name != "GROUP_CONCAT":
            raise ValueError("'SEPARATOR' can only be used for GROUP_CONCAT")
        return v

    def render(self) -> Generator[str, None, None]:
        yield f"{self.function_name}("
        if self.distinct:
            yield "DISTINCT "
        if self.expression == "*":
            yield "*"
        else:
            yield from self.expression.render()
        # Handle the separator for GROUP_CONCAT
        if self.separator:
            yield f" ; SEPARATOR='{self.separator}'"
        yield ")"


class RegexExpression(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rRegexExpression
    RegexExpression	  ::=  	'REGEX' '(' Expression ',' Expression ( ',' Expression )? ')'
    """

    text_expression: Expression
    pattern_expression: Expression
    flags_expression: Optional[Expression] = None

    def render(self) -> Generator[str, None, None]:
        yield "REGEX("
        yield from self.text_expression.render()
        yield ", "
        yield from self.pattern_expression.render()

        if self.flags_expression:
            yield ", "
            yield from self.flags_expression.render()

        yield ")"

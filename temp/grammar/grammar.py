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

    def collect_triples(self) -> List[TriplesSameSubjectPath]:
        """
        Recursively collect TriplesSameSubjectPath instances from this object.
        """
        triples = []

        # Iterate through all attributes of the object
        for attribute_name in self.model_fields:
            attribute_value = getattr(self, attribute_name)

            # Check if the attribute is a TriplesSameSubjectPath and collect it
            if isinstance(attribute_value, TriplesSameSubjectPath):
                triples.append(attribute_value)

            # If the attribute is a list, iterate through it and collect TriplesSameSubjectPath
            elif isinstance(attribute_value, list):
                for item in attribute_value:
                    if isinstance(item, TriplesSameSubjectPath):
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
        yield from self.part_1
        if self.part_2:
            yield from self.part_2


class Anon:
    """
    ANON	  ::=  	'[' WS* ']'
    https://www.w3.org/TR/sparql11-query/#rANON
    """

    def render(self):
        yield "[]"


class Var(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rVar
    Var	  ::=  	VAR1 | VAR2
    """
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
        yield " "

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


# class SimplifiedTriple(SPARQLGrammarBase):
#     """A simplified implmementation the triple pattern matches in the SPARQL grammar, to avoid implementing many classes
#     such as TriplesSameSubjectPath"""
#
#     subject: Union[IRI, Var, BlankNode]
#     predicate: Union[IRI, Var]
#     object: Union[IRI, RDFLiteral, Var, BlankNode, NumericLiteral]
#
#     def render(self) -> Generator[str, None, None]:
#         yield from self.subject.render()
#         yield " "
#         yield from self.predicate.render()
#         yield " "
#         yield from self.object.render()
#         yield " ."

# def __hash__(self):
#     return hash((self.subject, self.predicate, self.object))


class TriplesBlock(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rTriplesBlock
    TriplesBlock	  ::=  	TriplesSameSubjectPath ( '.' TriplesBlock? )?
    """
    triples: TriplesSameSubjectPath = None
    triples_block: Optional[TriplesBlock] = None

    def render(self) -> Generator[str, None, None]:
        if isinstance(self.triples, list):
            for i, triple in enumerate(self.triples):
                yield from triple.render()
                # if i < len(self.triples) - 1:  # Check if it's not the last triple
                yield "\n"
        else:
            yield from self.triples.render()
            if self.triples_block:
                yield " .\n"
                yield from self.triples_block.render()
                yield "\n"

    # TODO check if subject is same, if so, absorb into existing triples same subject path
    @classmethod
    def from_tssp_list(cls, tssp_list: Optional[List[TriplesSameSubjectPath]]):
        if tssp_list:
            tssp_iter = iter(tssp_list)
            first_tssp = next(tssp_iter)
            tb = cls(triples=first_tssp)
            for tssp in tssp_iter:
                tb = cls(triples=tssp, triples_block=tb)
            return tb


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
    def from_primary_expression(cls, primary_expression: PrimaryExpression) -> Expression:
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
                                            Expression.from_primary_expression(expr)
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
        yield "\n"
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

    # def add_triple(self, triple):
    #     if not isinstance(triple, TriplesSameSubjectPath):
    #         raise TypeError("Triple must be an instance of TriplesSameSubjectPath.")
    #     if self.triples_block is None:
    #         self.triples_block = TriplesBlock()
    #         # prevent duplicates
    #     if triple not in self.triples_block.triples:
    #         self.triples_block.triples.append(triple)


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

    content: SubSelect | GroupGraphPatternSub

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
                Expression.from_primary_expression(comp) for comp in comparators
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
        yield f" AS "
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
    group_by: Optional[GroupClause] = None

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


class TriplesSameSubject(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rTriplesSameSubject
    TriplesSameSubject	  ::=  	VarOrTerm PropertyListNotEmpty | TriplesNode PropertyList
    """

    content: Union[Tuple[VarOrTerm, PropertyListNotEmpty] | Tuple[TriplesNode, PropertyList]]

    def render(self):
        yield from self.content[0].render()
        yield " "
        yield from self.content[1].render()

    def __hash__(self):
        return hash(self.content)

    @classmethod
    def from_spo(cls, subject: Var | IRI | BlankNode, predicate: Var | IRI, object: Var | IRI | BlankNode):
        """
        Convenience method to create a TriplesSameSubject from a subject, predicate, and object.
        Currently supports only Var and IRI types for subject, predicate, and object.
        """
        # Handle subjects
        if isinstance(subject, Var):
            s_vot = VarOrTerm(varorterm=subject)
        elif isinstance(subject, (IRI, BlankNode)):
            s_vot = VarOrTerm(varorterm=GraphTerm(content=subject))
        else:
            raise ValueError("s must be a Var, IRI or BlankNode")

        # Handle predicates
        if isinstance(predicate, (Var, IRI)):
            verb = Verb(varoriri=VarOrIri(varoriri=predicate))
        else:
            raise ValueError("p must be a Var or IRI")

        # Handle objects
        if isinstance(object, Var):
            o_vot = VarOrTerm(varorterm=object)
        elif isinstance(object, (IRI, BlankNode)):
            o_vot = VarOrTerm(varorterm=GraphTerm(content=object))
        else:
            raise ValueError("o must be a Var, IRI or BlankNode")

        return cls(
            content=(
                s_vot,
                PropertyListNotEmpty(
                    verb_objectlist=[(
                        verb,
                        ObjectList(
                            list_object=[
                                Object(
                                    graphnode=GraphNode(
                                        varorterm_or_triplesnode=o_vot
                                    )
                                )
                            ]
                        )
                    )]
                )
            )
        )



class ConstructTriples(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rConstructTriples
    ConstructTriples	  ::=  	TriplesSameSubject ( '.' ConstructTriples? )?
    """

    triples: TriplesSameSubject
    construct_triples: Optional[ConstructTriples] = None

    def render(self) -> Generator[str, None, None]:
        yield from self.triples.render()
        if self.construct_triples:
            yield " .\n"
            yield from self.construct_triples.render()

    @classmethod
    def from_tss_list(cls, tss_list: List[TriplesSameSubject]):
        tss_iter = iter(tss_list)
        first_tss = next(tss_iter)
        ct = cls(triples=first_tss)
        for tss in tss_iter:
            try:
                ct = cls(triples=tss, construct_triples=ct)
            except Exception as e:
                print('')
        return ct

    def to_tss_list(self):
        tss_list = []
        ct = self
        while ct:
            tss_list.append(ct.triples)
            ct = ct.construct_triples
        return tss_list

    @classmethod
    def merge_ct(cls, ct_list: List[ConstructTriples]):
        """
        Merges a list of ConstructTriples objects into a single ConstructTriples.
        """
        ct_iter = iter(ct_list)
        try:
            first_ct = next(ct_iter)  # Start with the first ConstructTriples in the list
        except StopIteration:
            return None  # Return None if the list is empty

        current_ct = first_ct
        for next_ct in ct_iter:
            # Traverse to the last construct_triples that does not have a nested construct_triples
            while current_ct.construct_triples is not None:
                current_ct = current_ct.construct_triples
            # Link the next ConstructTriples in the list to the bottom of the current tree
            current_ct.construct_triples = next_ct
            current_ct = next_ct  # Move the pointer to the newly added ConstructTriples

        return first_ct


class ConstructTemplate(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rConstructTemplate
    ConstructTemplate	  ::=  	'{' ConstructTriples? '}'
    """

    construct_triples: Optional[ConstructTriples] = None

    def render(self) -> Generator[str, None, None]:
        if self.construct_triples:
            yield "{\n"
            yield from self.construct_triples.render()
            yield "\n}"

    def __hash__(self):
        return hash(self.construct_triples)


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

    other_expressions: Optional[Union[Aggregate, RegexExpression, ExistsFunc, NotExistsFunc]] = None
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
            "isURI",
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
    ) -> BuiltInCall:
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
        wrapped_expressions = [Expression.from_primary_expression(pe) for pe in expressions]

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

    def __hash__(self):
        return hash(self.content)


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


# class QueryUnit(SPARQLGrammarBase):
#     query: Query
#
#     def render(self) -> Generator[str, None, None]:
#         yield from self.query.render()
#
#
# class Query(SPARQLGrammarBase):
#     prologue: Prologue
#     query: Union[SelectQuery, ConstructQuery, DescribeQuery, AskQuery]
#     values_clause: ValuesClause

class VerbPath(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rVerbPath
    VerbPath	  ::=  	Path
    """
    path: SG_Path

    def render(self) -> Generator[str, None, None]:
        yield from self.path.render()

    def __hash__(self):
        return hash(self.path)


class VerbSimple(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rVerbSimple
    VerbSimple	  ::=  	Var
    """
    var: Var

    def render(self) -> Generator[str, None, None]:
        yield from self.var.render()

    def __hash__(self):
        return hash(self.var)


class ObjectListPath(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rObjectListPath
    ObjectListPath	  ::=  	ObjectPath ( ',' ObjectPath )*
    """
    object_paths: List[ObjectPath]

    def render(self):
        op_iter = iter(self.object_paths)
        first = next(op_iter)
        yield from first.render()
        for op in op_iter:
            yield ","
            yield from op.render()

    def __hash__(self):
        return hash(tuple(self.object_paths))


class ObjectPath(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rObjectPath
    ObjectPath	  ::=  	GraphNodePath
    """
    graph_node_path: GraphNodePath

    def render(self) -> Generator[str, None, None]:
        yield from self.graph_node_path.render()

    def __hash__(self):
        return hash(self.graph_node_path)


class SG_Path(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rPath
    Path	  ::=  	PathAlternative
    """
    path_alternative: PathAlternative

    def render(self) -> Generator[str, None, None]:
        yield from self.path_alternative.render()

    def __hash__(self):
        return hash(self.path_alternative)


class PathAlternative(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rPathAlternative
    PathAlternative	  ::=  	PathSequence ( '|' PathSequence )*
    """
    sequence_paths: List[PathSequence]

    @field_validator("sequence_paths")
    def must_contain_at_least_one_item(cls, v):
        if len(v) == 0:
            raise ValueError('sequence_paths must contain at least one item.')
        return v

    def render(self):
        sp_iter = iter(self.sequence_paths)
        first = next(sp_iter)

        yield from first.render()
        for sp in sp_iter:
            yield "|"
            yield from sp.render()

    def __hash__(self):
        return hash(tuple(self.sequence_paths))


class PathSequence(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rPathSequence
    PathSequence	  ::=  	PathEltOrInverse ( '/' PathEltOrInverse )*
    """

    list_path_elt_or_inverse: List[PathEltOrInverse]

    @field_validator("list_path_elt_or_inverse")
    def must_contain_at_least_one_item(cls, v):
        if len(v) == 0:
            raise ValueError('list_path_elt_or_inverse must contain at least one item.')
        return v

    def render(self):
        path_iter = iter(self.list_path_elt_or_inverse)
        first = next(path_iter)

        yield from first.render()
        for path in path_iter:
            yield "/"
            yield from path.render()

    def __hash__(self):
        return hash(tuple(self.list_path_elt_or_inverse))


class PathElt(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rPathElt
    PathElt	  ::=  	PathPrimary PathMod?
    """
    path_primary: PathPrimary
    path_mod: Optional[PathMod] = None

    def render(self):
        yield from self.path_primary.render()
        if self.path_mod:
            yield from self.path_mod.render()

    def __hash__(self):
        return hash((self.path_primary, self.path_mod))


class PathEltOrInverse(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rPathEltOrInverse
    PathEltOrInverse	  ::=  	PathElt | '^' PathElt
    """
    path_elt: PathElt
    inverse: bool = False

    def render(self):
        if self.inverse:
            yield "^"
        yield from self.path_elt.render()

    def __hash__(self):
        return hash((self.path_elt, self.inverse))


class PathMod(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rPathMod
    PathMod	  ::=  	'?' | '*' | '+'
    """
    pathmod: str

    def render(self):
        yield self.pathmod

    @field_validator("pathmod")
    def validate_function_name(cls, v):
        # TODO there's pydantic enumeration type that can be used on the type
        if v not in ["?", "*", "+"]:
            raise ValueError(
                "PathMod must be one of '?', '*', '+'"
            )
        return v

    def __hash__(self):
        return hash(self.pathmod)


class PathPrimary(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rPathPrimary
    PathPrimary	  ::=  	iri | 'a' | '!' PathNegatedPropertySet | '(' Path ')'
    """
    value: Union[IRI, str, PathNegatedPropertySet, SG_Path]

    @field_validator("value")
    def validate_function_name(cls, v):
        if isinstance(v, str) and v != "a":
            raise ValueError(
                "only valid string values for value is 'a'."
                "See https://www.w3.org/TR/sparql11-query/#rPathPrimary"
            )
        return v

    def render(self):
        if isinstance(self.value, str):
            yield self.value
        elif isinstance(self.value, IRI):
            yield from self.value.render()
        elif isinstance(self.value, PathNegatedPropertySet):
            yield "!"
            yield from self.value.render()
        elif isinstance(self.value, SG_Path):
            yield "("
            yield from self.value.render()
            yield ")"

    def __hash__(self):
        return hash(self.value)


class PathNegatedPropertySet(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rPathNegatedPropertySet
    PathNegatedPropertySet	  ::=  	PathOneInPropertySet | '(' ( PathOneInPropertySet ( '|' PathOneInPropertySet )* )? ')'
    """
    first_path: PathOneInPropertySet
    other_paths: Optional[List[PathOneInPropertySet]]  # negated paths?

    def render(self):
        yield from self.first_path.render()

        if self.other_paths:
            other_paths_iter = iter(self.other_paths)
            first_other_path = next(other_paths_iter)

            yield "("
            yield from first_other_path.render()

            for path in other_paths_iter:
                yield "|"
                yield from path.render()

            yield ")"

    def __hash__(self):
        return hash((self.first_path, self.other_paths))


class PathOneInPropertySet(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rPathOneInPropertySet
    PathOneInPropertySet	  ::=  	iri | 'a' | '^' ( iri | 'a' )
    """
    path: Union[IRI, str]
    negated: bool = False

    def render(self):
        if self.negated:
            yield "^"
        if isinstance(self.path, IRI):
            yield from self.path.render()
        elif isinstance(self.path, str):
            yield self.path

    def __hash__(self):
        return hash((self.path, self.negated))


class Integer(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rInteger
    Integer	  ::=  	INTEGER
    """
    integer: INTEGER

    def render(self):
        yield from self.integer.render()


class INTEGER(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rINTEGER
    INTEGER	  ::=  	[0-9]+
    """
    integer: str

    # TODO validation - use regex or str functions?
    def render(self):
        yield self.integer


class TriplesNode(SPARQLGrammarBase):
    coll_or_bnpl: SG_Collection | BlankNodePropertyList

    def render(self):
        yield from self.coll_or_bnpl.render()


class BlankNodePropertyList(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rBlankNodePropertyList
    BlankNodePropertyList	  ::=  	'[' PropertyListNotEmpty ']'
    """
    plne: PropertyListNotEmpty

    def render(self):
        yield "["
        yield from self.plne.render()
        yield "]"


class TriplesNodePath(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rTriplesNodePath
    TriplesNodePath	  ::=  	CollectionPath | BlankNodePropertyListPath
    """
    coll_path_or_bnpl_path: CollectionPath | BlankNodePropertyListPath

    def render(self):
        yield from self.coll_path_or_bnpl_path.render()

    def __hash__(self):
        return hash(self.coll_path_or_bnpl_path)


class BlankNodePropertyListPath(SPARQLGrammarBase):
    plpne: PropertyListPathNotEmpty

    def render(self):
        yield "["
        yield from self.plpne.render()
        yield "]"

    def __hash__(self):
        return hash(self.plpne)


class SG_Collection(SPARQLGrammarBase):
    graphnode_list: List[GraphNode]

    def render(self):
        yield "("
        for node in self.graphnode_list:
            yield from node.render()
        yield ")"


class CollectionPath(SPARQLGrammarBase):
    graphnodepath_list: List[GraphNodePath]

    def render(self):
        yield "("
        for node in self.graphnodepath_list:
            yield from node.render()
        yield ")"

    def __hash__(self):
        return hash(tuple(self.graphnodepath_list))


class GraphNode(SPARQLGrammarBase):
    varorterm_or_triplesnode: VarOrTerm | TriplesNode

    def render(self):
        yield from self.varorterm_or_triplesnode.render()


class GraphNodePath(SPARQLGrammarBase):
    varorterm_or_triplesnodepath: VarOrTerm | TriplesNodePath

    def render(self):
        yield from self.varorterm_or_triplesnodepath.render()

    def __hash__(self):
        return hash(self.varorterm_or_triplesnodepath)


class VarOrTerm(SPARQLGrammarBase):
    varorterm: Var | GraphTerm

    def render(self):
        yield from self.varorterm.render()

    def __hash__(self):
        return hash(self.varorterm)


class VarOrIri(SPARQLGrammarBase):
    varoriri: Var | IRI

    def render(self):
        yield from self.varoriri.render()


class PropertyListNotEmpty(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rPropertyListNotEmpty
    PropertyListNotEmpty	  ::=  	Verb ObjectList ( ';' ( Verb ObjectList )? )*
    """
    verb_objectlist: List[Tuple[Verb, ObjectList]]

    def render(self):
        vo_iter = iter(self.verb_objectlist)
        first_vo = next(vo_iter)
        yield from first_vo[0].render()  # verb
        yield " "
        yield from first_vo[1].render()  # objectlist
        for item in vo_iter:
            yield ";"
            yield from item[0].render()  # verb
            yield " "
            yield from item[1].render()  # objectlist


class Verb(SPARQLGrammarBase):
    varoriri: VarOrIri | str

    def render(self):
        if isinstance(self.varoriri, VarOrIri):
            yield from self.varoriri.render()
        elif isinstance(self.varoriri, str):
            yield "a"


class ObjectList(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rObjectList
    ObjectList	  ::=  	Object ( ',' Object )*
    """
    list_object: List[Object]

    def render(self):
        object_iter = iter(self.list_object)
        first_o = next(object_iter)
        yield from first_o.render()
        for item in object_iter:
            yield ","
            yield from item.render()

    def __hash__(self):
        return hash(tuple(self.list_object))


class Object(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rObject
    Object	  ::=  	GraphNode
    """
    graphnode: GraphNode

    def render(self):
        yield from self.graphnode.render()


class TriplesSameSubjectPath(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rTriplesSameSubjectPath
    TriplesSameSubjectPath	  ::=  	VarOrTerm PropertyListPathNotEmpty | TriplesNodePath PropertyListPath
    """
    content: Tuple[VarOrTerm, PropertyListPathNotEmpty] | Tuple[TriplesNodePath, PropertyListPath]

    def render(self):
        yield from self.content[0].render()
        yield " "
        yield from self.content[1].render()

    def __hash__(self):
        return hash(self.content)

    @classmethod
    def from_spo(cls, subject: Var | IRI | BlankNode, predicate: Var | IRI, object: Var | IRI | BlankNode):
        """
        Convenience method to create a TriplesSameSubjectPath from a subject, predicate, and object.
        Currently supports only Var and IRI types for subject, predicate, and object.
        """
        # Handle subjects
        if isinstance(subject, Var):
            s_vot = VarOrTerm(varorterm=subject)
        elif isinstance(subject, (IRI, BlankNode)):
            s_vot = VarOrTerm(varorterm=GraphTerm(content=subject))
        else:
            raise ValueError("s must be a Var, IRI or BlankNode")

        # Handle predicates
        if isinstance(predicate, Var):
            verb = VerbSimple(var=predicate)
        elif isinstance(predicate, IRI):
            verb = VerbPath(
                path=SG_Path(
                    path_alternative=PathAlternative(
                        sequence_paths=[
                            PathSequence(
                                list_path_elt_or_inverse=[
                                    PathEltOrInverse(
                                        path_elt=PathElt(
                                            path_primary=PathPrimary(
                                                value=predicate,
                                            )
                                        )
                                    )
                                ]
                            )
                        ]
                    )
                )
            )
        else:
            raise ValueError("p must be a Var or IRI")

        # Handle objects
        if isinstance(object, Var):
            o_vot = VarOrTerm(varorterm=object)
        elif isinstance(object, (IRI, BlankNode)):
            o_vot = VarOrTerm(varorterm=GraphTerm(content=object))
        else:
            raise ValueError("o must be a Var, IRI or BlankNode")

        return cls(
            content=(
                s_vot,
                PropertyListPathNotEmpty(
                    first_pair=(
                        verb,
                        ObjectListPath(
                            object_paths=[
                                ObjectPath(
                                    graph_node_path=GraphNodePath(
                                        varorterm_or_triplesnodepath=o_vot
                                    )
                                )
                            ]
                        ),
                    )
                )
            )
        )


class PropertyListPath(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rPropertyListPath
    PropertyListPath	  ::=  	PropertyListPathNotEmpty?
    """
    plpne: Optional[PropertyListPathNotEmpty] = None

    def render(self):
        if self.plpne:
            yield from self.plpne.render()


class PropertyListPathNotEmpty(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rPropertyListPathNotEmpty
    PropertyListPathNotEmpty	  ::=  	( VerbPath | VerbSimple ) ObjectListPath ( ';' ( ( VerbPath | VerbSimple ) ObjectList )? )*
    """
    first_pair: Tuple[VerbPath | VerbSimple, ObjectListPath]
    other_pairs: Optional[List[Tuple[VerbPath | VerbSimple, ObjectList]]] = None

    def render(self):
        yield from self.first_pair[0].render()
        yield " "
        yield from self.first_pair[1].render()
        if self.other_pairs:
            for pair in self.other_pairs:
                yield ";"
                yield from pair[0].render()
                yield " "
                yield from pair[1].render()

    def __hash__(self):
        return hash((self.first_pair, self.other_pairs))


class PropertyList(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rPropertyList
    PropertyList	  ::=  	PropertyListNotEmpty?
    """
    plne: Optional[PropertyListNotEmpty] = None

    def render(self):
        if self.plne:
            yield from self.plne.render()

    def __hash__(self):
        return hash(self.plne)


class ExistsFunc(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rExistsFunc
    ExistsFunc	  ::=  	'EXISTS' GroupGraphPattern
    """
    group_graph_pattern: GroupGraphPattern

    def render(self):
        yield "EXISTS"
        yield from self.group_graph_pattern.render()


class NotExistsFunc(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rNotExistsFunc
    NotExistsFunc	  ::=  	'NOT EXISTS' GroupGraphPattern
    """
    group_graph_pattern: GroupGraphPattern

    def render(self):
        yield "NOT EXISTS"
        yield from self.group_graph_pattern.render()

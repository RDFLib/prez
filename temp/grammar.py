from __future__ import annotations

from typing import List, Union, Optional, Generator

from pydantic import BaseModel, field_validator
from rdflib import URIRef, Variable, BNode, Literal
from rdflib.plugins.sparql import prepareQuery
from rdflib.plugins.sparql.algebra import translateAlgebra

from temp.cql_sparql_reference import cql_sparql_spatial_mapping


class SPARQLGrammarBase(BaseModel):
    indent_level: int = 0

    class Config:
        arbitrary_types_allowed = True

    def __str__(self):
        return "".join(part for part in self.render())

    def __repr__(self):
        return f"{self.__class__.__name__}({self})"

    def render(self):
        raise NotImplementedError("Subclasses must implement this method.")

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


class SimplifiedTriple(SPARQLGrammarBase):
    """A simplified implmementation the triple pattern matches in the SPARQL grammar, to avoid implementing many classes
    such as TriplesSameSubjectPath"""

    subject: Union[URIRef, Variable, BNode]
    predicate: Union[URIRef, Variable]
    object: Union[URIRef, Literal, Variable, BNode]

    def render(self) -> Generator[str, None, None]:
        yield f"\t{self.subject.n3()} {self.predicate.n3()} {self.object.n3()} ."

    def __hash__(self):
        return hash((self.subject, self.predicate, self.object))


class TriplesBlock(SPARQLGrammarBase):
    triples: List[SimplifiedTriple] = []

    def render(self) -> Generator[str, None, None]:
        for i, triple in enumerate(self.triples):
            yield from triple.render()
            if i < len(self.triples) - 1:  # Check if it's not the last triple
                yield "\n"


class InlineDataOneVar(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rInlineDataOneVar
    InlineDataOneVar	  ::=  	Var '{' DataBlockValue* '}'
    """

    variable: Variable
    values: List[Union[URIRef, Literal]]

    def render(self) -> Generator[str, None, None]:
        yield f"{self.variable.n3()} {{ "
        yield " ".join(value.n3() for value in self.values)
        yield " }"


class InlineDataFull(SPARQLGrammarBase):
    """
    https://www.w3.org/TR/sparql11-query/#rInlineDataFull
    ( NIL | '(' Var* ')' ) '{' ( '(' DataBlockValue* ')' | NIL )* '}'
    """

    variables: List[Variable]
    values: List[List[Union[URIRef, Literal]]]

    def render(self) -> Generator[str, None, None]:
        if self.vars:
            yield "("
            yield " ".join(var.n3() for var in self.vars)
            yield ") {"
        else:
            yield "{"

        if self.values_blocks is None:
            yield "()"
        else:
            for values_block in self.values_blocks:
                if values_block:
                    yield "("
                    yield " ".join(value.n3() for value in values_block)
                    yield ")"
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

    content: Union[GroupOrUnionGraphPattern, OptionalGraphPattern, Filter, InlineData]

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

    def add_pattern(self, pattern):
        if not isinstance(pattern, (TriplesBlock, GraphPatternNotTriples)):
            raise TypeError(
                "Pattern must be an instance of TriplesBlock or GraphPatternNotTriples."
            )
        if self.graph_patterns_or_triples_blocks is None:
            self.graph_patterns_or_triples_blocks = []
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
    Simplified model excluding casting of variables (e.g. (?var AS ?alias))
    """

    distinct: Optional[bool] = None
    reduced: Optional[bool] = None
    variables_or_all: Union[List[Variable], str]

    def render(self):
        yield "SELECT"
        if self.distinct:
            yield " DISTINCT"
        elif self.reduced:
            yield " REDUCED"
        if isinstance(self.variables_or_all, str):
            yield " *"
        else:
            for var in self.variables_or_all:
                yield f" {var.n3()}"


class SubSelect(SPARQLGrammarBase):
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
    select_string: str

    @field_validator("select_string")
    def validate_and_transform_select_string(cls, v):
        try:
            return translateAlgebra(prepareQuery(v))
        except Exception as e:
            # Handle exceptions from your translation function here
            raise ValueError(f"Invalid Select Subquery: {e}")

    def render(self):
        yield self.select_string


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
    variable: Variable
    expression: Union[URIRef, str]
    value: Optional[Union[Literal, List[Union[URIRef, Literal]]]] = None

    def render(self) -> Generator[str, None, None]:
        if self.expression in ["<", ">", "<=", ">="]:
            yield f"\n\tFILTER({self.variable.n3()}{self.expression}{self.value.n3()})"
        elif self.expression == "regex":
            yield f"\n\tFILTER regex({self.variable.n3()}, {self.value.n3()})"
        elif self.expression in cql_sparql_spatial_mapping.values():
            yield f"\n\tFILTER({self.expression.n3()}({self.variable.n3()}, {self.value.n3()}))"
        elif self.expression == "NOT IN":
            yield f'\n\tFILTER({self.variable.n3()} NOT IN({", ".join([value.n3() for value in self.value])}))'
        elif self.expression == "ISBLANK":
            yield f"\n\tFILTER(ISBLANK({self.variable.n3()}))"


class Bind(SPARQLGrammarBase):
    """
    An incorrect implemenation of BIND so as to avoid implementing a lot of the Grammar
    This is a simplified implementation that at present ONLY caters to the following kind of bind
    BIND(<expression>{ triple pattern } AS ?var
    Ideally the whole SPARQL Grammar is implemented as per spec and convenience functions are created for common use
    cases

    Bind	  ::=  	'BIND' '(' Expression 'AS' Var ')'
    https://www.w3.org/TR/sparql11-query/#rBind
    """

    expression: str
    triple: SimplifiedTriple
    var: Variable

    def render(self):
        yield f"\n\tBIND({self.expression}{{ {self.triple.render()} }} AS {self.var.n3()})"


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
    var: Variable
    direction: Optional[str] = None

    def render(self):
        if self.direction:
            yield f"{self.direction}({self.var.n3()})"
        else:
            yield self.var.n3()


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
    # group_by: Optional[GroupClause]

    def render(self) -> str:
        if self.order_by:
            yield from self.order_by.render()
        if self.limit_offset:
            if self.order_by:
                yield "\n"
            yield from self.limit_offset.render()


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


# class DescriptionSPARQLQuery(SPARQLGrammarBase):
#     # prolog: Prolog
#     blocks: List[Union[SelectBlock, SPARQLComponent]]
#
#     def render(self) -> Generator[str, None, None]:
#         # yield from self.prolog.render()
#         yield "\n\nCONSTRUCT {\n"
#         for block in self.blocks:
#             if isinstance(block, SelectBlock):
#                 yield "\t" + "\n\t".join(block.extract_triples())
#             else:
#                 yield from block.extract_triples()
#         yield "\n}"
#         # Join the parts produced by the generator into a string and then yield
#         yield "\nWHERE {"
#         for block in self.blocks:
#             yield from block.render()
#         yield "\n}"
#
#     def render(self) -> str:
#         return "".join(part for part in self.render())

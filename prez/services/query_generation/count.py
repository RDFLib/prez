from sparql_grammar import (
    ANON,
    IRI,
    Aggregate,
    Bind,
    BuiltInCall,
    ConstructQuery,
    ConstructTemplate,
    ConstructTriples,
    Expression,
    GroupGraphPattern,
    GroupGraphPatternSub,
    GroupOrUnionGraphPattern,
    LimitOffsetClauses,
    RDFLiteral,
    SelectClause,
    SolutionModifier,
    SubSelect,
    TriplesSameSubject,
    Var,
    WhereClause,
)

from prez.config import settings


def _clause_value(clause) -> int:
    """The integer held by a LimitClause/OffsetClause, or 0 when the clause is absent."""
    if clause is None:
        return 0
    return int(clause.limit.value if hasattr(clause, "limit") else clause.offset.value)


class CountQuery(ConstructQuery):
    """
    Counts focus nodes that can be retrieved for listing queries.
    Default limit is 100 and can be configured in the settings.

    Query is of the form:
    CONSTRUCT {
      []  <https://prez.dev/count> ?count_str
    }
    WHERE {
      {
        SELECT (COUNT(?focus_node) AS ?count)
        WHERE {
          SELECT DISTINCT ?focus_node
          WHERE {
            <<< original where clause >>>
          } LIMIT 101
        }
      }
      BIND(IF(?count = 101, ">100", STR(?count)) AS ?count_str)
    }
    """

    def __init__(self, original_subselect: SubSelect):
        """
        Handles pagination limits by comparing the requested range (offset + limit) against a configured maximum.
        Preserves the original range if it already exceeds the maximum, otherwise defaults to the system-defined limit.
        This limit then has one added so that the UI knows if there is more data available.
        """
        limit_offset = original_subselect.solution_modifier.limit_offset
        current_offset = _clause_value(
            limit_offset.offset_clause if limit_offset else None
        )
        current_limit = _clause_value(
            limit_offset.limit_clause if limit_offset else None
        )
        if (current_offset + current_limit) > settings.listing_count_limit:
            limit = current_offset + current_limit
        else:
            limit = settings.listing_count_limit
        limit_plus_one = limit + 1
        focus_node = Var(value="focus_node")
        count_var = Var(value="count")
        inner_ss = SubSelect(
            select_clause=SelectClause.create(focus_node, distinct=True),
            where_clause=original_subselect.where_clause,
            solution_modifier=SolutionModifier(
                limit_offset=LimitOffsetClauses.create(limit=limit_plus_one)
            ),
            values_clause=original_subselect.values_clause,
        )
        count_expression = Expression.from_primary_expression(
            Aggregate.count(focus_node)
        )
        outer_ss = SubSelect(
            select_clause=SelectClause([(count_expression, count_var)]),
            where_clause=WhereClause(GroupGraphPattern(inner_ss)),
        )
        # BIND(IF(?count = 101, ">100", STR(?count)) AS ?count_str)
        bind = Bind(
            Expression.from_primary_expression(
                BuiltInCall.create(
                    "IF",
                    Expression.compare(count_var, "=", limit_plus_one),
                    Expression.from_primary_expression(RDFLiteral(value=f">{limit}")),
                    Expression.from_primary_expression(
                        BuiltInCall.create("STR", count_var)
                    ),
                )
            ),
            Var(value="count_str"),
        )
        wc = WhereClause(
            GroupGraphPattern(
                GroupGraphPatternSub(
                    [GroupOrUnionGraphPattern([GroupGraphPattern(outer_ss)]), bind]
                )
            )
        )
        construct_template = ConstructTemplate(
            ConstructTriples(
                [
                    TriplesSameSubject.from_spo(
                        ANON(),
                        IRI(value="https://prez.dev/count"),
                        Var(value="count_str"),
                    )
                ]
            )
        )
        super().__init__(
            construct_template=construct_template,
            where_clause=wc,
            solution_modifier=SolutionModifier(),
        )


def startup_count_objects():
    """
    Retrieves hardcoded counts for collections in the repository (Feature Collections, Catalogs etc.)
    """
    return """PREFIX prez: <https://prez.dev/>
                CONSTRUCT { ?collection prez:count ?count }
                WHERE { ?collection prez:count ?count }"""

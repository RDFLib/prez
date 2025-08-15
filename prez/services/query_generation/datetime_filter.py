from datetime import datetime
from typing import List, Optional

from sparql_grammar_pydantic import (
    IRI,
    GraphPatternNotTriples,
    TriplesSameSubjectPath,
    Var,
    PrimaryExpression,
    Filter,
    RDFLiteral,
    TriplesBlock,
    GroupGraphPatternSub,
)

from prez.config import settings
from prez.models.query_params import DateTimeOrUnbounded
from prez.services.query_generation.grammar_helpers import create_filter_exists


def create_temporal_filter_gpnt(dt: datetime, op: str) -> GraphPatternNotTriples:
    if op not in ["=", "<=", ">=", "<", ">", "!="]:
        raise ValueError(f"Invalid operator: {op}")
    return GraphPatternNotTriples(
        content=Filter.filter_relational(
            focus=PrimaryExpression(
                content=Var(value="datetime"),
            ),
            comparators=PrimaryExpression(
                content=RDFLiteral(
                    value=dt.isoformat(),
                    datatype=IRI(value="http://www.w3.org/2001/XMLSchema#dateTime"),
                )
            ),
            operator=op,
        )
    )


def generate_datetime_filter(
    datetime_1: DateTimeOrUnbounded, datetime_2: Optional[DateTimeOrUnbounded]
) -> (List[GraphPatternNotTriples], List[TriplesSameSubjectPath]):
    """
    Generates datetime filter with FILTER EXISTS optimization.
    Returns a single FILTER EXISTS pattern wrapping all datetime patterns.
    """
    # Create patterns to be wrapped in FILTER EXISTS
    combined_patterns = GroupGraphPatternSub()
    
    # Add temporal triple
    combined_patterns.add_pattern(
        TriplesBlock(
            triples=TriplesSameSubjectPath.from_spo(
                subject=Var(value="focus_node"),
                predicate=IRI(value=settings.temporal_predicate),
                object=Var(value="datetime"),
            )
        )
    )

    # Add temporal filter conditions
    if datetime_1 is None and datetime_2 is None:
        # Case: No datetime filter - just return the triple pattern in FILTER EXISTS
        pass
    elif isinstance(datetime_1, datetime) and datetime_2 is None:
        # Case 1: Single date-time
        # Example: "2018-02-12T23:20:50Z"
        op = "="
        combined_patterns.add_pattern(create_temporal_filter_gpnt(datetime_1, op))
    elif datetime_1 == ".." and isinstance(datetime_2, datetime):
        # Case 2: Half-bounded interval with open start
        # Examples: "../2018-03-18T12:31:12Z" or "/2018-03-18T12:31:12Z"
        op = "<="
        combined_patterns.add_pattern(create_temporal_filter_gpnt(datetime_2, op))
    elif datetime_2 == ".." and isinstance(datetime_1, datetime):
        # Case 3: Half-bounded interval with open end
        # Examples: "2018-02-12T00:00:00Z/.." or "2018-02-12T00:00:00Z/"
        op = ">="
        combined_patterns.add_pattern(create_temporal_filter_gpnt(datetime_1, op))
    elif isinstance(datetime_1, datetime) and isinstance(datetime_2, datetime):
        # Case 4: Fully bounded interval
        # Example: "2018-02-12T00:00:00Z/2018-03-18T12:31:12Z"
        dt_1_op = ">="
        dt_2_op = "<="
        combined_patterns.add_pattern(create_temporal_filter_gpnt(datetime_1, dt_1_op))
        combined_patterns.add_pattern(create_temporal_filter_gpnt(datetime_2, dt_2_op))
    else:
        raise ValueError(
            f"Invalid datetime format, datetime_1: {datetime_1}, datetime_2: {datetime_2}"
        )
    
    # Wrap all patterns in FILTER EXISTS
    filter_exists_gpnt = create_filter_exists(combined_patterns)
    
    return [filter_exists_gpnt], []

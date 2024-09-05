from datetime import datetime
from typing import List, Optional
from prez.config import settings

from sparql_grammar_pydantic import GraphPatternNotTriples, TriplesSameSubjectPath, Filter, PrimaryExpression, \
    Var, IRI, RDFLiteral

from prez.models.query_params import DateTimeOrUnbounded
from prez.services.query_generation.cql import create_temporal_filter_gpnt


def generate_datetime_filter(datetime_1: DateTimeOrUnbounded, datetime_2: Optional[DateTimeOrUnbounded]) -> (
        GraphPatternNotTriples, List[TriplesSameSubjectPath]):
    # tssp
    tssp_list = [
        TriplesSameSubjectPath.from_spo(
            subject=Var(value="focus_node"),
            predicate=IRI(value=settings.temporal_predicate),
            object=Var(value="datetime"),
        )
    ]

    # gpnt
    filter_gpnts = []
    if datetime_1 is None and datetime_2 is None:
        # Case: No datetime filter
        pass
    elif isinstance(datetime_1, datetime) and datetime_2 is None:
        # Case 1: Single date-time
        # Example: "2018-02-12T23:20:50Z"
        op = "="
        filter_gpnts.append(create_temporal_filter_gpnt(datetime_1, op))
    elif datetime_1 == ".." and isinstance(datetime_2, datetime):
        # Case 2: Half-bounded interval with open start
        # Examples: "../2018-03-18T12:31:12Z" or "/2018-03-18T12:31:12Z"
        op = "<="
        filter_gpnts.append(create_temporal_filter_gpnt(datetime_2, op))
    elif datetime_2 == ".." and isinstance(datetime_1, datetime):
        # Case 3: Half-bounded interval with open end
        # Examples: "2018-02-12T00:00:00Z/.." or "2018-02-12T00:00:00Z/"
        op = ">="
        filter_gpnts.append(create_temporal_filter_gpnt(datetime_1, op))
    elif isinstance(datetime_1, datetime) and isinstance(datetime_2, datetime):
        # Case 4: Fully bounded interval
        # Example: "2018-02-12T00:00:00Z/2018-03-18T12:31:12Z"
        dt_1_op = ">="
        dt_2_op = "<="
        filter_gpnts.append(create_temporal_filter_gpnt(datetime_1, dt_1_op))
        filter_gpnts.append(create_temporal_filter_gpnt(datetime_2, dt_2_op))
    else:
        raise ValueError(f"Invalid datetime format, datetime_1: {datetime_1}, datetime_2: {datetime_2}")
    return filter_gpnts, tssp_list




import json
from pathlib import Path

import pytest

from prez.services.query_generation.cql import CQLParser

cql_time_filenames = [
    "example20.json",  # t_before instant
    "example21.json",  # t_after instant
    "example22.json",  # t_during
    "example53.json",  # t_after instant
    "example54.json",  # t_before instant
    "example55.json",  # t_contains interval
    "example56.json",  # t_disjoint interval
    "example57.json",  # t_during
    "clause7_13.json",  # t_during
    # "clause7_17.json",  # t_during
    "additional_temporal_disjoint_instant.json",
    "example58.json",  # t_equals instant
    "example59.json",  # t_finishedBy interval
    "example60.json",  # t_finishes interval
    "additional_temporal_during_intervals.json",  # t_before interval
    "example61.json",  # t_intersects interval
    "example62.json",  # t_meets interval
    "example63.json",  # t_metBy interval
    "example64.json",  # t_overlappedBy interval
    "example65.json",  # t_overlaps interval
    "example66.json",  # t_startedBy interval
    "example67.json",  # t_starts interval
    "clause7_12.json",  # t_intersects
]

cql_time_generated_queries = [
    Path(name).with_suffix(".rq") for name in cql_time_filenames
]


@pytest.mark.parametrize(
    "cql_json_filename, output_query_filename",
    [i for i in (zip(cql_time_filenames, cql_time_generated_queries))],
)
def test_time_funcs(cql_json_filename, output_query_filename):
    cql_json_path = (
        Path(__file__).parent.parent / f"test_data/cql/input/{cql_json_filename}"
    )
    cql_json = json.loads(cql_json_path.read_text())
    reference_query = (
        Path(__file__).parent.parent
        / f"test_data/cql/expected_generated_queries/{output_query_filename}"
    ).read_text()
    cql_parser = CQLParser(cql_json=cql_json)
    cql_parser.parse()
    if not cql_parser.query_str == reference_query:
        print(f"\n{cql_parser.query_str}")
    assert cql_parser.query_str == reference_query

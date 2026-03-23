import json


LUCENE_PREFIX = "urn:jena:lucene:index#"


def _sparql_string_literal(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _compact_json(value: dict | list[str]) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def generate_cql_lucene_json_sparql(
    lucene_index_name: str,
    q: str | None,
    filter_json: dict | None,
    facets: list[str] | None,
    limit: int,
    offset: int,
) -> str:
    query_string = q if q is not None else "*"

    lucene_query_args = [
        _sparql_string_literal(lucene_index_name),
        _sparql_string_literal(query_string),
    ]
    if filter_json is not None:
        lucene_query_args.append(_sparql_string_literal(_compact_json(filter_json)))
    lucene_query_args.append(str(limit))
    lucene_query_args_string = " ".join(lucene_query_args)

    query_branch = (
        "{\n"
        f"  (?focus_node ?score ?literal ?graph ?property) luc:query ( {lucene_query_args_string} ) .\n"
        "}"
    )

    where_branch = query_branch
    select_vars = [
        "?focus_node",
        "?score",
        "?literal",
        "?graph",
        "?property",
    ]

    if facets:
        lucene_facet_args = [
            _sparql_string_literal(lucene_index_name),
            _sparql_string_literal(query_string),
            _sparql_string_literal(_compact_json(facets)),
        ]
        if filter_json is not None:
            lucene_facet_args.append(_sparql_string_literal(_compact_json(filter_json)))
        lucene_facet_args.append(str(limit))
        lucene_facet_args_string = " ".join(lucene_facet_args)
        facet_branch = (
            "{\n"
            f"  (?facet_field ?facet_value ?facet_count) luc:facet ( {lucene_facet_args_string} ) .\n"
            "}"
        )
        where_branch = f"{query_branch}\nUNION\n{facet_branch}"
        select_vars.extend(["?facet_field", "?facet_value", "?facet_count"])

    select_vars_string = " ".join(select_vars)
    return (
        f"PREFIX luc: <{LUCENE_PREFIX}>\n"
        f"SELECT {select_vars_string}\n"
        "WHERE {\n"
        f"{where_branch}\n"
        "}\n"
        f"LIMIT {limit}\n"
        f"OFFSET {offset}"
    )

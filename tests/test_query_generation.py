"""Test to print generated SPARQL query for debugging"""
import pytest
from rdflib import URIRef
from prez.services.connegp_service import NegotiatedPMTs


@pytest.mark.asyncio
async def test_print_generated_query(client_no_override):
    """Print the generated SPARQL query to debug constraint_distance issue"""
    system_store = client_no_override.app.state._state.get("pyoxi_system_store")
    from prez.repositories import PyoxigraphRepo
    system_repo = PyoxigraphRepo(system_store)

    pmts = NegotiatedPMTs(
        headers={},
        params={},
        classes=[URIRef("http://www.w3.org/ns/dcat#Catalog")],
        listing=False,
        system_repo=system_repo,
    )

    query = pmts._compose_select_query()
    print("\n" + "="*80)
    print("GENERATED SPARQL QUERY:")
    print("="*80)
    print(query)
    print("="*80 + "\n")

    # Actually run the query
    response = await pmts._do_query(query)
    results = response[1][0][1]  # Extract results

    print("\n" + "="*80)
    print("QUERY RESULTS:")
    print("="*80)
    if results:
        print(f"Total results: {len(results)}")
        for i, item in enumerate(results):  # Print ALL results
            print(f"\nResult {i+1}: {item['title']['value']}")
            print(f"  Profile: {item['profile']['value']}")
            print(f"  constraint_distance: {item['constraint_distance']['value']}")
            print(f"  def_profile: {item['def_profile']['value']}")
            print(f"  alt_prof: {item['alt_prof']['value']}")
    else:
        print("NO RESULTS RETURNED")
    print("="*80 + "\n")

    assert True  # Just print, don't fail

import asyncio
import statistics
import time
from threading import Lock
from typing import List, Dict

import httpx
from fastapi.concurrency import run_in_threadpool
from httpx import BasicAuth
from pyoxigraph import Store, Quad, RdfFormat, parse

TEST_ENDPOINT = "https://query.wikidata.org/sparql"
SPARQL_USERNAME = ""
SPARQL_PASSWORD = ""

# This map is copied from prez.services.connegp_service to avoid circular import
OXIGRAPH_SERIALIZER_TYPES_MAP = {
    "text/turtle": RdfFormat.TURTLE,
    "application/n-triples": RdfFormat.N_TRIPLES,
    "application/n-quads": RdfFormat.N_QUADS,
    "application/rdf+xml": RdfFormat.RDF_XML,
}

# --- Synchronous Worker Functions (to be run in thread pool) ---

def _sync_get_quad_list(data: bytes) -> List[Quad]:
    """Parses data using pyoxigraph.parse and returns a list of Quads."""
    if not data:
        return []
    quads = parse(data, format=RdfFormat.N_TRIPLES)
    return list(quads)

def _sync_populate_store_with_bulk_load(data: bytes, store: Store, lock: Lock):
    """Loads raw RDF data into a store using store.bulk_load within a thread lock."""
    if not data:
        return
    # The lock is necessary as multiple threads are writing to the same store instance.
    with lock:
        store.bulk_load(data, RdfFormat.N_TRIPLES)

# --- Asynchronous Methods (mimicking the repository pattern) ---

async def get_quad_list_from_data(mock_data: bytes) -> List[Quad]:
    """Parses data and returns a list of quads from a thread pool."""
    return await run_in_threadpool(_sync_get_quad_list, mock_data)

async def query_and_populate_store(
    mock_data: bytes, store: Store, locks: Dict[int, Lock]
):
    """Populates a store in a thread pool from mock data using bulk_load."""
    lock = locks.setdefault(id(store), Lock())
    await run_in_threadpool(_sync_populate_store_with_bulk_load, mock_data, store, lock)

# --- Benchmark Execution ---

async def run_quads_benchmark(mock_data_slices):
    """Runs the benchmark for the 'list of quads' method, followed by store population."""
    start_time = time.time()
    tasks = [get_quad_list_from_data(data_slice) for data_slice in mock_data_slices]
    list_of_quad_lists = await asyncio.gather(*tasks)

    # Aggregate all quads into a single "global" list.
    rdf_results = []
    for quad_list in list_of_quad_lists:
        rdf_results.extend(quad_list)

    # Create the final store and populate it with one bulk_extend call.
    final_store = Store()
    final_store.bulk_extend(rdf_results)

    end_time = time.time()
    return end_time - start_time

async def run_store_benchmark(mock_data_slices):
    """Runs the benchmark for the 'bulk_load to store' method."""
    start_time = time.time()
    store = Store()
    locks = {}
    tasks = [
        query_and_populate_store(data_slice, store, locks) for data_slice in mock_data_slices
    ]
    await asyncio.gather(*tasks)
    end_time = time.time()
    return end_time - start_time

async def fetch_mock_data():
    """Fetches a large dataset once to be used as a mock response source."""
    print("--- Fetching mock data from SPARQL endpoint... ---")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                TEST_ENDPOINT,
                headers={"Accept": "application/n-triples", "Content-Type": "application/sparql-query"},
                data="CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o } LIMIT 30000",
                timeout=60.0,
                auth=BasicAuth(SPARQL_USERNAME, SPARQL_PASSWORD)
            )
            response.raise_for_status()
            print("--- Mock data fetched successfully. ---")
            return (await response.aread()).decode('utf-8').splitlines()
        except httpx.HTTPStatusError as e:
            print(f"Fatal: Could not fetch mock data. Error: {e.response.status_code}")
            return None

async def main():
    """Main function to run the benchmark."""
    mock_data_lines = await fetch_mock_data()
    if not mock_data_lines:
        return

    limits = [10, 100, 1000, 10000, 30000]
    runs = 3
    run_results = []

    for i in range(runs):
        print(f"\n--- RUN {i+1}/{runs} ---")
        run_data = {"quads": {}, "stores": {}}

        # Run all quads tests
        print("\nBenchmarking 'Quads List' (pyoxigraph.parse -> list -> store.bulk_extend)...")
        for limit in limits:
            mock_data_slices = [
                "\n".join(mock_data_lines[j*limit:(j+1)*limit]).encode('utf-8') for j in range(3)
            ]
            quads_time = await run_quads_benchmark(mock_data_slices)
            run_data["quads"][limit] = quads_time
            print(f"  LIMIT {limit}: {quads_time:.3f}s")

        # Run all store tests
        print("\nBenchmarking 'Single Store' (store.bulk_load)...")
        for limit in limits:
            mock_data_slices = [
                "\n".join(mock_data_lines[j*limit:(j+1)*limit]).encode('utf-8') for j in range(3)
            ]
            store_time = await run_store_benchmark(mock_data_slices)
            run_data["stores"][limit] = store_time
            print(f"  LIMIT {limit}: {store_time:.3f}s")
        
        run_results.append(run_data)

    # --- Print Results Table ---
    print("\n\n--- BENCHMARK RESULTS (in seconds, CPU/parsing time only) ---")
    
    # Header
    header = f"| {'Test Run':<20} |"
    for limit in limits:
        header += f" {limit:<10} |"
    print(header)
    print(f"|{'':-<22}|" + "-----------|" * len(limits))

    # Rows for each run
    for i in range(runs):
        quads_row = f"| {'Run ' + str(i+1) + ' - Quads':<20} |"
        for limit in limits:
            time_val = run_results[i]["quads"][limit]
            quads_row += f" {time_val:<10.3f} |"
        print(quads_row)

        stores_row = f"| {'Run ' + str(i+1) + ' - Stores':<20} |"
        for limit in limits:
            time_val = run_results[i]["stores"][limit]
            stores_row += f" {time_val:<10.3f} |"
        print(stores_row)

    # Separator
    print(f"|{'':-<22}|" + "-----------|" * len(limits))

    # Average rows
    avg_quads_row = f"| {'Average - Quads':<20} |"
    for limit in limits:
        avg_time = statistics.mean([run_results[i]["quads"][limit] for i in range(runs)])
        avg_quads_row += f" {avg_time:<10.3f} |"
    print(avg_quads_row)

    avg_stores_row = f"| {'Average - Stores':<20} |"
    for limit in limits:
        avg_time = statistics.mean([run_results[i]["stores"][limit] for i in range(runs)])
        avg_stores_row += f" {avg_time:<10.3f} |"
    print(avg_stores_row)


if __name__ == "__main__":
    asyncio.run(main())

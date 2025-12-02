"""Tests for SPARQL endpoint error passthrough functionality."""

import pytest
from unittest.mock import AsyncMock, Mock, patch
import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from prez.repositories.remote_sparql import RemoteSparqlRepo
from prez.services.exception_catchers import catch_httpx_error
from prez.config import settings
from starlette.requests import Request


@pytest.fixture
def mock_async_client():
    """Mock httpx AsyncClient for testing."""
    return Mock(spec=httpx.AsyncClient)


@pytest.fixture
def remote_repo(mock_async_client):
    """Create RemoteSparqlRepo with mocked client."""
    with patch.object(settings, "sparql_endpoint", "http://test-sparql-endpoint.com"):
        return RemoteSparqlRepo(mock_async_client)


class TestSparqlErrorPassthrough:
    """Test that SPARQL endpoint errors are passed through correctly."""

    @pytest.mark.asyncio
    async def test_send_query_with_400_error(self, remote_repo, mock_async_client):
        """Test that 400 errors from SPARQL endpoint are raised as HTTPStatusError."""
        # Setup mock response with 400 status code
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 400
        mock_response.text = "Invalid SPARQL query syntax"

        # Mock aread to make response.text available
        async def mock_aread():
            return b"Invalid SPARQL query syntax"

        mock_response.aread = mock_aread

        # Make raise_for_status raise HTTPStatusError
        def raise_status_error():
            raise httpx.HTTPStatusError(
                "Client error '400 Bad Request' for url",
                request=Mock(),
                response=mock_response
            )

        mock_response.raise_for_status = raise_status_error
        mock_async_client.build_request.return_value = Mock()
        mock_async_client.send.return_value = mock_response

        # Execute and verify HTTPStatusError is raised
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await remote_repo._send_query("INVALID QUERY")

        assert exc_info.value.response.status_code == 400
        assert exc_info.value.response.text == "Invalid SPARQL query syntax"

    @pytest.mark.asyncio
    async def test_send_query_with_500_error(self, remote_repo, mock_async_client):
        """Test that 500 errors from SPARQL endpoint are raised as HTTPStatusError."""
        # Setup mock response with 500 status code
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.text = "Internal SPARQL server error: query execution failed"

        # Mock aread to make response.text available
        async def mock_aread():
            return b"Internal SPARQL server error: query execution failed"

        mock_response.aread = mock_aread

        # Make raise_for_status raise HTTPStatusError
        def raise_status_error():
            raise httpx.HTTPStatusError(
                "Server error '500 Internal Server Error' for url",
                request=Mock(),
                response=mock_response
            )

        mock_response.raise_for_status = raise_status_error
        mock_async_client.build_request.return_value = Mock()
        mock_async_client.send.return_value = mock_response

        # Execute and verify HTTPStatusError is raised
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await remote_repo._send_query("SELECT * WHERE { ?s ?p ?o }")

        assert exc_info.value.response.status_code == 500
        assert "Internal SPARQL server error" in exc_info.value.response.text

    @pytest.mark.asyncio
    async def test_exception_handler_passes_through_status_code(self):
        """Test that catch_httpx_error handler passes through the SPARQL endpoint status code."""
        # Create mock request
        mock_request = Mock(spec=Request)

        # Create mock response with error
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 400
        mock_response.text = "Malformed SPARQL query"

        # Create HTTPStatusError
        exc = httpx.HTTPStatusError(
            "Client error '400 Bad Request' for url",
            request=Mock(),
            response=mock_response
        )

        # Call the exception handler
        response = await catch_httpx_error(mock_request, exc)

        # Verify response has correct status code and error details
        assert response.status_code == 400
        assert response.body is not None

        # Parse response body
        import json
        body = json.loads(response.body)
        assert body["error"] == "SPARQL_ENDPOINT_ERROR"
        assert "Malformed SPARQL query" in body["detail"]

    @pytest.mark.asyncio
    async def test_exception_handler_passes_through_500_status(self):
        """Test that catch_httpx_error handler passes through 500 status code."""
        mock_request = Mock(spec=Request)

        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.text = "Database connection failed"

        exc = httpx.HTTPStatusError(
            "Server error '500 Internal Server Error' for url",
            request=Mock(),
            response=mock_response
        )

        response = await catch_httpx_error(mock_request, exc)

        assert response.status_code == 500

        import json
        body = json.loads(response.body)
        assert body["error"] == "SPARQL_ENDPOINT_ERROR"
        assert "Database connection failed" in body["detail"]

    @pytest.mark.asyncio
    async def test_exception_handler_still_handles_timeout(self):
        """Test that catch_httpx_error still properly handles timeout exceptions."""
        mock_request = Mock(spec=Request)

        exc = httpx.TimeoutException("Request timed out after 30 seconds")

        response = await catch_httpx_error(mock_request, exc)

        assert response.status_code == 504

        import json
        body = json.loads(response.body)
        assert body["error"] == "SPARQL_TIMEOUT_ERROR"
        assert "timed out" in body["detail"]

    @pytest.mark.asyncio
    async def test_exception_handler_still_handles_connect_error(self):
        """Test that catch_httpx_error still properly handles connection errors."""
        mock_request = Mock(spec=Request)

        exc = httpx.ConnectError("Connection refused")

        response = await catch_httpx_error(mock_request, exc)

        assert response.status_code == 503

        import json
        body = json.loads(response.body)
        assert body["error"] == "SPARQL_CONNECTION_ERROR"
        assert "Connection refused" in body["detail"]

    @pytest.mark.asyncio
    async def test_send_query_success_does_not_raise(self, remote_repo, mock_async_client):
        """Test that successful queries don't raise exceptions."""
        # Setup successful mock response
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()  # Does nothing on success

        async def mock_aread():
            return b"<rdf>...</rdf>"

        mock_response.aread = mock_aread

        mock_async_client.build_request.return_value = Mock()
        mock_async_client.send.return_value = mock_response

        # Should not raise any exception
        result = await remote_repo._send_query("SELECT * WHERE { ?s ?p ?o }")
        assert result == mock_response
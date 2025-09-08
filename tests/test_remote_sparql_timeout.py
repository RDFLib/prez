import pytest
from unittest.mock import AsyncMock, Mock, patch
import httpx
from prez.repositories.remote_sparql import RemoteSparqlRepo
from prez.config import settings


@pytest.fixture
def mock_async_client():
    """Mock httpx AsyncClient for testing."""
    return Mock(spec=httpx.AsyncClient)


@pytest.fixture
def remote_repo(mock_async_client):
    """Create RemoteSparqlRepo with mocked client."""
    with patch.object(settings, 'sparql_endpoint', 'http://test-sparql-endpoint.com'):
        return RemoteSparqlRepo(mock_async_client)


class TestRemoteSparqlTimeout:
    """Test timeout parameter functionality in RemoteSparqlRepo."""

    @pytest.mark.asyncio
    async def test_send_query_with_timeout_param(self, remote_repo, mock_async_client):
        """Test that timeout parameter is added to form data when configured."""
        # Setup
        mock_response = Mock(spec=httpx.Response)
        mock_async_client.build_request.return_value = Mock()
        mock_async_client.send.return_value = mock_response
        
        with patch.object(settings, 'sparql_timeout_param_name', 'timeout'), \
             patch.object(settings, 'sparql_timeout', 30):
            
            # Execute
            await remote_repo._send_query("SELECT * WHERE { ?s ?p ?o }")
            
            # Verify
            mock_async_client.build_request.assert_called_once()
            call_args = mock_async_client.build_request.call_args
            
            # Check that timeout parameter was added to data
            assert call_args[1]['data']['query'] == "SELECT * WHERE { ?s ?p ?o }"
            assert call_args[1]['data']['timeout'] == "30"

    @pytest.mark.asyncio
    async def test_send_query_without_timeout_param(self, remote_repo, mock_async_client):
        """Test that no timeout parameter is added when not configured."""
        # Setup
        mock_response = Mock(spec=httpx.Response)
        mock_async_client.build_request.return_value = Mock()
        mock_async_client.send.return_value = mock_response
        
        with patch.object(settings, 'sparql_timeout_param_name', None):
            
            # Execute
            await remote_repo._send_query("SELECT * WHERE { ?s ?p ?o }")
            
            # Verify
            call_args = mock_async_client.build_request.call_args
            
            # Check that only query is in data, no timeout parameter
            assert call_args[1]['data'] == {'query': "SELECT * WHERE { ?s ?p ?o }"}

    @pytest.mark.asyncio
    async def test_sparql_get_with_timeout_param(self, remote_repo, mock_async_client):
        """Test that timeout parameter is added to GET query string."""
        # Setup
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status.return_value = None
        mock_async_client.send.return_value = mock_response
        
        with patch.object(settings, 'sparql_timeout_param_name', 'maxExecutionTime'), \
             patch.object(settings, 'sparql_timeout', 60), \
             patch.object(settings, 'sparql_endpoint', 'http://test-endpoint.com'):
            
            # Execute
            await remote_repo.sparql("SELECT * WHERE { ?s ?p ?o }", [], method="GET")
            
            # Verify
            mock_async_client.send.assert_called_once()
            request = mock_async_client.send.call_args[0][0]
            
            # Check that timeout parameter was added to URL
            assert 'maxExecutionTime=60' in str(request.url)
            assert 'query=' in str(request.url)

    @pytest.mark.asyncio
    async def test_sparql_post_with_timeout_param(self, remote_repo, mock_async_client):
        """Test that timeout parameter is added to POST form data."""
        # Setup
        mock_response = Mock(spec=httpx.Response)
        mock_response.raise_for_status.return_value = None
        mock_async_client.send.return_value = mock_response
        
        with patch.object(settings, 'sparql_timeout_param_name', 'timeout'), \
             patch.object(settings, 'sparql_timeout', 45), \
             patch.object(settings, 'sparql_endpoint', 'http://test-endpoint.com'):
            
            # Execute
            await remote_repo.sparql("SELECT * WHERE { ?s ?p ?o }", [], method="POST")
            
            # Verify
            request = mock_async_client.send.call_args[0][0]
            
            # Check that timeout parameter was added to form data
            content = request.content.decode('utf-8')
            assert 'timeout=45' in content
            assert 'query=' in content

    @pytest.mark.asyncio
    async def test_different_timeout_param_names(self, remote_repo, mock_async_client):
        """Test various timeout parameter names work correctly."""
        mock_response = Mock(spec=httpx.Response)
        mock_async_client.build_request.return_value = Mock()
        mock_async_client.send.return_value = mock_response
        
        timeout_params = ['timeout', 'maxExecutionTime', 'queryTimeout', 'timeoutMs']
        
        for param_name in timeout_params:
            with patch.object(settings, 'sparql_timeout_param_name', param_name), \
                 patch.object(settings, 'sparql_timeout', 120):
                
                await remote_repo._send_query("SELECT * WHERE { ?s ?p ?o }")
                
                call_args = mock_async_client.build_request.call_args
                assert call_args[1]['data'][param_name] == "120"

    @pytest.mark.asyncio  
    async def test_timeout_error_handling_with_nice_message(self, remote_repo, mock_async_client):
        """Test that timeout errors include helpful context about the timeout configuration."""
        # Setup timeout exception
        timeout_error = httpx.TimeoutException("Request timed out")
        mock_async_client.send.side_effect = timeout_error
        mock_async_client.build_request.return_value = Mock()
        
        with patch.object(settings, 'sparql_timeout_param_name', 'timeout'), \
             patch.object(settings, 'sparql_timeout', 30):
            
            # Execute and verify exception with enhanced message
            with pytest.raises(httpx.TimeoutException) as exc_info:
                await remote_repo._send_query("SELECT * WHERE { ?s ?p ?o }")
            
            # This should fail initially because we haven't added error handling yet
            error_message = str(exc_info.value)
            assert "30 seconds" in error_message
            assert "timeout=30" in error_message
            assert "remote endpoint" in error_message

    @pytest.mark.asyncio  
    async def test_timeout_error_without_param_name(self, remote_repo, mock_async_client):
        """Test timeout error message when no param name is configured."""
        timeout_error = httpx.TimeoutException("Request timed out")
        mock_async_client.send.side_effect = timeout_error  
        mock_async_client.build_request.return_value = Mock()
        
        with patch.object(settings, 'sparql_timeout_param_name', None), \
             patch.object(settings, 'sparql_timeout', 45):
            
            with pytest.raises(httpx.TimeoutException) as exc_info:
                await remote_repo._send_query("SELECT * WHERE { ?s ?p ?o }")
            
            error_message = str(exc_info.value)
            assert "45 seconds" in error_message
            # Should NOT mention remote endpoint since no param is configured
            assert "remote endpoint" not in error_message
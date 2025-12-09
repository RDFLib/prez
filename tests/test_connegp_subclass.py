"""
Tests for profile constraint subclass matching functionality.

These tests verify that profiles can match resources whose class is a subclass
of the constrained class, with configurable distance limits.
"""
import os
import pytest
from rdflib import URIRef

from prez.repositories import PyoxigraphRepo
from prez.services.connegp_service import NegotiatedPMTs


@pytest.mark.parametrize(
    "distance_config, resource_class, expected_profile_title, description",
    [
        # Distance = 0 (exact match only)
        (0, "http://example.org/test/BigCat", "BigCat Profile", "Exact match with distance=0"),
        (0, "http://example.org/test/Cat", "Cat Profile", "Exact match with distance=0"),
        (0, "http://example.org/test/Mammal", None, "No exact match exists for Mammal with distance=0"),

        # Distance = 1 (single hop - default)
        (1, "http://example.org/test/BigCat", "BigCat Profile", "Exact match wins over 1-hop superclass"),
        (1, "http://example.org/test/Cat", "Cat Profile", "Exact match wins over 1-hop superclass (Animal)"),
        (1, "http://example.org/test/Mammal", "Animal Profile", "1-hop superclass match (Mammal->Animal)"),

        # Distance = 2 (two hops)
        (2, "http://example.org/test/BigCat", "BigCat Profile", "Exact match wins with distance=2"),
        (2, "http://example.org/test/Cat", "Cat Profile", "Exact match wins with distance=2"),
        (2, "http://example.org/test/Mammal", "Animal Profile", "1-hop wins over 2-hop"),

        # Distance = -1 (unlimited - transitive closure)
        (-1, "http://example.org/test/BigCat", "BigCat Profile", "Exact match wins with unlimited distance"),
        (-1, "http://example.org/test/Cat", "Cat Profile", "Exact match wins with unlimited distance"),
        (-1, "http://example.org/test/Mammal", "Animal Profile", "Ancestor match with unlimited distance"),
    ],
)
@pytest.mark.asyncio
async def test_profile_subclass_matching(
    distance_config,
    resource_class,
    expected_profile_title,
    description,
    client_no_override,
    monkeypatch
):
    """
    Test profile matching with different constraint distance configurations.

    This test verifies that:
    1. Exact matches always take priority over superclass matches
    2. Closer superclass matches beat more distant ones
    3. Configuration via environment variable works correctly
    4. distance=0 reverts to exact-match-only behavior
    """
    # Set the configuration via environment variable
    monkeypatch.setenv("PROFILE_CONSTRAINT_MAX_DISTANCE", str(distance_config))

    # Reload settings to pick up new environment variable
    from prez import config
    # Force pydantic to reload from env vars
    config.settings = config.Settings()

    # Verify config was set correctly
    assert config.settings.profile_constraint_max_distance == distance_config, \
        f"Config not set correctly: expected {distance_config}, got {config.settings.profile_constraint_max_distance}"

    # Get system store and repo
    system_store = client_no_override.app.state._state.get("pyoxi_system_store")
    system_repo = PyoxigraphRepo(system_store)

    # Create NegotiatedPMTs instance for the resource class
    pmts = NegotiatedPMTs(
        headers={},
        params={},
        classes=[URIRef(resource_class)],
        listing=False,  # Object endpoint (not listing)
        system_repo=system_repo,
    )

    # Run the profile matching
    await pmts.setup()

    # Assert the expected profile was selected
    if expected_profile_title is None:
        # Should fall back to open-object profile when no match exists
        assert pmts.selected["profile"] == URIRef("https://prez.dev/profile/open-object"), \
            f"{description}: Expected fallback to open-object profile"
    else:
        assert pmts.selected["title"] == expected_profile_title, \
            f"{description}: Expected '{expected_profile_title}', got '{pmts.selected.get('title')}'"


@pytest.mark.asyncio
async def test_exact_match_priority_over_superclass(client_no_override, monkeypatch):
    """
    Test that exact match (constraint_distance=0) always beats superclass match (constraint_distance=1).

    BigCat resource should match:
    - BigCatProfile (exact, distance=0) ✓ WINNER
    - CatProfile (1-hop parent, distance=1)
    - AnimalProfile (2-hop parent, distance=2)

    The exact match should always win regardless of other factors.
    """
    monkeypatch.setenv("PROFILE_CONSTRAINT_MAX_DISTANCE", "2")
    from prez import config
    config.settings = config.Settings()

    system_store = client_no_override.app.state._state.get("pyoxi_system_store")
    system_repo = PyoxigraphRepo(system_store)

    pmts = NegotiatedPMTs(
        headers={},
        params={},
        classes=[URIRef("http://example.org/test/BigCat")],
        listing=False,
        system_repo=system_repo,
    )

    await pmts.setup()

    # BigCat should match BigCatProfile (exact) not CatProfile (1-hop) or AnimalProfile (2-hop)
    assert pmts.selected["title"] == "BigCat Profile", \
        "Exact match should beat superclass matches"


@pytest.mark.asyncio
async def test_superclass_match_when_no_exact_match(client_no_override, monkeypatch):
    """
    Test that superclass profile matches when no exact match exists.

    Mammal resource has no MammalProfile, so should match:
    - AnimalProfile (1-hop parent, distance=1) ✓ WINNER
    """
    monkeypatch.setenv("PROFILE_CONSTRAINT_MAX_DISTANCE", "1")
    from prez import config
    config.settings = config.Settings()

    system_store = client_no_override.app.state._state.get("pyoxi_system_store")
    system_repo = PyoxigraphRepo(system_store)

    pmts = NegotiatedPMTs(
        headers={},
        params={},
        classes=[URIRef("http://example.org/test/Mammal")],
        listing=False,
        system_repo=system_repo,
    )

    await pmts.setup()

    # Mammal should match AnimalProfile (1-hop superclass)
    assert pmts.selected["title"] == "Animal Profile", \
        "Should match 1-hop superclass when no exact match exists"


@pytest.mark.asyncio
async def test_distance_zero_exact_match_only(client_no_override, monkeypatch):
    """
    Test that distance=0 enforces exact-match-only behavior (original behavior).

    With distance=0:
    - BigCat matches BigCatProfile ✓
    - Cat matches CatProfile ✓
    - Mammal matches nothing (no MammalProfile exists) ✓
    """
    monkeypatch.setenv("PROFILE_CONSTRAINT_MAX_DISTANCE", "0")
    from prez import config
    config.settings = config.Settings()

    assert config.settings.profile_constraint_max_distance == 0

    system_store = client_no_override.app.state._state.get("pyoxi_system_store")
    system_repo = PyoxigraphRepo(system_store)

    # Test 1: Mammal should NOT match AnimalProfile (no superclass matching)
    pmts = NegotiatedPMTs(
        headers={},
        params={},
        classes=[URIRef("http://example.org/test/Mammal")],
        listing=False,
        system_repo=system_repo,
    )
    await pmts.setup()

    # Should fall back to open-object profile
    assert pmts.selected["profile"] == URIRef("https://prez.dev/profile/open-object"), \
        "With distance=0, Mammal should not match AnimalProfile"

    # Test 2: Cat SHOULD match CatProfile (exact match)
    pmts2 = NegotiatedPMTs(
        headers={},
        params={},
        classes=[URIRef("http://example.org/test/Cat")],
        listing=False,
        system_repo=system_repo,
    )
    await pmts2.setup()

    assert pmts2.selected["title"] == "Cat Profile", \
        "With distance=0, Cat should still match CatProfile (exact match)"


@pytest.mark.asyncio
async def test_config_validation_rejects_invalid_values(monkeypatch):
    """
    Test that the configuration validator rejects invalid distance values.

    Values < -1 should be rejected with a ValueError.
    """
    from prez.config import Settings

    # Test that -2 is rejected
    with pytest.raises(ValueError, match="must be >= -1"):
        Settings(profile_constraint_max_distance=-2)

    # Test that -3 is rejected
    with pytest.raises(ValueError, match="must be >= -1"):
        Settings(profile_constraint_max_distance=-100)

    # Test that valid values are accepted
    Settings(profile_constraint_max_distance=-1)  # Should not raise
    Settings(profile_constraint_max_distance=0)   # Should not raise
    Settings(profile_constraint_max_distance=1)   # Should not raise
    Settings(profile_constraint_max_distance=10)  # Should not raise


@pytest.mark.asyncio
async def test_unlimited_distance_transitive_closure(client_no_override, monkeypatch):
    """
    Test that distance=-1 uses transitive closure for unlimited ancestor matching.

    With distance=-1:
    - BigCat (exact match) -> BigCatProfile ✓
    - Cat (exact match) -> CatProfile ✓
    - Mammal (1-hop to Animal) -> AnimalProfile ✓

    All should work with unlimited transitive matching.
    """
    monkeypatch.setenv("PROFILE_CONSTRAINT_MAX_DISTANCE", "-1")
    from prez import config
    config.settings = config.Settings()

    assert config.settings.profile_constraint_max_distance == -1

    system_store = client_no_override.app.state._state.get("pyoxi_system_store")
    system_repo = PyoxigraphRepo(system_store)

    # All test cases should work with unlimited distance
    test_cases = [
        ("http://example.org/test/BigCat", "BigCat Profile"),
        ("http://example.org/test/Cat", "Cat Profile"),
        ("http://example.org/test/Mammal", "Animal Profile"),
    ]

    for resource_class, expected_title in test_cases:
        pmts = NegotiatedPMTs(
            headers={},
            params={},
            classes=[URIRef(resource_class)],
            listing=False,
            system_repo=system_repo,
        )
        await pmts.setup()

        assert pmts.selected["title"] == expected_title, \
            f"Unlimited distance: {resource_class} should match {expected_title}"


@pytest.mark.asyncio
async def test_backwards_compatibility(client_no_override):
    """
    Test that existing profiles still work with the new feature (default distance=1).

    This ensures that the feature doesn't break existing exact-match profiles.
    When a profile exists for the exact class, it should still be selected.
    """
    # Use default config (distance=1)
    from prez import config
    # Reset to default
    if os.environ.get("PROFILE_CONSTRAINT_MAX_DISTANCE"):
        del os.environ["PROFILE_CONSTRAINT_MAX_DISTANCE"]
    config.settings = config.Settings()

    system_store = client_no_override.app.state._state.get("pyoxi_system_store")
    system_repo = PyoxigraphRepo(system_store)

    # Test that existing exact matches still work
    pmts = NegotiatedPMTs(
        headers={},
        params={},
        classes=[URIRef("http://example.org/test/BigCat")],
        listing=False,
        system_repo=system_repo,
    )
    await pmts.setup()

    assert pmts.selected["title"] == "BigCat Profile", \
        "Backwards compatibility: exact matches should still work"

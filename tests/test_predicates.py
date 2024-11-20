import pytest
from pydantic import ValidationError

from prez.config import Settings


@pytest.mark.parametrize(
    "label_predicates, error",
    [
        [["https://schema.org/name"], None],
        [["1", "2", "3"], ValidationError],
        [[1], AttributeError],
        ["not a list", ValueError],
    ],
)
def test_label_predicates(label_predicates, error):
    if error:
        with pytest.raises(error):
            assert Settings(label_predicates=label_predicates)
    else:
        assert Settings(label_predicates=label_predicates)


@pytest.mark.parametrize(
    "description_predicates, error",
    [
        [["https://schema.org/description"], None],
        [["1", "2", "3"], ValidationError],
        [[1], AttributeError],
        ["not a list", ValueError],
    ],
)
def test_description_predicates(description_predicates, error):
    if error:
        with pytest.raises(error):
            assert Settings(description_predicates=description_predicates)
    else:
        assert Settings(description_predicates=description_predicates)


@pytest.mark.parametrize(
    "provenance_predicates, error",
    [
        [["https://schema.org/provenance"], None],
        [["1", "2", "3"], ValidationError],
        [[1], AttributeError],
        ["not a list", ValueError],
    ],
)
def test_provenance_predicates(provenance_predicates, error):
    if error:
        with pytest.raises(error):
            assert Settings(provenance_predicates=provenance_predicates)
    else:
        assert Settings(provenance_predicates=provenance_predicates)


@pytest.mark.parametrize(
    "search_predicates, error",
    [
        [["https://schema.org/search"], None],
        [["1", "2", "3"], ValidationError],
        [[1], AttributeError],
        ["not a list", ValueError],
    ],
)
def test_search_predicates(search_predicates, error):
    if error:
        with pytest.raises(error):
            assert Settings(search_predicates=search_predicates)
    else:
        assert Settings(search_predicates=search_predicates)


@pytest.mark.parametrize(
    "other_predicates, error",
    [
        [["https://schema.org/other"], None],
        [["1", "2", "3"], ValidationError],
        [[1], AttributeError],
        ["not a list", ValueError],
    ],
)
def test_other_predicates(other_predicates, error):
    if error:
        with pytest.raises(error):
            assert Settings(other_predicates=other_predicates)
    else:
        assert Settings(other_predicates=other_predicates)

"""Tests for project-name validation (path-traversal / injection blocking)."""

import pytest

from liara_agent.api.client import validate_project_name


@pytest.mark.parametrize("valid", ["my-app", "app1", "a1", "web-shop", "x" * 63])
def test_valid_names_accepted(valid):
    assert validate_project_name(valid) == valid


@pytest.mark.parametrize(
    "invalid",
    [
        "../evil",
        "../../etc",
        "a b",
        "UPPER",
        "-leading",
        "with_underscore",
        "a" * 64,
        "",
        "name;rm -rf",
        "%2e%2e%2f",
        "name@host",
    ],
)
def test_invalid_names_rejected(invalid):
    with pytest.raises(ValueError):
        validate_project_name(invalid)


async def test_get_project_validates_before_http():
    """A traversal payload must fail validation before any request is made."""
    from liara_agent.api.client import LiaraClient

    client = LiaraClient(token="tok")
    with pytest.raises(ValueError):
        await client.get_project("../evil")
    # Client was never initialised → no HTTP call possible.
    assert client._client is None

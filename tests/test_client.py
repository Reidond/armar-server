from __future__ import annotations

import pytest
from pytest_httpx import HTTPXMock

from armar_server.errors import WorkshopError, WorkshopFetchError
from armar_server.workshop.client import WORKSHOP_BASE_URL, HttpWorkshopClient, parse_mod_id


def test_parse_mod_id_from_url() -> None:
    url = "https://reforger.armaplatform.com/workshop/6922BD179EEDD0D2"
    assert parse_mod_id(url) == "6922BD179EEDD0D2"


def test_parse_mod_id_bare_lowercase() -> None:
    assert parse_mod_id("6922bd179eedd0d2") == "6922BD179EEDD0D2"


def test_parse_mod_id_invalid() -> None:
    with pytest.raises(WorkshopError):
        parse_mod_id("not-an-id")


def test_http_client_fetch(httpx_mock: HTTPXMock) -> None:
    mod_id = "6922BD179EEDD0D2"
    httpx_mock.add_response(url=f"{WORKSHOP_BASE_URL}{mod_id}", text="<html>ok</html>")
    with HttpWorkshopClient() as client:
        assert "ok" in client.fetch_page(mod_id)


def test_http_client_404_raises(httpx_mock: HTTPXMock) -> None:
    mod_id = "DEADBEEF"
    httpx_mock.add_response(url=f"{WORKSHOP_BASE_URL}{mod_id}", status_code=404)
    with HttpWorkshopClient() as client, pytest.raises(WorkshopFetchError):
        client.fetch_page(mod_id)

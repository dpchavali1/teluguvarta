import base64
from pathlib import Path

import pytest

from app.content.visa_bulletin import entry_errors
from app.content.visa_bulletin_parse import parse_bulletin_text, text_from_pdf
from tests.conftest import requires_postgres
from tests.test_editorial_workflow import _auth, _token

FIXTURE = Path(__file__).parent / "fixtures" / "visabulletin_2026-10.txt"


def _by_key(parsed):
    return {(e["chart"], e["category"], e["country"]): e["cutoff"] for e in parsed.entries}


def test_parses_october_2026_bulletin():
    parsed = parse_bulletin_text(FIXTURE.read_text())
    assert parsed.month == "2026-10"
    assert parsed.warnings == []
    assert len(parsed.entries) == 5 * 5 * 2 + 6 * 5 * 2
    assert all(entry_errors(e["chart"], e["category"], e["country"], e["cutoff"]) is None for e in parsed.entries)
    got = _by_key(parsed)
    assert got[("FINAL_ACTION", "F1", "ALL")] == "2020-01-22"
    assert got[("FINAL_ACTION", "F4", "INDIA")] == "2006-12-15"
    assert got[("DATES_FOR_FILING", "F2A", "MEXICO")] == "C"
    assert got[("FINAL_ACTION", "EB1", "ALL")] == "C"
    assert got[("FINAL_ACTION", "EB2", "INDIA")] == "2013-11-01"
    assert got[("FINAL_ACTION", "EB3-OW", "CHINA")] == "2019-10-01"
    assert got[("FINAL_ACTION", "EB5", "CHINA")] == "2016-12-01"
    assert got[("DATES_FOR_FILING", "EB2", "ALL")] == "2026-03-15"
    assert got[("DATES_FOR_FILING", "EB3-OW", "INDIA")] == "2015-01-15"


def test_one_cell_per_line_paste_still_parses():
    text = "\n".join(FIXTURE.read_text().split())
    parsed = parse_bulletin_text(text.replace("Immigrant\nNumbers\nfor", "Immigrant Numbers for"))
    assert len(parsed.entries) == 110


def test_reports_instead_of_guessing():
    parsed = parse_bulletin_text("nothing useful here")
    assert parsed.entries == []
    assert parsed.month is None
    assert len(parsed.warnings) == 5


@requires_postgres
def test_parse_endpoint_is_admin_only_and_saves_nothing(client, db_session):
    text = FIXTURE.read_text()
    assert client.post("/v1/admin/visa-bulletins/parse", json={"text": text}).status_code == 401
    auth = _auth(_token(client, db_session))
    out = client.post("/v1/admin/visa-bulletins/parse", json={"text": text}, headers=auth)
    assert out.status_code == 200
    assert (out.json()["month"], len(out.json()["entries"]), out.json()["warnings"]) == ("2026-10", 110, [])
    assert client.get("/v1/admin/visa-bulletins", headers=auth).json() == []


PDF = FIXTURE.with_suffix(".pdf")


def test_reads_the_official_pdf():
    parsed = parse_bulletin_text(text_from_pdf(PDF.read_bytes()))
    assert (parsed.month, len(parsed.entries), parsed.warnings) == ("2026-10", 110, [])
    assert _by_key(parsed)[("FINAL_ACTION", "EB2", "INDIA")] == "2013-11-01"


def test_unreadable_pdf_is_a_value_error():
    for junk in (b"not a pdf", b"%PDF-1.4 broken", b""):
        with pytest.raises(ValueError):
            text_from_pdf(junk)


@requires_postgres
def test_parse_endpoint_accepts_pdf_upload(client, db_session):
    auth = _auth(_token(client, db_session))
    url = "/v1/admin/visa-bulletins/parse"
    ok = client.post(url, json={"pdf_base64": base64.b64encode(PDF.read_bytes()).decode()}, headers=auth)
    assert (ok.status_code, ok.json()["month"], len(ok.json()["entries"])) == (200, "2026-10", 110)
    for body in ({"pdf_base64": "!!!"}, {"pdf_base64": base64.b64encode(b"nope").decode()}):
        bad = client.post(url, json=body, headers=auth)
        assert (bad.status_code, bad.json()["error"]["code"]) == (422, "PDF_UNREADABLE")
    both = client.post(url, json={"text": "x", "pdf_base64": "eA=="}, headers=auth)
    assert both.json()["error"]["code"] == "PARSE_INPUT"

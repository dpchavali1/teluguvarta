"""Admin test-feed probe: parsing preview plus SSRF/size/redirect guards.
No DB or network — httpx.MockTransport and a fake resolver."""

import httpx

from app.adapters.feed_probe import MAX_BYTES, probe_feed

RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>One</title><link>https://ex.com/1</link></item>
<item><title>Two</title><link>https://ex.com/2</link></item>
</channel></rss>"""

PUBLIC = lambda host: ["93.184.216.34"]


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_valid_feed_previews_headlines():
    result = probe_feed("https://ex.com/feed", _client(lambda r: httpx.Response(200, content=RSS)), PUBLIC)
    assert result.ok and result.item_count == 2 and result.headlines == ["One", "Two"]


def test_rejects_non_http_scheme():
    result = probe_feed("file:///etc/passwd", _client(lambda r: httpx.Response(200)), PUBLIC)
    assert not result.ok and "http" in result.error


def test_rejects_private_and_loopback_hosts():
    for addr in ("127.0.0.1", "10.0.0.5", "169.254.169.254", "::1"):
        called = []
        result = probe_feed(
            "http://internal/feed",
            _client(lambda r, calls=called: calls.append(r) or httpx.Response(200, content=RSS)),
            lambda host, a=addr: [a],
        )
        assert not result.ok and "public" in result.error
        assert not called, "must not fetch before the host check passes"


def test_rejects_if_any_resolved_address_is_private():
    result = probe_feed("http://x/feed", _client(lambda r: httpx.Response(200, content=RSS)), lambda h: ["93.184.216.34", "10.0.0.1"])
    assert not result.ok


def test_redirect_is_reported_not_followed():
    result = probe_feed("https://ex.com/feed", _client(lambda r: httpx.Response(302, headers={"location": "http://127.0.0.1/"})), PUBLIC)
    assert not result.ok and "redirect" in result.error.lower()


def test_http_error_status():
    result = probe_feed("https://ex.com/feed", _client(lambda r: httpx.Response(404)), PUBLIC)
    assert not result.ok and "404" in result.error


def test_oversized_body_rejected():
    big = b"x" * (MAX_BYTES + 1)
    result = probe_feed("https://ex.com/feed", _client(lambda r: httpx.Response(200, content=big)), PUBLIC)
    assert not result.ok and "2 MB" in result.error


def test_non_feed_body():
    result = probe_feed("https://ex.com/feed", _client(lambda r: httpx.Response(200, content=b"<html><p>hi</html>")), PUBLIC)
    assert not result.ok and "valid RSS" in result.error


def test_empty_feed():
    empty = b'<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>'
    result = probe_feed("https://ex.com/feed", _client(lambda r: httpx.Response(200, content=empty)), PUBLIC)
    assert not result.ok and "no items" in result.error


def test_unresolvable_host():
    def boom(host):
        raise OSError("nxdomain")

    result = probe_feed("https://nope.invalid/feed", _client(lambda r: httpx.Response(200)), boom)
    assert not result.ok and "resolve" in result.error

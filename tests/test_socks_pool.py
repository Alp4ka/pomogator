from pomogator.infrastructure.telegram.socks_pool import parse_proxy_lines


def test_parse_host_port_lines():
    text = """
    # comment
    1.2.3.4:1080

    5.6.7.8:9050
    not-a-proxy
    socks5://9.9.9.9:1080
    http://bad.example:3128
    """
    assert parse_proxy_lines(text) == [
        "socks5://1.2.3.4:1080",
        "socks5://5.6.7.8:9050",
        "socks5://9.9.9.9:1080",
    ]


def test_parse_ignores_invalid_ports():
    assert parse_proxy_lines("host:abc\n:1080\nonlyhost") == []

"""
Specialized HTML and client-side obfuscation parsers for non-API proxy portals.
Handles JavaScript mathematical port calculation, DOM decoys, and Base64 encoding
using pure Python standard library routines (zero heavy headless browser dependencies).
"""
import re
import json
import base64
import logging
from typing import List, Optional
from core.models import Proxy, ProxyProtocol

logger = logging.getLogger(__name__)


def parse_spys(html: str, target_protocol: ProxyProtocol) -> List[Proxy]:
    """
    Reverse-engineers spys.one JavaScript port encryption.
    spys.one uses an inline script that assigns pseudo-random variables and prints ports via:
        document.write("..." + (var1 ^ var2) + (var3 ^ var4) + ...)
    Using XOR involutory identity: (X ^ K) ^ K = X, we compute the digits in <5ms.
    """
    results: List[Proxy] = []
    try:
        var_map = {}
        for var_name, val in re.findall(r"([a-z0-9]+)=([0-9]+);", html):
            var_map[var_name] = int(val)
        for var_name, d1, v2 in re.findall(r"([a-z0-9]+)=([0-9]+)\^([a-z0-9]+);", html):
            if v2 in var_map:
                var_map[var_name] = int(d1) ^ var_map[v2]

        pattern = re.compile(
            r"(\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b).*?document\.write\([^\)]*?\+(.*?)\)</script>.*?(SOCKS4|SOCKS5|HTTP)",
            re.DOTALL | re.IGNORECASE,
        )

        seen = set()
        for ip, port_expr, proto_str in pattern.findall(html):
            proto_upper = proto_str.upper()
            if target_protocol == ProxyProtocol.HTTP and "HTTP" not in proto_upper:
                continue
            if target_protocol == ProxyProtocol.SOCKS4 and "SOCKS4" not in proto_upper:
                continue
            if target_protocol == ProxyProtocol.SOCKS5 and "SOCKS5" not in proto_upper:
                continue

            terms = re.findall(r"\(([a-z0-9]+)\^([a-z0-9]+)\)", port_expr)
            digits = []
            for t1, t2 in terms:
                if t1 in var_map and t2 in var_map:
                    digits.append(str(var_map[t1] ^ var_map[t2]))
            if digits:
                port = int("".join(digits))
                key = f"{ip}:{port}"
                if key not in seen and 1 <= port <= 65535:
                    seen.add(key)
                    results.append(Proxy(host=ip, port=port, protocol=target_protocol))
    except Exception as e:
        logger.debug(f"spys.one parsing error: {e}")

    return results


def parse_proxydb(html: str, target_protocol: ProxyProtocol) -> List[Proxy]:
    """
    Parses proxydb.net HTML.
    proxydb inserts hidden decoy tags (<div style='display:none'>12</div>) in port columns
    to mislead naive scrapers into reading corrupted ports.
    We extract clean IP:Port directly from anchor href attributes: href="/IP/PORT#protocol".
    """
    results: List[Proxy] = []
    try:
        proto_slug = "http"
        if target_protocol == ProxyProtocol.SOCKS4:
            proto_slug = "socks4"
        elif target_protocol == ProxyProtocol.SOCKS5:
            proto_slug = "socks5"

        pattern = re.compile(
            rf'href=[\"\']/(\d{{1,3}}\.\d{{1,3}}\.\d{{1,3}}\.\d{{1,3}})/(\d+)#{proto_slug}',
            re.IGNORECASE,
        )
        seen = set()
        for ip, port_str in pattern.findall(html):
            port = int(port_str)
            key = f"{ip}:{port}"
            if key not in seen and 1 <= port <= 65535:
                seen.add(key)
                results.append(Proxy(host=ip, port=port, protocol=target_protocol))
    except Exception as e:
        logger.debug(f"proxydb parsing error: {e}")

    return results


def parse_b64_proxy_list(html: str, target_protocol: ProxyProtocol) -> List[Proxy]:
    """
    Parses proxy-list.org HTML.
    The portal obfuscates IP:Port within JavaScript calls: Proxy('BASE64_STRING').
    Decodes each Base64 token on the fly.
    """
    results: List[Proxy] = []
    try:
        b64_matches = re.findall(r"Proxy\('([A-Za-z0-9+/=]+)'\)", html)
        seen = set()
        for b in b64_matches:
            try:
                dec = base64.b64decode(b).decode("utf-8")
                if ":" in dec:
                    ip, port_str = dec.split(":", 1)
                    port = int(port_str)
                    key = f"{ip}:{port}"
                    if key not in seen and 1 <= port <= 65535:
                        seen.add(key)
                        results.append(Proxy(host=ip, port=port, protocol=target_protocol))
            except Exception:
                continue
    except Exception as e:
        logger.debug(f"proxy-list.org parsing error: {e}")

    return results


def parse_advanced_name(html: str, target_protocol: ProxyProtocol) -> List[Proxy]:
    """
    Parses advanced.name/freeproxy HTML.
    The portal obfuscates the IP and Port values inside data attributes in Base64:
        <td data-ip="MTA4LjE3MC4xMi4xMw=="></td>
        <td data-port="ODA="></td>
    Decodes the Base64 attributes and maps to the requested protocol.
    """
    results: List[Proxy] = []
    try:
        pattern = re.compile(
            r'data-ip=[\"\']([A-Za-z0-9+/=]+)[\"\'].*?data-port=[\"\']([A-Za-z0-9+/=]+)[\"\']',
            re.DOTALL,
        )
        seen = set()
        for b_ip, b_port in pattern.findall(html):
            try:
                ip = base64.b64decode(b_ip).decode("utf-8").strip()
                port_str = base64.b64decode(b_port).decode("utf-8").strip()
                port = int(port_str)
                key = f"{ip}:{port}"
                if key not in seen and 1 <= port <= 65535:
                    seen.add(key)
                    results.append(Proxy(host=ip, port=port, protocol=target_protocol))
            except Exception:
                continue
    except Exception as e:
        logger.debug(f"advanced.name parsing error: {e}")

    return results


def parse_freeproxy_world(html: str, target_protocol: ProxyProtocol) -> List[Proxy]:
    """
    Parses freeproxy.world HTML tables.
    Extracts IP from td[0] and Port from td[1] anchor or inner text across paginated views.
    """
    results: List[Proxy] = []
    seen = set()
    try:
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)
        for r in rows:
            tds = re.findall(r'<td[^>]*>(.*?)</td>', r, re.DOTALL)
            if len(tds) >= 2:
                ip_match = re.search(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b', tds[0])
                port_match = re.search(r'\b\d{2,5}\b', tds[1])
                if ip_match and port_match:
                    ip = ip_match.group(0)
                    port = int(port_match.group(0))
                    key = f"{ip}:{port}"
                    if key not in seen and 1 <= port <= 65535:
                        seen.add(key)
                        results.append(Proxy(host=ip, port=port, protocol=target_protocol))
    except Exception as e:
        logger.debug(f"freeproxy.world parsing error: {e}")

    return results


def parse_geonode(json_text: str, target_protocol: ProxyProtocol) -> List[Proxy]:
    """
    Parses Geonode public API JSON pagination response:
    {"data": [{"ip": "...", "port": 1080, "protocols": ["socks5"], ...}]}
    """
    results: List[Proxy] = []
    seen = set()
    try:
        data = json.loads(json_text)
        items = data.get("data", [])
        for item in items:
            ip = item.get("ip")
            port = item.get("port")
            if ip and port:
                port = int(port)
                key = f"{ip}:{port}"
                if key not in seen and 1 <= port <= 65535:
                    seen.add(key)
                    results.append(Proxy(host=ip, port=port, protocol=target_protocol))
    except Exception as e:
        logger.debug(f"geonode parsing error: {e}")

    return results


def parse_proxycompass(json_text: str, target_protocol: ProxyProtocol) -> List[Proxy]:
    """
    Parses proxycompass.com public API JSON response:
    {"count": 2899, "results": [{"ip_address": "40.177.104.199", "port": 38213, ...}]}
    """
    results: List[Proxy] = []
    seen = set()
    try:
        data = json.loads(json_text)
        items = data.get("results", [])
        for item in items:
            ip = item.get("ip_address")
            port = item.get("port")
            if ip and port:
                port = int(port)
                key = f"{ip}:{port}"
                if key not in seen and 1 <= port <= 65535:
                    seen.add(key)
                    results.append(Proxy(host=ip, port=port, protocol=target_protocol))
    except Exception as e:
        logger.debug(f"proxycompass parsing error: {e}")

    return results


def parse_free_proxy_list(html: str, target_protocol: ProxyProtocol) -> List[Proxy]:
    """
    Parses free-proxy-list.net, socks-proxy.net, sslproxies.org, and us-proxy.org HTML tables.
    Extracts IP from td[0] and Port from td[1].
    """
    results: List[Proxy] = []
    seen = set()
    try:
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)
        for r in rows:
            tds = re.findall(r'<td[^>]*>(.*?)</td>', r, re.DOTALL)
            if len(tds) >= 2:
                ip = tds[0].strip()
                port_str = tds[1].strip()
                if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip) and re.match(r'^\d{2,5}$', port_str):
                    port = int(port_str)
                    key = f"{ip}:{port}"
                    if key not in seen and 1 <= port <= 65535:
                        seen.add(key)
                        results.append(Proxy(host=ip, port=port, protocol=target_protocol))
    except Exception as e:
        logger.debug(f"free-proxy-list network parsing error: {e}")

    return results


def parse_html_source(url: str, html: str, protocol: ProxyProtocol) -> Optional[List[Proxy]]:
    """
    Routes known HTML-based proxy sources and JSON APIs to their specialized parser routines.
    Returns None if the URL does not belong to a recognized portal,
    allowing fallback to generic IP:PORT scanning.
    """
    lower_url = url.lower()

    if "proxycompass.com" in lower_url:
        return parse_proxycompass(html, protocol)
    elif "spys.one" in lower_url:
        return parse_spys(html, protocol)
    elif "proxydb.net" in lower_url:
        return parse_proxydb(html, protocol)
    elif "proxy-list.org" in lower_url:
        return parse_b64_proxy_list(html, protocol)
    elif "advanced.name" in lower_url:
        return parse_advanced_name(html, protocol)
    elif "freeproxy.world" in lower_url:
        return parse_freeproxy_world(html, protocol)
    elif "geonode.com" in lower_url:
        return parse_geonode(html, protocol)
    elif any(d in lower_url for d in ["free-proxy-list.net", "socks-proxy.net", "sslproxies.org", "us-proxy.org"]):
        return parse_free_proxy_list(html, protocol)

    return None



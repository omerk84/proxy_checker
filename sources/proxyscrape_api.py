"""
Dynamic ProxyScrape v4 API integration module.
Fetches proxies directly from the official ProxyScrape REST API v4 using dynamic user-configured
parameters (protocol and timeout threshold in ms).
Includes robust parsing for raw, unformatted, or malformed proxy streams.
"""
import re
import json
import logging
import ipaddress
import asyncio
from typing import List, Set
import aiohttp

import config
from core.models import Proxy, ProxyProtocol

logger = logging.getLogger(__name__)

# Strict IPv4:Port extraction regex (allows optional protocol prefixes, handles arbitrary whitespace/delimiters)
IP_PORT_STRICT_REGEX = re.compile(
    r"(?:https?://|socks[45]://)?\b((?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)):([0-9]{1,5})\b"
)

BASE_PROXY_SCRAPE_V4_URL = "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=ipport&format=text"


def build_proxyscrape_urls(protocol: ProxyProtocol, timeout_ms: int) -> List[str]:
    """
    Constructs the dynamic ProxyScrape v4 API URL(s) based on the user's protocol and timeout threshold.
    For HTTP protocol, queries both 'http' and 'https' endpoints to capture the entire HTTP pool.
    """
    clamped_timeout = max(100, int(timeout_ms))

    if protocol == ProxyProtocol.HTTP:
        # ProxyScrape v4 partitions plain HTTP and CONNECT HTTPS
        return [
            f"{BASE_PROXY_SCRAPE_V4_URL}&protocol=http&timeout={clamped_timeout}",
            f"{BASE_PROXY_SCRAPE_V4_URL}&protocol=https&timeout={clamped_timeout}",
        ]
    elif protocol == ProxyProtocol.SOCKS4:
        return [
            f"{BASE_PROXY_SCRAPE_V4_URL}&protocol=socks4&timeout={clamped_timeout}"
        ]
    elif protocol == ProxyProtocol.SOCKS5:
        return [
            f"{BASE_PROXY_SCRAPE_V4_URL}&protocol=socks5&timeout={clamped_timeout}"
        ]
    return []


def parse_proxyscrape_raw_text(raw_text: str, protocol: ProxyProtocol) -> List[Proxy]:
    """
    Ultra-robust raw parser for ProxyScrape API responses.
    Handles:
      - Raw text with Windows CRLF, Unix LF, CR, or arbitrary whitespace
      - Proxies separated by commas, semicolons, HTML tags, or spaces
      - Potential JSON-formatted payloads (fallback)
      - Validation against non-routable, private, loopback, multicast, or reserved IPs
      - Strict port range validation (1..65535)
      - Deduplication preserving discovery order
    """
    if not raw_text:
        return []

    proxies: List[Proxy] = []
    seen: Set[str] = set()
    stripped = raw_text.strip()

    # 1. Fallback JSON Parsing (if API returns JSON format or error payload)
    if (stripped.startswith("{") or stripped.startswith("[")) and ("proxies" in stripped or "ip" in stripped):
        try:
            data = json.loads(stripped)
            items = []
            if isinstance(data, dict):
                items = data.get("proxies") or data.get("data") or data.get("results") or []
                if not isinstance(items, list):
                    items = [data]
            elif isinstance(data, list):
                items = data

            for item in items:
                if isinstance(item, dict):
                    ip = item.get("ip") or item.get("host") or item.get("ip_address")
                    port_raw = item.get("port")
                    if ip and port_raw:
                        try:
                            port = int(port_raw)
                            ip_str = str(ip).strip()
                            ip_obj = ipaddress.ip_address(ip_str)
                            if (
                                1 <= port <= 65535
                                and ip_obj.is_global
                                and not (ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_reserved or ip_obj.is_multicast)
                            ):
                                addr = f"{ip_str}:{port}"
                                if addr not in seen:
                                    seen.add(addr)
                                    proxies.append(Proxy(host=ip_str, port=port, protocol=protocol))
                        except Exception:
                            pass
        except Exception:
            pass

    # 2. Strict Regex Parsing on Raw Text
    matches = IP_PORT_STRICT_REGEX.findall(raw_text)
    for ip_str, port_str in matches:
        try:
            port = int(port_str)
            if not (1 <= port <= 65535):
                continue
            ip_obj = ipaddress.ip_address(ip_str)
            if not (
                ip_obj.is_global
                and not ip_obj.is_private
                and not ip_obj.is_loopback
                and not ip_obj.is_reserved
                and not ip_obj.is_multicast
            ):
                continue

            addr = f"{ip_str}:{port}"
            if addr not in seen:
                seen.add(addr)
                proxies.append(Proxy(host=ip_str, port=port, protocol=protocol))
        except (ValueError, TypeError):
            continue

    return proxies


async def fetch_single_proxyscrape_url(
    session: aiohttp.ClientSession,
    url: str,
    protocol: ProxyProtocol,
) -> List[Proxy]:
    """Fetches a single ProxyScrape API endpoint with retry on rate limit."""
    headers = {"User-Agent": config.DEFAULT_USER_AGENT}
    timeout = aiohttp.ClientTimeout(total=config.SCRAPER_TIMEOUT)

    for attempt in range(2):
        try:
            async with session.get(url, timeout=timeout, headers=headers) as response:
                if response.status == 200:
                    text = await response.text(errors="ignore")
                    return parse_proxyscrape_raw_text(text, protocol)
                elif response.status in (429, 503) and attempt == 0:
                    logger.debug(f"ProxyScrape rate-limited (HTTP {response.status}), retrying with backoff...")
                    await asyncio.sleep(1.5)
                    continue
                else:
                    logger.warning(f"ProxyScrape API returned HTTP {response.status} for {url}")
                    return []
        except Exception as e:
            if attempt == 0:
                await asyncio.sleep(1.0)
                continue
            logger.warning(f"Failed to fetch ProxyScrape API URL {url}: {e}")
            return []
    return []


async def fetch_dynamic_proxyscrape(
    protocol: ProxyProtocol,
    timeout_ms: int,
    session: aiohttp.ClientSession,
) -> List[Proxy]:
    """
    Primary entry point to fetch and parse proxies from ProxyScrape v4 API
    using dynamic protocol and timeout parameters.
    """
    urls = build_proxyscrape_urls(protocol, timeout_ms)
    if not urls:
        return []

    tasks = [fetch_single_proxyscrape_url(session, url, protocol) for url in urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_proxies: List[Proxy] = []
    seen: Set[str] = set()

    for res in results:
        if isinstance(res, list):
            for proxy in res:
                if proxy.address not in seen:
                    seen.add(proxy.address)
                    all_proxies.append(proxy)

    logger.info(f"ProxyScrape v4 API fetched {len(all_proxies)} unique candidate proxies (timeout={timeout_ms}ms).")
    return all_proxies

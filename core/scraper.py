"""
High-performance asynchronous proxy scraper.
Fetches proxies concurrently from multiple public API endpoints and repositories.
"""
import re
import asyncio
import logging
from typing import List, Set, Optional, Callable, Dict
import aiohttp

import config
from core.models import Proxy, ProxyProtocol
from sources.html_parsers import parse_html_source

logger = logging.getLogger(__name__)

# Regular expression to extract IP:Port accurately
IP_PORT_PATTERN = re.compile(
    r"\b((?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)):(\d{1,5})\b"
)


class ProxyScraper:
    """Asynchronous engine for scraping and deduplicating proxies from various sources."""

    def __init__(self, protocol: ProxyProtocol):
        from sources.proxy_sources import get_sources_for_protocol
        self.protocol = protocol
        self.sources = get_sources_for_protocol(protocol)

    async def _fetch_single_source(
        self,
        session: aiohttp.ClientSession,
        url: str,
        on_source_done: Optional[Callable[[str, int], None]] = None,
    ) -> List[Proxy]:
        """Fetch raw content from a single URL and parse proxies."""
        proxies: List[Proxy] = []
        try:
            timeout = aiohttp.ClientTimeout(total=config.SCRAPER_TIMEOUT)
            headers = {"User-Agent": config.DEFAULT_USER_AGENT}
            async with session.get(url, timeout=timeout, headers=headers) as response:
                if response.status == 200:
                    text = await response.text(errors="ignore")

                    # Route through specialized HTML parser if applicable
                    html_proxies = parse_html_source(url, text, self.protocol)
                    if html_proxies is not None:
                        proxies.extend(html_proxies)
                    else:
                        matches = IP_PORT_PATTERN.findall(text)
                        for ip, port_str in matches:
                            port = int(port_str)
                            if 1 <= port <= 65535:
                                proxies.append(
                                    Proxy(host=ip, port=port, protocol=self.protocol)
                                )
                else:
                    logger.debug(f"Source returned HTTP {response.status}: {url}")
        except Exception as e:
            logger.debug(f"Failed to scrape source {url}: {e}")

        if on_source_done:
            on_source_done(url, len(proxies))

        return proxies

    async def scrape(
        self,
        on_source_done: Optional[Callable[[str, int], None]] = None,
        stop_event: Optional[asyncio.Event] = None,
    ) -> List[Proxy]:
        """
        Scrapes all sources concurrently, deduplicates results,
        and returns a unique list of Proxy objects ordered strictly by source quality precedence.
        Supports early termination via stop_event.
        """
        results_by_url: Dict[str, List[Proxy]] = {}

        connector = aiohttp.TCPConnector(ssl=False, limit=50)
        async with aiohttp.ClientSession(connector=connector) as session:
            task_to_url = {
                asyncio.create_task(self._fetch_single_source(session, url, on_source_done)): url
                for url in self.sources
            }

            pending = set(task_to_url.keys())
            while pending and not (stop_event and stop_event.is_set()):
                done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                for t in done:
                    url = task_to_url[t]
                    try:
                        result = t.result()
                        if isinstance(result, list):
                            results_by_url[url] = result
                    except (asyncio.CancelledError, Exception) as e:
                        logger.debug(f"Source scrape error: {e}")

            # If finish was requested early, cleanly cancel lingering pending tasks
            if pending:
                for t in pending:
                    t.cancel()
                await asyncio.gather(*pending, return_exceptions=True)

        # Assemble unique_proxies strictly preserving self.sources quality precedence!
        seen_addresses: Set[str] = set()
        unique_proxies: List[Proxy] = []
        for url in self.sources:
            if url in results_by_url:
                for proxy in results_by_url[url]:
                    if proxy.address not in seen_addresses:
                        seen_addresses.add(proxy.address)
                        unique_proxies.append(proxy)

        return unique_proxies




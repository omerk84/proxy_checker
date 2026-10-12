"""
High-concurrency asynchronous proxy health and latency checker.
Measures latency (ping in milliseconds) and filters alive/working proxies.
Features:
- Configurable Retry Mechanism: Second-chance retry for failed proxies to recover transient glitches
- Targeted Failover: Switches endpoints if target test service returns 429/503 rate limits
- Stability Double-Check: Conducts jitter verification exclusively for verified alive proxies
- Anonymity Detection: Distinguishes Elite vs Anonymous proxies
- Leak Prevention: Discards any proxy that leaks the client's home IP
"""
import sys
import re
import time
import asyncio
import logging
from dataclasses import dataclass
from typing import List, Optional, Callable
import aiohttp
from aiohttp_socks import ProxyConnector

import config
from core.models import Proxy, ProxyProtocol, ProxyStatus

logger = logging.getLogger(__name__)

# Regular expression to verify genuine IPv4 echo response from test endpoint
IPV4_REGEX = re.compile(r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$")

# Patch Windows Proactor transport bug where remote resets raise unhandled WinError 10054 in callback
if sys.platform == "win32":
    try:
        from asyncio.proactor_events import _ProactorBasePipeTransport
        _orig_call_connection_lost = _ProactorBasePipeTransport._call_connection_lost

        def _safe_call_connection_lost(self, exc):
            try:
                _orig_call_connection_lost(self, exc)
            except (ConnectionResetError, OSError):
                pass

        _ProactorBasePipeTransport._call_connection_lost = _safe_call_connection_lost
    except Exception:
        pass


@dataclass
class _PingResult:
    latency_ms: Optional[float] = None
    is_socket_dead: bool = False       # Proxy connection refused, timed out, or closed
    is_endpoint_error: bool = False    # HTTP 429/503 or invalid HTML response from echo service
    echo_ip: Optional[str] = None


class ProxyChecker:
    """Asynchronous checker engine evaluating proxy availability, round-trip latency, and stability."""

    def __init__(
        self,
        concurrency: int = config.DEFAULT_CONCURRENCY,
        timeout: float = config.DEFAULT_TIMEOUT,
        primary_test_url: str = config.PRIMARY_TEST_URL,
        fallback_test_url: str = config.FALLBACK_TEST_URL,
        max_latency_ms: Optional[float] = None,
        local_ip: Optional[str] = None,
        verify_stability: bool = True,
        retries: int = 1,
    ):
        self.concurrency = concurrency
        self.timeout = timeout
        self.primary_test_url = primary_test_url
        self.fallback_test_url = fallback_test_url
        self.max_latency_ms = max_latency_ms
        self.local_ip = local_ip
        self.verify_stability = verify_stability
        self.retries = max(0, retries)
        self.semaphore = asyncio.Semaphore(concurrency)

        # Network socket timeout: ensures sufficient time for multi-hop WAN handshake without false early dropouts.
        # Max latency filtering is applied strictly to measured round-trip time, not as a premature socket killer.
        self.effective_timeout = max(3.5, self.timeout)

    def _validate_response_body(self, text: str) -> bool:
        """
        Validates that the test endpoint returned a legitimate external IP,
        filtering out HTML captive portals, ISP block pages, and direct connection leaks.
        """
        clean_text = text.strip()
        if not IPV4_REGEX.match(clean_text):
            return False
        if self.local_ip and clean_text == self.local_ip:
            # The proxy leaked the user's home IP (did not actually tunnel)
            return False
        return True

    async def _send_single_http_ping(
        self,
        session: aiohttp.ClientSession,
        proxy_url: str,
        target_url: str,
        timeout: aiohttp.ClientTimeout,
        headers: dict,
    ) -> _PingResult:
        """Sends a single request to target_url through proxy and returns structured result."""
        start_time = time.perf_counter()
        try:
            async with session.get(target_url, proxy=proxy_url, timeout=timeout, headers=headers) as response:
                if response.status == 200:
                    body = (await response.text(errors="ignore")).strip()
                    if self._validate_response_body(body):
                        elapsed_ms = (time.perf_counter() - start_time) * 1000
                        return _PingResult(latency_ms=elapsed_ms, echo_ip=body)
                    else:
                        return _PingResult(is_endpoint_error=True)
                elif response.status in (429, 500, 502, 503):
                    return _PingResult(is_endpoint_error=True)
                else:
                    return _PingResult(is_socket_dead=True)
        except (aiohttp.ClientConnectorError, aiohttp.ClientProxyConnectionError, asyncio.TimeoutError, ConnectionRefusedError, OSError):
            return _PingResult(is_socket_dead=True)
        except Exception:
            return _PingResult(is_socket_dead=True)

    async def _check_single_http_proxy(
        self,
        session: aiohttp.ClientSession,
        proxy: Proxy,
    ) -> Proxy:
        """Check standard HTTP/HTTPS proxy using a shared session with configurable retries."""
        async with self.semaphore:
            proxy_url = f"http://{proxy.address}"
            client_timeout = aiohttp.ClientTimeout(total=self.effective_timeout)
            headers = {"User-Agent": config.DEFAULT_USER_AGENT}

            attempts = 1 + self.retries
            for attempt in range(attempts):
                # 1. Primary ping attempt
                res = await self._send_single_http_ping(
                    session, proxy_url, self.primary_test_url, client_timeout, headers
                )

                # Targeted Failover if echo endpoint had rate limit or server error
                if res.is_endpoint_error and res.latency_ms is None:
                    res = await self._send_single_http_ping(
                        session, proxy_url, self.fallback_test_url, client_timeout, headers
                    )

                # If successfully connected and validated
                if res.latency_ms is not None:
                    if self.max_latency_ms and res.latency_ms > self.max_latency_ms:
                        proxy.status = ProxyStatus.DEAD
                        proxy.error_message = f"Exceeded max MS ({res.latency_ms:.1f}ms > {self.max_latency_ms}ms)"
                        return proxy

                    final_ms = res.latency_ms
                    # 2. Stability Double-Check for confirmed working proxy
                    if self.verify_stability:
                        res2 = await self._send_single_http_ping(
                            session, proxy_url, self.fallback_test_url, client_timeout, headers
                        )
                        if res2.latency_ms is not None:
                            final_ms = (res.latency_ms + res2.latency_ms) / 2.0

                    proxy.latency_ms = round(final_ms, 1)
                    proxy.status = ProxyStatus.ALIVE
                    if res.echo_ip:
                        proxy.anonymity = "Elite" if res.echo_ip == proxy.host else "Anonymous"
                    return proxy

                # If failed and more retry attempts remain, wait brief backoff before trying again
                if attempt < attempts - 1:
                    await asyncio.sleep(0.15)

            # All attempts exhausted
            proxy.status = ProxyStatus.DEAD
            proxy.error_message = "Connection failed after retries"
            return proxy

    async def _send_single_socks_ping(
        self,
        connector: ProxyConnector,
        target_url: str,
        timeout: aiohttp.ClientTimeout,
        headers: dict,
    ) -> _PingResult:
        """Sends a single request through SOCKS proxy."""
        start_time = time.perf_counter()
        try:
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(target_url, timeout=timeout, headers=headers) as response:
                    if response.status == 200:
                        body = (await response.text(errors="ignore")).strip()
                        if self._validate_response_body(body):
                            elapsed_ms = (time.perf_counter() - start_time) * 1000
                            return _PingResult(latency_ms=elapsed_ms, echo_ip=body)
                        else:
                            return _PingResult(is_endpoint_error=True)
                    elif response.status in (429, 500, 502, 503):
                        return _PingResult(is_endpoint_error=True)
                    else:
                        return _PingResult(is_socket_dead=True)
        except (aiohttp.ClientConnectorError, aiohttp.ClientProxyConnectionError, asyncio.TimeoutError, ConnectionRefusedError, OSError):
            return _PingResult(is_socket_dead=True)
        except Exception:
            return _PingResult(is_socket_dead=True)

    async def _check_single_socks_proxy(
        self,
        proxy: Proxy,
    ) -> Proxy:
        """Check SOCKS4 or SOCKS5 proxy using ProxyConnector with configurable retries."""
        async with self.semaphore:
            client_timeout = aiohttp.ClientTimeout(total=self.effective_timeout)
            headers = {"User-Agent": config.DEFAULT_USER_AGENT}

            attempts = 1 + self.retries
            for attempt in range(attempts):
                connector = None
                try:
                    connector = ProxyConnector.from_url(proxy.url, ssl=False)

                    # Primary test
                    res = await self._send_single_socks_ping(
                        connector, self.primary_test_url, client_timeout, headers
                    )

                    # Targeted Failover if echo endpoint had rate limit
                    if res.is_endpoint_error and res.latency_ms is None:
                        fallback_connector = ProxyConnector.from_url(proxy.url, ssl=False)
                        try:
                            res = await self._send_single_socks_ping(
                                fallback_connector, self.fallback_test_url, client_timeout, headers
                            )
                        finally:
                            if not fallback_connector.closed:
                                await fallback_connector.close()

                    if res.latency_ms is not None:
                        if self.max_latency_ms and res.latency_ms > self.max_latency_ms:
                            proxy.status = ProxyStatus.DEAD
                            proxy.error_message = f"Exceeded max MS ({res.latency_ms:.1f}ms > {self.max_latency_ms}ms)"
                            return proxy

                        proxy.latency_ms = round(res.latency_ms, 1)
                        proxy.status = ProxyStatus.ALIVE
                        proxy.supports_https = True  # SOCKS natively tunnels TLS/HTTPS
                        if res.echo_ip:
                            proxy.anonymity = "Elite" if res.echo_ip == proxy.host else "Anonymous"
                        return proxy

                except asyncio.TimeoutError:
                    pass
                except Exception as e:
                    pass
                finally:
                    if connector and not connector.closed:
                        try:
                            await connector.close()
                        except Exception:
                            pass

                # If retry attempts remain, wait brief backoff before trying again
                if attempt < attempts - 1:
                    await asyncio.sleep(0.15)

            # All attempts exhausted
            proxy.status = ProxyStatus.DEAD
            proxy.error_message = "Connection failed after retries"
            return proxy

    async def check_all(
        self,
        proxies: List[Proxy],
        on_proxy_checked: Optional[Callable[[Proxy], None]] = None,
        stop_event: Optional[asyncio.Event] = None,
    ) -> List[Proxy]:
        """
        Check all proxies in parallel using a bounded worker queue.
        Supports graceful early finish via stop_event.
        Returns all alive proxies that satisfy the max_latency_ms criteria, sorted by latency.
        """
        if not proxies:
            return []

        # Suppress loop-level Windows 10054 connection reset tracebacks
        loop = asyncio.get_running_loop()
        def _silent_handler(l, context):
            exc = context.get("exception")
            if isinstance(exc, (ConnectionResetError, OSError)):
                return
            msg = str(context.get("message", ""))
            if "10054" in msg or "connection_lost" in msg:
                return
            l.default_exception_handler(context)

        loop.set_exception_handler(_silent_handler)

        protocol = proxies[0].protocol
        checked_results: List[Proxy] = []
        queue: asyncio.Queue[Proxy] = asyncio.Queue()
        for p in proxies:
            queue.put_nowait(p)

        worker_count = min(self.concurrency, len(proxies))

        async def worker(session: Optional[aiohttp.ClientSession] = None):
            while not queue.empty():
                if stop_event and stop_event.is_set():
                    break
                try:
                    proxy = queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

                try:
                    if protocol == ProxyProtocol.HTTP and session is not None:
                        res = await self._check_single_http_proxy(session, proxy)
                    else:
                        res = await self._check_single_socks_proxy(proxy)

                    checked_results.append(res)
                    if on_proxy_checked:
                        on_proxy_checked(res)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.debug(f"Checker worker error: {e}")
                finally:
                    queue.task_done()

        worker_tasks = []
        try:
            if protocol == ProxyProtocol.HTTP:
                tcp_connector = aiohttp.TCPConnector(ssl=False, limit=0)
                try:
                    async with aiohttp.ClientSession(connector=tcp_connector) as session:
                        worker_tasks = [asyncio.create_task(worker(session)) for _ in range(worker_count)]
                        await asyncio.gather(*worker_tasks, return_exceptions=True)
                finally:
                    if not tcp_connector.closed:
                        await tcp_connector.close()
            else:
                worker_tasks = [asyncio.create_task(worker()) for _ in range(worker_count)]
                await asyncio.gather(*worker_tasks, return_exceptions=True)
        except (KeyboardInterrupt, asyncio.CancelledError):
            if stop_event:
                stop_event.set()
            for t in worker_tasks:
                if not t.done():
                    t.cancel()
            await asyncio.gather(*worker_tasks, return_exceptions=True)

        # Allow any lingering OS sockets to cleanly finalize
        await asyncio.sleep(0.05)

        # Filter working proxies that are ALIVE and within max_latency_ms
        alive_proxies = [
            p for p in checked_results
            if p.status == ProxyStatus.ALIVE
            and (self.max_latency_ms is None or (p.latency_ms is not None and p.latency_ms <= self.max_latency_ms))
        ]
        alive_proxies.sort(key=lambda p: p.latency_ms if p.latency_ms is not None else float("inf"))

        return alive_proxies

"""
Main entry point for the Proxy Scraper & Checker application.
Orchestrates protocol selection, multi-source scraping, interactive MS & Thread configuration,
concurrent latency checks, anti-leak IP validation, and persistence.
"""
import asyncio
import sys
import urllib.request
from typing import List, Optional

# Windows console UTF-8 & VT100 color support and Proactor transport patch
if sys.platform == "win32":
    try:
        if sys.stdout and hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if sys.stderr and hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        for h_id in (-11, -12):
            h = kernel32.GetStdHandle(h_id)
            if h and h != -1:
                mode = ctypes.c_ulong()
                if kernel32.GetConsoleMode(h, ctypes.byref(mode)):
                    kernel32.SetConsoleMode(h, mode.value | 0x0004 | 0x0008)
        h_con = kernel32.CreateFileW("CONOUT$", 0x40000000, 2, None, 3, 0, None)
        if h_con and h_con != -1:
            mode = ctypes.c_ulong()
            if kernel32.GetConsoleMode(h_con, ctypes.byref(mode)):
                kernel32.SetConsoleMode(h_con, mode.value | 0x0004 | 0x0008)
            kernel32.CloseHandle(h_con)
    except Exception:
        pass

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
from core.models import Proxy, ProxyProtocol, ProxyStatus
from core.scraper import ProxyScraper
from core.checker import ProxyChecker
from utils.storage import ProxyStorage
from utils.display import (
    show_banner,
    prompt_initial_config,
    prompt_checker_options,
    show_summary_and_top_proxies,
    create_scrape_progress,
    create_check_progress,
    console,
)


import threading
import time

class EarlyFinishController:
    """
    Listens for keypresses ('f', 'q', Enter, Space) on Windows to trigger graceful early finish.
    """
    def __init__(self):
        self.stop_event = asyncio.Event()
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        self.stop_event.clear()
        if sys.platform == "win32":
            self._running = True
            self._thread = threading.Thread(target=self._key_listener, daemon=True)
            self._thread.start()

    def _key_listener(self):
        try:
            import msvcrt
            while self._running and not self.stop_event.is_set():
                if msvcrt.kbhit():
                    ch = msvcrt.getch()
                    # Trigger on 'f' (Finish), 'q' (Quit current stage), Enter, Space, or Ctrl+C
                    if ch in (b'f', b'F', b'q', b'Q', b'\r', b' ', b'\x03'):
                        self.stop_event.set()
                        break
                time.sleep(0.04)
        except Exception:
            pass

    def stop(self):
        self._running = False


def get_local_public_ip() -> Optional[str]:
    """Retrieves current public IP for anti-leak proxy validation."""
    for url in ["http://api.ipify.org", "http://icanhazip.com"]:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                return resp.read().decode("utf-8").strip()
        except Exception:
            continue
    return None


async def run_pipeline():
    show_banner()

    # 1. Step 1: User selects proxy protocol & a single unified Max Latency MS
    protocol, max_latency_ms = prompt_initial_config()

    console.print(
        f"\n[bold green][+] Starting scraper for [bold yellow]{protocol.value.upper()}[/bold yellow] "
        f"(Unified Max Latency: [bold yellow]{int(max_latency_ms)}ms[/bold yellow])...[/bold green]"
    )
    console.print("[dim yellow]  (Tip: Press 'f' (Finish), 'q', [Enter] or Ctrl+C at any time to finish scraping early)[/dim yellow]\n")

    # 2. Step 2: Scrape all available proxies for this protocol (ProxyScrape API filters server-side by max_latency_ms)
    scraper = ProxyScraper(protocol=protocol, timeout_ms=int(max_latency_ms))
    scraped_proxies: List[Proxy] = []

    controller = EarlyFinishController()
    controller.start()

    try:
        with create_scrape_progress() as progress:
            scrape_task = progress.add_task(
                f"Scraping {protocol.value.upper()} sources...",
                total=scraper.total_sources_count,
            )

            def on_source_done(url: str, count: int):
                progress.advance(scrape_task)

            scraped_proxies = await scraper.scrape(
                on_source_done=on_source_done,
                stop_event=controller.stop_event,
            )
    except (KeyboardInterrupt, asyncio.CancelledError):
        controller.stop_event.set()
        console.print("\n[bold yellow][!] Finish requested. Keeping proxies collected so far...[/bold yellow]")
    finally:
        controller.stop()

    # 3. Step 3: Display exact count of scraped proxies
    total_scraped = len(scraped_proxies)
    if controller.stop_event.is_set():
        console.print(
            f"\n[bold yellow][+] Scraping finished early! Collected [bold white]{total_scraped:,}[/bold white] "
            f"unique {protocol.value.upper()} candidate proxies.[/bold yellow]\n"
        )
    else:
        console.print(
            f"\n[bold green][+] Scraping complete! Collected [bold white]{total_scraped:,}[/bold white] "
            f"unique {protocol.value.upper()} candidate proxies across all sources.[/bold green]\n"
        )

    if not scraped_proxies:
        console.print("[bold red]No candidate proxies were found from sources. Exiting.[/bold red]")
        return

    # 4. Step 4: Prompt user for Concurrency, Retries, and test limit (reusing unified max_latency_ms)
    concurrency, max_to_check, retries = prompt_checker_options(total_scraped, max_latency_ms)

    candidates_to_check = scraped_proxies[:max_to_check]

    # Resolve local public IP to detect and eliminate proxies that leak the client's home IP
    local_ip = get_local_public_ip()
    if local_ip:
        console.print(f"[dim]Detected client IP ({local_ip}) for leak prevention filtering.[/dim]")

    console.print(
        f"[bold green][+] Initializing checker with [bold yellow]{concurrency}[/bold yellow] threads "
        f"(Retries: {retries}), filtering for latency <= [bold yellow]{int(max_latency_ms)} ms[/bold yellow]...[/bold green]"
    )
    console.print("[dim yellow]  (Tip: Press 'f' (Finish), 'q', [Enter] or Ctrl+C at any time to finish checking early and save results)[/dim yellow]\n")

    # 5. Step 5: Concurrent Latency & Health Checking
    checker = ProxyChecker(
        concurrency=concurrency,
        max_latency_ms=max_latency_ms,
        local_ip=local_ip,
        retries=retries,
    )

    working_proxies: List[Proxy] = []
    collected_alive: List[Proxy] = []
    alive_count = 0
    dead_count = 0

    check_controller = EarlyFinishController()
    check_controller.start()

    try:
        with create_check_progress() as progress:
            check_task = progress.add_task(
                f"Testing {len(candidates_to_check):,} proxies...",
                total=len(candidates_to_check),
                status_summary="[green]Working: 0[/green] | [red]Excluded: 0[/red]",
            )

            def on_proxy_checked(proxy: Proxy):
                nonlocal alive_count, dead_count
                if proxy.status == ProxyStatus.ALIVE:
                    alive_count += 1
                    if max_latency_ms is None or (proxy.latency_ms is not None and proxy.latency_ms <= max_latency_ms):
                        collected_alive.append(proxy)
                else:
                    dead_count += 1

                summary_text = f"[green]Working: {alive_count}[/green] | [red]Excluded: {dead_count}[/red]"
                progress.update(check_task, advance=1, status_summary=summary_text)

            working_proxies = await checker.check_all(
                candidates_to_check,
                on_proxy_checked=on_proxy_checked,
                stop_event=check_controller.stop_event,
            )
    except (KeyboardInterrupt, asyncio.CancelledError):
        check_controller.stop_event.set()
        console.print("\n[bold yellow][!] Finish requested. Finalizing and saving working proxies found so far...[/bold yellow]")
    finally:
        check_controller.stop()

    # Guarantee: if interrupted early, recover all alive proxies collected so far!
    if not working_proxies and collected_alive:
        working_proxies = sorted(
            collected_alive,
            key=lambda p: p.latency_ms if p.latency_ms is not None else float("inf")
        )

    actual_tested = (alive_count + dead_count) if check_controller.stop_event.is_set() and (alive_count + dead_count) > 0 else len(candidates_to_check)

    if check_controller.stop_event.is_set():
        console.print(
            f"\n[bold yellow][+] Checking finished early! Found [bold white]{len(working_proxies)}[/bold white] "
            f"alive proxies satisfying latency <= {int(max_latency_ms)}ms (out of {actual_tested:,} tested).[/bold yellow]\n"
        )
    else:
        console.print(
            f"\n[bold green][+] Completed checking! Found [bold white]{len(working_proxies)}[/bold white] "
            f"alive proxies satisfying latency <= {int(max_latency_ms)}ms.[/bold green]\n"
        )

    # 6. Step 6: Export & Presentation (Only single {protocol}_working.txt is generated)
    storage = ProxyStorage()
    saved_files = storage.save_results(protocol, working_proxies, max_latency_ms=max_latency_ms)

    show_summary_and_top_proxies(
        total_scraped=total_scraped,
        total_tested=actual_tested,
        checked_alive=working_proxies,
        max_ms=max_latency_ms,
        file_paths=saved_files,
    )


def main():
    try:
        asyncio.run(run_pipeline())
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Operation finished by user. Exiting cleanly.[/bold yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[bold red]Unexpected error: {e}[/bold red]")
        sys.exit(1)


if __name__ == "__main__":
    main()


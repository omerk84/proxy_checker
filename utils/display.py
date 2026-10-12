"""
Terminal interface utilities powered by Rich.
Provides styled banners, interactive prompts, live progress indicators, and result tables.
"""
import sys
from typing import List, Tuple, Dict, Optional
from pathlib import Path

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

import config
from core.models import Proxy, ProxyProtocol


def setup_windows_console():
    """
    Ensures Windows terminal has UTF-8 encoding and Virtual Terminal Processing (VT100)
    enabled, guaranteeing rich colors, rounded borders, and proper spacing in cmd.exe.
    """
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
            # 0x0004 = ENABLE_VIRTUAL_TERMINAL_PROCESSING
            # 0x0008 = DISABLE_NEWLINE_AUTO_RETURN
            for h_id in (-11, -12):
                h = kernel32.GetStdHandle(h_id)
                if h and h != -1:
                    mode = ctypes.c_ulong()
                    if kernel32.GetConsoleMode(h, ctypes.byref(mode)):
                        kernel32.SetConsoleMode(h, mode.value | 0x0004 | 0x0008)

            # Also apply directly to CONOUT$ in case standard handles are wrapped
            h_con = kernel32.CreateFileW("CONOUT$", 0x40000000, 2, None, 3, 0, None)
            if h_con and h_con != -1:
                mode = ctypes.c_ulong()
                if kernel32.GetConsoleMode(h_con, ctypes.byref(mode)):
                    kernel32.SetConsoleMode(h_con, mode.value | 0x0004 | 0x0008)
                kernel32.CloseHandle(h_con)
        except Exception:
            pass


setup_windows_console()

console = Console(
    force_terminal=True,
    color_system="auto",
    safe_box=False,
    highlight=False,
)


def show_banner():
    """Prints the application banner."""
    console.print()
    banner_text = Text()
    banner_text.append("=== PROXY SCRAPER & SPEED CHECKER ===\n", style="bold cyan")
    banner_text.append("High-Performance Asynchronous Discovery & MS Latency Benchmarking", style="dim white")
    console.print(Panel(banner_text, border_style="cyan", box=box.ROUNDED, expand=False))
    console.print()


def prompt_protocol() -> ProxyProtocol:
    """
    Step 1: Displays the interactive protocol selection menu.
    Returns: selected ProxyProtocol
    """
    menu = Table(show_header=True, header_style="bold magenta", border_style="cyan", box=box.ROUNDED)
    menu.add_column("Option", style="bold yellow", width=8, justify="center")
    menu.add_column("Protocol", style="bold white", width=16)
    menu.add_column("Description", style="dim")

    menu.add_row("1", "HTTP / HTTPS", "Standard web proxies (browsers, scrapers, APIs)")
    menu.add_row("2", "SOCKS4", "TCP proxying protocol (low overhead)")
    menu.add_row("3", "SOCKS5", "Advanced proxying with UDP and authentication support")

    console.print(menu)
    console.print()

    while True:
        choice = console.input("[bold cyan]  [?] Select proxy protocol [1/2/3] (default 1): [/bold cyan]").strip()
        if not choice:
            choice = "1"
        try:
            return ProxyProtocol.from_choice(choice)
        except ValueError:
            console.print("[bold red]  [!] Invalid option. Please choose 1, 2, or 3.[/bold red]\n")


def prompt_checker_options(total_scraped: int) -> Tuple[float, int, int, int]:
    """
    Step 2 (after scraping finishes): Prompts user for Max MS latency, Concurrency, and Retries.
    Returns: (max_latency_ms, concurrency, max_to_check, retries)
    """
    console.print()
    console.print(Panel(
        f"  Total proxies scraped & ready to test: [bold green]{total_scraped:,}[/bold green]\n"
        f"  [dim]Configure latency thresholds, thread concurrency, and retries below:[/dim]",
        title="[bold yellow]  Configure Checker Parameters  [/bold yellow]",
        border_style="yellow",
        box=box.ROUNDED,
        expand=False,
    ))
    console.print()

    # 1. Max MS Prompt
    max_ms_input = console.input(
        "[bold cyan]  [?] Max MS Latency (e.g. 1000 for <=1000ms, Enter for 1000ms): [/bold cyan]"
    ).strip()
    try:
        max_ms = float(max_ms_input) if max_ms_input else 1000.0
    except ValueError:
        max_ms = 1000.0

    console.print()

    # 2. Concurrency (Threads) Prompt
    threads_input = console.input(
        f"[bold cyan]  [?] Threads / Concurrency [Enter for {config.DEFAULT_CONCURRENCY}]: [/bold cyan]"
    ).strip()
    concurrency = int(threads_input) if threads_input.isdigit() and int(threads_input) > 0 else config.DEFAULT_CONCURRENCY

    console.print()

    # 3. Retries for failed proxies
    retries_input = console.input(
        "[bold cyan]  [?] Retries on failure [0 for fastest, 1 for second-chance retry] (default 1): [/bold cyan]"
    ).strip()
    retries = int(retries_input) if retries_input.isdigit() else 1

    console.print()

    # 4. Candidate limit prompt
    limit_input = console.input(
        f"[bold cyan]  [?] How many proxies to test? [Enter for ALL ({total_scraped:,}), or enter a number, e.g. 1000]: [/bold cyan]"
    ).strip()
    max_to_check = int(limit_input) if limit_input.isdigit() and int(limit_input) > 0 else total_scraped

    console.print()
    return max_ms, concurrency, max_to_check, retries



def create_scrape_progress() -> Progress:
    """Creates a progress bar for scraping sources."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TextColumn("[bold green]{task.completed}/{task.total} sources"),
        TimeElapsedColumn(),
        console=console,
    )


def create_check_progress() -> Progress:
    """Creates a high-information progress bar for testing proxies."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(),
        TextColumn("[bold]{task.completed}/{task.total}[/]"),
        TextColumn("[dim]|[/dim]"),
        TextColumn("{task.fields[status_summary]}"),
        TimeRemainingColumn(),
        TimeElapsedColumn(),
        console=console,
    )


def show_summary_and_top_proxies(
    total_scraped: int,
    total_tested: int,
    checked_alive: List[Proxy],
    max_ms: float,
    file_paths: Dict[str, Path],
):
    """Renders final analytics summary and top fastest proxies table."""
    total_working = len(checked_alive)
    fast_count = sum(1 for p in checked_alive if p.speed_tier == "FAST")
    medium_count = sum(1 for p in checked_alive if p.speed_tier == "MEDIUM")
    slow_count = sum(1 for p in checked_alive if p.speed_tier == "SLOW")
    dead_count = total_tested - total_working

    avg_ms = (
        round(sum(p.latency_ms for p in checked_alive if p.latency_ms) / total_working, 1)
        if total_working > 0
        else 0.0
    )

    # Summary Panel
    stats_text = (
        f"[bold white]Total Scraped:[/] {total_scraped:,} | "
        f"[bold white]Total Tested:[/] {total_tested:,} | "
        f"[bold green]Working (<={int(max_ms)}ms):[/] {total_working:,} | "
        f"[bold red]Failed/Too Slow:[/] {dead_count:,}\n"
        f"[bold green][FAST] (<{int(config.FAST_LATENCY_THRESHOLD_MS)}ms):[/] {fast_count} | "
        f"[bold yellow][MEDIUM] (<{int(config.MEDIUM_LATENCY_THRESHOLD_MS)}ms):[/] {medium_count} | "
        f"[bold red][SLOW]:[/] {slow_count}\n"
        f"[bold cyan]Average Latency:[/] [bold yellow]{avg_ms} ms[/] (Filter: <= {int(max_ms)} ms)"
    )
    console.print()
    console.print(Panel(stats_text, title="[bold green]Scan Results Summary[/bold green]", border_style="green", box=box.ROUNDED))
    console.print()

    # Top Fastest Proxies Table
    if checked_alive:
        table = Table(
            title=">>> Top Fastest Working Proxies (Lowest MS) <<<",
            header_style="bold cyan",
            border_style="cyan",
            box=box.ROUNDED,
        )
        table.add_column("#", justify="center", style="dim", width=4)
        table.add_column("Proxy Address", style="bold white", width=22)
        table.add_column("Protocol", style="magenta", width=10)
        table.add_column("Ping (ms)", justify="right", width=12)
        table.add_column("Tier", justify="center", width=10)
        table.add_column("Anonymity", justify="center", width=11)

        for idx, proxy in enumerate(checked_alive[:15], start=1):
            ms_val = f"{proxy.latency_ms} ms"
            if proxy.speed_tier == "FAST":
                tier_style = "[bold green]FAST[/bold green]"
                ms_style = f"[bold green]{ms_val}[/bold green]"
            elif proxy.speed_tier == "MEDIUM":
                tier_style = "[yellow]MEDIUM[/yellow]"
                ms_style = f"[yellow]{ms_val}[/yellow]"
            else:
                tier_style = "[red]SLOW[/red]"
                ms_style = f"[red]{ms_val}[/red]"

            anon_val = proxy.anonymity or "Anon"
            anon_style = "[bold green]ELITE[/bold green]" if anon_val == "Elite" else "[cyan]ANON[/cyan]"

            table.add_row(
                str(idx),
                proxy.address,
                proxy.protocol.value.upper(),
                ms_style,
                tier_style,
                anon_style,
            )

        console.print(table)
        console.print()
    else:
        console.print(f"[bold red]No working proxies found with latency <= {int(max_ms)}ms. Consider increasing max MS or testing more proxies.[/bold red]\n")

    # Output files listing
    files_info = "\n".join([f"  [*] [bold white]{key.upper()}:[/] [dim]{path}[/dim]" for key, path in file_paths.items()])
    console.print(Panel(files_info, title="[bold cyan]Saved Output Files[/bold cyan]", border_style="cyan", box=box.ROUNDED))
    console.print()


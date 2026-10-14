"""
File export and persistence utilities for verified proxies.
"""
from pathlib import Path
from typing import List, Dict, Optional

import config
from core.models import Proxy, ProxyProtocol, ProxyStatus



class ProxyStorage:
    """Handles saving working proxies into structured files."""

    def __init__(self, output_dir: Path = config.OUTPUT_DIR):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save_results(
        self,
        protocol: ProxyProtocol,
        working_proxies: List[Proxy],
        max_latency_ms: Optional[float] = None,
    ) -> Dict[str, Path]:
        """
        Saves proxies into a single clean text file: {protocol}_working.txt.
        Contains all verified proxies meeting the run criteria (status alive and latency <= max_latency_ms).
        """
        prefix = protocol.value
        working_file = self.output_dir / f"{prefix}_working.txt"

        # Filter strictly for alive proxies meeting max_latency_ms (if specified)
        valid_proxies = [
            p for p in working_proxies
            if p.status == ProxyStatus.ALIVE
            and (max_latency_ms is None or (p.latency_ms is not None and p.latency_ms <= max_latency_ms))
        ]
        # Sort by latency ascending
        valid_proxies.sort(key=lambda p: p.latency_ms if p.latency_ms is not None else float("inf"))

        # Deduplicate by address while preserving fastest latency entry
        seen = set()
        unique_valid = []
        for p in valid_proxies:
            if p.address not in seen:
                seen.add(p.address)
                unique_valid.append(p)

        # Write clean IP:Port list
        content = "\n".join([p.address for p in unique_valid]) + ("\n" if unique_valid else "")
        working_file.write_text(content, encoding="utf-8")

        return {"working": working_file}


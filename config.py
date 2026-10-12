"""
Global configuration settings for the Proxy Scraper & Checker.
"""
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"

# Network & Checker Settings
DEFAULT_TIMEOUT = 5.0          # Seconds to wait for a proxy response
DEFAULT_CONCURRENCY = 200      # Max simultaneous connections to test proxies
SCRAPER_TIMEOUT = 10.0         # Seconds to wait when fetching proxy lists from web sources

# Primary target endpoint: Cloudflare Edge (icanhazip) responds in ~40ms globally.
# Fallback: AWS CloudFront (checkip.amazonaws.com).
# This ensures ultra-fast, accurate RTT latency measurement without third-party rate limiting.
PRIMARY_TEST_URL = "http://icanhazip.com"
FALLBACK_TEST_URL = "http://checkip.amazonaws.com"

# Latency classification thresholds (in milliseconds)
FAST_LATENCY_THRESHOLD_MS = 600.0     # Under 600ms is considered fast
MEDIUM_LATENCY_THRESHOLD_MS = 1500.0  # 600ms - 1500ms is medium, above is slow

# Headers to use when scraping / checking
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

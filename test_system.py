"""
End-to-end validation test for Scraper and Checker modules.
"""
import asyncio
from core.models import Proxy, ProxyProtocol, ProxyStatus
from core.scraper import ProxyScraper
from core.checker import ProxyChecker
from utils.storage import ProxyStorage


async def test_scraper_and_checker():
    print("1. Testing Scraper for HTTP...")
    scraper = ProxyScraper(ProxyProtocol.HTTP)
    # Test scraping all or single source
    proxies = await scraper.scrape()
    print(f"Scraped {len(proxies)} HTTP candidate proxies!")
    assert len(proxies) > 0, "Scraper should return proxies from public sources"

    # Take first 20 candidate proxies to test checker quickly
    sample = proxies[:20]
    print(f"2. Testing Checker on a batch of {len(sample)} proxies with concurrency=10, timeout=3.0s...")
    checker = ProxyChecker(concurrency=10, timeout=3.0)

    checked = await checker.check_all(sample)
    print(f"Checker completed! Found {len(checked)} alive proxies in test sample.")
    for p in checked:
        print(f" -> Alive proxy: {p.address} | Latency: {p.latency_ms} ms | Tier: {p.speed_tier}")

    print("3. Testing Storage export...")
    storage = ProxyStorage()
    paths = storage.save_results(ProxyProtocol.HTTP, checked)
    print(f"Saved test results to: {paths}")
    print("ALL TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    asyncio.run(test_scraper_and_checker())

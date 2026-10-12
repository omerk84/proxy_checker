"""
Data models and enumerations representing proxies and their health statuses.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional
import config


class ProxyProtocol(str, Enum):
    HTTP = "http"
    SOCKS4 = "socks4"
    SOCKS5 = "socks5"

    @classmethod
    def from_choice(cls, choice: str) -> "ProxyProtocol":
        mapping = {
            "1": cls.HTTP,
            "http": cls.HTTP,
            "https": cls.HTTP,
            "2": cls.SOCKS4,
            "socks4": cls.SOCKS4,
            "3": cls.SOCKS5,
            "socks5": cls.SOCKS5,
        }
        val = mapping.get(choice.strip().lower())
        if not val:
            raise ValueError(f"Unknown proxy protocol choice: {choice}")
        return val


class ProxyStatus(str, Enum):
    PENDING = "PENDING"
    ALIVE = "ALIVE"
    DEAD = "DEAD"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"


@dataclass
class Proxy:
    host: str
    port: int
    protocol: ProxyProtocol
    latency_ms: Optional[float] = None
    status: ProxyStatus = ProxyStatus.PENDING
    error_message: Optional[str] = None
    anonymity: Optional[str] = None        # "Elite", "Anonymous", or "Transparent"
    supports_https: Optional[bool] = None  # True if verified to support HTTPS CONNECT

    @property
    def address(self) -> str:
        """Returns host:port string."""
        return f"{self.host}:{self.port}"

    @property
    def url(self) -> str:
        """Returns standard proxy URL, e.g. socks5://1.2.3.4:1080"""
        return f"{self.protocol.value}://{self.host}:{self.port}"

    @property
    def speed_tier(self) -> str:
        """Categorizes proxy speed based on configured thresholds."""
        if self.status != ProxyStatus.ALIVE or self.latency_ms is None:
            return "DEAD"
        if self.latency_ms <= config.FAST_LATENCY_THRESHOLD_MS:
            return "FAST"
        if self.latency_ms <= config.MEDIUM_LATENCY_THRESHOLD_MS:
            return "MEDIUM"
        return "SLOW"

    def __hash__(self):
        return hash((self.host, self.port, self.protocol))

    def __eq__(self, other):
        if not isinstance(other, Proxy):
            return False
        return (self.host, self.port, self.protocol) == (other.host, other.port, other.protocol)

"""
FREE INDIAN PROXY SERVICE
Fetches Indian HTTP proxies so Playwright on Render (Singapore)
appears as traffic from India to NIC portals.
"""

import asyncio
from typing import Optional, Dict
import structlog

logger = structlog.get_logger()

PROXY_LIST_URL = (
    "https://api.proxyscrape.com/v2/?"
    "request=displayproxies&protocol=http&timeout=3000&"
    "country=IN&ssl=all&anonymity=all"
)

FALLBACK_INDIAN_PROXIES = [
    "http://103.152.112.162:80",
    "http://103.241.227.106:8080",
    "http://103.174.102.130:8080",
    "http://117.250.3.238:8080",
]


class IndianProxyService:
    _cached_proxy: Optional[str] = None

    @classmethod
    async def get_working_indian_proxy(cls) -> Optional[Dict[str, str]]:
        from config.settings import settings

        custom = getattr(settings, "CUSTOM_INDIAN_PROXY", None)
        if custom and str(custom).strip():
            return {"server": str(custom).strip()}

        if cls._cached_proxy:
            return {"server": cls._cached_proxy}

        try:
            import httpx
            async with httpx.AsyncClient(timeout=4.0) as client:
                res = await client.get(PROXY_LIST_URL)
                if res.status_code == 200 and res.text.strip():
                    proxies = [
                        line.strip()
                        for line in res.text.strip().splitlines()
                        if line.strip()
                    ]
                    if proxies:
                        selected = f"http://{proxies[0]}"
                        cls._cached_proxy = selected
                        logger.info("indian_proxy_fetched", proxy=selected)
                        return {"server": selected}
        except Exception as e:
            logger.warning("proxy_fetch_failed", error=str(e))

        for fb in FALLBACK_INDIAN_PROXIES:
            cls._cached_proxy = fb
            logger.info("using_fallback_indian_proxy", proxy=fb)
            return {"server": fb}

        return None


def get_indian_proxy_sync() -> Optional[Dict[str, str]]:
    try:
        return asyncio.run(IndianProxyService.get_working_indian_proxy())
    except Exception:
        if FALLBACK_INDIAN_PROXIES:
            return {"server": FALLBACK_INDIAN_PROXIES[0]}
        return None
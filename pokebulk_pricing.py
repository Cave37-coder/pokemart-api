"""
PokéBulk SA — Pricing Utility
==============================
Live USD/ZAR rate with 3-source fallback chain.
Pricing formula: market_usd × zar_rate × 1.10, min R1.50, round UP to R0.50

Drop this file into your project root or products/ directory.
Import with: from pokebulk_pricing import get_live_zar_rate, pokebulk_price
"""

import math
import requests
import logging

logger = logging.getLogger(__name__)

# Fallback rate used ONLY if all 3 live sources fail
FALLBACK_ZAR_RATE = 18.50

# Pricing constants
MARKUP = 1.10       # 10% markup on market price
MINIMUM_ZAR = 1.50  # Minimum price in Rands
ROUND_NEAREST = 0.50  # Round UP to nearest R0.50


def get_live_zar_rate():
    """
    Fetch live USD/ZAR exchange rate.
    Tries 3 free sources in order — returns first successful result.
    No API key required for any source.

    Sources (in priority order):
    1. Frankfurter (European Central Bank data) — most reliable
    2. ExchangeRate-API (open tier) — good backup
    3. fawazahmed0 CDN — community-maintained, very stable

    Returns:
        float: USD/ZAR rate (e.g. 18.72)
    """
    sources = [
        {
            "name": "Frankfurter (ECB)",
            "url": "https://api.frankfurter.app/latest?from=USD&to=ZAR",
            "extract": lambda d: d["rates"]["ZAR"],
        },
        {
            "name": "ExchangeRate-API",
            "url": "https://open.er-api.com/v6/latest/USD",
            "extract": lambda d: d["rates"]["ZAR"],
        },
        {
            "name": "fawazahmed0 CDN",
            "url": "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json",
            "extract": lambda d: d["usd"]["zar"],
        },
    ]

    headers = {"User-Agent": "PokeBulkSA/1.0.0"}

    for source in sources:
        try:
            r = requests.get(source["url"], headers=headers, timeout=10)
            if r.status_code == 200:
                data = r.json()
                rate = float(source["extract"](data))
                # Sanity check: ZAR/USD should always be between 10 and 35
                if 10.0 < rate < 35.0:
                    logger.info(f"Live USD/ZAR: R{rate:.4f} (source: {source['name']})")
                    return rate
                else:
                    logger.warning(
                        f"Suspicious rate R{rate} from {source['name']} — trying next source"
                    )
        except Exception as e:
            logger.warning(f"FX source '{source['name']}' failed: {e}")

    logger.error(
        f"ALL 3 FX sources failed — using fallback rate R{FALLBACK_ZAR_RATE}. "
        f"Check internet connectivity."
    )
    return FALLBACK_ZAR_RATE


def pokebulk_price(market_usd, zar_rate):
    """
    Calculate the PokéBulk retail price in ZAR for a card variant.

    Formula:
        1. raw = market_usd × zar_rate × 1.10  (+10% markup)
        2. price = max(raw, R1.50)              (minimum R1.50)
        3. final = round UP to nearest R0.50

    Args:
        market_usd: TCGPlayer market price in USD (float or Decimal)
        zar_rate: Live USD/ZAR rate (float)

    Returns:
        float: Retail price in ZAR, rounded up to nearest R0.50

    Examples:
        pokebulk_price(0.05, 18.72) → 1.50   (minimum kicks in)
        pokebulk_price(0.10, 18.72) → 2.50
        pokebulk_price(1.00, 18.72) → 21.00
        pokebulk_price(10.00, 18.72) → 206.00
        pokebulk_price(579.25, 18.72) → 11928.00  (Charizard Base Set)
    """
    if not market_usd or float(market_usd) <= 0:
        return MINIMUM_ZAR

    raw = float(market_usd) * float(zar_rate) * MARKUP
    price = max(raw, MINIMUM_ZAR)

    # Round UP to nearest R0.50
    # math.ceil(price / 0.50) * 0.50 — equivalent to math.ceil(price * 2) / 2
    return math.ceil(price * 2) / 2


def price_card(market_usd, low_usd=None, zar_rate=None):
    """
    Full price calculation for a card variant.
    Fetches live ZAR rate if not provided.

    Args:
        market_usd: TCGPlayer market price in USD
        low_usd: TCGPlayer low price in USD (optional)
        zar_rate: USD/ZAR rate — if None, fetches live rate

    Returns:
        dict with keys: market_usd, low_usd, usd_zar_rate, pokebulk_zar
    """
    if zar_rate is None:
        zar_rate = get_live_zar_rate()

    return {
        "market_usd": float(market_usd) if market_usd else None,
        "low_usd": float(low_usd) if low_usd else None,
        "usd_zar_rate": round(zar_rate, 4),
        "pokebulk_zar": pokebulk_price(market_usd, zar_rate),
    }


if __name__ == "__main__":
    # Quick test when run directly
    print("Testing PokéBulk pricing utility...")
    rate = get_live_zar_rate()
    print(f"\nLive USD/ZAR rate: R{rate:.4f}")
    print(f"\n{'USD':>10}  {'Raw ZAR':>10}  {'PokeBulk ZAR':>14}")
    print("-" * 40)
    for usd in [0.01, 0.05, 0.10, 0.25, 0.50, 1.00, 2.50, 5.00, 10.00, 50.00, 100.00]:
        raw = usd * rate * 1.10
        final = pokebulk_price(usd, rate)
        print(f"${usd:>9.2f}  R{raw:>9.2f}  R{final:>12.2f}")

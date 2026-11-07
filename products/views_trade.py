"""
Poke-Trade (2026-11-07) -- Michael: "a trading app, keep 2 collections of
selected cards, so you can see relative values, based purely on current tcg
price ... must make making trades easy on trade day!"

Two read-only, public endpoints for the phone app at pokebulk.co.za/trade:

  GET /api/trade/search/?q=charizard+bs&page=2 -> cards matching every word, 40 a page
  GET /api/trade/prices/?ids=12,34,56          -> today's value for saved cards

Value = PokemonProduct.tcg_market_zar: the TCG market price in Rand with no
shop markup (written nightly by sync_prices_only). Until a row has been
through one nightly sync, it falls back to our shop price / 1.10 (the shop
price is market x rate x 1.10) -- except for hand-priced rows, whose shop
price says nothing about the market, which show as "TBC" (null).

No login, no cookies, nothing written: anyone at a trade day can use it.
"""
from decimal import Decimal

from django.db.models import Case, F, IntegerField, Q, Value, When
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import PokemonProduct

VARIANT_LABEL = {
    "N": "Normal", "H": "Holo", "RH": "Reverse Holo", "FE": "1st Edition",
    "PB": "Poke Ball", "MB": "Master Ball", "LB": "Love Ball", "FB": "Friend Ball",
    "QB": "Quick Ball", "UB": "Ultra Ball", "DB": "Dusk Ball", "TR": "Team Rocket",
    "SE": "Secret", "PBP": "Poke Ball Pattern", "MBP": "Master Ball Pattern",
    "CC": "Code Card", "TT": "Trick or Trade", "CH": "Cosmos Holo", "ESH": "Energy Symbol Holo",
    "HR-EX": "Illustration Rare", "EX": "Double Rare",
}
# WotC print runs (same rule as the site's lib/printing.ts).
FIRST_ED_SETS = {"BSS", "JU", "FO", "TR", "G1", "G2", "N1", "N2", "N3", "N4"}
PAGE_SIZE = 40
MAX_IDS = 300


def _variant_label(p):
    v = p.variant_override or "N"
    code = p.card_set.code if p.card_set else ""
    holo = v == "H" or "holo" in (p.rarity or "")
    if v == "FE":
        return "1st Edition Holo" if "holo" in (p.rarity or "") else "1st Edition"
    if code == "BSS" and v in ("N", "H"):
        return "Shadowless Holo" if holo else "Shadowless"
    if (code == "BS" or code in FIRST_ED_SETS) and v in ("N", "H"):
        return "Unlimited Holo" if holo else "Unlimited"
    return VARIANT_LABEL.get(v, v)


def _tcg_zar(p):
    if p.tcg_market_zar is not None:
        return float(p.tcg_market_zar) if p.tcg_market_zar > 0 else None
    if p.price and p.price > 0 and not p.price_locked and not p.sell_pct:
        return float((p.price / Decimal("1.10")).quantize(Decimal("0.01")))
    return None


def _number(p):
    if p.number:
        return p.number
    if p.card_number is None:
        return ""
    total = p.card_set.total_cards if p.card_set else None
    return f"{p.card_number:03d}/{total:03d}" if total else str(p.card_number)


def _row(p):
    return {
        "id": p.id,
        "name": p.name,
        "set_code": p.card_set.code if p.card_set else "",
        "set_name": p.card_set.name if p.card_set else "",
        "number": _number(p),
        "variant": p.variant_override or "N",
        "variant_label": _variant_label(p),
        "rarity": (p.rarity or "").replace("_", " ").title(),
        "image": p.image_small_url or p.image_url or "",
        "tcg_zar": _tcg_zar(p),
    }


def _base_qs():
    return (PokemonProduct.objects
            .select_related("card_set")
            .filter(condition="NM", is_active=True, card_set__isnull=False))


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def trade_search(request):
    q = (request.query_params.get("q") or "").strip()
    words = [w for w in q.split() if w][:6]
    if not words or len(q) < 2:
        return Response({"results": [], "total_matches": 0, "page": 1, "pages": 0, "page_size": PAGE_SIZE})

    qs = _base_qs()
    for w in words:
        cond = Q(name__icontains=w) | Q(card_set__code__iexact=w) | Q(card_set__name__icontains=w) | Q(number__istartswith=w)
        num = w.split("/")[0]
        if num.isdigit():
            cond |= Q(card_number=int(num))
        qs = qs.filter(cond)

    total = qs.count()
    pages = max(1, -(-total // PAGE_SIZE))
    try:
        page = min(max(1, int(request.query_params.get("page", 1))), pages)
    except (TypeError, ValueError):
        page = 1
    # Names starting with the first word first (so "pikachu" lists Pikachu
    # before "Ash's Pikachu"), then newest sets, then card number / print order.
    qs = qs.annotate(starts=Case(When(name__istartswith=words[0], then=Value(0)), default=Value(1),
                                 output_field=IntegerField()))
    qs = qs.order_by("starts", F("card_set__release_date").desc(nulls_last=True), "card_number", "variant_sort", "id")
    start = (page - 1) * PAGE_SIZE
    rows = qs[start:start + PAGE_SIZE]
    return Response({"results": [_row(p) for p in rows], "total_matches": total,
                     "page": page, "pages": pages, "page_size": PAGE_SIZE})


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def trade_prices(request):
    ids = []
    for part in (request.query_params.get("ids") or "").split(","):
        part = part.strip()
        if part.isdigit():
            ids.append(int(part))
    ids = ids[:MAX_IDS]
    if not ids:
        return Response({"prices": {}})
    out = {}
    for p in PokemonProduct.objects.select_related("card_set").filter(id__in=ids):
        out[str(p.id)] = _tcg_zar(p)
    return Response({"prices": out})

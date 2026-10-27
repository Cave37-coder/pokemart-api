"""
products/card_info.py -- turn a TCGCSV product's extendedData into
PokemonProduct fields, and re-host its image on R2 (2026-10-27).

Used by sync_promos and sync_blister_cosmos so new cards arrive with their
full card info (type, HP, stage, attacks with energy cost, weakness,
resistance, retreat, card text) rather than just name/number/price.

TCGCSV extendedData names (Pokemon, category 3): Number, Rarity, Card Type,
HP, Stage, CardText, Attack 1..4, Weakness, Resistance, RetreatCost.
Formats seen:
    Attack 1   "[DD] Dusk Raid (110+)<br> If your Benched Pokemon have..."
    Weakness   "Gx2"      Resistance "F-30"     RetreatCost "2"
Energy letters follow the standard TCG shorthand.
"""
import html
import re

ENERGY = {
    "G": "Grass", "R": "Fire", "W": "Water", "L": "Lightning", "P": "Psychic",
    "F": "Fighting", "D": "Darkness", "M": "Metal", "Y": "Fairy", "N": "Dragon",
    "C": "Colorless", "0": "",
}
TRAINER_TYPES = {"supporter", "item", "stadium", "pokemon tool", "tool", "trainer", "technical machine"}


def ext(extended_data, name):
    for item in extended_data or []:
        if item.get("name") == name:
            return (item.get("value") or "").strip()
    return ""


def _clean(text):
    text = re.sub(r"<br\s*/?>", "\n", text or "", flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    return "\n".join(line.strip() for line in text.splitlines()).strip()


def parse_attack(raw):
    """'[DD] Dusk Raid (110+)<br> text' -> (cost 'Darkness,Darkness', name, damage, text)."""
    raw = _clean(raw)
    if not raw:
        return "", "", "", ""
    first, _, rest = raw.partition("\n")
    cost = ""
    m = re.match(r"^\[([^\]]*)\]\s*", first)
    if m:
        parts = []
        for ch in m.group(1):
            if ch.isdigit():  # older notation: "[1L]" = 1 Colorless + Lightning
                parts += ["Colorless"] * int(ch)
            elif ENERGY.get(ch.upper()):
                parts.append(ENERGY[ch.upper()])
        cost = ",".join(parts)
        first = first[m.end():]
    damage = ""
    m = re.search(r"\(([0-9]+[+x×\-]?)\)\s*$", first)
    if m:
        damage = m.group(1)
        first = first[:m.start()]
    return cost, first.strip(), damage, rest.strip()


def parse_weak_res(raw):
    """'Gx2' -> ('Grass','x2');  'F-30' -> ('Fighting','-30')."""
    raw = (raw or "").strip()
    m = re.match(r"^([A-Za-z])\s*([x×+\-]\s*\d+)$", raw)
    if not m:
        return "", ""
    return ENERGY.get(m.group(1).upper(), ""), m.group(2).replace(" ", "").replace("×", "x")


def card_fields(extended_data):
    """Model field values for a card (only keys with a real value)."""
    e = lambda n: ext(extended_data, n)
    f = {}
    card_type = e("Card Type")
    stage = e("Stage")
    if e("HP").isdigit():
        f["hp"] = int(e("HP"))
    if stage:
        f["stage"] = stage
    # supertype convention on this site: Pokemon rows carry their stage,
    # Trainer/Energy rows carry the trainer kind (see data-model notes).
    if card_type and card_type.lower() in TRAINER_TYPES:
        f["supertype"] = card_type
    elif stage:
        f["supertype"] = stage
    text = _clean(e("CardText"))
    if text:
        f["description"] = text
        m = re.match(r"^(?:Ability|Poké-POWER|Poke-POWER|Poké-BODY|Poke-BODY)\s*:?\s*(.+?)\n(.+)$", text, re.S)
        if m:
            f["ability_type"] = "Ability"
            f["ability_name"] = m.group(1).strip()
            f["ability_text"] = m.group(2).strip()
    for i in (1, 2, 3):
        cost, name, dmg, txt = parse_attack(e(f"Attack {i}"))
        if name:
            f[f"attack_{i}_name"] = name[:200]
            f[f"attack_{i}_cost"] = cost[:80]
            f[f"attack_{i}_damage"] = dmg[:20]
            f[f"attack_{i}_text"] = txt
    wt, wv = parse_weak_res(e("Weakness"))
    if wt:
        f["weakness_type"], f["weakness_value"] = wt, wv
    rt, rv = parse_weak_res(e("Resistance"))
    if rt:
        f["resistance_type"], f["resistance_value"] = rt, rv
    if e("RetreatCost").isdigit():
        f["retreat_cost"] = int(e("RetreatCost"))
    f["_card_type"] = card_type  # energy type for pokemon_types (handled by caller)
    return f


def apply_fields(product, fields, only_blank=True):
    """Copy parsed fields onto product. With only_blank, never overwrite
    something already filled in (e.g. by Serebii/Bulbapedia enrichment).
    Returns the list of field names changed."""
    changed = []
    for k, v in fields.items():
        if k.startswith("_") or v in ("", None):
            continue
        cur = getattr(product, k, None)
        if only_blank and cur not in ("", None, 0):
            continue
        if cur != v:
            setattr(product, k, v)
            changed.append(k)
    return changed


def set_types(product, card_type):
    """Add the energy type (e.g. 'Darkness') to pokemon_types if that type exists."""
    if not card_type or card_type.lower() in TRAINER_TYPES:
        return
    from products.models import PokemonType
    t = PokemonType.objects.filter(name__iexact=card_type).first()
    if t and not product.pokemon_types.filter(pk=t.pk).exists():
        product.pokemon_types.add(t)


def rehost_card_image(product, source_url):
    """Download a card image (TCGplayer CDN etc.) and store it on R2 under
    the existing key scheme cards/{set}_{pid}_{variant}.jpg (CLAUDE.md: always
    R2). Returns the R2 URL, or '' if the source has no image."""
    import requests
    from products.admin import _r2_client, R2_BUCKET, R2_CDN
    if not source_url:
        return ""
    if source_url.startswith(R2_CDN):
        return source_url
    resp = requests.get(source_url, timeout=20, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"})
    if resp.status_code in (403, 404) or not resp.content:
        return ""
    resp.raise_for_status()
    set_code = (product.card_set.code if product.card_set_id else "unknown").lower()
    pid = product.tcgcsv_product_id or product.pk
    variant = (product.variant_override or "n").lower()
    ext_ = "png" if "png" in resp.headers.get("Content-Type", "") else "jpg"
    key = f"cards/{set_code}_{pid}_{variant}.{ext_}"
    _r2_client().put_object(Bucket=R2_BUCKET, Key=key, Body=resp.content,
                            ContentType="image/png" if ext_ == "png" else "image/jpeg")
    return f"{R2_CDN}/{key}"


def tcgplayer_image(pid, size="400w"):
    """TCGplayer CDN image for a product id ('200w' always exists when any
    image does; '400w' is sharper and used first)."""
    return f"https://tcgplayer-cdn.tcgplayer.com/product/{pid}_{size}.jpg"

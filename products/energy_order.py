"""
Energy ordering (Michael, 2026-11-16): Energies always list in this type order, then variants:
1 Grass, 2 Fire, 3 Water, 4 Lightning (Electric), 5 Psychic, 6 Fighting, 7 Darkness, 8 Fairy, 9 Metal (Steel),
then 10 Dragon and 11 Colorless (not official basics, but they have Special Energies).

energy_rank(name): 0-10 for a basic Energy, 20-30 for a typed Special Energy ("Growing Grass", "Telepathic Psychic",
"Double Colorless" ...), 40 for anything else ("Rainbow", "Twin" ...). Used by the checklist generator and the
buy-in / Manual Invoice set browsers for the per-era Energy sets.
"""
import re

TYPE_ORDER = ["grass", "fire", "water", "lightning", "psychic", "fighting", "darkness", "fairy", "metal", "dragon", "colorless"]
ALIASES = {"electric": "lightning", "dark": "darkness", "steel": "metal"}
# Kalos-style one-letter specials: "Bubbly W Energy", "Nitro R Energy", "Magnetic M Energy" ...
LETTERS = {"g": "grass", "r": "fire", "w": "water", "l": "lightning", "p": "psychic", "f": "fighting",
           "d": "darkness", "y": "fairy", "m": "metal", "n": "dragon", "c": "colorless"}

ERA_ENERGY_SET_CODES = {"MEE", "SVE", "SWSHE", "SME", "XYE", "BWE", "HGSSE", "DPE", "EXE", "WOTCOE", "WOTCLE", "WOTCNE", "WOTCE"}

_WORDS = "|".join(TYPE_ORDER + list(ALIASES))
_BASIC = re.compile(rf"^(?:basic\s+)?({_WORDS})\s+energy$")
_TYPED = re.compile(rf"\b({_WORDS})\b")
_LETTER = re.compile(r"\b([grwlpfdymnc])\s+energy$")


def _clean(name):
    n = re.sub(r"\s*\[[^\]]*\]", "", name or "")
    pats = (r"\s*-\s*\d+(/\d+)?\s*$", r"\s*\((?:[^()]|\([^()]*\))*\)\s*$")
    changed = True
    while changed:
        changed = False
        for p in pats:
            m = re.sub(p, "", n)
            if m != n:
                n, changed = m, True
    return n.strip().lower()


def _type_index(word):
    return TYPE_ORDER.index(ALIASES.get(word, word))


def energy_rank(name):
    n = _clean(name)
    m = _BASIC.match(n)
    if m:
        return _type_index(m.group(1))
    m = _TYPED.search(n) or None
    if m:
        return 20 + _type_index(m.group(1))
    m = _LETTER.search(n)
    if m:
        return 20 + TYPE_ORDER.index(LETTERS[m.group(1)])
    return 40


def browse_sort_key(p):
    """Sort key for a PokemonProduct in an era Energy set: oldest home-set release first, then home set,
    then Energy type order, then card number and variant."""
    cs = p.card_set
    rel = str(cs.release_date) if cs and cs.release_date else "9999-12-31"
    return (rel, cs.code if cs else "", energy_rank(p.name), p.card_number or 0, p.variant_sort or 9, p.name)

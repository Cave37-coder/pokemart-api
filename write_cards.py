content = '''
import { Suspense } from "react"
import Link from "next/link"

const API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000"
const PAGE_SIZE = 60

async function getCards(params: Record<string, string>) {
  const qs = new URLSearchParams({
    page: params.page || "1",
    page_size: String(PAGE_SIZE),
    ...(params.set && { card_set__code: params.set }),
    ...(params.era && { card_set__era__code: params.era }),
    ...(params.type && { pokemon_types__name: params.type }),
    ...(params.rarity && { rarity: params.rarity }),
    ...(params.search && { search: params.search }),
  })
  const res = await fetch(`${API}/api/products/?${qs}`, { cache: "no-store" })
  if (!res.ok) return { results: [], count: 0 }
  return res.json()
}

async function getSets() {
  const res = await fetch(`${API}/api/sets/`, { cache: "no-store" })
  if (!res.ok) return []
  return res.json()
}

async function getEras() {
  const res = await fetch(`${API}/api/eras/`, { cache: "no-store" })
  if (!res.ok) return []
  return res.json()
}

async function getTypes() {
  const res = await fetch(`${API}/api/types/`, { cache: "no-store" })
  if (!res.ok) return []
  return res.json()
}

const RARITY_LABELS: Record<string, string> = {
  common: "Common",
  uncommon: "Uncommon",
  rare: "Rare",
  holo_rare: "Holo Rare",
  ultra_rare: "Ultra Rare",
  illustration_rare: "IR",
  special_illustration_rare: "SIR",
  hyper_rare: "HR",
  mega_hyper_rare: "MHR",
  mega_attack_rare: "MAR",
  secret_rare: "Secret Rare",
  legendary: "Legendary",
  ace_spec: "ACE SPEC",
  gold_star: "Gold Star",
  shining: "Shining",
}

const RARITY_COLORS: Record<string, string> = {
  common: "#9ca3af",
  uncommon: "#6ee7b7",
  rare: "#60a5fa",
  holo_rare: "#a78bfa",
  ultra_rare: "#f59e0b",
  illustration_rare: "#f97316",
  special_illustration_rare: "#ec4899",
  hyper_rare: "#ef4444",
  mega_hyper_rare: "#dc2626",
  mega_attack_rare: "#7c3aed",
  secret_rare: "#fbbf24",
  legendary: "#d97706",
  ace_spec: "#0ea5e9",
  gold_star: "#eab308",
  shining: "#a3e635",
}

const TYPE_COLORS: Record<string, string> = {
  Fire: "#ef4444",
  Water: "#3b82f6",
  Grass: "#22c55e",
  Lightning: "#eab308",
  Psychic: "#a855f7",
  Fighting: "#f97316",
  Darkness: "#374151",
  Metal: "#6b7280",
  Dragon: "#6366f1",
  Colorless: "#d1d5db",
  Fairy: "#ec4899",
}

export default async function CardsPage({
  searchParams,
}: {
  searchParams: Record<string, string>
}) {
  const page = parseInt(searchParams.page || "1")
  const [data, sets, eras, types] = await Promise.all([
    getCards(searchParams),
    getSets(),
    getEras(),
    getTypes(),
  ])

  const cards = data.results || []
  const total = data.count || 0
  const totalPages = Math.ceil(total / PAGE_SIZE)

  function buildUrl(overrides: Record<string, string>) {
    const p = { ...searchParams, ...overrides }
    Object.keys(p).forEach((k) => !p[k] && delete p[k])
    return "/cards?" + new URLSearchParams(p).toString()
  }

  const PaginationBar = () => {
    if (totalPages <= 1) return null
    const pages: (number | "...")[] = []
    if (totalPages <= 7) {
      for (let i = 1; i <= totalPages; i++) pages.push(i)
    } else {
      pages.push(1)
      if (page > 3) pages.push("...")
      for (let i = Math.max(2, page - 1); i <= Math.min(totalPages - 1, page + 1); i++) pages.push(i)
      if (page < totalPages - 2) pages.push("...")
      pages.push(totalPages)
    }
    return (
      <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap", justifyContent: "center" }}>
        {page > 1 && (
          <Link href={buildUrl({ page: String(page - 1) })} style={paginBtn}>← Prev</Link>
        )}
        {pages.map((p, i) =>
          p === "..." ? (
            <span key={i} style={{ color: "#6b7280", padding: "0 4px" }}>…</span>
          ) : (
            <Link
              key={p}
              href={buildUrl({ page: String(p) })}
              style={{ ...paginBtn, ...(p === page ? paginActive : {}) }}
            >
              {p}
            </Link>
          )
        )}
        {page < totalPages && (
          <Link href={buildUrl({ page: String(page + 1) })} style={paginBtn}>Next →</Link>
        )}
      </div>
    )
  }

  return (
    <div style={{ minHeight: "100vh", background: "#0f0f0f", color: "#e5e7eb" }}>
      {/* Header */}
      <div style={{ background: "#1a1a2e", borderBottom: "1px solid #2d2d4e", padding: "16px 24px", display: "flex", alignItems: "center", gap: 16 }}>
        <Link href="/" style={{ color: "#f59e0b", fontWeight: 700, fontSize: 20, textDecoration: "none" }}>
          🃏 PokéBulk SA
        </Link>
        <span style={{ color: "#6b7280" }}>/</span>
        <span style={{ color: "#e5e7eb" }}>Browse Cards</span>
        <div style={{ marginLeft: "auto", background: "#2d2d4e", borderRadius: 8, padding: "6px 12px", fontSize: 14, color: "#9ca3af" }}>
          {total.toLocaleString()} cards found
        </div>
      </div>

      <div style={{ display: "flex", maxWidth: 1600, margin: "0 auto" }}>
        {/* Sidebar Filters */}
        <aside style={{ width: 220, minWidth: 220, padding: "20px 16px", borderRight: "1px solid #1f2937", position: "sticky", top: 0, height: "100vh", overflowY: "auto" }}>

          {/* Search */}
          <form method="GET" action="/cards">
            <div style={filterSection}>
              <div style={filterLabel}>Search</div>
              <input
                name="search"
                defaultValue={searchParams.search || ""}
                placeholder="Pokémon name..."
                style={inputStyle}
              />
            </div>

            {/* Era */}
            <div style={filterSection}>
              <div style={filterLabel}>Era</div>
              <select name="era" defaultValue={searchParams.era || ""} style={selectStyle}>
                <option value="">All Eras</option>
                {eras.map((e: any) => (
                  <option key={e.code} value={e.code}>{e.name}</option>
                ))}
              </select>
            </div>

            {/* Set */}
            <div style={filterSection}>
              <div style={filterLabel}>Set</div>
              <select name="set" defaultValue={searchParams.set || ""} style={selectStyle}>
                <option value="">All Sets</option>
                {sets.map((s: any) => (
                  <option key={s.code} value={s.code}>{s.code} — {s.name}</option>
                ))}
              </select>
            </div>

            {/* Type */}
            <div style={filterSection}>
              <div style={filterLabel}>Energy Type</div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {(types.length > 0 ? types : Object.keys(TYPE_COLORS)).map((t: any) => {
                  const name = typeof t === "string" ? t : t.name
                  const color = TYPE_COLORS[name] || "#6b7280"
                  const active = searchParams.type === name
                  return (
                    <button
                      key={name}
                      type="submit"
                      name="type"
                      value={active ? "" : name}
                      style={{
                        background: active ? color : "transparent",
                        border: `1px solid ${color}`,
                        borderRadius: 6,
                        padding: "3px 8px",
                        fontSize: 11,
                        color: active ? "#000" : color,
                        cursor: "pointer",
                        fontWeight: active ? 700 : 400,
                      }}
                    >
                      {name}
                    </button>
                  )
                })}
              </div>
            </div>

            {/* Rarity */}
            <div style={filterSection}>
              <div style={filterLabel}>Rarity</div>
              <select name="rarity" defaultValue={searchParams.rarity || ""} style={selectStyle}>
                <option value="">All Rarities</option>
                {Object.entries(RARITY_LABELS).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </div>

            <input type="hidden" name="page" value="1" />
            <button type="submit" style={applyBtn}>Apply Filters</button>
            <a href="/cards" style={{ display: "block", textAlign: "center", marginTop: 8, color: "#6b7280", fontSize: 13 }}>Clear All</a>
          </form>
        </aside>

        {/* Main Content */}
        <main style={{ flex: 1, padding: "20px 24px" }}>
          {/* Top pagination */}
          <div style={{ marginBottom: 20 }}>
            <PaginationBar />
            <div style={{ textAlign: "center", color: "#6b7280", fontSize: 13, marginTop: 8 }}>
              Page {page} of {totalPages} — showing {cards.length} of {total.toLocaleString()} cards
            </div>
          </div>

          {/* Grid */}
          {cards.length === 0 ? (
            <div style={{ textAlign: "center", padding: 80, color: "#6b7280" }}>
              <div style={{ fontSize: 48 }}>🃏</div>
              <div style={{ marginTop: 16, fontSize: 18 }}>No cards found</div>
              <a href="/cards" style={{ color: "#f59e0b", marginTop: 8, display: "block" }}>Clear filters</a>
            </div>
          ) : (
            <div style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))",
              gap: 16,
            }}>
              {cards.map((card: any) => {
                const rarityColor = RARITY_COLORS[card.rarity] || "#6b7280"
                const rarityLabel = RARITY_LABELS[card.rarity] || card.rarity
                return (
                  <Link
                    key={card.id}
                    href={`/cards/${card.id}`}
                    style={{ textDecoration: "none" }}
                  >
                    <div style={{
                      background: "#1a1a2e",
                      border: `1px solid #2d2d4e`,
                      borderRadius: 12,
                      overflow: "hidden",
                      transition: "border-color 0.2s",
                      cursor: "pointer",
                    }}
                      onMouseEnter={e => (e.currentTarget.style.borderColor = rarityColor)}
                      onMouseLeave={e => (e.currentTarget.style.borderColor = "#2d2d4e")}
                    >
                      {/* Card image */}
                      <div style={{ position: "relative", background: "#0f0f0f", aspectRatio: "3/4" }}>
                        {card.image_small_url || card.image_url ? (
                          <img
                            src={card.image_small_url || card.image_url}
                            alt={card.name}
                            style={{ width: "100%", height: "100%", objectFit: "contain" }}
                          />
                        ) : (
                          <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center", color: "#374151", fontSize: 32 }}>
                            🃏
                          </div>
                        )}
                        {/* Rarity badge */}
                        <div style={{
                          position: "absolute", top: 6, right: 6,
                          background: rarityColor + "22",
                          border: `1px solid ${rarityColor}`,
                          borderRadius: 4, padding: "2px 5px",
                          fontSize: 9, color: rarityColor, fontWeight: 700,
                        }}>
                          {rarityLabel}
                        </div>
                      </div>

                      {/* Card info */}
                      <div style={{ padding: "8px 10px" }}>
                        <div style={{ fontSize: 12, fontWeight: 600, color: "#e5e7eb", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {card.name}
                        </div>
                        <div style={{ fontSize: 10, color: "#6b7280", marginTop: 2 }}>
                          {card.card_set?.code} #{String(card.card_number || "").padStart(3, "0")}
                        </div>
                        <div style={{ fontSize: 13, color: "#f59e0b", fontWeight: 700, marginTop: 4 }}>
                          R{Number(card.price).toFixed(2)}
                        </div>
                        <button style={{
                          width: "100%", marginTop: 6,
                          background: card.stock > 0 ? "#f59e0b" : "#374151",
                          color: card.stock > 0 ? "#000" : "#6b7280",
                          border: "none", borderRadius: 6, padding: "5px 0",
                          fontSize: 11, fontWeight: 700, cursor: card.stock > 0 ? "pointer" : "default",
                        }}>
                          {card.stock > 0 ? "Add to Pile 🃏" : "Out of Stock"}
                        </button>
                      </div>
                    </div>
                  </Link>
                )
              })}
            </div>
          )}

          {/* Bottom pagination */}
          <div style={{ marginTop: 40, paddingTop: 24, borderTop: "1px solid #1f2937" }}>
            <PaginationBar />
            <div style={{ textAlign: "center", color: "#6b7280", fontSize: 13, marginTop: 8 }}>
              Page {page} of {totalPages} — {total.toLocaleString()} total cards
            </div>
          </div>
        </main>
      </div>
    </div>
  )
}

// Styles
const filterSection: React.CSSProperties = { marginBottom: 20 }
const filterLabel: React.CSSProperties = { fontSize: 11, fontWeight: 700, color: "#6b7280", textTransform: "uppercase", letterSpacing: 1, marginBottom: 8 }
const inputStyle: React.CSSProperties = { width: "100%", background: "#0f0f0f", border: "1px solid #374151", borderRadius: 6, padding: "7px 10px", color: "#e5e7eb", fontSize: 13, boxSizing: "border-box" }
const selectStyle: React.CSSProperties = { width: "100%", background: "#0f0f0f", border: "1px solid #374151", borderRadius: 6, padding: "7px 10px", color: "#e5e7eb", fontSize: 13 }
const applyBtn: React.CSSProperties = { width: "100%", background: "#f59e0b", color: "#000", border: "none", borderRadius: 8, padding: "9px 0", fontWeight: 700, fontSize: 14, cursor: "pointer", marginTop: 4 }
const paginBtn: React.CSSProperties = { background: "#1a1a2e", border: "1px solid #374151", borderRadius: 6, padding: "6px 12px", color: "#e5e7eb", fontSize: 13, textDecoration: "none", cursor: "pointer" }
const paginActive: React.CSSProperties = { background: "#f59e0b", color: "#000", borderColor: "#f59e0b", fontWeight: 700 }
'''

with open(r"C:\\Users\\texca\\pokemart-frontend\\src\\app\\cards\\page.tsx", "w", encoding="utf-8") as f:
    f.write(content)
print("cards/page.tsx written!")
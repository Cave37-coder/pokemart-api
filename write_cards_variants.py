content = r'''import Link from "next/link";
import { getCards } from "@/lib/api";

const ERAS = [
  { label: "All", value: "" },
  { label: "WotC", value: "B1" },
  { label: "EX Era", value: "B2" },
  { label: "D&P", value: "B3" },
  { label: "B&W", value: "B4" },
  { label: "XY", value: "B5" },
  { label: "Sun & Moon", value: "B6" },
  { label: "Sword & Shield", value: "B7" },
  { label: "Scarlet & Violet", value: "B8" },
  { label: "Mega Era", value: "ME" },
];

const ENERGY_TYPES = [
  { label: "🌿 Grass", value: "Grass", color: "#4ade80" },
  { label: "🔥 Fire", value: "Fire", color: "#f97316" },
  { label: "💧 Water", value: "Water", color: "#38bdf8" },
  { label: "⚡ Lightning", value: "Lightning", color: "#facc15" },
  { label: "🔮 Psychic", value: "Psychic", color: "#c084fc" },
  { label: "🤺 Fighting", value: "Fighting", color: "#fb923c" },
  { label: "🌑 Darkness", value: "Darkness", color: "#94a3b8" },
  { label: "⚙️ Metal", value: "Metal", color: "#cbd5e1" },
  { label: "🐉 Dragon", value: "Dragon", color: "#818cf8" },
  { label: "⭐ Colorless", value: "Colorless", color: "#e2e8f0" },
];

const SUPERTYPES = [
  { label: "Pokémon", value: "Pokemon" },
  { label: "Trainer", value: "Trainer" },
  { label: "Energy", value: "Energy" },
];

const RARITIES = [
  { value: "", label: "All Rarities" },
  { value: "common", label: "Common" },
  { value: "uncommon", label: "Uncommon" },
  { value: "rare", label: "Rare" },
  { value: "holo_rare", label: "Holo Rare" },
  { value: "ultra_rare", label: "Ultra Rare" },
  { value: "secret_rare", label: "Secret Rare" },
  { value: "illustration_rare", label: "Illus. Rare ★" },
  { value: "special_illustration_rare", label: "Special Illus. ★★" },
  { value: "hyper_rare", label: "Hyper Rare ★★★" },
];

const SORT_OPTIONS = [
  { value: "card_number", label: "Card # (low→high)" },
  { value: "-card_number", label: "Card # (high→low)" },
  { value: "price", label: "Price (low→high)" },
  { value: "-price", label: "Price (high→low)" },
  { value: "name", label: "Name A→Z" },
];

// ─── Variant badge system ───────────────────────────────────────────────────

type VariantKey = "N"|"H"|"RH"|"ERH"|"RH-PB"|"RH-MB"|"BRH-FB"|"BRH-LB"|"BRH-QB"|"BRH-DB"|"BRH-R"|"DR"|"AS"|"MH"|"1ST"|"IR"|"SIR"|"HR";

function getVariantKey(card: {
  variant_override: string;
  rarity: string;
  price_first_edition: string | null;
}): VariantKey {
  const v = card.variant_override;
  const r = card.rarity;
  if (card.price_first_edition) return "1ST";
  if (v === "H") return "H";
  if (v === "RH") return "RH";
  if (v === "ERH") return "ERH";
  if (v === "RH-PB") return "RH-PB";
  if (v === "RH-MB") return "RH-MB";
  if (v === "BRH-FB") return "BRH-FB";
  if (v === "BRH-LB") return "BRH-LB";
  if (v === "BRH-QB") return "BRH-QB";
  if (v === "BRH-DB") return "BRH-DB";
  if (v === "BRH-R") return "BRH-R";
  if (v === "DR") return "DR";
  if (v === "AS") return "AS";
  if (v === "MH") return "MH";
  if (r === "illustration_rare") return "IR";
  if (r === "special_illustration_rare") return "SIR";
  if (r === "hyper_rare") return "HR";
  return "N";
}

// Border color and width per variant
const VARIANT_BORDER: Record<VariantKey, { color: string; width: string }> = {
  N:       { color: "#2a2a3a", width: "1px" },
  H:       { color: "#BA7517", width: "1px" },
  RH:      { color: "#7F77DD", width: "1px" },
  ERH:     { color: "#0F6E56", width: "1px" },
  "RH-PB": { color: "#A32D2D", width: "1px" },
  "RH-MB": { color: "#534AB7", width: "1px" },
  "BRH-FB":{ color: "#3B6D11", width: "1px" },
  "BRH-LB":{ color: "#993556", width: "1px" },
  "BRH-QB":{ color: "#854F0B", width: "1px" },
  "BRH-DB":{ color: "#085041", width: "1px" },
  "BRH-R": { color: "#A32D2D", width: "1px" },
  DR:      { color: "#888780", width: "1px" },
  AS:      { color: "#7F77DD", width: "1px" },
  MH:      { color: "#378ADD", width: "1px" },
  "1ST":   { color: "#0F6E56", width: "1px" },
  IR:      { color: "#BA7517", width: "1px" },
  SIR:     { color: "#BA7517", width: "2px" },
  HR:      { color: "#7F77DD", width: "2px" },
};

// Overlay rendered on top of the card image
function VariantOverlay({ vk }: { vk: VariantKey }) {
  const badge = (label: string, bg: string, color: string, pos: "tr"|"tl" = "tr") => (
    <div style={{
      position: "absolute",
      ...(pos === "tr" ? { top: 5, right: 5 } : { top: 5, left: 5 }),
      background: bg, color,
      fontSize: 9, fontWeight: 600,
      padding: "2px 6px", borderRadius: 10, zIndex: 4,
      letterSpacing: "0.3px", lineHeight: 1.4,
    }}>{label}</div>
  );

  const diag = (rgba: string) => (
    <div style={{
      position: "absolute", inset: 0, zIndex: 1, pointerEvents: "none",
      background: `repeating-linear-gradient(45deg,transparent,transparent 5px,${rgba} 5px,${rgba} 6px)`,
    }} />
  );

  const ball = (top: string, bot: string, line: string, dot?: string, stripe?: boolean, heart?: boolean) => {
    if (heart) return (
      <div style={{ position: "absolute", bottom: 5, right: 5, zIndex: 3 }}>
        <svg width="18" height="16" viewBox="0 0 18 16">
          <path d="M9 14C3.5 9.5 1 7 1 4.2 1 2.2 2.8 1 5 1c1.8 0 3.2 1.2 4 2.5C9.8 2.2 11.2 1 13 1c2.2 0 4 1.2 4 3.2C17 7 14.5 9.5 9 14Z" fill={top}/>
        </svg>
      </div>
    );
    return (
      <div style={{ position: "absolute", bottom: 5, right: 5, width: 18, height: 18, borderRadius: "50%", overflow: "hidden", border: "0.5px solid #33333355", zIndex: 3 }}>
        <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: "50%", background: top }} />
        <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, height: "50%", background: bot }} />
        <div style={{ position: "absolute", top: "50%", left: 0, right: 0, height: 1, background: line, transform: "translateY(-50%)" }} />
        {dot && <div style={{ position: "absolute", top: 2, left: "50%", transform: "translateX(-50%)", width: 5, height: 5, borderRadius: "50%", background: dot }} />}
        {stripe && <div style={{ position: "absolute", top: 1, right: 3, width: 3, height: 7, background: top, borderRadius: 1 }} />}
      </div>
    );
  };

  const stars = (count: number, colors: string[]) => (
    <div style={{ position: "absolute", bottom: 6, left: "50%", transform: "translateX(-50%)", display: "flex", gap: 2, zIndex: 3 }}>
      {Array.from({ length: count }).map((_, i) => (
        <span key={i} style={{ fontSize: 11, color: colors[i] || colors[0], lineHeight: 1 }}>★</span>
      ))}
    </div>
  );

  const aceBorder = (
    <div style={{
      position: "absolute", inset: 3, borderRadius: 3, zIndex: 2, pointerEvents: "none",
      border: "1.5px solid transparent",
      backgroundImage: "linear-gradient(#0000,#0000),linear-gradient(135deg,#e24b4a,#ef9f27,#639922,#1d9e75,#378add,#7f77dd)",
      backgroundOrigin: "border-box",
      backgroundClip: "padding-box,border-box",
    }} />
  );

  switch (vk) {
    case "H": return (<>
      {diag("rgba(186,117,23,0.12)")}
      {badge("HOLO","#633806","#FAC775")}
      <div style={{ position:"absolute",bottom:0,left:0,right:0,height:3,background:"#EF9F27",zIndex:2 }}/>
    </>);

    case "RH": return (<>
      {diag("rgba(127,119,221,0.15)")}
      {badge("RH","#3C3489","#CECBF6")}
    </>);

    case "ERH": return (<>
      {diag("rgba(29,158,117,0.15)")}
      {badge("ERH","#085041","#9FE1CB")}
      <div style={{ position:"absolute",bottom:5,right:5,width:16,height:16,borderRadius:"50%",background:"#1D9E75",display:"flex",alignItems:"center",justifyContent:"center",fontSize:9,fontWeight:600,color:"#E1F5EE",zIndex:3 }}>E</div>
    </>);

    case "RH-PB": return (<>
      {badge("PB","#791F1F","#F7C1C1")}
      {ball("#E24B4A","#f5f5f5","#333")}
    </>);

    case "RH-MB": return (<>
      {badge("MB","#3C3489","#CECBF6")}
      {ball("#7F77DD","#f0f0f0","#333","#EEEDFE")}
    </>);

    case "BRH-FB": return (<>
      {badge("FB","#27500A","#C0DD97")}
      {ball("#639922","#e8f5d0","#333")}
    </>);

    case "BRH-LB": return (<>
      {badge("LB","#72243E","#F4C0D1")}
      {ball("#D4537E","#D4537E","#D4537E",undefined,undefined,true)}
    </>);

    case "BRH-QB": return (<>
      {badge("QB","#633806","#FAC775")}
      {ball("#EF9F27","#f5f5e0","#333",undefined,true)}
    </>);

    case "BRH-DB": return (<>
      {badge("DB","#04342C","#5DCAA5")}
      {ball("#0F6E56","#c0c0b0","#222","#1D9E75")}
    </>);

    case "BRH-R": return (<>
      {diag("rgba(226,75,74,0.15)")}
      {badge("R","#791F1F","#F7C1C1")}
      <div style={{ position:"absolute",bottom:4,right:6,fontSize:14,fontWeight:700,color:"#E24B4A",zIndex:3,lineHeight:1 }}>R</div>
    </>);

    case "DR": return (<>
      {diag("rgba(180,178,169,0.12)")}
      {badge("DR","#444441","#D3D1C7")}
      <div style={{ position:"absolute",bottom:4,right:4,fontSize:9,fontWeight:600,color:"#B4B2A9",zIndex:3 }}>EX</div>
    </>);

    case "AS": return (<>
      {aceBorder}
      {badge("ACE","linear-gradient(90deg,#a32d2d,#854F0B,#27500A,#185FA5,#534AB7)","#fff")}
    </>);

    case "MH": return (<>
      <div style={{ position:"absolute",inset:0,zIndex:1,pointerEvents:"none",background:"repeating-linear-gradient(90deg,transparent,transparent 4px,rgba(55,138,221,0.1) 4px,rgba(55,138,221,0.1) 5px)" }}/>
      <div style={{ position:"absolute",inset:0,zIndex:1,pointerEvents:"none",background:"repeating-linear-gradient(0deg,transparent,transparent 4px,rgba(55,138,221,0.07) 4px,rgba(55,138,221,0.07) 5px)" }}/>
      {badge("MH","#0C447C","#B5D4F4")}
    </>);

    case "1ST": return (<>
      <div style={{ position:"absolute",inset:0,zIndex:1,pointerEvents:"none",boxShadow:"inset 0 0 0 2px rgba(29,158,117,0.3)" }}/>
      {badge("1st ED","#085041","#9FE1CB","tl")}
    </>);

    case "IR": return (<>
      {diag("rgba(186,117,23,0.1)")}
      {badge("IR","#633806","#FAC775")}
      {stars(1,["#EF9F27"])}
    </>);

    case "SIR": return (<>
      <div style={{ position:"absolute",inset:0,zIndex:1,pointerEvents:"none",background:"repeating-linear-gradient(60deg,transparent,transparent 4px,rgba(239,159,39,0.15) 4px,rgba(239,159,39,0.15) 5px)" }}/>
      <div style={{ position:"absolute",inset:0,zIndex:1,pointerEvents:"none",background:"repeating-linear-gradient(-60deg,transparent,transparent 4px,rgba(239,159,39,0.08) 4px,rgba(239,159,39,0.08) 5px)" }}/>
      {badge("SIR","#412402","#FAC775")}
      {stars(2,["#EF9F27","#EF9F27"])}
    </>);

    case "HR": return (<>
      {aceBorder}
      {badge("HR","linear-gradient(90deg,#a32d2d,#854F0B,#27500A,#185FA5,#534AB7)","#fff")}
      {stars(3,["#E24B4A","#EF9F27","#7F77DD"])}
    </>);

    default: return null;
  }
}

// ─── Helpers ────────────────────────────────────────────────────────────────

function buildHref(current: Record<string, string | undefined>, overrides: Record<string, string | undefined>) {
  const merged = { ...current, ...overrides, page: "1" };
  if ("page" in overrides) merged.page = overrides.page || "1";
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(merged)) {
    if (v) params.set(k, v);
  }
  return `/cards?${params.toString()}`;
}

function Paginator({ current, total, params }: { current: number; total: number; params: Record<string, string | undefined> }) {
  if (total <= 1) return null;
  const pages: (number | "...")[] = [];
  const delta = 2;
  if (total <= 7) {
    for (let i = 1; i <= total; i++) pages.push(i);
  } else {
    pages.push(1);
    if (current - delta > 2) pages.push("...");
    for (let i = Math.max(2, current - delta); i <= Math.min(total - 1, current + delta); i++) pages.push(i);
    if (current + delta < total - 1) pages.push("...");
    pages.push(total);
  }
  const btn: React.CSSProperties = {
    padding: "7px 12px", borderRadius: "6px", fontSize: "13px",
    textDecoration: "none", fontWeight: 500, display: "inline-block",
    border: "1px solid #2a2a3a", minWidth: "36px", textAlign: "center",
  };
  return (
    <div style={{ display: "flex", justifyContent: "center", gap: "4px", flexWrap: "wrap", alignItems: "center" }}>
      {current > 1 && <Link href={buildHref(params, { page: String(current - 1) })} style={{ ...btn, background: "#1a1a24", color: "#fff" }}>‹</Link>}
      {pages.map((p, i) =>
        p === "..." ? (
          <span key={`e${i}`} style={{ ...btn, background: "transparent", border: "none", color: "#555", cursor: "default" }}>…</span>
        ) : (
          <Link key={p} href={buildHref(params, { page: String(p) })} style={{
            ...btn,
            background: p === current ? "#ff6b35" : "#1a1a24",
            color: "#fff",
            borderColor: p === current ? "#ff6b35" : "#2a2a3a",
          }}>{p}</Link>
        )
      )}
      {current < total && <Link href={buildHref(params, { page: String(current + 1) })} style={{ ...btn, background: "#1a1a24", color: "#fff" }}>›</Link>}
      <span style={{ color: "#555", fontSize: "12px", marginLeft: "8px" }}>Page {current} of {total}</span>
    </div>
  );
}

// ─── Page ───────────────────────────────────────────────────────────────────

export default async function CardsPage({
  searchParams,
}: {
  searchParams: Promise<{ [key: string]: string | undefined }>;
}) {
  const params = await searchParams;
  const page = parseInt(params.page || "1");
  const pageSize = 20;

  const data = await getCards({
    ...(params.search && { search: params.search }),
    ...(params.rarity && { rarity: params.rarity }),
    ...(params.ordering && { ordering: params.ordering }),
    ...(params.era && { era: params.era }),
    ...(params.energy_type && { energy_type: params.energy_type }),
    ...(params.supertype && { supertype: params.supertype }),
    ...(params.page && { page: params.page }),
  });

  const totalPages = Math.ceil((data.count || 0) / pageSize);
  const activeFilters = [
    params.era && ERAS.find(e => e.value === params.era)?.label,
    params.energy_type && `${params.energy_type} type`,
    params.supertype && params.supertype,
    params.rarity && RARITIES.find(r => r.value === params.rarity)?.label,
    params.search && `"${params.search}"`,
  ].filter(Boolean);

  return (
    <div style={{ maxWidth: "1400px", margin: "0 auto", padding: "20px 1.5rem" }}>

      {/* ERA TABS */}
      <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", marginBottom: "12px", borderBottom: "1px solid #2a2a3a", paddingBottom: "12px" }}>
        {ERAS.map((era) => (
          <Link key={era.value} href={buildHref(params, { era: era.value || undefined, page: "1" })} style={{
            background: (params.era || "") === era.value ? "#ff6b35" : "#1a1a24",
            border: `1px solid ${(params.era || "") === era.value ? "#ff6b35" : "#2a2a3a"}`,
            color: "#fff", padding: "6px 14px", borderRadius: "6px",
            textDecoration: "none", fontSize: "13px", fontWeight: 500,
          }}>{era.label}</Link>
        ))}
      </div>

      {/* ENERGY TYPE FILTER */}
      <div style={{ display: "flex", gap: "5px", flexWrap: "wrap", marginBottom: "6px" }}>
        {ENERGY_TYPES.map((t) => (
          <Link key={t.value} href={buildHref(params, { energy_type: params.energy_type === t.value ? undefined : t.value, page: "1" })} style={{
            background: params.energy_type === t.value ? t.color + "33" : "#1a1a24",
            border: `1px solid ${params.energy_type === t.value ? t.color : "#2a2a3a"}`,
            color: params.energy_type === t.value ? t.color : "#a0a0b0",
            padding: "4px 11px", borderRadius: "6px", textDecoration: "none", fontSize: "12px", fontWeight: 500,
          }}>{t.label}</Link>
        ))}
      </div>

      {/* SUPERTYPE FILTER */}
      <div style={{ display: "flex", gap: "5px", flexWrap: "wrap", marginBottom: "12px" }}>
        {SUPERTYPES.map((t) => (
          <Link key={t.value} href={buildHref(params, { supertype: params.supertype === t.value ? undefined : t.value, page: "1" })} style={{
            background: params.supertype === t.value ? "#4facfe22" : "#1a1a24",
            border: `1px solid ${params.supertype === t.value ? "#4facfe" : "#2a2a3a"}`,
            color: params.supertype === t.value ? "#4facfe" : "#a0a0b0",
            padding: "4px 11px", borderRadius: "6px", textDecoration: "none", fontSize: "12px", fontWeight: 500,
          }}>{t.label}</Link>
        ))}
      </div>

      {/* SEARCH + RARITY + SORT */}
      <form method="GET" style={{ display: "flex", gap: "10px", marginBottom: "12px", flexWrap: "wrap", alignItems: "center" }}>
        {params.era && <input type="hidden" name="era" value={params.era} />}
        {params.energy_type && <input type="hidden" name="energy_type" value={params.energy_type} />}
        {params.supertype && <input type="hidden" name="supertype" value={params.supertype} />}
        <input name="search" defaultValue={params.search} placeholder="Search name, set..." style={{
          background: "#1a1a24", border: "1px solid #2a2a3a", borderRadius: "6px",
          padding: "8px 14px", color: "#fff", fontSize: "13px", flex: 1, minWidth: "180px",
        }} />
        <select name="rarity" defaultValue={params.rarity || ""} style={{
          background: "#1a1a24", border: "1px solid #2a2a3a", borderRadius: "6px",
          padding: "8px 12px", color: "#fff", fontSize: "13px",
        }}>
          {RARITIES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
        </select>
        <select name="ordering" defaultValue={params.ordering || "card_number"} style={{
          background: "#1a1a24", border: "1px solid #2a2a3a", borderRadius: "6px",
          padding: "8px 12px", color: "#fff", fontSize: "13px",
        }}>
          {SORT_OPTIONS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
        </select>
        <button type="submit" style={{
          background: "#ff6b35", color: "#fff", border: "none", borderRadius: "6px",
          padding: "8px 18px", fontSize: "13px", fontWeight: 600, cursor: "pointer",
        }}>Search</button>
        {(params.search || params.rarity || params.era || params.energy_type || params.supertype) && (
          <Link href="/cards" style={{
            color: "#a0a0b0", fontSize: "12px", textDecoration: "none",
            padding: "8px 12px", border: "1px solid #2a2a3a", borderRadius: "6px", background: "#1a1a24",
          }}>✕ Clear all</Link>
        )}
      </form>

      {/* COUNT + ACTIVE FILTER CHIPS */}
      <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "16px", flexWrap: "wrap" }}>
        <span style={{ color: "#a0a0b0", fontSize: "13px" }}>
          <strong style={{ color: "#fff" }}>{data.count?.toLocaleString()}</strong> cards
          {activeFilters.length > 0 && <span> matching </span>}
        </span>
        {activeFilters.map((f, i) => (
          <span key={i} style={{
            background: "#ff6b3520", border: "1px solid #ff6b3560",
            color: "#ff6b35", padding: "2px 10px", borderRadius: "20px", fontSize: "12px",
          }}>{f}</span>
        ))}
      </div>

      {/* TOP PAGINATION */}
      <div style={{ marginBottom: "20px" }}>
        <Paginator current={page} total={totalPages} params={params} />
      </div>

      {/* CARD GRID */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(155px, 1fr))", gap: "10px" }}>
        {data.results.map((card: any) => {
          const vk = getVariantKey(card) as VariantKey;
          const vb = VARIANT_BORDER[vk];
          const cardNum = card.card_number != null ? String(card.card_number).padStart(3, "0") : "???";
          const dexNum = card.pokedex_number != null ? String(card.pokedex_number).padStart(4, "0") : "";
          const setCode = card.card_set?.code || "";
          const eraCode = card.card_set?.era?.code || "";

          return (
            <div key={card.pb_id || card.id} style={{
              background: "#1a1a24",
              border: `${vb.width} solid ${vb.color}`,
              borderRadius: "8px", overflow: "hidden",
            }}>
              <Link href={`/cards/${card.id}`} style={{ textDecoration: "none" }}>
                {/* IMAGE + OVERLAY */}
                <div style={{ position: "relative", width: "100%", aspectRatio: "3/4" }}>
                  {card.image_small_url ? (
                    <img
                      src={card.image_small_url}
                      alt={card.name}
                      style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
                    />
                  ) : (
                    <div style={{
                      width: "100%", height: "100%", background: "#12121a",
                      display: "flex", alignItems: "center", justifyContent: "center", fontSize: "36px",
                    }}>🃏</div>
                  )}
                  <VariantOverlay vk={vk} />
                </div>

                {/* CARD INFO */}
                <div style={{ padding: "8px 10px" }}>
                  <div style={{ fontSize: "10px", color: "#555", marginBottom: "2px" }}>
                    {eraCode} · {setCode} · #{cardNum}{dexNum ? ` · 🔢${dexNum}` : ""}
                  </div>
                  <div style={{ fontSize: "11px", color: "#ddd", marginBottom: "3px", lineHeight: 1.3, fontWeight: 500 }}>
                    {card.name}
                  </div>
                  <div style={{ fontSize: "10px", color: "#555", marginBottom: "5px" }}>
                    {card.rarity?.replace(/_/g, " ").toUpperCase()}
                  </div>
                  <div style={{ fontWeight: 700, color: "#ff6b35", fontSize: "14px" }}>
                    R {parseFloat(card.price).toFixed(2)}
                  </div>
                </div>
              </Link>

              {/* ADD TO PILE */}
              <div style={{ padding: "0 10px 10px" }}>
                <button style={{
                  width: "100%",
                  background: card.in_stock ? "#ff6b35" : "#1e1e2a",
                  color: card.in_stock ? "#fff" : "#555",
                  border: `1px solid ${card.in_stock ? "#ff6b35" : "#2a2a3a"}`,
                  borderRadius: "6px", padding: "6px", fontSize: "11px",
                  fontWeight: 600, cursor: card.in_stock ? "pointer" : "not-allowed",
                }}>
                  {card.in_stock ? "Add to my Pile! 🃏" : "Out of Stock"}
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* BOTTOM PAGINATION */}
      <div style={{ marginTop: "32px", marginBottom: "24px" }}>
        <Paginator current={page} total={totalPages} params={params} />
        <p style={{ textAlign: "center", color: "#555", fontSize: "12px", marginTop: "8px" }}>
          Page {page} of {totalPages} — {data.count?.toLocaleString()} total cards
        </p>
      </div>

      {/* PICKUP INFO */}
      <div style={{
        padding: "16px 20px", background: "#1a1a24", borderRadius: "8px",
        border: "1px solid #2a2a3a", fontSize: "13px", color: "#a0a0b0",
      }}>
        <strong style={{ color: "#fff" }}>🏠 Local Pickup</strong> — Birchleigh North, Kempton Park<br />
        Mon–Fri: 18:30–21:00 &nbsp;|&nbsp; Sat: 10:00–18:00 &nbsp;|&nbsp; Sun: 10:00–15:00<br />
        <span style={{ color: "#ff6b35" }}>Give us 24 hours notice to prep your order!</span>
      </div>
    </div>
  );
}
'''

with open(r"C:\Users\texca\pokemart-frontend\src\app\cards\page.tsx", "w", encoding="utf-8") as f:
    f.write(content)
print("Done! cards/page.tsx updated with all 18 variant treatments.")

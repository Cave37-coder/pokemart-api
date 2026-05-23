"use client";
import { useEffect, useState } from "react";
import Link from "next/link";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

interface CartItem {
  id: number;
  quantity: number;
  subtotal: string;
  product: {
    id: number;
    name: string;
    price: string;
    stock: number;
    image_small_url: string;
    card_set: { code: string; name: string };
    rarity: string;
  };
}

interface Cart {
  id: number;
  total: string;
  items: CartItem[];
}

export default function PilePage() {
  const [cart, setCart]       = useState<Cart | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState("");
  const [removing, setRemoving] = useState<number | null>(null);

  const fetchCart = async () => {
    const token = localStorage.getItem("access_token");
    if (!token) { setError("Please sign in to view your pile."); setLoading(false); return; }
    try {
      const res = await fetch(`${API_URL}/api/cart/`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.status === 401) { setError("Please sign in to view your pile."); setLoading(false); return; }
      const data = await res.json();
      setCart(data);
    } catch { setError("Failed to load pile."); }
    finally { setLoading(false); }
  };

  useEffect(() => { fetchCart(); }, []);

  const removeItem = async (itemId: number) => {
    const token = localStorage.getItem("access_token");
    if (!token) return;
    setRemoving(itemId);
    try {
      await fetch(`${API_URL}/api/cart/remove/${itemId}/`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      window.dispatchEvent(new Event("pile-updated"));
      fetchCart();
    } finally { setRemoving(null); }
  };

  if (loading) return (
    <div style={{ maxWidth: 700, margin: "60px auto", padding: "0 1.5rem", color: "#a0a0b0", textAlign: "center" }}>
      Loading your pile...
    </div>
  );

  if (error) return (
    <div style={{ maxWidth: 600, margin: "60px auto", padding: "0 1.5rem", textAlign: "center" }}>
      <div style={{ color: "#EF4444", marginBottom: 16 }}>{error}</div>
      <Link href="/auth/login" style={{ color: "#ff6b35", textDecoration: "none" }}>Sign in</Link>
    </div>
  );

  const items = cart?.items || [];
  const total = parseFloat(cart?.total || "0");

  return (
    <div style={{ maxWidth: 720, margin: "40px auto", padding: "0 1.5rem" }}>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, margin: "0 0 4px", color: "#fff" }}>My Pile</h1>
        <p style={{ color: "#a0a0b0", fontSize: 14, margin: 0 }}>
          {items.length} {items.length === 1 ? "card" : "cards"}
        </p>
      </div>

      {items.length === 0 ? (
        <div style={{ background: "#1a1a24", border: "1px solid #2a2a3a", borderRadius: 12, padding: "48px 24px", textAlign: "center" }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>🃏</div>
          <div style={{ color: "#a0a0b0", marginBottom: 16 }}>Your pile is empty.</div>
          <Link href="/cards" style={{ color: "#ff6b35", textDecoration: "none", fontWeight: 600 }}>Browse cards</Link>
        </div>
      ) : (
        <>
          {/* ITEMS */}
          <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 20 }}>
            {items.map((item) => (
              <div key={item.id} style={{
                background: "#1a1a24", border: "1px solid #2a2a3a", borderRadius: 10,
                padding: "12px 16px", display: "flex", gap: 12, alignItems: "center",
              }}>
                {item.product.image_small_url && (
                  <img src={item.product.image_small_url} alt={item.product.name}
                    style={{ width: 50, height: 70, objectFit: "cover", borderRadius: 4, flexShrink: 0 }} />
                )}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 600, color: "#fff", fontSize: 14, marginBottom: 2 }}>{item.product.name}</div>
                  <div style={{ fontSize: 11, color: "#555", marginBottom: 4 }}>
                    {item.product.card_set?.name} · {item.product.rarity?.replace(/_/g, " ").toUpperCase()}
                  </div>
                  <div style={{ fontSize: 11, color: "#a0a0b0" }}>
                    Qty: {item.quantity} × R {parseFloat(item.product.price).toFixed(2)}
                  </div>
                </div>
                <div style={{ textAlign: "right", flexShrink: 0 }}>
                  <div style={{ fontWeight: 700, color: "#ff6b35", fontSize: 15, marginBottom: 6 }}>
                    R {parseFloat(item.subtotal).toFixed(2)}
                  </div>
                  <button onClick={() => removeItem(item.id)} disabled={removing === item.id}
                    style={{ background: "transparent", border: "1px solid #2a2a3a", color: "#555", borderRadius: 6, padding: "3px 10px", fontSize: 11, cursor: "pointer" }}>
                    {removing === item.id ? "..." : "Remove"}
                  </button>
                </div>
              </div>
            ))}
          </div>

          {/* SUMMARY + CHECKOUT BUTTON */}
          <div style={{ background: "#1a1a24", border: "1px solid #2a2a3a", borderRadius: 12, padding: 20 }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
              <span style={{ color: "#a0a0b0" }}>Subtotal ({items.length} cards)</span>
              <span style={{ fontWeight: 700, color: "#fff", fontSize: 16 }}>R {total.toFixed(2)}</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16, fontSize: 12, color: "#555" }}>
              <span>Shipping calculated at checkout</span>
            </div>

            <Link href="/checkout" style={{
              display: "block", width: "100%", background: "#ff6b35", color: "#fff",
              border: "none", borderRadius: 8, padding: "14px", fontSize: 15,
              fontWeight: 700, cursor: "pointer", textAlign: "center", textDecoration: "none",
              boxSizing: "border-box",
            }}>
              Proceed to Checkout — R {total.toFixed(2)}
            </Link>

            <div style={{ textAlign: "center", marginTop: 10, fontSize: 11, color: "#555" }}>
              Secure payment via PayFast · Collection available
            </div>
          </div>
        </>
      )}
    </div>
  );
}

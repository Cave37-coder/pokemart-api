"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

// Shipping options
const SHIPPING_OPTIONS = [
  { id: "collection",   label: "Local Collection",         price: 0,   desc: "Birchleigh North, Kempton Park — Mon-Fri 18:30-21:00 | Sat 10:00-18:00 | Sun 10:00-15:00. Give us 24hrs notice!" },
  { id: "pudo_locker",  label: "Pudo Kiosk-to-Locker",    price: 75,  desc: "1-4 business days. Delivered to your nearest Pudo locker." },
  { id: "pudo_door",    label: "Pudo Door-to-Door",        price: 95,  desc: "2-4 business days. Delivered to your door." },
  { id: "postnet",      label: "Postnet-to-Postnet",       price: 85,  desc: "2-5 business days. Collect from your nearest PostNet." },
];

interface Profile {
  first_name: string; last_name: string; email: string; phone_number: string;
  delivery_preference: string;
  address_line1: string; address_line2: string; address_city: string;
  address_province: string; address_postal_code: string;
  pudo_locker_name: string; pudo_locker_address: string; pudo_locker_code: string;
}

interface CartItem {
  id: number; quantity: number; subtotal: string;
  product: { id: number; name: string; price: string; image_small_url: string; card_set: { code: string; name: string } };
}

interface Cart { id: number; total: string; items: CartItem[]; }

export default function CheckoutPage() {
  const router = useRouter();
  const [cart, setCart]         = useState<Cart | null>(null);
  const [profile, setProfile]   = useState<Profile | null>(null);
  const [shipping, setShipping] = useState("collection");
  const [note, setNote]         = useState("");
  const [step, setStep]         = useState<"review" | "payment">("review");
  const [loading, setLoading]   = useState(true);
  const [placing, setPlacing]   = useState(false);
  const [error, setError]       = useState("");

  // Editable delivery fields
  const [delivery, setDelivery] = useState({
    first_name: "", last_name: "", email: "", phone: "",
    address_line1: "", address_line2: "", city: "", province: "", postal_code: "",
    pudo_locker_name: "", pudo_locker_address: "",
  });

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) { router.push("/auth/login"); return; }

    Promise.all([
      fetch(`${API_URL}/api/cart/`, { headers: { Authorization: `Bearer ${token}` } }).then(r => r.json()),
      fetch(`${API_URL}/api/auth/profile/`, { headers: { Authorization: `Bearer ${token}` } }).then(r => r.json()),
    ]).then(([cartData, profileData]) => {
      setCart(cartData);
      setProfile(profileData);
      // Pre-fill delivery from profile
      setDelivery({
        first_name:        profileData.first_name || "",
        last_name:         profileData.last_name  || "",
        email:             profileData.email       || "",
        phone:             profileData.phone_number || "",
        address_line1:     profileData.address_line1 || "",
        address_line2:     profileData.address_line2 || "",
        city:              profileData.address_city || "",
        province:          profileData.address_province || "",
        postal_code:       profileData.address_postal_code || "",
        pudo_locker_name:  profileData.pudo_locker_name || "",
        pudo_locker_address: profileData.pudo_locker_address || "",
      });
      // Default shipping from profile preference
      const pref = profileData.delivery_preference;
      if (pref === "collection") setShipping("collection");
      else if (pref === "pudo")  setShipping("pudo_locker");
      else                        setShipping("pudo_locker");
      setLoading(false);
    }).catch(() => { setError("Failed to load checkout data."); setLoading(false); });
  }, []);

  const shippingCost = SHIPPING_OPTIONS.find(s => s.id === shipping)?.price || 0;
  const cartTotal    = parseFloat(cart?.total || "0");
  const orderTotal   = cartTotal + shippingCost;
  const items        = cart?.items || [];

  const inp = (style?: React.CSSProperties): React.CSSProperties => ({
    width: "100%", background: "#12121a", border: "1px solid #2a2a3a",
    borderRadius: 8, padding: "9px 12px", color: "#fff", fontSize: 13,
    boxSizing: "border-box", ...style,
  });

  const placeOrder = async () => {
    const token = localStorage.getItem("access_token");
    if (!token) return;
    setPlacing(true);
    setError("");

    try {
      // 1. Create order
      const orderRes = await fetch(`${API_URL}/api/checkout/`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          delivery_method:      shipping === "collection" ? "collection" : "courier",
          address_line1:        delivery.address_line1,
          address_line2:        delivery.address_line2,
          city:                 delivery.city,
          province:             delivery.province,
          postal_code:          delivery.postal_code,
          customer_note:        note,
          shipping_method:      shipping,
          shipping_cost:        shippingCost,
          pudo_locker_name:     delivery.pudo_locker_name,
          pudo_locker_address:  delivery.pudo_locker_address,
        }),
      });

      if (!orderRes.ok) {
        const err = await orderRes.json();
        throw new Error(err.error || "Failed to create order");
      }

      const order = await orderRes.json();

      // 2. Save delivery details to profile
      await fetch(`${API_URL}/api/auth/profile/`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          first_name: delivery.first_name,
          last_name:  delivery.last_name,
          phone_number: delivery.phone,
          address_line1: delivery.address_line1,
          address_line2: delivery.address_line2,
          address_city: delivery.city,
          address_province: delivery.province,
          address_postal_code: delivery.postal_code,
          pudo_locker_name: delivery.pudo_locker_name,
          pudo_locker_address: delivery.pudo_locker_address,
          delivery_preference: shipping === "collection" ? "collection" : "pudo",
        }),
      });

      // 3. Initiate PayFast (skip for collection — cash on collection)
      if (shipping === "collection") {
        window.dispatchEvent(new Event("pile-updated"));
        router.push(`/orders/${order.id}?payment=collection`);
        return;
      }

      const pfRes = await fetch(`${API_URL}/api/payments/initiate/`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ order_id: order.id }),
      });

      if (!pfRes.ok) throw new Error("Failed to initiate payment");
      const pfData = await pfRes.json();

      window.dispatchEvent(new Event("pile-updated"));
      // Redirect to PayFast
      window.location.href = pfData.redirect_url;

    } catch (e: any) {
      setError(e.message || "Something went wrong");
      setPlacing(false);
    }
  };

  if (loading) return (
    <div style={{ maxWidth: 800, margin: "60px auto", padding: "0 1.5rem", color: "#a0a0b0", textAlign: "center" }}>
      Loading checkout...
    </div>
  );

  if (items.length === 0) return (
    <div style={{ maxWidth: 600, margin: "60px auto", padding: "0 1.5rem", textAlign: "center" }}>
      <div style={{ fontSize: 40, marginBottom: 12 }}>🃏</div>
      <div style={{ color: "#a0a0b0", marginBottom: 16 }}>Your pile is empty.</div>
      <Link href="/cards" style={{ color: "#ff6b35", textDecoration: "none", fontWeight: 600 }}>Browse cards</Link>
    </div>
  );

  return (
    <div style={{ maxWidth: 900, margin: "32px auto", padding: "0 1.5rem" }}>
      <h1 style={{ fontSize: 22, fontWeight: 700, color: "#fff", marginBottom: 24 }}>Checkout</h1>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: 24, alignItems: "start" }}>

        {/* ── LEFT: Delivery + Shipping ── */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

          {/* Contact */}
          <div style={{ background: "#1a1a24", border: "1px solid #2a2a3a", borderRadius: 12, padding: 20 }}>
            <h2 style={{ fontSize: 15, fontWeight: 700, color: "#fff", margin: "0 0 14px" }}>Contact details</h2>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <div>
                <label style={{ fontSize: 11, color: "#a0a0b0", display: "block", marginBottom: 4 }}>First name</label>
                <input style={inp()} value={delivery.first_name} onChange={e => setDelivery(d => ({...d, first_name: e.target.value}))} placeholder="Ash" />
              </div>
              <div>
                <label style={{ fontSize: 11, color: "#a0a0b0", display: "block", marginBottom: 4 }}>Last name</label>
                <input style={inp()} value={delivery.last_name} onChange={e => setDelivery(d => ({...d, last_name: e.target.value}))} placeholder="Ketchum" />
              </div>
              <div>
                <label style={{ fontSize: 11, color: "#a0a0b0", display: "block", marginBottom: 4 }}>Email</label>
                <input style={inp()} type="email" value={delivery.email} onChange={e => setDelivery(d => ({...d, email: e.target.value}))} placeholder="ash@pokemon.com" />
              </div>
              <div>
                <label style={{ fontSize: 11, color: "#a0a0b0", display: "block", marginBottom: 4 }}>Phone</label>
                <input style={inp()} value={delivery.phone} onChange={e => setDelivery(d => ({...d, phone: e.target.value}))} placeholder="074 000 0000" />
              </div>
            </div>
          </div>

          {/* Shipping method */}
          <div style={{ background: "#1a1a24", border: "1px solid #2a2a3a", borderRadius: 12, padding: 20 }}>
            <h2 style={{ fontSize: 15, fontWeight: 700, color: "#fff", margin: "0 0 14px" }}>Shipping method</h2>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {SHIPPING_OPTIONS.map(opt => (
                <button key={opt.id} onClick={() => setShipping(opt.id)} style={{
                  background: shipping === opt.id ? "#ff6b3515" : "#12121a",
                  border: `1px solid ${shipping === opt.id ? "#ff6b35" : "#2a2a3a"}`,
                  borderRadius: 8, padding: "12px 14px", cursor: "pointer",
                  display: "flex", justifyContent: "space-between", alignItems: "flex-start", textAlign: "left",
                }}>
                  <div>
                    <div style={{ fontWeight: 600, color: shipping === opt.id ? "#ff6b35" : "#fff", fontSize: 13, marginBottom: 2 }}>
                      {opt.label}
                    </div>
                    <div style={{ fontSize: 11, color: "#a0a0b0", lineHeight: 1.5, maxWidth: 320 }}>{opt.desc}</div>
                  </div>
                  <div style={{ fontWeight: 700, color: shipping === opt.id ? "#ff6b35" : "#a0a0b0", fontSize: 14, marginLeft: 12, flexShrink: 0 }}>
                    {opt.price === 0 ? "FREE" : `R ${opt.price}`}
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Address fields — shown for door/postnet */}
          {(shipping === "pudo_door" || shipping === "postnet") && (
            <div style={{ background: "#1a1a24", border: "1px solid #2a2a3a", borderRadius: 12, padding: 20 }}>
              <h2 style={{ fontSize: 15, fontWeight: 700, color: "#fff", margin: "0 0 14px" }}>Delivery address</h2>
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                <div>
                  <label style={{ fontSize: 11, color: "#a0a0b0", display: "block", marginBottom: 4 }}>Address line 1</label>
                  <input style={inp()} value={delivery.address_line1} onChange={e => setDelivery(d => ({...d, address_line1: e.target.value}))} placeholder="4 Heliose Street" />
                </div>
                <div>
                  <label style={{ fontSize: 11, color: "#a0a0b0", display: "block", marginBottom: 4 }}>Address line 2 (optional)</label>
                  <input style={inp()} value={delivery.address_line2} onChange={e => setDelivery(d => ({...d, address_line2: e.target.value}))} placeholder="Complex / Unit" />
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 120px", gap: 10 }}>
                  <div>
                    <label style={{ fontSize: 11, color: "#a0a0b0", display: "block", marginBottom: 4 }}>City</label>
                    <input style={inp()} value={delivery.city} onChange={e => setDelivery(d => ({...d, city: e.target.value}))} placeholder="Kempton Park" />
                  </div>
                  <div>
                    <label style={{ fontSize: 11, color: "#a0a0b0", display: "block", marginBottom: 4 }}>Province</label>
                    <input style={inp()} value={delivery.province} onChange={e => setDelivery(d => ({...d, province: e.target.value}))} placeholder="Gauteng" />
                  </div>
                  <div>
                    <label style={{ fontSize: 11, color: "#a0a0b0", display: "block", marginBottom: 4 }}>Postal code</label>
                    <input style={inp()} value={delivery.postal_code} onChange={e => setDelivery(d => ({...d, postal_code: e.target.value}))} placeholder="1618" />
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Pudo locker fields */}
          {shipping === "pudo_locker" && (
            <div style={{ background: "#1a1a24", border: "1px solid #2a2a3a", borderRadius: 12, padding: 20 }}>
              <h2 style={{ fontSize: 15, fontWeight: 700, color: "#fff", margin: "0 0 6px" }}>Pudo locker details</h2>
              <p style={{ fontSize: 12, color: "#a0a0b0", margin: "0 0 14px" }}>
                Find your nearest locker at{" "}
                <a href="https://www.pudo.co.za/find-a-locker" target="_blank" rel="noreferrer" style={{ color: "#ff6b35" }}>pudo.co.za</a>
              </p>
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                <div>
                  <label style={{ fontSize: 11, color: "#a0a0b0", display: "block", marginBottom: 4 }}>Locker name</label>
                  <input style={inp()} value={delivery.pudo_locker_name} onChange={e => setDelivery(d => ({...d, pudo_locker_name: e.target.value}))} placeholder="e.g. Birchleigh North Mall" />
                </div>
                <div>
                  <label style={{ fontSize: 11, color: "#a0a0b0", display: "block", marginBottom: 4 }}>Locker address</label>
                  <input style={inp()} value={delivery.pudo_locker_address} onChange={e => setDelivery(d => ({...d, pudo_locker_address: e.target.value}))} placeholder="e.g. Mooifontein Rd, Birchleigh North" />
                </div>
              </div>
            </div>
          )}

          {/* Note */}
          <div style={{ background: "#1a1a24", border: "1px solid #2a2a3a", borderRadius: 12, padding: 20 }}>
            <h2 style={{ fontSize: 15, fontWeight: 700, color: "#fff", margin: "0 0 10px" }}>Order notes (optional)</h2>
            <textarea value={note} onChange={e => setNote(e.target.value)}
              placeholder="Any special requests..."
              style={{ ...inp(), resize: "vertical", minHeight: 70 }} />
          </div>
        </div>

        {/* ── RIGHT: Order summary ── */}
        <div style={{ position: "sticky", top: 20 }}>
          <div style={{ background: "#1a1a24", border: "1px solid #2a2a3a", borderRadius: 12, padding: 20 }}>
            <h2 style={{ fontSize: 15, fontWeight: 700, color: "#fff", margin: "0 0 14px" }}>Order summary</h2>

            {/* Items */}
            <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 14 }}>
              {items.map(item => (
                <div key={item.id} style={{ display: "flex", gap: 10, alignItems: "center" }}>
                  {item.product.image_small_url && (
                    <img src={item.product.image_small_url} alt={item.product.name}
                      style={{ width: 36, height: 50, objectFit: "cover", borderRadius: 4, flexShrink: 0 }} />
                  )}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 12, color: "#ddd", fontWeight: 500, lineHeight: 1.3 }}>{item.product.name}</div>
                    <div style={{ fontSize: 11, color: "#555" }}>Qty {item.quantity}</div>
                  </div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: "#fff", flexShrink: 0 }}>
                    R {parseFloat(item.subtotal).toFixed(2)}
                  </div>
                </div>
              ))}
            </div>

            <div style={{ borderTop: "1px solid #2a2a3a", paddingTop: 12, display: "flex", flexDirection: "column", gap: 6 }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, color: "#a0a0b0" }}>
                <span>Subtotal</span>
                <span>R {cartTotal.toFixed(2)}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, color: "#a0a0b0" }}>
                <span>Shipping</span>
                <span style={{ color: shippingCost === 0 ? "#10B981" : "#fff" }}>
                  {shippingCost === 0 ? "FREE" : `R ${shippingCost}.00`}
                </span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 16, fontWeight: 700, color: "#fff", marginTop: 6, paddingTop: 8, borderTop: "1px solid #2a2a3a" }}>
                <span>Total</span>
                <span style={{ color: "#ff6b35" }}>R {orderTotal.toFixed(2)}</span>
              </div>
            </div>

            {error && (
              <div style={{ background: "#EF444420", border: "1px solid #EF444440", borderRadius: 8, padding: "10px 12px", marginTop: 12, color: "#EF4444", fontSize: 12 }}>
                {error}
              </div>
            )}

            <button onClick={placeOrder} disabled={placing} style={{
              width: "100%", background: placing ? "#cc5528" : "#ff6b35",
              color: "#fff", border: "none", borderRadius: 8,
              padding: "14px", fontSize: 15, fontWeight: 700,
              cursor: placing ? "not-allowed" : "pointer", marginTop: 14,
            }}>
              {placing ? "Processing..." :
                shipping === "collection"
                  ? `Place Order — R ${orderTotal.toFixed(2)}`
                  : `Pay with PayFast — R ${orderTotal.toFixed(2)}`}
            </button>

            {shipping === "collection" && (
              <div style={{ textAlign: "center", marginTop: 8, fontSize: 11, color: "#555" }}>
                Pay cash on collection at Birchleigh North
              </div>
            )}
            {shipping !== "collection" && (
              <div style={{ textAlign: "center", marginTop: 8, fontSize: 11, color: "#555" }}>
                You'll be redirected to PayFast to complete payment securely
              </div>
            )}

            <div style={{ marginTop: 14, display: "flex", justifyContent: "center", gap: 6, flexWrap: "wrap" }}>
              {["VISA", "Mastercard", "EFT", "Instant EFT"].map(m => (
                <span key={m} style={{ fontSize: 10, color: "#555", background: "#12121a", border: "1px solid #2a2a3a", borderRadius: 4, padding: "2px 7px" }}>{m}</span>
              ))}
            </div>
          </div>

          <div style={{ marginTop: 12 }}>
            <Link href="/pile" style={{ color: "#a0a0b0", fontSize: 12, textDecoration: "none" }}>← Back to pile</Link>
          </div>
        </div>
      </div>
    </div>
  );
}

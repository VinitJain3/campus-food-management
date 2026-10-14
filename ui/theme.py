"""Stylesheet for Campus Bites. Injected once per run; colours mirror .streamlit/config.toml."""

import streamlit as st

CSS = """
<style>
:root {
  --brand: #C2410C; --brand-ink: #9A3412; --brand-soft: #FFEDD5;
  --ink: #1C1917; --muted: #57534E; --line: #EADBCB; --surface: #FFFFFF; --page: #FFFBF6;
  --leaf: #15803D; --leaf-soft: #DCFCE7; --amber: #B45309; --amber-soft: #FEF3C7;
  --berry: #B91C1C; --berry-soft: #FEE2E2; --teal: #0F766E; --teal-soft: #CCFBF1;
  --radius: 18px; --shadow: 0 1px 2px rgba(28,25,23,.06), 0 8px 24px rgba(28,25,23,.06);
  --shadow-lift: 0 2px 4px rgba(28,25,23,.08), 0 16px 32px rgba(194,65,12,.14);
}

/* ---------- Motion ---------- */
@keyframes rise { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
@keyframes pop  { 0% { transform: scale(.6); opacity: 0; } 70% { transform: scale(1.08); opacity: 1; } 100% { transform: scale(1); } }
@keyframes pulse { 0%,100% { box-shadow: 0 0 0 0 rgba(194,65,12,.35); } 50% { box-shadow: 0 0 0 7px rgba(194,65,12,0); } }
[data-testid="stMainBlockContainer"] { animation: rise .28s ease-out both; }
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation: none !important; transition: none !important; } }

/* ---------- Layout ---------- */
[data-testid="stMainBlockContainer"] { padding-bottom: 4rem; max-width: 1180px; }
h1, h2, h3 { letter-spacing: -0.015em; }
.eyebrow { font-size: .78rem; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; color: var(--brand); margin: 0 0 .25rem; }
.muted { color: var(--muted); }
.money { font-variant-numeric: tabular-nums; font-weight: 700; white-space: nowrap; }

/* ---------- Focus: always visible for keyboard users ---------- */
button:focus-visible, a:focus-visible, [role="tab"]:focus-visible, input:focus-visible, textarea:focus-visible,
[role="radio"]:focus-visible, [role="checkbox"]:focus-visible, [data-baseweb="select"] div:focus-visible {
  outline: 3px solid var(--brand) !important; outline-offset: 2px !important; border-radius: 10px;
}

/* ---------- Buttons ---------- */
.stButton button, .stDownloadButton button, [data-testid="stPageLink"] a, .stFormSubmitButton button {
  transition: transform .12s ease, box-shadow .12s ease, background-color .12s ease; min-height: 2.5rem;
}
.stButton button:hover:not(:disabled), .stFormSubmitButton button:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 6px 14px rgba(28,25,23,.10); }
.stButton button:active:not(:disabled) { transform: translateY(0) scale(.98); }
.stButton button:disabled { opacity: .45; cursor: not-allowed; }

/* ---------- Cards (outlets, menu items, orders, grouped content) ---------- */
[class*="st-key-card-"] {
  background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius);
  box-shadow: var(--shadow); padding: .9rem .9rem 1rem; transition: transform .18s ease, box-shadow .18s ease, border-color .18s;
  animation: rise .35s ease-out both;
}
[class*="st-key-card-outlet-"]:hover, [class*="st-key-card-item-"]:hover { transform: translateY(-3px); box-shadow: var(--shadow-lift); border-color: #F5C9A6; }
[class*="st-key-card-"] h3 { margin: .1rem 0 0; font-size: 1.25rem; line-height: 1.25; }
[class*="st-key-panel-"] { background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); padding: 1.1rem 1.1rem 1.2rem; box-shadow: var(--shadow); }

/* ---------- Food tiles (visual thumbnails, no image files needed) ---------- */
.tile {
  position: relative; aspect-ratio: 16 / 9; border-radius: 14px; overflow: hidden; display: grid; place-items: center;
  background:
    radial-gradient(circle at 18% 22%, rgba(255,255,255,.55) 0 14%, transparent 15%),
    radial-gradient(circle at 82% 78%, rgba(255,255,255,.22) 0 18%, transparent 19%),
    radial-gradient(rgba(255,255,255,.18) 1px, transparent 1.5px) 0 0 / 14px 14px,
    linear-gradient(135deg, var(--b), var(--a));
}
.tile.sm { aspect-ratio: 1; width: 56px; border-radius: 12px; }
.tile.lg { aspect-ratio: 4 / 3; border-radius: 20px; }
.emoji, .banner .big, .empty .big { font-family: "Segoe UI Emoji", "Apple Color Emoji", "Noto Color Emoji", sans-serif; }
.tile .emoji { font-size: clamp(3rem, 6vw, 4.4rem); line-height: 1; filter: drop-shadow(0 10px 12px rgba(0,0,0,.28)); transition: transform .35s cubic-bezier(.2,.8,.2,1); }
.tile.sm .emoji { font-size: 1.7rem; filter: drop-shadow(0 3px 4px rgba(0,0,0,.25)); }
.tile.lg .emoji { font-size: clamp(5rem, 12vw, 7.5rem); }
[class*="st-key-card-"]:hover .tile .emoji { transform: scale(1.1) rotate(-5deg); }
.tile .chip { position: absolute; top: 10px; left: 10px; }
.tile .chip.right { left: auto; right: 10px; }
.tile.dim { filter: grayscale(.85) opacity(.75); }

/* ---------- Chips and tags ---------- */
.chip { display: inline-flex; align-items: center; gap: .3rem; padding: .18rem .6rem; border-radius: 999px; font-size: .78rem; font-weight: 700; line-height: 1.4; background: rgba(255,255,255,.92); color: var(--ink); white-space: nowrap; }
.chip.ok { color: var(--leaf); } .chip.warn { color: var(--amber); } .chip.bad { color: var(--berry); }
.chip.solid-ok { background: var(--leaf-soft); color: var(--leaf); } .chip.solid-warn { background: var(--amber-soft); color: var(--amber); }
.chip.solid-bad { background: var(--berry-soft); color: var(--berry); } .chip.solid-brand { background: var(--brand-soft); color: var(--brand-ink); }
.chip.solid-teal { background: var(--teal-soft); color: var(--teal); }
.tags { display: flex; flex-wrap: wrap; gap: .35rem; margin: .35rem 0 .1rem; }
.tag { font-size: .74rem; font-weight: 600; padding: .1rem .5rem; border-radius: 6px; border: 1px solid var(--line); color: var(--muted); background: #FFF; }
.tag.veg::before, .tag.vegan::before { content: ""; display: inline-block; width: 8px; height: 8px; border-radius: 2px; margin-right: 5px; border: 1.5px solid var(--leaf); background: radial-gradient(circle, var(--leaf) 0 2px, transparent 2.5px); vertical-align: 0; }
.tag.egg::before { content: ""; display: inline-block; width: 8px; height: 8px; border-radius: 2px; margin-right: 5px; border: 1.5px solid var(--amber); background: radial-gradient(circle, var(--amber) 0 2px, transparent 2.5px); }
.meta { display: flex; flex-wrap: wrap; gap: .25rem .9rem; color: var(--muted); font-size: .88rem; margin: .2rem 0; }
.meta b { color: var(--ink); }
.desc { color: var(--muted); font-size: .92rem; margin: .25rem 0 .2rem; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; line-height: 1.5; min-height: 3em; }
.price-row { display: flex; justify-content: space-between; align-items: baseline; gap: .5rem; }
.price-row .money { font-size: 1.1rem; }

/* ---------- Hero and banners ---------- */
.hero { border-radius: 24px; padding: clamp(1.25rem, 3vw, 2.25rem); background:
  radial-gradient(circle at 92% 12%, rgba(253,186,116,.55), transparent 38%),
  radial-gradient(circle at 8% 110%, rgba(194,65,12,.18), transparent 40%), #FFF3E8; border: 1px solid var(--line); }
.hero h1 { font-size: clamp(1.9rem, 4.6vw, 3.1rem); line-height: 1.06; margin: .2rem 0 .6rem; padding: 0; }
.hero p { color: var(--muted); font-size: 1.05rem; max-width: 46ch; margin: 0; }
.hero .stats { display: flex; flex-wrap: wrap; gap: .5rem 1.4rem; margin-top: 1rem; font-size: .92rem; color: var(--muted); }
.hero .stats b { color: var(--ink); font-size: 1.05rem; }
.banner { border-radius: 22px; padding: clamp(1rem, 3vw, 1.6rem); color: #fff; display: flex; gap: 1.1rem; align-items: center; flex-wrap: wrap;
  background: radial-gradient(circle at 90% 20%, rgba(255,255,255,.25), transparent 35%), linear-gradient(120deg, var(--a), var(--b)); }
.banner .big { font-size: clamp(3rem, 8vw, 4.5rem); filter: drop-shadow(0 8px 10px rgba(0,0,0,.3)); }
.banner h1 { color: #fff; margin: 0; padding: 0; font-size: clamp(1.7rem, 4vw, 2.4rem); }
.banner p { margin: .15rem 0 0; opacity: .95; }
.banner .chip { background: rgba(255,255,255,.95); }
.vendor-banner { border-radius: 20px; padding: 1rem 1.25rem; background: linear-gradient(120deg, #0F766E, #115E59); color: #fff; display: flex; justify-content: space-between; align-items: center; gap: 1rem; flex-wrap: wrap; }
.vendor-banner h1 { color: #fff; margin: 0; padding: 0; font-size: clamp(1.5rem, 3.5vw, 2rem); }
.vendor-banner p { margin: .1rem 0 0; opacity: .9; }

/* ---------- Order timeline ---------- */
.tl { list-style: none; display: flex; margin: .6rem 0 .2rem !important; padding: 0 !important; counter-reset: step; }
.tl li { flex: 1; position: relative; text-align: center; font-size: .78rem; color: var(--muted); padding-top: 30px; min-width: 0; }
.tl li::before { content: ""; position: absolute; top: 11px; left: -50%; width: 100%; height: 3px; background: var(--line); }
.tl li:first-child::before { display: none; }
.tl li .dot { position: absolute; top: 0; left: 50%; transform: translateX(-50%); width: 24px; height: 24px; border-radius: 50%; background: #fff; border: 2px solid var(--line); display: grid; place-items: center; font-size: .72rem; font-weight: 800; z-index: 1; }
.tl li.done .dot { background: var(--leaf); border-color: var(--leaf); color: #fff; }
.tl li.done::before, .tl li.current::before { background: var(--leaf); }
.tl li.current .dot { background: var(--brand); border-color: var(--brand); color: #fff; animation: pulse 1.8s infinite; }
.tl li.current .lbl { color: var(--brand-ink); font-weight: 800; }
.tl li.stop .dot { background: var(--berry); border-color: var(--berry); color: #fff; }
.tl li.stop .lbl { color: var(--berry); font-weight: 800; }
.tl li .lbl { display: block; font-weight: 600; color: var(--ink); overflow-wrap: anywhere; }
.tl li .t { display: block; font-size: .72rem; color: var(--muted); }
@media (max-width: 560px) {
  .tl { flex-direction: column; gap: .2rem; }
  .tl li { text-align: left; padding: 0 0 .55rem 36px; min-height: 30px; }
  .tl li::before { top: -12px; left: 11px; width: 3px; height: 100%; }
  .tl li .dot { left: 12px; }
  .tl li .lbl, .tl li .t { display: inline; margin-right: .4rem; }
}

/* ---------- Checkout steps ---------- */
.steps { display: flex; gap: .4rem; flex-wrap: wrap; margin: .2rem 0 1rem !important; padding: 0 !important; list-style: none; }
.steps li { display: flex; align-items: center; gap: .45rem; font-weight: 700; font-size: .9rem; color: var(--muted); padding: .35rem .8rem .35rem .4rem; border-radius: 999px; background: #fff; border: 1px solid var(--line); }
.steps li span { width: 22px; height: 22px; border-radius: 50%; display: grid; place-items: center; background: var(--line); color: var(--ink); font-size: .75rem; }
.steps li.on { color: var(--brand-ink); border-color: #F5C9A6; background: var(--brand-soft); }
.steps li.on span { background: var(--brand); color: #fff; }
.steps li.done span { background: var(--leaf); color: #fff; }

/* ---------- Bill ---------- */
.bill { width: 100%; border-collapse: collapse; font-size: .95rem; }
.bill td { padding: .32rem 0; }
.bill td:last-child { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.bill tr.total td { border-top: 1px dashed var(--line); padding-top: .6rem; font-size: 1.15rem; font-weight: 800; }
.lines { width: 100%; border-collapse: collapse; font-size: .92rem; }
.lines th { text-align: left; font-size: .74rem; letter-spacing: .06em; text-transform: uppercase; color: var(--muted); font-weight: 700; padding: .25rem 0; border-bottom: 1px solid var(--line); }
.lines td { padding: .4rem .25rem .4rem 0; border-bottom: 1px solid #F3EAE1; vertical-align: top; }
.lines td.n, .lines th.n { text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }
.lines .opt { display: block; color: var(--muted); font-size: .8rem; }

/* ---------- Empty and success states ---------- */
.empty { text-align: center; padding: 2.5rem 1rem; border: 2px dashed var(--line); border-radius: 22px; background: #fff; }
.empty .big { font-size: 3.5rem; } .empty h3 { margin: .4rem 0 .2rem; } .empty p { color: var(--muted); margin: 0 auto; max-width: 38ch; }
.success { text-align: center; padding: 1.4rem 1rem 1rem; }
.success .tick { width: 74px; height: 74px; margin: 0 auto .6rem; border-radius: 50%; background: var(--leaf); color: #fff; font-size: 2.4rem; display: grid; place-items: center; animation: pop .5s cubic-bezier(.2,.9,.3,1.3) both; box-shadow: 0 10px 24px rgba(21,128,61,.3); }
.success h1 { margin: 0; font-size: clamp(1.7rem, 4vw, 2.3rem); }
.demo-note { border-radius: 12px; padding: .6rem .85rem; background: var(--amber-soft); color: #78350F; font-size: .9rem; border: 1px solid #FCD34D; }

/* ---------- Payment method cards (styled radio) ---------- */
.st-key-pay-method [data-testid="stElementContainer"], .st-key-pay-method [data-testid="stRadio"] { width: 100%; }
.st-key-pay-method [role="radiogroup"] { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: .75rem; width: 100%; }
.st-key-pay-method [role="radiogroup"] > div { border: 2px solid var(--line); border-radius: 16px; padding: .9rem 1rem; background: #fff; transition: border-color .15s, box-shadow .15s; cursor: pointer; }
.st-key-pay-method [role="radiogroup"] > div:hover { border-color: #F5C9A6; }
.st-key-pay-method [role="radiogroup"] > div[data-selected="true"] { border-color: var(--brand); box-shadow: 0 0 0 4px var(--brand-soft); }
.st-key-pay-method [data-testid="stRadioOption"] p { font-weight: 700; font-size: 1.02rem; }
.qr { width: 168px; height: 168px; border-radius: 14px; background: #fff; padding: 10px; border: 1px solid var(--line); }

/* ---------- Metrics ---------- */
[data-testid="stMetric"] { background: #fff; border: 1px solid var(--line); border-radius: 16px; padding: .8rem 1rem; box-shadow: var(--shadow); }
[data-testid="stMetricValue"] { font-variant-numeric: tabular-nums; }

/* ---------- Small screens ---------- */
@media (max-width: 640px) {
  [data-testid="stMainBlockContainer"] { padding-left: 1rem; padding-right: 1rem; }
  .hero { border-radius: 18px; }
  [class*="st-key-card-"] { padding: .75rem; }
}
</style>
"""

VENDOR_CSS = """
<style>
.stButton button[kind="primary"], .stFormSubmitButton button[kind="primaryFormSubmit"] { background: #0F766E; border-color: #0F766E; }
.stButton button[kind="primary"]:hover:not(:disabled) { background: #115E59; border-color: #115E59; }
button:focus-visible, a:focus-visible, [role="tab"]:focus-visible, input:focus-visible, textarea:focus-visible { outline-color: #0F766E !important; }
[data-testid="stMainBlockContainer"] { max-width: 1280px; }
</style>
"""


def inject(vendor: bool = False) -> None:
    st.html(CSS + (VENDOR_CSS if vendor else ""))

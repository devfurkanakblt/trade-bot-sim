from flask import Flask, Response, jsonify

from src.storage.db import get_recent_trades

INDEX_HTML = """<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<title>Trade Bot Sim - Canlı Panel</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 24px; background: #f5f6f8; color: #1a1d21; }
  h1 { font-size: 20px; }
  .totals { margin: 12px 0 20px; font-size: 16px; }
  table { border-collapse: collapse; width: 100%; }
  th, td { padding: 8px 12px; text-align: left; border-bottom: 1px solid #e0e2e6; }
  th { color: #5c626b; font-weight: 600; }
  .BUY { color: #1e9e57; font-weight: 700; }
  .SELL { color: #d63a2b; font-weight: 700; }
  .HOLD { color: #6b7078; font-weight: 700; }
  .pos { color: #1e9e57; }
  .neg { color: #d63a2b; }
  .muted { color: #6b7078; font-size: 12px; }
  .charts { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 24px; }
  .chart { background: #ffffff; border: 1px solid #e0e2e6; border-radius: 8px; padding: 12px; }
  .chart h2 { font-size: 14px; margin: 0 0 6px; display: flex; justify-content: space-between; }
  .chart svg { width: 100%; height: 120px; display: block; }
</style>
</head>
<body>
<h1>Trade Bot Sim — Canlı Panel</h1>
<div class="totals" id="totals">Yükleniyor…</div>
<div class="charts" id="charts"></div>
<table>
  <thead>
    <tr><th>Bot</th><th>Karar</th><th>Sembol</th><th>Net K/Z ($)</th><th>Net K/Z (%)</th><th>Nakit</th><th>Portföy</th></tr>
  </thead>
  <tbody id="rows"></tbody>
</table>
<p class="muted" id="updated"></p>
<script>
function fmt(n) { return (n >= 0 ? "+" : "") + n.toFixed(2); }
function cls(n) { return n >= 0 ? "pos" : "neg"; }
async function refresh() {
  try {
    const r = await fetch("/api/state");
    const d = await r.json();
    document.getElementById("totals").innerHTML =
      "Toplam portföy: <b>$" + d.total_value.toFixed(2) + "</b> &nbsp; " +
      "Toplam net K/Z: <b class='" + cls(d.total_pnl_abs) + "'>$" + fmt(d.total_pnl_abs) + "</b>";
    const rows = d.agents.map(a =>
      "<tr>" +
      "<td>" + a.name + "</td>" +
      "<td class='" + a.decision + "'>" + a.decision + "</td>" +
      "<td>" + (a.symbol || "—") + "</td>" +
      "<td class='" + cls(a.pnl_abs) + "'>$" + fmt(a.pnl_abs) + "</td>" +
      "<td class='" + cls(a.pnl_pct) + "'>" + fmt(a.pnl_pct) + "%</td>" +
      "<td>$" + a.cash.toFixed(2) + "</td>" +
      "<td>$" + a.total_value.toFixed(2) + "</td>" +
      "</tr>"
    ).join("");
    document.getElementById("rows").innerHTML = rows;
    document.getElementById("updated").textContent =
      d.updated_at ? ("Son güncelleme: " + d.updated_at) : "Henüz veri yok";
  } catch (e) {
    document.getElementById("updated").textContent = "Bağlantı hatası, yeniden denenecek…";
  }
}
refresh();
setInterval(refresh, 5000);

const CHART_W = 300, CHART_H = 120, PAD = 6;
function chartPoints(series) {
  const closes = series.map(p => p.c);
  const min = Math.min(...closes), max = Math.max(...closes);
  const span = (max - min) || 1;
  const n = series.length;
  return series.map((p, i) => {
    const x = n === 1 ? CHART_W / 2 : PAD + (i / (n - 1)) * (CHART_W - 2 * PAD);
    const y = PAD + (1 - (p.c - min) / span) * (CHART_H - 2 * PAD);
    return x.toFixed(1) + "," + y.toFixed(1);
  }).join(" ");
}
async function drawCharts() {
  try {
    const r = await fetch("/api/candles");
    const d = await r.json();
    const html = Object.keys(d).map(sym => {
      const series = d[sym];
      if (!series || series.length === 0) return "";
      const last = series[series.length - 1].c;
      const up = last >= series[0].c;
      const color = up ? "#1e9e57" : "#d63a2b";
      return "<div class='chart'>" +
        "<h2><span>" + sym + "</span><span class='" + (up ? "pos" : "neg") + "'>$" + last.toFixed(2) + "</span></h2>" +
        "<svg viewBox='0 0 " + CHART_W + " " + CHART_H + "' preserveAspectRatio='none'>" +
        "<polyline fill='none' stroke='" + color + "' stroke-width='1.5' vector-effect='non-scaling-stroke' points='" + chartPoints(series) + "'/>" +
        "</svg></div>";
    }).join("");
    document.getElementById("charts").innerHTML = html || "<p class='muted'>Grafik verisi bekleniyor…</p>";
  } catch (e) { /* sessizce yeniden denenecek */ }
}
drawCharts();
setInterval(drawCharts, 15000);
</script>
</body>
</html>
"""

MAIN_NAV = """<nav style="display:flex;align-items:center;gap:8px;margin:0 0 24px;padding-bottom:14px;border-bottom:1px solid #e0e2e6">
<a href="/" aria-current="page" style="padding:7px 10px;border-radius:6px;background:#1a1d21;color:#f5f6f8;text-decoration:none;font-size:14px;font-weight:650">Canli Panel</a>
<a href="/results" style="padding:7px 10px;border-radius:6px;color:#343940;text-decoration:none;font-size:14px;font-weight:650">Bot Sonuclari</a>
</nav>"""

RESULTS_HTML = """<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<title>Trade Bot Sim - Bot Sonuclari</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 24px; background: #f5f6f8; color: #1a1d21; }
  h1 { font-size: 22px; margin: 0; } h2 { font-size: 15px; margin: 30px 0 10px; }
  .sub { color: #5c626b; margin: 6px 0 0; font-size: 14px; }
  .summary { display: flex; gap: 28px; flex-wrap: wrap; margin: 22px 0; padding: 14px 0; border-top: 1px solid #e0e2e6; border-bottom: 1px solid #e0e2e6; }
  .summary span { color: #5c626b; font-size: 12px; display: block; } .summary b { font-size: 18px; }
  .table-wrap { overflow-x: auto; background: #ffffff; border: 1px solid #e0e2e6; border-radius: 8px; }
  table { border-collapse: collapse; min-width: 720px; width: 100%; }
  th, td { padding: 10px 12px; text-align: left; border-bottom: 1px solid #e0e2e6; font-size: 13px; }
  th { color: #5c626b; font-weight: 650; background: #fafbfc; } tr:last-child td { border-bottom: 0; }
  .positive { color: #1e9e57; font-weight: 650; } .negative { color: #d63a2b; font-weight: 650; }
  .tag { display: inline-block; padding: 3px 7px; border-radius: 99px; background: #eef0f2; color: #343940; font-size: 11px; font-weight: 700; }
  .tag.futures { background: #fff1e9; color: #a64415; } .tag.long { background: #e8f6ee; color: #187743; } .tag.short { background: #fceaea; color: #ab3329; }
  .muted { color: #6b7078; } .empty { padding: 24px 12px; color: #6b7078; }
  @media (max-width: 640px) { body { margin: 16px; } .summary { gap: 18px; } }
</style>
</head>
<body>
<nav style="display:flex;align-items:center;gap:8px;margin:0 0 24px;padding-bottom:14px;border-bottom:1px solid #e0e2e6">
<a href="/" style="padding:7px 10px;border-radius:6px;color:#343940;text-decoration:none;font-size:14px;font-weight:650">Canli Panel</a>
<a href="/results" aria-current="page" style="padding:7px 10px;border-radius:6px;background:#1a1d21;color:#f5f6f8;text-decoration:none;font-size:14px;font-weight:650">Bot Sonuclari</a>
</nav>
<h1>Bot Sonuclari</h1>
<p class="sub">Anlik portfoy durumu ve kalici islem gecmisi.</p>
<div class="summary" id="summary"><span>Yukleniyor</span></div>
<h2>Bot durumu</h2>
<div class="table-wrap"><table><thead><tr><th>Bot</th><th>Mod</th><th>Son karar</th><th>Sembol</th><th>Toplam K/Z</th><th>Portfoy</th><th>Acik pozisyon</th></tr></thead><tbody id="agents"></tbody></table></div>
<h2>Son islemler</h2>
<div class="table-wrap"><table><thead><tr><th>Zaman</th><th>Bot</th><th>Sembol</th><th>Islem</th><th>Fiyat</th><th>Adet</th><th>Gerceklesen K/Z</th></tr></thead><tbody id="trades"></tbody></table></div>
<script>
function esc(v) { const e = document.createElement('span'); e.textContent = v == null ? '' : String(v); return e.innerHTML; }
function usd(n, signed=false) { if (n == null) return '-'; const p = signed && n >= 0 ? '+' : ''; return p + '$' + Number(n).toFixed(2); }
function valueClass(n) { return n >= 0 ? 'positive' : 'negative'; }
function positionText(p) { const items = Object.entries(p || {}); if (!items.length) return '<span class="muted">Yok</span>'; return items.map(([s, v]) => esc(s) + ' ' + esc(v.side || 'LONG') + (v.leverage > 1 ? ' ' + esc(v.leverage) + 'x' : '')).join('<br>'); }
function modeTag(a) { return '<span class="tag ' + (a.mode === 'FUTURES' ? 'futures' : '') + '">' + esc(a.mode || 'SPOT') + (a.mode === 'FUTURES' ? ' ' + esc(a.leverage) + 'x' : '') + '</span>'; }
function tradeTag(side) { const c = side.includes('SHORT') ? 'short' : side.includes('LONG') ? 'long' : ''; return '<span class="tag ' + c + '">' + esc(side) + '</span>'; }
function render(data) {
  const agents = data.state.agents || [];
  document.getElementById('summary').innerHTML = '<div><span>Izlenen bot</span><b>' + agents.length + '</b></div><div><span>Toplam portfoy</span><b>' + usd(data.state.total_value || 0) + '</b></div><div><span>Toplam K/Z</span><b class="' + valueClass(data.state.total_pnl_abs || 0) + '">' + usd(data.state.total_pnl_abs || 0, true) + '</b></div><div><span>Son guncelleme</span><b>' + esc(data.state.updated_at ? new Date(data.state.updated_at).toLocaleString('tr-TR') : 'Veri bekleniyor') + '</b></div>';
  document.getElementById('agents').innerHTML = agents.length ? agents.map(a => '<tr><td><b>' + esc(a.name) + '</b></td><td>' + modeTag(a) + '</td><td>' + tradeTag(a.decision) + '</td><td>' + esc(a.symbol || '-') + '</td><td class="' + valueClass(a.pnl_abs) + '">' + usd(a.pnl_abs, true) + ' (' + Number(a.pnl_pct).toFixed(2) + '%)</td><td>' + usd(a.total_value) + '</td><td>' + positionText(a.positions) + '</td></tr>').join('') : '<tr><td colspan="7" class="empty">Botlardan ilk veri bekleniyor.</td></tr>';
  const trades = data.trades || [];
  document.getElementById('trades').innerHTML = trades.length ? trades.map(t => '<tr><td>' + esc(new Date(t.timestamp).toLocaleString('tr-TR')) + '</td><td>' + esc(t.agent_name) + '</td><td>' + esc(t.symbol) + '</td><td>' + tradeTag(t.side) + '</td><td>' + usd(t.price) + '</td><td>' + Number(t.quantity).toFixed(6) + '</td><td class="' + (t.pnl == null ? 'muted' : valueClass(t.pnl)) + '">' + usd(t.pnl, true) + '</td></tr>').join('') : '<tr><td colspan="7" class="empty">Henuz kaydedilmis islem yok.</td></tr>';
}
async function refresh() { try { const r = await fetch('/api/results'); render(await r.json()); } catch (_) { document.getElementById('summary').innerHTML = '<span>Sonuc verisi alinamadi, yeniden denenecek.</span>'; } }
refresh(); setInterval(refresh, 5000);
</script>
</body>
</html>"""


def create_app(live_state, storage_conn=None) -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def index() -> Response:
        return Response(INDEX_HTML.replace("<body>", f"<body>{MAIN_NAV}", 1), mimetype="text/html")

    @app.get("/results")
    def results() -> Response:
        return Response(RESULTS_HTML, mimetype="text/html")

    @app.get("/api/state")
    def api_state():
        return jsonify(live_state.snapshot())

    @app.get("/api/candles")
    def api_candles():
        return jsonify(live_state.candles_snapshot())

    @app.get("/api/results")
    def api_results():
        trades = get_recent_trades(storage_conn) if storage_conn is not None else []
        return jsonify({"state": live_state.snapshot(), "trades": trades})

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    return app


def run_dashboard(live_state, port: int, storage_conn=None) -> None:
    app = create_app(live_state, storage_conn=storage_conn)
    app.run(host="127.0.0.1", port=port, threaded=True, use_reloader=False)

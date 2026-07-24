from flask import Flask, Response, jsonify

INDEX_HTML = """<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<title>Trade Bot Sim - Canlı Panel</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 24px; background: #0f1115; color: #e6e6e6; }
  h1 { font-size: 20px; }
  .totals { margin: 12px 0 20px; font-size: 16px; }
  table { border-collapse: collapse; width: 100%; }
  th, td { padding: 8px 12px; text-align: left; border-bottom: 1px solid #2a2d34; }
  th { color: #9aa0aa; font-weight: 600; }
  .BUY { color: #2ecc71; font-weight: 700; }
  .SELL { color: #e74c3c; font-weight: 700; }
  .HOLD { color: #8a8f98; font-weight: 700; }
  .pos { color: #2ecc71; }
  .neg { color: #e74c3c; }
  .muted { color: #8a8f98; font-size: 12px; }
  .charts { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 24px; }
  .chart { background: #171a21; border: 1px solid #2a2d34; border-radius: 8px; padding: 12px; }
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
      const color = up ? "#2ecc71" : "#e74c3c";
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


def create_app(live_state) -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def index() -> Response:
        return Response(INDEX_HTML, mimetype="text/html")

    @app.get("/api/state")
    def api_state():
        return jsonify(live_state.snapshot())

    @app.get("/api/candles")
    def api_candles():
        return jsonify(live_state.candles_snapshot())

    return app


def run_dashboard(live_state, port: int) -> None:
    app = create_app(live_state)
    app.run(host="127.0.0.1", port=port, threaded=True, use_reloader=False)

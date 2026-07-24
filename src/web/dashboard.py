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
</style>
</head>
<body>
<h1>Trade Bot Sim — Canlı Panel</h1>
<div class="totals" id="totals">Yükleniyor…</div>
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

    return app


def run_dashboard(live_state, port: int) -> None:
    app = create_app(live_state)
    app.run(host="127.0.0.1", port=port, threaded=True, use_reloader=False)

from src.portfolio.portfolio import Portfolio


def compute_agent_report(
    agent_name: str,
    portfolio: Portfolio,
    current_prices: dict[str, float],
    trades_today: list[dict],
    previous_balance: float,
) -> dict:
    balance = portfolio.total_value(current_prices)
    total_pnl_abs, total_pnl_pct = portfolio.total_pnl(current_prices)
    daily_pnl_abs = balance - previous_balance
    daily_pnl_pct = (daily_pnl_abs / previous_balance * 100) if previous_balance else 0.0

    sell_trades = [t for t in trades_today if t["side"] == "SELL" and t.get("pnl") is not None]
    wins = [t for t in sell_trades if t["pnl"] > 0]
    win_rate_pct = (len(wins) / len(sell_trades) * 100) if sell_trades else 0.0

    return {
        "name": agent_name,
        "balance": balance,
        "daily_pnl_abs": daily_pnl_abs,
        "daily_pnl_pct": daily_pnl_pct,
        "total_pnl_abs": total_pnl_abs,
        "total_pnl_pct": total_pnl_pct,
        "open_positions": list(portfolio.positions.keys()),
        "trades_today": len(trades_today),
        "win_rate_pct": win_rate_pct,
    }


def build_daily_report(agent_reports: list[dict], report_date: str) -> str:
    ranked = sorted(agent_reports, key=lambda r: r["total_pnl_pct"], reverse=True)
    lines = [f"Trade Bot Sim - Daily Report - {report_date}", ""]
    for rank, r in enumerate(ranked, start=1):
        lines.append(f"#{rank} {r['name']}")
        lines.append(f"  Balance: ${r['balance']:.2f}")
        lines.append(f"  Today: {r['daily_pnl_abs']:+.2f}$ ({r['daily_pnl_pct']:+.2f}%)")
        lines.append(f"  Total: {r['total_pnl_abs']:+.2f}$ ({r['total_pnl_pct']:+.2f}%)")
        lines.append(f"  Open positions: {', '.join(r['open_positions']) or 'none'}")
        lines.append(f"  Trades today: {r['trades_today']} | Win rate: {r['win_rate_pct']:.1f}%")
        lines.append("")
    return "\n".join(lines)

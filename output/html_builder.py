"""
Fairway Intel — HTML Builder (complete)
Generates the complete index.html pushed to GitHub Pages.
Preserves prior analysis, updates incrementally.
Two separate rankings: Overall and Value. Pool section always separate.
Flags tab always present.
"""

import json
from datetime import datetime
from typing import Dict, List, Optional


def build_full_html(state: Dict) -> str:
    event      = state.get("event", {})
    analysis   = state.get("analysis", {})
    bet_card   = state.get("bet_card", {})
    pool       = state.get("pool", {})
    flags      = state.get("flags", {})
    weather    = state.get("weather", {})
    odds       = state.get("odds", {})
    run_log    = state.get("run_log", [])

    event_name   = event.get("name", "Current Event")
    course_name  = event.get("course", "TBD")
    last_updated = analysis.get("last_updated", datetime.now().isoformat())

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Fairway Intel — {event_name}</title>
  <style>{_css()}</style>
</head>
<body>
  <div class="container">
    {_header(event_name, course_name, last_updated, weather)}
    <nav class="tabs">
      <button class="tab-btn active"  onclick="showTab('briefing')">📋 Briefing</button>
      <button class="tab-btn"         onclick="showTab('rankings')">📊 Rankings</button>
      <button class="tab-btn"         onclick="showTab('betcard')">🎯 Bet Card</button>
      <button class="tab-btn"         onclick="showTab('frl')">⛳ FRL</button>
      <button class="tab-btn pool-tab" onclick="showTab('pool')">💰 Pool</button>
      <button class="tab-btn"         onclick="showTab('players')">👤 Players</button>
      <button class="tab-btn flags-tab" onclick="showTab('flags')">🚩 Flags</button>
    </nav>
    <div id="tab-briefing" class="tab-content active">{_briefing_tab(analysis, weather, event)}</div>
    <div id="tab-rankings" class="tab-content">{_rankings_tab(analysis)}</div>
    <div id="tab-betcard" class="tab-content">{_betcard_tab(bet_card)}</div>
    <div id="tab-frl"     class="tab-content">{_frl_tab(bet_card, weather)}</div>
    <div id="tab-pool"    class="tab-content">{_pool_tab(pool)}</div>
    <div id="tab-players" class="tab-content">{_players_tab(analysis)}</div>
    <div id="tab-flags"   class="tab-content">{_flags_tab(flags, run_log)}</div>
  </div>
  <script>{_javascript()}</script>
</body>
</html>"""
    return html


# ─────────────────────────────────────────────────────────────
# SECTION BUILDERS
# ─────────────────────────────────────────────────────────────

def _header(event_name, course, last_updated, weather):
    try:
        dt = datetime.fromisoformat(last_updated)
        updated_str = dt.strftime("%a %b %d %Y %I:%M %p ET")
    except Exception:
        updated_str = last_updated or "Pending"

    r1 = weather.get("r1", {})
    r1_wind = r1.get("wind_mph")
    weather_badge = (
        f'<span class="weather-badge">{r1.get("category","").upper()} WIND R1 ~{r1_wind:.0f}mph</span>'
        if r1_wind else ""
    )
    wave_badge = (
        '<span class="wave-badge">⚠️ WAVE SPLIT MATTERS</span>'
        if weather.get("wave_split_matters") else ""
    )
    return f"""
<header class="site-header">
  <div class="header-logo">⛳ FAIRWAY INTEL</div>
  <div class="header-event">
    <h1>{event_name}</h1>
    <div class="header-meta">{course} {weather_badge} {wave_badge}</div>
  </div>
  <div class="header-updated">Last updated<br><strong>{updated_str}</strong></div>
</header>"""


def _briefing_tab(analysis, weather, event):
    briefing      = analysis.get("briefing_paragraph", "Briefing pending — check back after Sunday night's run.")
    course_notes  = event.get("course_notes", "")
    dominant_stat = event.get("dominant_stat", "TBD")
    dist_mult     = event.get("distance_multiplier", "TBD")
    rough         = event.get("rough_penalty", "TBD")
    angle         = event.get("angle_penalty", "TBD")

    weather_rows = ""
    for rn in ["r1", "r2", "r3", "r4"]:
        rd = weather.get(rn, {})
        if rd:
            weather_rows += f"""<tr>
  <td class="round-label">{rn.upper()}</td>
  <td>{rd.get('narrative','TBD')}</td>
  <td>{rd.get('wind_mph','?')} mph {rd.get('wind_dir','')}</td>
</tr>"""

    wave_alert = ""
    ws = weather.get("wave_split", {})
    if ws.get("wave_split_matters"):
        wave_alert = f'<div class="wave-alert">⚠️ {ws.get("explanation","")}</div>'

    return f"""
<section class="card">
  <div class="section-title">Weekly Briefing</div>
  <div class="briefing-text">{briefing}</div>
</section>
<div class="two-col">
  <section class="card">
    <div class="section-title">Course Profile</div>
    <div class="stat-row"><span class="stat-label">Dominant Stat</span><span class="stat-value dominant">{dominant_stat}</span></div>
    <div class="stat-row"><span class="stat-label">Distance Multiplier</span><span class="stat-value">{dist_mult}</span></div>
    <div class="stat-row"><span class="stat-label">Rough Penalty</span><span class="stat-value">{rough}</span></div>
    <div class="stat-row"><span class="stat-label">Angle Penalty</span><span class="stat-value">{angle}</span></div>
    <p class="muted-text">{course_notes}</p>
  </section>
  <section class="card">
    <div class="section-title">Weather by Round</div>
    {"<table class='weather-table'><tbody>" + weather_rows + "</tbody></table>" if weather_rows else "<p class='muted-text'>Weather data pending.</p>"}
    {wave_alert}
  </section>
</div>"""


def _rankings_tab(analysis):
    overall = analysis.get("overall_ranking", [])
    value   = analysis.get("value_ranking", [])
    tiers   = analysis.get("tiers", {})

    def rank_list(players, title, css_class):
        if not players:
            return f'<section class="card"><div class="section-title {css_class}">{title}</div><p class="muted-text">Pending odds and analysis.</p></section>'
        rows = ""
        for i, p in enumerate(players[:20], 1):
            name  = p if isinstance(p, str) else p.get("player", str(p))
            note  = "" if isinstance(p, str) else p.get("note", "")
            odds  = "" if isinstance(p, str) else p.get("odds", "")
            odds_span = f'<span class="rank-odds">{odds}</span>' if odds else ""
            rows += f'<div class="rank-row"><span class="rank-num">{i}</span><span class="rank-name">{name}</span>{odds_span}<span class="rank-note">{note}</span></div>'
        return f'<section class="card"><div class="section-title {css_class}">{title}</div>{rows}</section>'

    def tier_block(key, label, css):
        players = tiers.get(key, [])
        if not players:
            return ""
        items = ""
        for p in players:
            name   = p if isinstance(p, str) else p.get("player", str(p))
            reason = "" if isinstance(p, str) else p.get("reason", "")
            items += f'<div class="tier-item"><span class="tier-name">{name}</span><span class="tier-reason">{reason}</span></div>'
        return f'<div class="tier-block tier-{css}"><div class="tier-label">{label}</div>{items}</div>'

    return f"""
<div class="rankings-grid">
  {rank_list(overall, "🏆 Overall — Best Chance to Win", "title-blue")}
  {rank_list(value,   "💎 Value — Mispriced by Market",  "title-gold")}
</div>
<section class="card">
  <div class="section-title">Tier Assignments</div>
  <div class="tiers-grid">
    {tier_block("S",    "S Tier — Primary Targets",  "s")}
    {tier_block("A",    "A Tier — Strong Plays",      "a")}
    {tier_block("B",    "B Tier — Positions / FRL",   "b")}
    {tier_block("C",    "C Tier — Pass / Monitor",    "c")}
    {tier_block("FADE", "Fade — Active Fades",         "fade")}
  </div>
</section>"""


def _betcard_tab(bet_card):
    outrights  = bet_card.get("outrights", [])
    positions  = bet_card.get("positions", [])
    hard_fades = bet_card.get("hard_fades", [])
    last_upd   = bet_card.get("last_updated", "")

    if not outrights and not positions:
        return '<div class="empty-card">Bet card builds throughout the week. Final card by Wednesday 4pm ET.</div>'

    def outright_rows(bets):
        if not bets:
            return "<p class='muted-text'>No outrights yet.</p>"
        out = '<div class="bet-header"><span>Player</span><span>Odds</span><span>Stake</span><span>Reasoning</span></div>'
        for b in bets:
            out += f'''<div class="bet-row">
  <span class="bet-player">{b.get("player","")}</span>
  <span class="bet-odds">{b.get("odds","")}</span>
  <span class="bet-stake">{b.get("stake","")}</span>
  <span class="bet-note">{b.get("note","")}</span>
</div>'''
        return out

    def pos_rows(bets):
        if not bets:
            return "<p class='muted-text'>No positions yet.</p>"
        out = ""
        for b in bets:
            out += f'<div class="pos-row"><span class="pos-player">{b.get("player","")}</span><span class="pos-market">{b.get("market","")}</span><span class="pos-odds">{b.get("odds","")}</span><span class="pos-stake">{b.get("stake","")}</span></div>'
        return out

    fade_section = ""
    if hard_fades:
        rows = "".join(
            f'<div class="fade-row"><span class="fade-player">✗ {f.get("player","")}</span><span class="fade-reason">{f.get("reason","")}</span></div>'
            for f in hard_fades
        )
        fade_section = f'<section class="card fade-card"><div class="section-title">Hard Fades</div>{rows}</section>'

    return f"""
<section class="card">
  <div class="section-title">Outrights</div>
  {outright_rows(outrights)}
</section>
<section class="card">
  <div class="section-title">Positions</div>
  {pos_rows(positions)}
</section>
{fade_section}
<p class="muted-text" style="margin-top:8px">Last updated: {last_upd or "Pending"}</p>"""


def _frl_tab(bet_card, weather):
    frl_bets = bet_card.get("frl", [])
    ws = weather.get("wave_split", {})
    wave_box = (
        f'<div class="wave-alert-box"><strong>⚠️ WAVE SPLIT MATTERS</strong><br>{ws.get("explanation","")}</div>'
        if ws.get("wave_split_matters") else ""
    )

    if not frl_bets:
        return f"""{wave_box}
<div class="empty-card">
  FRL targets confirmed once wave assignments are locked in.<br>
  Always verify tee time / wave before placing FRL bets.
</div>"""

    rows = ""
    for b in frl_bets:
        rows += f"""<div class="frl-row">
  <span class="frl-player">{b.get("player","")}</span>
  <span class="frl-wave">Wave: {b.get("wave","TBD")} | {b.get("tee_time","TBD")}</span>
  <span class="frl-odds">{b.get("odds","")}</span>
  <span class="frl-notes">{b.get("notes","")}</span>
</div>"""

    return f"""{wave_box}
<section class="card">
  <div class="section-title">FRL Targets — By Wave</div>
  <p class="muted-text" style="margin-bottom:12px">Wave matters meaningfully. Always confirm wave assignment before betting FRL.</p>
  {rows}
</section>"""


def _pool_tab(pool):
    primary    = pool.get("primary_pick") or {}
    available  = pool.get("available_plays", [])
    traps      = pool.get("trap_plays", [])
    usage_tbl  = pool.get("season_usage_table", [])
    tier_note  = pool.get("tier_note", "")
    strategy   = pool.get("strategy_note", "")

    primary_html = ""
    if primary and primary.get("player"):
        notes_html = "<br>".join(primary.get("notes", []))
        primary_html = f"""<div class="pool-primary">
  <div class="pool-primary-label">PRIMARY PICK</div>
  <div class="pool-primary-player">{primary["player"]}</div>
  <div class="pool-primary-notes">{notes_html}</div>
  <div class="pool-uses">Uses remaining: {primary.get("uses_remaining","?")}/2</div>
</div>"""

    avail_rows = "".join(
        f'<div class="pool-avail-row"><span class="pool-player">{p.get("player","")}</span>'
        f'<span class="pool-uses-sm">{p.get("uses_remaining","?")}/2 uses</span>'
        f'<span class="pool-pnotes">{" | ".join(p.get("notes",[]))}</span></div>'
        for p in available
    )
    trap_rows = "".join(
        f'<div class="pool-trap">✗ {t.get("player","")} — {t.get("reason","")}</div>'
        for t in traps
    )
    usage_rows = "".join(
        f'<tr class="{"exhausted" if u.get("status")=="EXHAUSTED" else ""}">'
        f'<td>{u.get("player","")}</td><td>{u.get("uses",0)}</td>'
        f'<td>{u.get("remaining",0)}</td><td>{u.get("status","")}</td></tr>'
        for u in usage_tbl
    )

    return f"""
<div class="pool-banner">⚠️ POOL IS COMPLETELY SEPARATE FROM BET CARD — ODDS ARE IRRELEVANT — PICK MOST LIKELY WINNER</div>
<p class="pool-tier-note">{tier_note}</p>
<p class="muted-text">{strategy}</p>
{primary_html}
{"<section class='card'><div class='section-title'>Available Plays</div>" + avail_rows + "</section>" if avail_rows else ""}
{"<section class='card fade-card'><div class='section-title'>Trap Plays — Do Not Select</div>" + trap_rows + "</section>" if trap_rows else ""}
<section class="card">
  <div class="section-title">Season Usage Tracker (2 uses max per player)</div>
  <table class="usage-table">
    <thead><tr><th>Player</th><th>Uses</th><th>Remaining</th><th>Status</th></tr></thead>
    <tbody>{usage_rows}</tbody>
  </table>
</section>"""


def _players_tab(analysis):
    notes = analysis.get("player_notes", {})
    if not notes:
        return '<div class="empty-card">Player notes build throughout the week. Every field member gets a note.</div>'

    rows = ""
    for player, data in sorted(notes.items()):
        tier      = data.get("tier", "C") if isinstance(data, dict) else "C"
        note_text = data.get("note", data) if isinstance(data, dict) else str(data)
        rows += f"""<div class="pn-row tier-border-{tier.lower()}" data-name="{player.lower()}">
  <span class="pn-name">{player}</span>
  <span class="tier-badge tier-badge-{tier.lower()}">{tier}</span>
  <span class="pn-text">{note_text}</span>
</div>"""

    return f"""
<section class="card">
  <div class="section-title">Full Field — Player Notes</div>
  <input type="text" id="playerSearch" onkeyup="filterPlayers()" placeholder="Search player name…" class="search-input">
  <div id="playerList" style="margin-top:8px">{rows}</div>
</section>"""


def _flags_tab(flags, run_log):
    def flag_list(items, title, icon):
        if not items:
            return ""
        rows = "".join(
            f'<div class="flag-item">{icon} {i if isinstance(i,str) else json.dumps(i)}</div>'
            for i in items
        )
        return f'<div class="flag-group"><div class="flag-title">{title}</div>{rows}</div>'

    run_rows = "".join(
        f'<div class="run-item">{r.get("time","")} — {r.get("run_type","")} — {r.get("status","")}</div>'
        for r in (run_log or [])[-10:]
    )

    return f"""
<section class="card">
  <div class="section-title">🚩 Flags, Gaps &amp; Manual Log</div>
  {flag_list(flags.get("blocked_articles",[]),      "Blocked Articles",            "🔒")}
  {flag_list(flags.get("odds_gaps",[]),             "Odds Gaps",                   "❓")}
  {flag_list(flags.get("data_anomalies",[]),        "Data Anomalies",              "⚠️")}
  {flag_list(flags.get("analysis_uncertainties",[]),"Analysis Uncertainties",      "🤔")}
  {flag_list(flags.get("manual_interventions",[]),  "Manual Interventions",        "✏️")}
  {flag_list(flags.get("withdrawals",[]),           "Withdrawals",                 "🚫")}
  {flag_list(flags.get("calibration_suggestions",[]),"Calibration Suggestions",    "🎯")}
  {flag_list(flags.get("article_log",[]),           "Article Processing Log",      "📰")}
  {"<div class='flag-group'><div class='flag-title'>Run Log (Last 10)</div>" + run_rows + "</div>" if run_rows else ""}
</section>"""


# ─────────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────────

def _css():
    return """
:root{--bg:#0d1117;--surface:#161b22;--surface2:#21262d;--border:#30363d;
--text:#e6edf3;--muted:#8b949e;--green:#3fb950;--blue:#58a6ff;
--gold:#f0b429;--red:#f85149;--accent:#1f6feb;--purple:#a371f7}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:14px;line-height:1.6}
.container{max-width:1200px;margin:0 auto;padding:16px}

/* HEADER */
.site-header{display:flex;align-items:center;gap:16px;padding:16px;background:var(--surface);
border-radius:8px;margin-bottom:16px;border:1px solid var(--border)}
.header-logo{font-size:22px;font-weight:800;color:var(--green);white-space:nowrap}
.header-event{flex:1}
.header-event h1{font-size:20px;font-weight:700}
.header-meta{color:var(--muted);font-size:12px;display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:4px}
.header-updated{text-align:right;font-size:12px;color:var(--muted);white-space:nowrap}
.weather-badge{background:#1a3f1a;color:var(--green);padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600}
.wave-badge{background:#3d2a00;color:var(--gold);padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600}

/* TABS */
.tabs{display:flex;gap:4px;margin-bottom:16px;flex-wrap:wrap}
.tab-btn{background:var(--surface);border:1px solid var(--border);color:var(--muted);
padding:8px 14px;border-radius:6px;cursor:pointer;font-size:13px;transition:all .15s}
.tab-btn:hover{border-color:var(--blue);color:var(--text)}
.tab-btn.active{background:var(--accent);border-color:var(--accent);color:#fff;font-weight:600}
.pool-tab.active{background:var(--gold);border-color:var(--gold);color:#000}
.flags-tab.active{background:var(--red);border-color:var(--red);color:#fff}
.tab-content{display:none}
.tab-content.active{display:block}

/* CARDS */
.card{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:16px;margin-bottom:16px}
.section-title{font-size:13px;font-weight:700;color:var(--muted);text-transform:uppercase;
letter-spacing:.5px;margin-bottom:12px;padding-bottom:8px;border-bottom:1px solid var(--border)}
.title-blue{color:var(--blue)}
.title-gold{color:var(--gold)}
.two-col{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media(max-width:768px){.two-col{grid-template-columns:1fr}}

/* BRIEFING */
.briefing-text{font-size:15px;line-height:1.85;white-space:pre-wrap}
.stat-row{display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid var(--border)}
.stat-label{color:var(--muted)}
.stat-value{font-weight:600}
.stat-value.dominant{color:var(--gold)}
.muted-text{color:var(--muted);font-size:13px;margin-top:8px}
.weather-table{width:100%;border-collapse:collapse}
.weather-table td{padding:6px 8px;border-bottom:1px solid var(--border)}
.round-label{font-weight:700;color:var(--blue);width:40px}
.wave-alert{background:#3d2a00;border:1px solid var(--gold);border-radius:6px;
padding:10px;color:var(--gold);margin-top:12px;font-size:13px}
.wave-alert-box{background:#3d2a00;border:1px solid var(--gold);border-radius:6px;
padding:12px;color:var(--gold);margin-bottom:16px}

/* RANKINGS */
.rankings-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px}
@media(max-width:768px){.rankings-grid{grid-template-columns:1fr}}
.rank-row{display:flex;align-items:baseline;gap:8px;padding:6px 0;border-bottom:1px solid var(--border)}
.rank-num{color:var(--muted);font-size:12px;width:22px;flex-shrink:0}
.rank-name{font-weight:600;flex:1}
.rank-odds{color:var(--green);font-size:13px;white-space:nowrap}
.rank-note{color:var(--muted);font-size:12px}
.tiers-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}
.tier-block{border-radius:6px;padding:12px;border:1px solid}
.tier-block.tier-s{border-color:var(--gold);background:rgba(240,180,41,.06)}
.tier-block.tier-a{border-color:var(--green);background:rgba(63,185,80,.06)}
.tier-block.tier-b{border-color:var(--blue);background:rgba(88,166,255,.06)}
.tier-block.tier-c{border-color:var(--border)}
.tier-block.tier-fade{border-color:var(--red);background:rgba(248,81,73,.06)}
.tier-label{font-size:11px;font-weight:700;text-transform:uppercase;margin-bottom:8px;letter-spacing:.5px}
.tier-item{padding:4px 0;border-bottom:1px solid var(--border)}
.tier-name{font-weight:600;font-size:13px}
.tier-reason{color:var(--muted);font-size:12px;display:block}

/* BET CARD */
.bet-header{display:grid;grid-template-columns:2fr 1fr 1fr 3fr;gap:8px;
padding:6px 0;color:var(--muted);font-size:11px;font-weight:600;
text-transform:uppercase;border-bottom:1px solid var(--border)}
.bet-row{display:grid;grid-template-columns:2fr 1fr 1fr 3fr;gap:8px;
padding:9px 0;border-bottom:1px solid var(--border);align-items:start}
.bet-player{font-weight:700}
.bet-odds{color:var(--green);font-weight:700}
.bet-stake{color:var(--gold)}
.bet-note{color:var(--muted);font-size:12px}
.pos-row{display:flex;gap:10px;padding:7px 0;border-bottom:1px solid var(--border)}
.pos-player{font-weight:600;flex:2}
.pos-market{color:var(--blue);font-size:12px;flex:1}
.pos-odds{color:var(--green);font-weight:600;flex:1}
.pos-stake{color:var(--gold);flex:1}
.fade-card{border-color:var(--red);background:rgba(248,81,73,.04)}
.fade-row{display:flex;gap:10px;padding:6px 0;border-bottom:1px solid var(--border)}
.fade-player{color:var(--red);font-weight:600;flex:2}
.fade-reason{color:var(--muted);font-size:12px;flex:3}
.empty-card{text-align:center;padding:48px 16px;color:var(--muted);
background:var(--surface);border:1px solid var(--border);border-radius:8px;
line-height:2;margin-bottom:16px}

/* FRL */
.frl-row{display:grid;grid-template-columns:2fr 2fr 1fr 3fr;gap:8px;
padding:10px 0;border-bottom:1px solid var(--border)}
@media(max-width:768px){.frl-row{grid-template-columns:1fr}}
.frl-player{font-weight:700}
.frl-wave{color:var(--blue);font-size:12px}
.frl-odds{color:var(--green);font-weight:700}
.frl-notes{color:var(--muted);font-size:12px}

/* POOL */
.pool-banner{background:#3d2a00;border:1px solid var(--gold);border-radius:6px;
padding:10px 16px;color:var(--gold);font-weight:700;font-size:13px;margin-bottom:12px}
.pool-tier-note{color:var(--muted);margin-bottom:6px;font-size:13px}
.pool-primary{background:rgba(240,180,41,.08);border:2px solid var(--gold);
border-radius:8px;padding:16px;margin:12px 0}
.pool-primary-label{font-size:11px;font-weight:700;text-transform:uppercase;
color:var(--gold);letter-spacing:1px}
.pool-primary-player{font-size:24px;font-weight:800;margin:4px 0}
.pool-primary-notes{color:var(--muted);font-size:13px}
.pool-uses{margin-top:6px;font-size:12px;color:var(--gold)}
.pool-avail-row{display:flex;gap:10px;padding:6px 0;border-bottom:1px solid var(--border)}
.pool-player{font-weight:600;flex:2}
.pool-uses-sm{color:var(--muted);font-size:12px;flex:1}
.pool-pnotes{color:var(--muted);font-size:12px;flex:3}
.pool-trap{color:var(--red);padding:6px 0;border-bottom:1px solid var(--border);font-size:13px}
.usage-table{width:100%;border-collapse:collapse;font-size:13px}
.usage-table th{background:var(--surface2);padding:8px;text-align:left;
color:var(--muted);font-size:12px}
.usage-table td{padding:7px 8px;border-bottom:1px solid var(--border)}
.usage-table tr.exhausted td{color:var(--red);opacity:.6;text-decoration:line-through}

/* PLAYERS */
.search-input{width:100%;padding:8px 12px;background:var(--surface2);
border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:14px}
.pn-row{display:grid;grid-template-columns:200px 50px 1fr;gap:8px;
padding:8px 0;border-bottom:1px solid var(--border);align-items:start;
border-left:3px solid var(--border);padding-left:8px}
.tier-border-s{border-left-color:var(--gold)}
.tier-border-a{border-left-color:var(--green)}
.tier-border-b{border-left-color:var(--blue)}
.tier-border-fade{border-left-color:var(--red)}
.pn-name{font-weight:600;font-size:13px}
.tier-badge{font-size:11px;font-weight:700;text-transform:uppercase;
padding:2px 6px;border-radius:4px;text-align:center}
.tier-badge-s{background:rgba(240,180,41,.2);color:var(--gold)}
.tier-badge-a{background:rgba(63,185,80,.2);color:var(--green)}
.tier-badge-b{background:rgba(88,166,255,.2);color:var(--blue)}
.tier-badge-c{background:var(--surface2);color:var(--muted)}
.tier-badge-fade{background:rgba(248,81,73,.2);color:var(--red)}
.pn-text{color:var(--muted);font-size:13px}

/* FLAGS */
.flag-group{margin-bottom:16px}
.flag-title{font-size:12px;font-weight:700;text-transform:uppercase;
color:var(--muted);margin-bottom:6px;padding-bottom:4px;border-bottom:1px solid var(--border)}
.flag-item{padding:5px 0;border-bottom:1px solid var(--border);font-size:13px;color:var(--muted)}
.run-item{padding:4px 0;font-size:12px;color:var(--muted);border-bottom:1px solid var(--border)}
"""


# ─────────────────────────────────────────────────────────────
# JAVASCRIPT
# ─────────────────────────────────────────────────────────────

def _javascript():
    return """
function showTab(name) {
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
  const content = document.getElementById('tab-' + name);
  if (content) content.classList.add('active');
  const btns = document.querySelectorAll('.tab-btn');
  btns.forEach(btn => { if (btn.getAttribute('onclick') === "showTab('" + name + "')") btn.classList.add('active'); });
}

function filterPlayers() {
  const q = document.getElementById('playerSearch').value.toLowerCase();
  document.querySelectorAll('.pn-row').forEach(row => {
    row.style.display = row.dataset.name && row.dataset.name.includes(q) ? '' : 'none';
  });
}
"""

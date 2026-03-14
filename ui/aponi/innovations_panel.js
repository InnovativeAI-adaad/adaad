/**
 * ADAAD Aponi — Innovations Panel (Phase 69)
 * ──────────────────────────────────────────
 * Four sub-panels rendered inside the Innovations tab:
 *   1. Oracle          — deterministic Q&A over evolutionary history
 *   2. Story Mode      — living narrative arc timeline
 *   3. Federation Map  — animated constellation galaxy canvas
 *   4. Seeds           — capability seed lifecycle registry
 *   5. Personalities   — agent identity cards (Architect / Dream / Beast)
 *
 * Self-contained: injects its own CSS, owns its state, wires to Phase 68 API.
 */
(function(global) {
  "use strict";

  /* ══════════════════════════════════════════════════════════════════════
     CSS INJECTION
  ══════════════════════════════════════════════════════════════════════ */
  const INNOVATIONS_CSS = `
    @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

    :root {
      --arch: #00e5ff;          /* Architect — ice cyan   */
      --dream: #e040fb;         /* Dream     — aurora mag */
      --beast: #ff6d00;         /* Beast     — ember      */
      --seed-glow: #69ff47;     /* Seed      — bio-green  */
      --oracle-glow: #ffe57f;   /* Oracle    — gold       */
      --inno-bg: #020810;
      --inno-panel: rgba(8,18,38,0.88);
      --inno-border: rgba(0,229,255,0.09);
      --inno-border-bright: rgba(0,229,255,0.25);
      --inno-glow: 0 0 40px rgba(0,229,255,0.07);
      --img-low-weight-opacity: 0.9;
      --img-low-weight-saturation: 0.9;
      --img-low-weight-max-glow: 6px;
      --img-low-weight-hover-opacity: 0.98;
      --img-low-weight-hover-saturation: 1;
      --img-low-weight-hover-glow-alpha: 0.18;
    }

    /* ── Innovations wrapper ──────────────────────────────────────── */
    .inno-wrap {
      display: grid;
      gap: 20px;
      padding-top: 8px;
      animation: inno-enter 0.45s cubic-bezier(.22,1,.36,1) both;
    }
    @keyframes inno-enter {
      from { opacity: 0; transform: translateY(14px); }
      to   { opacity: 1; transform: translateY(0); }
    }

    /* ── Sub-nav pills ────────────────────────────────────────────── */
    .inno-subnav {
      display: flex; gap: 6px; flex-wrap: wrap;
    }
    .inno-pill {
      font-family: 'Syne', sans-serif;
      font-size: 11px; font-weight: 700;
      letter-spacing: .12em; text-transform: uppercase;
      padding: 7px 16px; border-radius: 999px; cursor: pointer;
      border: 1px solid var(--inno-border);
      background: rgba(255,255,255,0.025);
      color: rgba(255,255,255,0.45);
      transition: all .18s ease;
    }
    .inno-pill:hover { color: rgba(255,255,255,0.8); border-color: rgba(0,229,255,0.22); }
    .inno-pill.active {
      color: #00e5ff;
      border-color: rgba(0,229,255,0.5);
      background: rgba(0,229,255,0.07);
      box-shadow: 0 0 18px rgba(0,229,255,0.12);
    }
    .inno-pill.dream.active  { color: var(--dream); border-color: rgba(224,64,251,0.5); background: rgba(224,64,251,0.07); box-shadow: 0 0 18px rgba(224,64,251,0.12); }
    .inno-pill.beast.active  { color: var(--beast); border-color: rgba(255,109,0,0.5);  background: rgba(255,109,0,0.07);  box-shadow: 0 0 18px rgba(255,109,0,0.12); }
    .inno-pill.seed.active   { color: var(--seed-glow); border-color: rgba(105,255,71,0.5); background: rgba(105,255,71,0.07); box-shadow: 0 0 18px rgba(105,255,71,0.12); }

    /* ── Glass card ───────────────────────────────────────────────── */
    .inno-card {
      border-radius: 18px;
      border: 1px solid var(--inno-border);
      background: var(--inno-panel);
      backdrop-filter: blur(16px);
      box-shadow: var(--inno-glow), 0 22px 55px rgba(0,0,0,0.55);
      overflow: hidden;
      position: relative;
    }
    .inno-card::before {
      content: '';
      position: absolute; top: 0; left: 0; right: 0; height: 1px;
      background: linear-gradient(90deg, transparent, rgba(0,229,255,0.35), transparent);
    }
    .inno-card-header {
      padding: 18px 22px 14px;
      display: flex; align-items: center; justify-content: space-between;
      border-bottom: 1px solid var(--inno-border);
    }
    .inno-card-title {
      font-family: 'Syne', sans-serif;
      font-size: 13px; font-weight: 800;
      letter-spacing: .15em; text-transform: uppercase;
      color: rgba(255,255,255,0.9);
      display: flex; align-items: center; gap: 10px;
    }
    .inno-card-icon {
      width: 28px; height: 28px; border-radius: 8px;
      display: flex; align-items: center; justify-content: center;
      font-size: 14px;
    }
    .inno-card-body { padding: 20px 22px; }

    /* ── Oracle panel ─────────────────────────────────────────────── */
    .oracle-input-row {
      display: flex; gap: 10px; margin-bottom: 20px;
    }
    .oracle-input {
      flex: 1;
      font-family: 'JetBrains Mono', monospace;
      font-size: 13px;
      padding: 10px 16px;
      background: rgba(255,229,127,0.04);
      border: 1px solid rgba(255,229,127,0.18);
      border-radius: 10px;
      color: var(--oracle-glow);
      outline: none;
      transition: border-color .15s, box-shadow .15s;
      caret-color: var(--oracle-glow);
    }
    .oracle-input::placeholder { color: rgba(255,229,127,0.3); }
    .oracle-input:focus {
      border-color: rgba(255,229,127,0.45);
      box-shadow: 0 0 20px rgba(255,229,127,0.08);
    }
    .oracle-btn {
      font-family: 'Syne', sans-serif;
      font-size: 11px; font-weight: 700;
      letter-spacing: .1em; text-transform: uppercase;
      padding: 10px 20px;
      background: rgba(255,229,127,0.1);
      border: 1px solid rgba(255,229,127,0.3);
      border-radius: 10px; color: var(--oracle-glow); cursor: pointer;
      transition: all .15s;
    }
    .oracle-btn:hover {
      background: rgba(255,229,127,0.16);
      box-shadow: 0 0 24px rgba(255,229,127,0.14);
    }
    .oracle-chips {
      display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px;
    }
    .oracle-chip {
      font-family: 'JetBrains Mono', monospace;
      font-size: 10px; padding: 4px 10px;
      border-radius: 6px; cursor: pointer;
      border: 1px solid rgba(255,229,127,0.18);
      color: rgba(255,229,127,0.55);
      background: rgba(255,229,127,0.03);
      transition: all .12s;
    }
    .oracle-chip:hover { color: var(--oracle-glow); border-color: rgba(255,229,127,0.4); background: rgba(255,229,127,0.07); }
    .oracle-result {
      font-family: 'JetBrains Mono', monospace;
      font-size: 11.5px; line-height: 1.65;
      color: rgba(255,229,127,0.8);
      background: rgba(255,229,127,0.025);
      border: 1px solid rgba(255,229,127,0.1);
      border-radius: 10px; padding: 16px;
      white-space: pre-wrap; word-break: break-word;
      max-height: 320px; overflow-y: auto;
      transition: all .25s;
    }
    .oracle-result:empty::before { content: 'Ask the oracle anything about ADAAD\'s evolutionary history…'; color: rgba(255,229,127,0.2); font-style: italic; }
    .oracle-loading {
      display: flex; align-items: center; gap: 10px;
      color: rgba(255,229,127,0.5); font-family: 'JetBrains Mono', monospace;
      font-size: 12px; padding: 12px 0;
    }
    .oracle-spinner {
      width: 16px; height: 16px; border-radius: 50%;
      border: 2px solid rgba(255,229,127,0.15);
      border-top-color: var(--oracle-glow);
      animation: spin 0.7s linear infinite;
    }

    /* ── Story Mode timeline ──────────────────────────────────────── */
    .story-timeline {
      display: flex; flex-direction: column; gap: 0;
      max-height: 440px; overflow-y: auto;
      padding-right: 4px;
    }
    .story-arc {
      display: flex; gap: 0; position: relative;
      animation: arc-enter 0.3s ease both;
    }
    @keyframes arc-enter {
      from { opacity: 0; transform: translateX(-8px); }
      to   { opacity: 1; transform: translateX(0); }
    }
    .story-arc-line {
      width: 28px; flex-shrink: 0;
      display: flex; flex-direction: column; align-items: center;
    }
    .story-arc-dot {
      width: 10px; height: 10px; border-radius: 50%;
      border: 2px solid var(--arch); background: rgba(0,229,255,0.15);
      margin-top: 14px; z-index: 1; flex-shrink: 0;
      transition: box-shadow .2s;
    }
    .story-arc:hover .story-arc-dot {
      box-shadow: 0 0 12px rgba(0,229,255,0.6);
    }
    .story-arc-dot.promoted { border-color: var(--seed-glow); background: rgba(105,255,71,0.15); }
    .story-arc-dot.rejected { border-color: rgba(255,70,70,0.8); background: rgba(255,70,70,0.1); }
    .story-arc-dot.dream    { border-color: var(--dream); background: rgba(224,64,251,0.15); }
    .story-arc-dot.beast    { border-color: var(--beast); background: rgba(255,109,0,0.15); }
    .story-arc-connector {
      width: 2px; flex: 1;
      background: linear-gradient(180deg, rgba(0,229,255,0.25), rgba(0,229,255,0.05));
      margin: 0 auto;
    }
    .story-arc-content {
      flex: 1; padding: 10px 0 10px 14px;
      border-bottom: 1px solid rgba(255,255,255,0.04);
    }
    .story-arc:last-child .story-arc-content { border-bottom: none; }
    .story-arc-epoch {
      font-family: 'JetBrains Mono', monospace;
      font-size: 10px; color: rgba(0,229,255,0.5);
      margin-bottom: 3px; letter-spacing: .06em;
    }
    .story-arc-title {
      font-family: 'Syne', sans-serif;
      font-size: 13px; font-weight: 600;
      color: rgba(255,255,255,0.88);
      margin-bottom: 4px;
    }
    .story-arc-meta {
      display: flex; gap: 8px; flex-wrap: wrap;
    }
    .story-arc-badge {
      font-family: 'JetBrains Mono', monospace;
      font-size: 9px; padding: 2px 7px; border-radius: 4px;
      letter-spacing: .06em; text-transform: uppercase;
    }
    .story-arc-badge.promoted { background: rgba(105,255,71,0.12); color: var(--seed-glow); border: 1px solid rgba(105,255,71,0.25); }
    .story-arc-badge.rejected { background: rgba(255,70,70,0.1); color: rgba(255,100,100,0.9); border: 1px solid rgba(255,70,70,0.25); }
    .story-arc-badge.agent    { background: rgba(0,229,255,0.07); color: rgba(0,229,255,0.7); border: 1px solid rgba(0,229,255,0.18); }

    /* ── Federation Galaxy canvas ─────────────────────────────────── */
    .galaxy-wrap {
      position: relative; border-radius: 12px; overflow: hidden;
      background: radial-gradient(ellipse at 50% 50%, rgba(0,10,30,1) 0%, rgba(2,8,16,1) 100%);
    }
    #galaxyCanvas {
      display: block; width: 100%; height: 340px;
    }
    .galaxy-legend {
      display: flex; gap: 16px; flex-wrap: wrap;
      padding: 12px 16px;
      border-top: 1px solid rgba(0,229,255,0.08);
    }
    .galaxy-legend-item {
      display: flex; align-items: center; gap: 6px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 10px; color: rgba(255,255,255,0.45);
    }
    .galaxy-legend-dot {
      width: 8px; height: 8px; border-radius: 50%;
    }

    /* ── Character Roster (replaces simple persona-grid) ─────────────── */
    .roster-wrap { display: flex; flex-direction: column; gap: 20px; }
    .roster-spotlight {
      border-radius: 20px; overflow: hidden; position: relative;
      border: 1px solid rgba(255,215,0,0.2);
      background: linear-gradient(135deg, rgba(4,8,24,0.98), rgba(10,14,40,0.95));
      box-shadow: 0 0 60px rgba(255,180,0,0.07), 0 24px 64px rgba(0,0,0,0.7);
      display: flex; min-height: 260px;
      animation: roster-enter 0.5s cubic-bezier(.22,1,.36,1) both;
    }
    @keyframes roster-enter {
      from { opacity:0; transform: scale(0.97) translateY(12px); }
      to   { opacity:1; transform: scale(1)    translateY(0); }
    }
    .roster-spotlight::before {
      content:''; position:absolute; inset:0; pointer-events:none;
      background: radial-gradient(ellipse 60% 80% at 75% 50%, rgba(255,180,0,0.12), transparent 65%),
                  radial-gradient(ellipse 40% 60% at 25% 30%, rgba(30,60,140,0.25), transparent 60%);
    }
    .spotlight-img-wrap {
      flex: 0 0 240px; display: flex; align-items: flex-end;
      justify-content: center; overflow: hidden; position: relative;
    }
    .spotlight-img {
      height: 255px; object-fit: contain;
      filter: drop-shadow(0 0 32px rgba(255,180,0,0.4));
      transform: scale(1.05); transition: transform 0.4s ease;
    }
    .roster-spotlight:hover .spotlight-img { transform: scale(1.12) translateY(-6px); }
    .spotlight-info {
      flex: 1; padding: 28px 28px 24px; display: flex;
      flex-direction: column; justify-content: center; gap: 12px;
    }
    .spotlight-badge {
      font-family: 'JetBrains Mono', monospace; font-size: 10px;
      letter-spacing: .15em; text-transform: uppercase; padding: 4px 12px;
      border-radius: 6px; background: rgba(255,215,0,0.1); color: rgba(255,215,0,0.8);
      border: 1px solid rgba(255,215,0,0.25); width: fit-content;
    }
    .spotlight-name {
      font-family: 'Syne', sans-serif; font-size: 36px; font-weight: 800;
      line-height: 1; letter-spacing: .06em; text-transform: uppercase;
      background: linear-gradient(135deg, #ffd700, #ffe566, #ffaa00);
      -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
    }
    .spotlight-philosophy {
      font-family: 'JetBrains Mono', monospace; font-size: 11px;
      color: rgba(255,255,255,0.35); letter-spacing: .1em; text-transform: uppercase;
    }
    .spotlight-description {
      font-size: 13px; color: rgba(255,255,255,0.5); line-height: 1.65; max-width: 360px;
    }
    .spotlight-stats { display: flex; flex-direction: column; gap: 7px; margin-top: 4px; }
    .spotlight-stat-row { display: flex; align-items: center; gap: 10px; }
    .spotlight-stat-label {
      font-family: 'JetBrains Mono', monospace; font-size: 9px;
      letter-spacing: .08em; text-transform: uppercase;
      color: rgba(255,255,255,0.28); width: 62px; flex-shrink: 0;
    }
    .spotlight-stat-track {
      flex: 1; height: 4px; border-radius: 2px;
      background: rgba(255,255,255,0.06); overflow: hidden;
    }
    .spotlight-stat-fill {
      height: 100%; border-radius: 2px;
      background: linear-gradient(90deg, rgba(255,150,0,0.6), #ffd700);
      transition: width 1.2s cubic-bezier(.22,1,.36,1);
    }
    .spotlight-stat-val {
      font-family: 'JetBrains Mono', monospace; font-size: 9px;
      color: rgba(255,215,0,0.55); width: 26px; text-align: right;
    }
    .spotlight-detail-pills { display: flex; gap: 7px; flex-wrap: wrap; margin-top: 4px; }
    .spotlight-detail-pill {
      font-family: 'JetBrains Mono', monospace; font-size: 9px; padding: 3px 9px;
      border-radius: 5px; background: rgba(255,215,0,0.06); color: rgba(255,215,0,0.55);
      border: 1px solid rgba(255,215,0,0.16); letter-spacing: .06em;
    }
    /* Agent trio cards */
    .roster-trio { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }
    .agent-card {
      border-radius: 18px; overflow: hidden; position: relative;
      border: 1px solid transparent; transition: transform .25s ease, box-shadow .25s ease;
      cursor: pointer;
    }
    .agent-card:hover { transform: translateY(-5px) scale(1.01); }
    .agent-card.architect {
      background: linear-gradient(160deg, rgba(6,12,36,0.97), rgba(8,16,48,0.95));
      border-color: rgba(255,215,0,0.2); box-shadow: 0 8px 36px rgba(255,180,0,0.08);
    }
    .agent-card.dream {
      background: linear-gradient(160deg, rgba(8,6,28,0.97), rgba(16,8,44,0.95));
      border-color: rgba(147,112,219,0.25); box-shadow: 0 8px 36px rgba(130,80,255,0.1);
    }
    .agent-card.beast {
      background: linear-gradient(160deg, rgba(4,10,20,0.97), rgba(6,14,28,0.95));
      border-color: rgba(0,229,255,0.2); box-shadow: 0 8px 36px rgba(0,229,255,0.07);
    }
    .agent-card::before {
      content:''; position:absolute; inset:0; pointer-events:none;
      opacity:0; transition: opacity .3s ease;
    }
    .agent-card.architect::before { background: radial-gradient(ellipse 70% 70% at 50% 0%, rgba(255,180,0,0.12), transparent); }
    .agent-card.dream::before     { background: radial-gradient(ellipse 70% 70% at 50% 0%, rgba(180,120,255,0.14), transparent); }
    .agent-card.beast::before     { background: radial-gradient(ellipse 70% 70% at 50% 0%, rgba(0,229,255,0.1), transparent); }
    .agent-card:hover::before { opacity: 1; }
    .agent-portrait-wrap {
      width: 100%; aspect-ratio: 4/3;
      display: flex; align-items: flex-end; justify-content: center; overflow: hidden;
    }
    .agent-portrait {
      height: 100%; max-height: 195px; object-fit: contain;
      transition: transform 0.35s ease, filter 0.35s ease, opacity 0.35s ease;
    }
    .img-low-weight {
      opacity: var(--img-low-weight-opacity);
      filter: saturate(var(--img-low-weight-saturation));
    }
    .agent-card:hover .agent-portrait.img-low-weight {
      transform: scale(1.06) translateY(-4px);
      opacity: var(--img-low-weight-hover-opacity);
      filter:
        saturate(var(--img-low-weight-hover-saturation))
        drop-shadow(0 0 var(--img-low-weight-max-glow) rgba(255,255,255,var(--img-low-weight-hover-glow-alpha)));
    }
    .agent-info { padding: 12px 15px 16px; border-top: 1px solid rgba(255,255,255,0.05); }
    .agent-name-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 3px; }
    .agent-name {
      font-family: 'Syne', sans-serif; font-size: 14px; font-weight: 800;
      letter-spacing: .1em; text-transform: uppercase;
    }
    .agent-card.architect .agent-name { color: #ffd700; }
    .agent-card.dream     .agent-name { color: #b388ff; }
    .agent-card.beast     .agent-name { color: var(--arch); }
    .agent-active-dot {
      width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0;
      opacity: 0; transition: opacity .3s;
    }
    .agent-card.architect .agent-active-dot { background: #ffd700; box-shadow: 0 0 8px rgba(255,215,0,0.8); }
    .agent-card.dream     .agent-active-dot { background: #b388ff; box-shadow: 0 0 8px rgba(179,136,255,0.8); }
    .agent-card.beast     .agent-active-dot { background: var(--arch); box-shadow: 0 0 8px rgba(0,229,255,0.8); }
    .agent-card.is-active .agent-active-dot { opacity: 1; animation: pulse-ring 1.4s ease-out infinite; }
    .agent-philosophy {
      font-family: 'JetBrains Mono', monospace; font-size: 9px;
      letter-spacing: .1em; text-transform: uppercase;
      color: rgba(255,255,255,0.28); margin-bottom: 10px;
    }
    .agent-bars { display: flex; flex-direction: column; gap: 5px; }
    .agent-bar-row { display: flex; align-items: center; gap: 7px; }
    .agent-bar-label {
      font-family: 'JetBrains Mono', monospace; font-size: 8px;
      letter-spacing: .06em; text-transform: uppercase;
      color: rgba(255,255,255,0.22); width: 48px; flex-shrink: 0;
    }
    .agent-bar-track { flex: 1; height: 3px; border-radius: 2px; background: rgba(255,255,255,0.05); overflow: hidden; }
    .agent-bar-fill { height: 100%; border-radius: 2px; transition: width 1.3s cubic-bezier(.22,1,.36,1); }
    .agent-card.architect .agent-bar-fill { background: linear-gradient(90deg, rgba(255,150,0,0.5), #ffd700); }
    .agent-card.dream     .agent-bar-fill { background: linear-gradient(90deg, rgba(120,60,255,0.5), #b388ff); }
    .agent-card.beast     .agent-bar-fill { background: linear-gradient(90deg, rgba(0,180,220,0.5), var(--arch)); }
    .agent-detail-tags { display: flex; gap: 5px; flex-wrap: wrap; margin-top: 9px; }
    .agent-tag {
      font-family: 'JetBrains Mono', monospace; font-size: 8px; padding: 2px 7px;
      border-radius: 4px; letter-spacing: .06em; text-transform: uppercase;
    }
    .agent-card.architect .agent-tag { background: rgba(255,215,0,0.07); color: rgba(255,215,0,0.55); border: 1px solid rgba(255,215,0,0.16); }
    .agent-card.dream     .agent-tag { background: rgba(179,136,255,0.07); color: rgba(179,136,255,0.6); border: 1px solid rgba(179,136,255,0.18); }
    .agent-card.beast     .agent-tag { background: rgba(0,229,255,0.06); color: rgba(0,229,255,0.55); border: 1px solid rgba(0,229,255,0.16); }
    .roster-trio-banner {
      border-radius: 18px; overflow: hidden; position: relative;
      border: 1px solid rgba(255,255,255,0.06);
    }
    .trio-banner-img {
      width: 100%; display: block; border-radius: 18px;
      transition: filter 0.3s ease, opacity 0.3s ease;
    }
    .trio-banner-overlay {
      position: absolute; bottom: 0; left: 0; right: 0; padding: 16px 22px;
      background: linear-gradient(0deg, rgba(2,6,18,0.95) 0%, transparent 100%);
    }
    .trio-banner-title {
      font-family: 'Syne', sans-serif; font-size: 12px; font-weight: 800;
      letter-spacing: .18em; text-transform: uppercase;
      color: rgba(255,255,255,0.55); margin-bottom: 3px;
    }
    .trio-banner-sub {
      font-family: 'JetBrains Mono', monospace; font-size: 10px;
      color: rgba(255,255,255,0.22); letter-spacing: .08em;
    }

    /* ── Seed registry ────────────────────────────────────────────── */
    .seed-form { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 18px; }
    .seed-input {
      font-family: 'JetBrains Mono', monospace;
      font-size: 12px; padding: 9px 12px;
      background: rgba(105,255,71,0.03);
      border: 1px solid rgba(105,255,71,0.15);
      border-radius: 8px; color: rgba(255,255,255,0.85);
      outline: none; transition: border-color .15s;
    }
    .seed-input::placeholder { color: rgba(105,255,71,0.2); }
    .seed-input:focus { border-color: rgba(105,255,71,0.35); box-shadow: 0 0 16px rgba(105,255,71,0.06); }
    .seed-input.full { grid-column: 1 / -1; }
    .seed-register-btn {
      grid-column: 1 / -1;
      font-family: 'Syne', sans-serif;
      font-size: 11px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase;
      padding: 10px; border-radius: 8px; cursor: pointer;
      background: rgba(105,255,71,0.08);
      border: 1px solid rgba(105,255,71,0.3);
      color: var(--seed-glow); transition: all .15s;
    }
    .seed-register-btn:hover { background: rgba(105,255,71,0.14); box-shadow: 0 0 20px rgba(105,255,71,0.12); }
    .seed-list { display: flex; flex-direction: column; gap: 8px; max-height: 280px; overflow-y: auto; }
    .seed-item {
      border-radius: 10px; padding: 12px 14px;
      background: rgba(105,255,71,0.03);
      border: 1px solid rgba(105,255,71,0.1);
      display: flex; align-items: center; gap: 12px;
      transition: border-color .15s;
    }
    .seed-item:hover { border-color: rgba(105,255,71,0.22); }
    .seed-item-icon {
      font-size: 18px; flex-shrink: 0;
      filter: drop-shadow(0 0 6px rgba(105,255,71,0.4));
    }
    .seed-item-body { flex: 1; min-width: 0; }
    .seed-item-id {
      font-family: 'JetBrains Mono', monospace;
      font-size: 12px; font-weight: 600; color: var(--seed-glow);
      margin-bottom: 2px;
    }
    .seed-item-intent {
      font-size: 11px; color: rgba(255,255,255,0.4);
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    .seed-item-lane {
      font-family: 'JetBrains Mono', monospace;
      font-size: 9px; padding: 2px 7px; border-radius: 4px; flex-shrink: 0;
      background: rgba(105,255,71,0.1); color: rgba(105,255,71,0.7);
      letter-spacing: .08em; text-transform: uppercase;
    }
    .seed-empty {
      text-align: center; padding: 32px 16px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 11px; color: rgba(105,255,71,0.2);
    }
    .seed-empty-icon { font-size: 36px; display: block; margin-bottom: 10px; opacity: 0.5; }

    /* ── Status badge ─────────────────────────────────────────────── */
    .inno-status {
      font-family: 'JetBrains Mono', monospace;
      font-size: 9px; letter-spacing: .1em; text-transform: uppercase;
      padding: 3px 9px; border-radius: 5px;
    }
    .inno-status.live   { background: rgba(0,229,255,0.1); color: rgba(0,229,255,0.8); border: 1px solid rgba(0,229,255,0.25); }
    .inno-status.cached { background: rgba(255,255,255,0.04); color: rgba(255,255,255,0.35); border: 1px solid rgba(255,255,255,0.1); }

    /* ── Scrollbar styling for inno panels ────────────────────────── */
    .story-timeline::-webkit-scrollbar,
    .oracle-result::-webkit-scrollbar,
    .seed-list::-webkit-scrollbar { width: 4px; }
    .story-timeline::-webkit-scrollbar-track,
    .oracle-result::-webkit-scrollbar-track,
    .seed-list::-webkit-scrollbar-track { background: transparent; }
    .story-timeline::-webkit-scrollbar-thumb,
    .oracle-result::-webkit-scrollbar-thumb,
    .seed-list::-webkit-scrollbar-thumb { background: rgba(0,229,255,0.15); border-radius: 2px; }

    /* ── Reflection banner ────────────────────────────────────────── */
    .reflect-banner {
      border-radius: 12px; padding: 14px 18px;
      background: linear-gradient(135deg, rgba(0,229,255,0.06), rgba(224,64,251,0.06));
      border: 1px solid rgba(0,229,255,0.15);
      display: flex; align-items: center; gap: 14px;
    }
    .reflect-icon { font-size: 22px; flex-shrink: 0; }
    .reflect-body { flex: 1; min-width: 0; }
    .reflect-title {
      font-family: 'Syne', sans-serif;
      font-size: 12px; font-weight: 700; letter-spacing: .1em;
      text-transform: uppercase; color: rgba(0,229,255,0.8);
      margin-bottom: 3px;
    }
    .reflect-text {
      font-family: 'JetBrains Mono', monospace;
      font-size: 11px; color: rgba(255,255,255,0.5); line-height: 1.5;
    }
  `;

  /* ══════════════════════════════════════════════════════════════════════
     STATE
  ══════════════════════════════════════════════════════════════════════ */
  const innState = {
    subpanel: "oracle",
    oracleQuery: "",
    oracleResult: null,
    oracleLoading: false,
    oracleVision: null,
    storyArcs: [],
    storyLoaded: false,
    storyVision: null,
    galaxy: null,
    galaxyLoaded: false,
    seeds: [],
    seedsLoaded: false,
    reflection: null,
    // Personalities (deterministic defaults)
    personalities: [
      { id: "architect", philosophy: "minimalist",  vector: [0.9, 0.2, 0.3, 0.1], active: false },
      { id: "dream",     philosophy: "exploratory", vector: [0.6, 0.8, 0.4, 0.2], active: false },
      { id: "beast",     philosophy: "aggressive",  vector: [0.5, 0.5, 0.9, 0.8], active: false },
    ],
    activePersonality: null,
    personalityProfiles: [],
    personalityHistory: [],
    personalityLoaded: false,
  };

  const VEC_LABELS = ["intent", "explore", "risk", "speed"];

  /* ══════════════════════════════════════════════════════════════════════
     HELPERS
  ══════════════════════════════════════════════════════════════════════ */
  function apiBase() {
    return (global._adaadState?.baseUrl || "http://127.0.0.1:8000");
  }

  async function apiFetch(path, opts = {}) {
    const token = global._adaadState?.auditToken || "";
    const headers = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const res = await fetch(apiBase() + path, { headers, ...opts });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return res.json();
  }

  function h(tag, attrs, ...children) {
    const el = document.createElement(tag);
    if (attrs) Object.entries(attrs).forEach(([k, v]) => {
      if (k === "class") el.className = v;
      else if (k === "style") el.style.cssText = v;
      else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v);
    });
    children.forEach(c => {
      if (c == null) return;
      el.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    });
    return el;
  }

  function escHtml(s) {
    return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
  }

  /* ══════════════════════════════════════════════════════════════════════
     GALAXY CANVAS RENDERER
  ══════════════════════════════════════════════════════════════════════ */
  let galaxyAnim = null;
  let galaxyParticles = [];

  function initGalaxy(canvas, data) {
    if (galaxyAnim) cancelAnimationFrame(galaxyAnim);
    const ctx = canvas.getContext("2d");
    const DPR = window.devicePixelRatio || 1;
    const W = canvas.offsetWidth;
    const H = canvas.offsetHeight;
    canvas.width  = W * DPR;
    canvas.height = H * DPR;
    ctx.scale(DPR, DPR);

    const stars  = data?.stars || ["ADAAD", "Repo-A", "Repo-B"];
    const paths  = data?.paths || [];

    // Place stars in a cosmic layout
    const starMap = {};
    const cx = W / 2, cy = H / 2;
    stars.forEach((s, i) => {
      const angle = (i / stars.length) * Math.PI * 2 - Math.PI / 2;
      const r = Math.min(W, H) * 0.32;
      const px = stars.length === 1 ? cx : cx + Math.cos(angle) * r;
      const py = stars.length === 1 ? cy : cy + Math.sin(angle) * r;
      starMap[s] = { x: px, y: py, name: s };
    });

    // Background star field
    const bgStars = Array.from({length: 120}, () => ({
      x: Math.random() * W, y: Math.random() * H,
      r: Math.random() * 1.2 + 0.2,
      a: Math.random(), da: (Math.random() - 0.5) * 0.004,
    }));

    // Animated particles on mutation paths
    galaxyParticles = paths.flatMap(p => {
      const from = starMap[p.from];
      const to   = starMap[p.to];
      if (!from || !to) return [];
      return Array.from({length: p.state === "flare" ? 5 : 2}, () => ({
        t: Math.random(), speed: 0.002 + Math.random() * 0.003,
        from, to, flare: p.state === "flare",
      }));
    });

    let tick = 0;
    function draw() {
      ctx.clearRect(0, 0, W, H);

      // Background stars
      bgStars.forEach(s => {
        s.a += s.da;
        if (s.a > 1 || s.a < 0) s.da *= -1;
        ctx.beginPath();
        ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(200,220,255,${s.a * 0.6})`;
        ctx.fill();
      });

      // Paths
      paths.forEach(p => {
        const from = starMap[p.from];
        const to   = starMap[p.to];
        if (!from || !to) return;
        const grad = ctx.createLinearGradient(from.x, from.y, to.x, to.y);
        if (p.state === "flare") {
          grad.addColorStop(0, "rgba(255,109,0,0.0)");
          grad.addColorStop(0.5,"rgba(255,109,0,0.35)");
          grad.addColorStop(1, "rgba(255,109,0,0.0)");
        } else {
          grad.addColorStop(0, "rgba(0,229,255,0.0)");
          grad.addColorStop(0.5,"rgba(0,229,255,0.18)");
          grad.addColorStop(1, "rgba(0,229,255,0.0)");
        }
        ctx.beginPath();
        ctx.moveTo(from.x, from.y);
        ctx.lineTo(to.x, to.y);
        ctx.strokeStyle = grad;
        ctx.lineWidth = p.state === "flare" ? 1.5 : 1;
        ctx.stroke();
      });

      // Particles
      galaxyParticles.forEach(p => {
        p.t += p.speed;
        if (p.t > 1) p.t = 0;
        const x = p.from.x + (p.to.x - p.from.x) * p.t;
        const y = p.from.y + (p.to.y - p.from.y) * p.t;
        const col = p.flare ? "255,109,0" : "0,229,255";
        const grd = ctx.createRadialGradient(x, y, 0, x, y, 5);
        grd.addColorStop(0, `rgba(${col},0.9)`);
        grd.addColorStop(1, `rgba(${col},0.0)`);
        ctx.beginPath();
        ctx.arc(x, y, 5, 0, Math.PI * 2);
        ctx.fillStyle = grd;
        ctx.fill();
      });

      // Stars (repos)
      Object.values(starMap).forEach(s => {
        // Outer glow
        const pulse = 0.6 + Math.sin(tick * 0.018 + s.x) * 0.3;
        const grd = ctx.createRadialGradient(s.x, s.y, 0, s.x, s.y, 28);
        grd.addColorStop(0, `rgba(0,229,255,${0.25 * pulse})`);
        grd.addColorStop(1, "rgba(0,229,255,0.0)");
        ctx.beginPath();
        ctx.arc(s.x, s.y, 28, 0, Math.PI * 2);
        ctx.fillStyle = grd;
        ctx.fill();

        // Core dot
        ctx.beginPath();
        ctx.arc(s.x, s.y, 5, 0, Math.PI * 2);
        ctx.fillStyle = "#00e5ff";
        ctx.shadowBlur = 12; ctx.shadowColor = "#00e5ff";
        ctx.fill();
        ctx.shadowBlur = 0;

        // Label
        ctx.font = "600 11px 'Syne', sans-serif";
        ctx.fillStyle = "rgba(0,229,255,0.75)";
        ctx.textAlign = "center";
        ctx.fillText(s.name, s.x, s.y - 14);
      });

      tick++;
      galaxyAnim = requestAnimationFrame(draw);
    }
    draw();
  }

  /* ══════════════════════════════════════════════════════════════════════
     PANEL RENDERERS
  ══════════════════════════════════════════════════════════════════════ */

  function renderVisionSummary(vision) {
    const box = h("div", {class: "reflect-banner", style:"margin-top:14px;"});
    const body = h("div", {class: "reflect-body"});
    const bands = vision?.trajectory_bands || {};
    const deadEnds = vision?.dead_end_diagnostics || [];
    const deltas = vision?.capability_graph_deltas || [];
    const meta = vision?.confidence_metadata || {};
    body.appendChild(h("div", {class: "reflect-title"}, `Vision Forecast · ${vision?.horizon_epochs || 0} epochs`));
    body.appendChild(h("div", {class: "reflect-text"},
      `Trajectory cues  best:${(bands.best ?? 0).toFixed ? bands.best.toFixed(4) : bands.best}  base:${(bands.base ?? 0).toFixed ? bands.base.toFixed(4) : bands.base}  worst:${(bands.worst ?? 0).toFixed ? bands.worst.toFixed(4) : bands.worst}`
    ));
    body.appendChild(h("div", {class: "reflect-text"},
      `Coverage ${(meta.coverage_ratio ?? 0)} · Confidence ${(meta.confidence_score ?? 0)} · Replayable ${meta.replayable ? "yes" : "no"}`
    ));
    if (deltas.length) {
      body.appendChild(h("div", {class: "reflect-text"}, `Path cards: ${deltas.map(d => `${d.capability} (${d.fitness_delta_sum})`).join(" · ")}`));
    }
    if (deadEnds.length) {
      body.appendChild(h("div", {class: "reflect-text"}, `Dead-ends: ${deadEnds.map(d => `${d.path_id}:${d.blocking_cause}`).join(" · ")}`));
    }
    box.appendChild(h("div", {class: "reflect-icon"}, "📈"));
    box.appendChild(body);
    return box;
  }

  // ── Oracle ──────────────────────────────────────────────────────────
  function renderOracle() {
    const wrap = h("div", {class: "inno-wrap"});

    const card = h("div", {class: "inno-card"});
    const hdr  = h("div", {class: "inno-card-header"});
    hdr.appendChild(h("div", {class: "inno-card-title"},
      h("div", {class: "inno-card-icon", style:"background:rgba(255,229,127,0.1);"}, "🔮"),
      "ADAAD Oracle"
    ));
    hdr.appendChild(h("span", {class: "inno-status live"}, "v9.3"));
    card.appendChild(hdr);

    const body = h("div", {class: "inno-card-body"});

    // Pre-set query chips
    const chips = h("div", {class: "oracle-chips"});
    ["divergence", "rejected", "performance", "contributed"].forEach(q => {
      const chip = h("div", {class: "oracle-chip"}, q);
      chip.addEventListener("click", () => {
        input.value = q;
        innState.oracleQuery = q;
      });
      chips.appendChild(chip);
    });
    body.appendChild(chips);

    // Input row
    const inputRow = h("div", {class: "oracle-input-row"});
    const input = h("input", {
      class: "oracle-input",
      placeholder: "divergence · rejected · performance · contributed…",
      value: innState.oracleQuery || "",
    });
    input.addEventListener("input", e => { innState.oracleQuery = e.target.value; });
    input.addEventListener("keydown", e => { if (e.key === "Enter") runOracle(); });
    const btn = h("button", {class: "oracle-btn", onclick: runOracle}, "Ask");
    inputRow.appendChild(input);
    inputRow.appendChild(btn);
    body.appendChild(inputRow);

    // Result area
    const resultEl = h("div", {class: "oracle-result"});
    if (innState.oracleLoading) {
      const loader = h("div", {class: "oracle-loading"},
        h("div", {class: "oracle-spinner"}),
        "Consulting the oracle…"
      );
      resultEl.appendChild(loader);
    } else if (innState.oracleResult) {
      resultEl.textContent = JSON.stringify(innState.oracleResult, null, 2);
    }
    body.appendChild(resultEl);
    if (innState.oracleVision) body.appendChild(renderVisionSummary(innState.oracleVision));
    card.appendChild(body);
    wrap.appendChild(card);

    async function runOracle() {
      const q = input.value.trim() || "divergence";
      innState.oracleQuery = q;
      innState.oracleLoading = true;
      resultEl.innerHTML = `<div class="oracle-loading"><div class="oracle-spinner"></div>Consulting the oracle…</div>`;
      try {
        const data = await apiFetch(`/innovations/oracle?q=${encodeURIComponent(q)}&limit=100&horizon=120&seed_input=aponi-oracle`);
        innState.oracleResult = data.answer;
        innState.oracleVision = data.vision_projection || null;
        resultEl.textContent = JSON.stringify(data.answer, null, 2);
      } catch(e) {
        // Fallback demo data
        innState.oracleResult = { query_type: "demo", message: "Oracle endpoint not reachable. Start the ADAAD server to connect.", query: q };
        innState.oracleVision = null;
        resultEl.textContent = JSON.stringify(innState.oracleResult, null, 2);
      }
      innState.oracleLoading = false;
    }

    return wrap;
  }

  // ── Story Mode ──────────────────────────────────────────────────────
  function renderStory() {
    const wrap = h("div", {class: "inno-wrap"});
    const card = h("div", {class: "inno-card"});

    const hdr = h("div", {class: "inno-card-header"});
    hdr.appendChild(h("div", {class: "inno-card-title"},
      h("div", {class: "inno-card-icon", style:"background:rgba(0,229,255,0.07);"}, "📖"),
      "Story Mode"
    ));
    const refreshBtn = h("button", {class: "oracle-btn"}, "Refresh");
    refreshBtn.addEventListener("click", loadStory);
    hdr.appendChild(refreshBtn);
    card.appendChild(hdr);

    const body = h("div", {class: "inno-card-body"});

    // Reflection banner if available
    if (innState.reflection) {
      const b = h("div", {class: "reflect-banner", style:"margin-bottom:18px;"});
      b.appendChild(h("div", {class: "reflect-icon"}, "🧠"));
      const bd = h("div", {class: "reflect-body"});
      bd.appendChild(h("div", {class: "reflect-title"}, `Self-Reflection Report`));
      bd.appendChild(h("div", {class: "reflect-text"},
        `Dominant: ${innState.reflection.dominant_agent}  ·  Underperforming: ${innState.reflection.underperforming_agent}\n` +
        `Hint: ${innState.reflection.rebalance_hint}`
      ));
      b.appendChild(bd);
      body.appendChild(b);
    }

    const timeline = h("div", {class: "story-timeline"});

    const arcs = innState.storyArcs.length
      ? innState.storyArcs
      : DEMO_ARCS;

    arcs.forEach((arc, i) => {
      const agentClass = ["architect","dream","beast"].includes(arc.agent) ? arc.agent : "";
      const resultClass = arc.result === "promoted" ? "promoted" : arc.result === "rejected" ? "rejected" : agentClass;

      const row = h("div", {class: "story-arc"});
      row.style.animationDelay = `${i * 0.04}s`;

      const line = h("div", {class: "story-arc-line"});
      const dot  = h("div", {class: `story-arc-dot ${resultClass}`});
      const conn = h("div", {class: "story-arc-connector"});
      line.appendChild(dot);
      if (i < arcs.length - 1) line.appendChild(conn);

      const content = h("div", {class: "story-arc-content"});
      content.appendChild(h("div", {class: "story-arc-epoch"}, arc.epoch || `epoch-${i}`));
      content.appendChild(h("div", {class: "story-arc-title"}, arc.title || arc.decision || "Governance event"));

      const meta = h("div", {class: "story-arc-meta"});
      if (arc.agent) meta.appendChild(h("span", {class: "story-arc-badge agent"}, arc.agent));
      if (arc.result) meta.appendChild(h("span", {class: `story-arc-badge ${arc.result}`}, arc.result));
      content.appendChild(meta);

      row.appendChild(line);
      row.appendChild(content);
      timeline.appendChild(row);
    });

    body.appendChild(timeline);
    if (innState.storyVision) body.appendChild(renderVisionSummary(innState.storyVision));
    card.appendChild(body);
    wrap.appendChild(card);

    if (!innState.storyLoaded) loadStory();

    async function loadStory() {
      try {
        const data = await apiFetch("/innovations/story-mode?limit=80&horizon=120&seed_input=aponi-story");
        innState.storyArcs = data.arcs || [];
        innState.storyVision = data.vision_projection || null;
        innState.storyLoaded = true;
        // Re-render
        timeline.innerHTML = "";
        (innState.storyArcs.length ? innState.storyArcs : DEMO_ARCS).forEach((arc, i) => {
          const agentClass = ["architect","dream","beast"].includes(arc.agent) ? arc.agent : "";
          const resultClass = arc.result === "promoted" ? "promoted" : arc.result === "rejected" ? "rejected" : agentClass;
          const row = h("div", {class: "story-arc"});
          row.style.animationDelay = `${i * 0.04}s`;
          const line = h("div", {class: "story-arc-line"});
          line.appendChild(h("div", {class: `story-arc-dot ${resultClass}`}));
          if (i < innState.storyArcs.length - 1) line.appendChild(h("div", {class: "story-arc-connector"}));
          const content = h("div", {class: "story-arc-content"});
          content.appendChild(h("div", {class: "story-arc-epoch"}, arc.epoch || `epoch-${i}`));
          content.appendChild(h("div", {class: "story-arc-title"}, arc.title || arc.decision || "Governance event"));
          const meta = h("div", {class: "story-arc-meta"});
          if (arc.agent) meta.appendChild(h("span", {class: "story-arc-badge agent"}, arc.agent));
          if (arc.result) meta.appendChild(h("span", {class: `story-arc-badge ${arc.result}`}, arc.result));
          content.appendChild(meta);
          row.appendChild(line); row.appendChild(content);
          timeline.appendChild(row);
        });
      } catch(_) { /* keep demo data */ }
    }

    return wrap;
  }

  // ── Galaxy ──────────────────────────────────────────────────────────
  function renderGalaxy() {
    const wrap = h("div", {class: "inno-wrap"});
    const card = h("div", {class: "inno-card"});

    const hdr = h("div", {class: "inno-card-header"});
    hdr.appendChild(h("div", {class: "inno-card-title"},
      h("div", {class: "inno-card-icon", style:"background:rgba(0,229,255,0.07);"}, "🌌"),
      "Federated Evolution Map"
    ));
    hdr.appendChild(h("span", {class: "inno-status live"}, "Live"));
    card.appendChild(hdr);

    const body = h("div", {class: "inno-card-body", style:"padding:0;"});
    const galaxyWrap = h("div", {class: "galaxy-wrap"});
    const canvas = h("canvas", {id: "galaxyCanvas"});
    galaxyWrap.appendChild(canvas);

    const legend = h("div", {class: "galaxy-legend"});
    [
      ["🔵", "--arch", "Stable repository"],
      ["🟠", "--beast", "Divergence flare"],
      ["⚡", "--oracle-glow", "Mutation flow"],
    ].forEach(([dot, color, label]) => {
      const item = h("div", {class: "galaxy-legend-item"});
      item.innerHTML = `<span>${dot}</span><span>${label}</span>`;
      legend.appendChild(item);
    });
    galaxyWrap.appendChild(legend);
    body.appendChild(galaxyWrap);
    card.appendChild(body);
    wrap.appendChild(card);

    // Init galaxy after DOM insertion
    requestAnimationFrame(() => {
      setTimeout(() => {
        const cvs = document.getElementById("galaxyCanvas");
        if (!cvs) return;
        const galaxyData = innState.galaxy || DEMO_GALAXY;
        initGalaxy(cvs, galaxyData);
      }, 50);
    });

    if (!innState.galaxyLoaded) {
      apiFetch("/innovations/federation-map?limit=200").then(data => {
        innState.galaxy = data.galaxy;
        innState.galaxyLoaded = true;
        const cvs = document.getElementById("galaxyCanvas");
        if (cvs) initGalaxy(cvs, data.galaxy);
      }).catch(() => {});
    }

    return wrap;
  }

  // ── Seeds ──────────────────────────────────────────────────────────
  function renderSeeds() {
    const wrap = h("div", {class: "inno-wrap"});
    const card = h("div", {class: "inno-card"});

    const hdr = h("div", {class: "inno-card-header"});
    hdr.appendChild(h("div", {class: "inno-card-title"},
      h("div", {class: "inno-card-icon", style:"background:rgba(105,255,71,0.07);"}, "🌱"),
      "Capability Seeds"
    ));
    hdr.appendChild(h("span", {class: "inno-status live"}, `${innState.seeds.length} registered`));
    card.appendChild(hdr);

    const body = h("div", {class: "inno-card-body"});

    // Registration form
    const form = h("div", {class: "seed-form"});
    const idIn      = h("input", {class: "seed-input",      placeholder: "seed_id  (e.g. oracle-v1)"});
    const laneIn    = h("input", {class: "seed-input",      placeholder: "lane  (governance / performance…)"});
    const intentIn  = h("input", {class: "seed-input full", placeholder: "intent  — what should ADAAD grow?"});
    const scaffoldIn= h("input", {class: "seed-input full", placeholder: "scaffold  — starter code (optional)"});
    const authorIn  = h("input", {class: "seed-input",      placeholder: "author"});

    const regBtn = h("button", {class: "seed-register-btn", onclick: registerSeed}, "🌱  Plant Seed");

    form.appendChild(idIn); form.appendChild(laneIn);
    form.appendChild(intentIn); form.appendChild(scaffoldIn);
    form.appendChild(authorIn);
    form.appendChild(regBtn);
    body.appendChild(form);

    // Seed list
    const listWrap = h("div", {class: "seed-list"});
    renderSeedList();
    body.appendChild(listWrap);
    card.appendChild(body);
    wrap.appendChild(card);

    if (!innState.seedsLoaded) loadSeeds();

    function renderSeedList() {
      listWrap.innerHTML = "";
      const seeds = innState.seeds.length ? innState.seeds : [];
      if (!seeds.length) {
        const empty = h("div", {class: "seed-empty"});
        empty.innerHTML = `<span class="seed-empty-icon">🌱</span>No seeds registered yet.<br>Plant the first idea.`;
        listWrap.appendChild(empty);
        return;
      }
      seeds.forEach(seed => {
        const item = h("div", {class: "seed-item"});
        item.appendChild(h("div", {class: "seed-item-icon"}, "🌱"));
        const bd = h("div", {class: "seed-item-body"});
        bd.appendChild(h("div", {class: "seed-item-id"}, seed.seed_id || seed.capability_id || "—"));
        bd.appendChild(h("div", {class: "seed-item-intent"}, seed.intent || seed.description || "—"));
        item.appendChild(bd);
        item.appendChild(h("div", {class: "seed-item-lane"}, seed.lane || "experimental"));
        listWrap.appendChild(item);
      });
    }

    async function loadSeeds() {
      try {
        const data = await apiFetch("/innovations/seeds");
        innState.seeds = data.seeds || [];
        innState.seedsLoaded = true;
        renderSeedList();
      } catch(_) {}
    }

    async function registerSeed() {
      const seed = {
        seed_id: idIn.value.trim() || `seed-${Date.now()}`,
        intent:  intentIn.value.trim() || "Unnamed seed",
        scaffold: scaffoldIn.value.trim() || "def handler(): pass",
        author:  authorIn.value.trim() || "operator",
        lane:    laneIn.value.trim() || "experimental",
      };
      try {
        await apiFetch("/innovations/seeds/register", {
          method: "POST",
          body: JSON.stringify([seed]),
        });
        idIn.value = ""; intentIn.value = ""; scaffoldIn.value = "";
        authorIn.value = ""; laneIn.value = "";
        innState.seedsLoaded = false;
        await loadSeeds();
      } catch(e) {
        // Optimistic local add for demo
        innState.seeds.push(seed);
        renderSeedList();
      }
    }

    return wrap;
  }

  function summarizePersonaHistory(agentId) {
    const rows = (innState.personalityHistory || []).filter(r => r.agent_id === agentId);
    const wins = rows.filter(r => r.outcome === "win").length;
    const losses = rows.filter(r => r.outcome === "loss").length;
    const recent = rows.slice(-4).reverse();
    const latest = rows.length ? rows[rows.length - 1] : null;
    return { wins, losses, recent, latest };
  }

  async function loadPersonalityProfiles() {
    try {
      const data = await apiFetch("/innovations/personality-profiles");
      innState.personalityProfiles = data.profiles || [];
      innState.personalityHistory = data.history || [];
      innState.personalityLoaded = true;
    } catch (_) {}
  }

  // ── Personalities — Cinematic character art roster ──────────────────
  function renderPersonalities() {
    const wrap = h("div", {class: "roster-wrap"});

    const AGENT_DATA = [
      {
        id: "architect",
        img: "agent_architect.png",
        noahImg: "agent_noah.png",
        color: "#ffd700",
        philosophy: "minimalist",
        description: "The constitutional guardian. Architect enforces governance law with precision, bearing the Law-Book of invariants and the Justice Emblem. Every epoch begins with her approval.",
        vector: [0.9, 0.2, 0.3, 0.1],
        tags: ["Justice Emblem", "Law-Book", "Tier-0 Guard", "Constitutional"],
      },
      {
        id: "dream",
        img: "agent_dream.png",
        color: "#b388ff",
        philosophy: "exploratory",
        description: "Vision made manifest. Dream navigates the possibility space with Galaxy Eyes that see 200 epochs ahead, guided by the Dream Orb that pulses with future capability paths.",
        vector: [0.6, 0.8, 0.4, 0.2],
        tags: ["Galaxy Eyes", "Dream Orb", "Vision Mode", "Explorer"],
      },
      {
        id: "beast",
        img: "agent_beast.png",
        color: "#00e5ff",
        philosophy: "aggressive",
        description: "Raw evolutionary pressure. Beast drives mutation velocity to the constitutional edge — Mutation Spines crackling with entropy, Faceplate locked on fitness regression targets.",
        vector: [0.5, 0.5, 0.9, 0.8],
        tags: ["Mutation Spines", "Faceplate", "Beast Mode", "High-Risk"],
      },
    ];

    const VEC_LABELS = ["intent", "explore", "risk", "speed"];

    // ── Featured spotlight (Architect / Noah) ────────────────────────
    const archData = AGENT_DATA[0];
    const spotlight = h("div", {class: "roster-spotlight"});
    const imgWrap = h("div", {class: "spotlight-img-wrap"});
    const img = h("img", {
      class: "spotlight-img",
      src: archData.noahImg || archData.img,
      alt: "Architect",
    });
    img.onerror = () => { img.src = archData.img; };
    imgWrap.appendChild(img);
    spotlight.appendChild(imgWrap);

    const info = h("div", {class: "spotlight-info"});
    info.appendChild(h("div", {class: "spotlight-badge"}, "✦  Featured Agent"));
    info.appendChild(h("div", {class: "spotlight-name"}, "Architect"));
    info.appendChild(h("div", {class: "spotlight-philosophy"}, archData.philosophy));
    info.appendChild(h("div", {class: "spotlight-description"}, archData.description));

    const stats = h("div", {class: "spotlight-stats"});
    archData.vector.forEach((val, i) => {
      const row = h("div", {class: "spotlight-stat-row"});
      row.appendChild(h("div", {class: "spotlight-stat-label"}, VEC_LABELS[i]));
      const track = h("div", {class: "spotlight-stat-track"});
      const fill  = h("div", {class: "spotlight-stat-fill"});
      fill.style.width = "0%";
      track.appendChild(fill);
      row.appendChild(track);
      row.appendChild(h("div", {class: "spotlight-stat-val"}, (val * 100).toFixed(0)));
      stats.appendChild(row);
      requestAnimationFrame(() => setTimeout(() => { fill.style.width = `${val * 100}%`; }, 100 + i * 80));
    });
    info.appendChild(stats);

    const pills = h("div", {class: "spotlight-detail-pills"});
    archData.tags.forEach(t => pills.appendChild(h("div", {class: "spotlight-detail-pill"}, t)));
    info.appendChild(pills);
    spotlight.appendChild(info);
    wrap.appendChild(spotlight);

    // ── Agent trio cards ─────────────────────────────────────────────
    const trio = h("div", {class: "roster-trio"});
    AGENT_DATA.forEach((a, ai) => {
      const card = h("div", {class: `agent-card ${a.id}`});
      const profile = (innState.personalityProfiles || []).find(p => p.agent_id === a.id) || {};
      const history = summarizePersonaHistory(a.id);
      const isActive = innState.activePersonality?.agent_id === a.id;
      if (isActive) card.classList.add("is-active");

      // Portrait
      const pw = h("div", {class: "agent-portrait-wrap"});
      const portrait = h("img", {class: "agent-portrait img-low-weight", src: a.img, alt: a.id});
      portrait.onerror = () => { pw.innerHTML = `<div style="font-size:44px;opacity:0.3;align-self:center;">${["⚖️","✨","⚡"][ai]}</div>`; };
      pw.appendChild(portrait);
      card.appendChild(pw);

      const info2 = h("div", {class: "agent-info"});
      const nameRow = h("div", {class: "agent-name-row"});
      nameRow.appendChild(h("div", {class: "agent-name"}, a.id));
      nameRow.appendChild(h("div", {class: "agent-active-dot"}));
      info2.appendChild(nameRow);
      info2.appendChild(h("div", {class: "agent-philosophy"}, profile.philosophy || a.philosophy));

      const bars = h("div", {class: "agent-bars"});
      const sourceVector = (profile.vector && profile.vector.length === 4) ? profile.vector : a.vector;
      sourceVector.forEach((val, i) => {
        const row = h("div", {class: "agent-bar-row"});
        row.appendChild(h("div", {class: "agent-bar-label"}, VEC_LABELS[i]));
        const track = h("div", {class: "agent-bar-track"});
        const fill  = h("div", {class: "agent-bar-fill"});
        fill.style.width = "0%";
        track.appendChild(fill);
        row.appendChild(track);
        bars.appendChild(row);
        requestAnimationFrame(() => setTimeout(() => { fill.style.width = `${val * 100}%`; }, 200 + ai * 80 + i * 50));
      });
      info2.appendChild(bars);

      const tags = h("div", {class: "agent-detail-tags"});
      a.tags.slice(0, 2).forEach(t => tags.appendChild(h("div", {class: "agent-tag"}, t)));
      const delta = history.latest && history.latest.vector_before && history.latest.vector_after
        ? history.latest.vector_after.map((v, i) => (v - history.latest.vector_before[i]).toFixed(2)).join("/")
        : "0.00/0.00/0.00/0.00";
      tags.appendChild(h("div", {class: "agent-tag"}, `Δ ${delta}`));
      tags.appendChild(h("div", {class: "agent-tag"}, `W:${history.wins} L:${history.losses}`));
      info2.appendChild(tags);

      const recent = h("div", {class: "agent-philosophy", style: "margin-top:6px; font-size:10px;"},
        history.recent.length
          ? `Recent: ${history.recent.map(r => `${r.epoch_id}:${r.outcome}`).join(" · ")}`
          : "Recent: no persona outcomes yet"
      );
      info2.appendChild(recent);

      card.appendChild(info2);
      trio.appendChild(card);
    });
    wrap.appendChild(trio);

    // ── Trio banner ───────────────────────────────────────────────────
    const banner = h("div", {class: "roster-trio-banner"});
    const bannerImg = h("img", {class: "trio-banner-img img-low-weight", src: "agent_trio.png", alt: "ADAAD Agents"});
    bannerImg.onerror = () => { banner.style.display = "none"; };
    banner.appendChild(bannerImg);
    const overlay = h("div", {class: "trio-banner-overlay"});
    overlay.appendChild(h("div", {class: "trio-banner-title"}, "The ADAAD Trinity"));
    overlay.appendChild(h("div", {class: "trio-banner-sub"}, "Architect  ·  Dream  ·  Beast  —  Constitutional Evolution Agents"));
    banner.appendChild(overlay);
    wrap.appendChild(banner);

    return wrap;
  }

    /* ══════════════════════════════════════════════════════════════════════
     DEMO DATA (shown when server not connected)
  ══════════════════════════════════════════════════════════════════════ */
  const DEMO_ARCS = [
    {epoch:"epoch-001", title:"Constitutional gate certified",     agent:"architect", result:"promoted"},
    {epoch:"epoch-002", title:"Fitness regression detected",       agent:"dream",     result:"rejected"},
    {epoch:"epoch-003", title:"Beast mode promotion cycle",        agent:"beast",     result:"promoted"},
    {epoch:"epoch-004", title:"Lineage snapshot divergence",       agent:"architect", result:"rejected"},
    {epoch:"epoch-005", title:"Vision projection: 3 capabilities", agent:"dream",     result:"promoted"},
    {epoch:"epoch-006", title:"G-plugin blocked new dependency",   agent:"beast",     result:"rejected"},
    {epoch:"epoch-007", title:"Self-reflection: rebalance bandit", agent:"architect", result:"promoted"},
    {epoch:"epoch-008", title:"Oracle query answered in 0.3ms",    agent:"dream",     result:"promoted"},
  ];

  const DEMO_GALAXY = {
    stars: ["ADAAD", "Staging", "Prod"],
    paths: [
      {from:"ADAAD", to:"Staging", state:"stable"},
      {from:"ADAAD", to:"Prod",    state:"flare"},
      {from:"Staging",to:"Prod",   state:"stable"},
    ]
  };

  /* ══════════════════════════════════════════════════════════════════════
     MAIN VIEW
  ══════════════════════════════════════════════════════════════════════ */
  function viewInnovations() {
    const root = document.createElement("div");
    root.style.cssText = "padding-top:8px;";

    // Sub-nav
    const subnav = h("div", {class: "inno-subnav", style: "margin-bottom:20px;"});
    const PANELS = [
      {id:"oracle",        label:"Oracle",       cls:""},
      {id:"story",         label:"Story Mode",   cls:""},
      {id:"galaxy",        label:"Galaxy",        cls:""},
      {id:"seeds",         label:"Seeds",         cls:"seed"},
      {id:"personalities", label:"Agents",        cls:"dream"},
    ];
    PANELS.forEach(p => {
      const pill = h("div", {class: `inno-pill ${p.cls} ${innState.subpanel === p.id ? "active" : ""}`}, p.label);
      pill.addEventListener("click", () => {
        innState.subpanel = p.id;
        // Stop galaxy animation when leaving
        if (p.id !== "galaxy" && galaxyAnim) {
          cancelAnimationFrame(galaxyAnim);
          galaxyAnim = null;
        }
        re();
      });
      subnav.appendChild(pill);
    });
    root.appendChild(subnav);

    // Content
    const content = document.createElement("div");
    function re() {
      root.querySelector(".inno-subnav").querySelectorAll(".inno-pill").forEach((el, i) => {
        el.className = `inno-pill ${PANELS[i].cls} ${innState.subpanel === PANELS[i].id ? "active" : ""}`;
      });
      content.innerHTML = "";
      if (innState.subpanel === "oracle")        content.appendChild(renderOracle());
      if (innState.subpanel === "story")         content.appendChild(renderStory());
      if (innState.subpanel === "galaxy")        content.appendChild(renderGalaxy());
      if (innState.subpanel === "seeds")         content.appendChild(renderSeeds());
      if (innState.subpanel === "personalities") {
        if (!innState.personalityLoaded) loadPersonalityProfiles();
        content.appendChild(renderPersonalities());
      }
    }
    re();
    root.appendChild(content);

    return root;
  }

  /* ══════════════════════════════════════════════════════════════════════
     WEBSOCKET LIVE FEED MANAGER (Phase 70)
  ══════════════════════════════════════════════════════════════════════ */

  const WS_CSS = `
    /* ── Epoch progress bar ───────────────────────────────────────── */
    #innoEpochBar {
      position: fixed; top: 0; left: 0; right: 0; height: 2px;
      z-index: 10000; pointer-events: none; overflow: hidden;
      background: transparent;
    }
    #innoEpochFill {
      height: 100%; width: 0%;
      background: linear-gradient(90deg, var(--arch), var(--dream), var(--beast));
      background-size: 200% 100%;
      animation: inno-shimmer 1.4s linear infinite;
      transition: width 0.6s cubic-bezier(.22,1,.36,1);
      border-radius: 0 2px 2px 0;
    }
    @keyframes inno-shimmer {
      0%   { background-position: 200% 0; }
      100% { background-position: -200% 0; }
    }
    #innoEpochBar.idle #innoEpochFill { transition: width 0.3s ease; }

    /* ── Active personality badge in header ───────────────────────── */
    #innoPersonaBadge {
      display: none; align-items: center; gap: 7px;
      padding: 5px 12px; border-radius: 999px;
      font-family: 'Syne', sans-serif;
      font-size: 10px; font-weight: 700;
      letter-spacing: .12em; text-transform: uppercase;
      border: 1px solid; cursor: default;
      animation: persona-in 0.3s cubic-bezier(.22,1,.36,1) both;
    }
    @keyframes persona-in {
      from { opacity: 0; transform: scale(0.88); }
      to   { opacity: 1; transform: scale(1); }
    }
    #innoPersonaBadge.arch  { color: var(--arch);  border-color: rgba(0,229,255,0.4);  background: rgba(0,229,255,0.07); }
    #innoPersonaBadge.dream { color: var(--dream); border-color: rgba(224,64,251,0.4); background: rgba(224,64,251,0.07); }
    #innoPersonaBadge.beast { color: var(--beast); border-color: rgba(255,109,0,0.4);  background: rgba(255,109,0,0.07); }
    #innoPersonaBadge .persona-dot {
      width: 6px; height: 6px; border-radius: 50%;
      animation: pulse-ring 1.4s ease-out infinite;
    }
    #innoPersonaBadge.arch  .persona-dot { background: var(--arch); }
    #innoPersonaBadge.dream .persona-dot { background: var(--dream); }
    #innoPersonaBadge.beast .persona-dot { background: var(--beast); }

    /* ── Live arc entry ───────────────────────────────────────────── */
    .story-arc.live-new {
      animation: arc-live 0.45s cubic-bezier(.22,1,.36,1) both;
    }
    @keyframes arc-live {
      from { opacity: 0; transform: translateX(-12px) scale(0.97); background: rgba(0,229,255,0.04); }
      to   { opacity: 1; transform: translateX(0)    scale(1);    background: transparent; }
    }

    /* ── Reflection toast ─────────────────────────────────────────── */
    .inno-toast {
      position: fixed; bottom: 80px; left: 50%;
      transform: translateX(-50%);
      z-index: 9998;
      min-width: 320px; max-width: 480px;
      padding: 14px 20px; border-radius: 14px;
      background: rgba(8,18,38,0.95);
      border: 1px solid rgba(0,229,255,0.2);
      box-shadow: 0 12px 48px rgba(0,0,0,0.7), 0 0 0 1px rgba(0,229,255,0.06);
      backdrop-filter: blur(20px);
      display: flex; align-items: flex-start; gap: 14px;
      animation: inno-toast-in 0.35s cubic-bezier(.22,1,.36,1) both;
      pointer-events: none;
    }
    @keyframes inno-toast-in {
      from { opacity: 0; transform: translateX(-50%) translateY(16px) scale(0.94); }
      to   { opacity: 1; transform: translateX(-50%) translateY(0)     scale(1); }
    }
    @keyframes inno-toast-out {
      from { opacity: 1; transform: translateX(-50%) translateY(0)     scale(1); }
      to   { opacity: 0; transform: translateX(-50%) translateY(8px)  scale(0.95); }
    }
    .inno-toast-icon { font-size: 20px; flex-shrink: 0; margin-top: 1px; }
    .inno-toast-body { flex: 1; min-width: 0; }
    .inno-toast-title {
      font-family: 'Syne', sans-serif;
      font-size: 12px; font-weight: 800; letter-spacing: .1em;
      text-transform: uppercase; color: rgba(0,229,255,0.9); margin-bottom: 4px;
    }
    .inno-toast-text {
      font-family: 'JetBrains Mono', monospace;
      font-size: 11px; color: rgba(255,255,255,0.5); line-height: 1.55;
    }
    .inno-toast.seed   { border-color: rgba(105,255,71,0.25); }
    .inno-toast.seed   .inno-toast-title { color: var(--seed-glow); }
    .inno-toast.reflect{ border-color: rgba(224,64,251,0.2); }
    .inno-toast.reflect .inno-toast-title { color: var(--dream); }

    /* ── WS status indicator ──────────────────────────────────────── */
    #innoWsStatus {
      width: 6px; height: 6px; border-radius: 50%;
      background: rgba(255,255,255,0.15);
      transition: background 0.4s ease, box-shadow 0.4s ease;
      flex-shrink: 0;
    }
    #innoWsStatus.connected {
      background: var(--arch);
      box-shadow: 0 0 8px rgba(0,229,255,0.6);
    }
    #innoWsStatus.error { background: rgba(255,70,70,0.8); }
  `;

  // CEL step names in order — used to drive progress bar
  const CEL_STEPS_TOTAL = 14;

  const wsManager = {
    ws: null,
    reconnectTimer: null,
    epochProgress: 0,

    init() {
      // Inject WS-specific CSS
      if (!document.getElementById("innovations-ws-css")) {
        const s = document.createElement("style");
        s.id = "innovations-ws-css";
        s.textContent = WS_CSS;
        document.head.appendChild(s);
      }
      // Epoch progress bar
      if (!document.getElementById("innoEpochBar")) {
        const bar  = document.createElement("div"); bar.id  = "innoEpochBar";
        const fill = document.createElement("div"); fill.id = "innoEpochFill";
        bar.appendChild(fill); document.body.appendChild(bar);
      }
      // Persona badge — inject into Aponi header if present
      if (!document.getElementById("innoPersonaBadge")) {
        const badge = document.createElement("div");
        badge.id = "innoPersonaBadge";
        badge.innerHTML = `<span class="persona-dot"></span><span id="innoPersonaLabel">—</span>`;
        // Try to append to .hdr-right; fall back to body float
        const hdr = document.querySelector(".hdr-right");
        if (hdr) hdr.insertBefore(badge, hdr.firstChild);
        else {
          badge.style.cssText = "position:fixed;top:14px;right:80px;z-index:9999;";
          document.body.appendChild(badge);
        }
      }
      // WS status dot in header
      if (!document.getElementById("innoWsStatus")) {
        const dot = document.createElement("div");
        dot.id = "innoWsStatus"; dot.title = "Innovations live feed";
        const hdr = document.querySelector(".hdr-right");
        if (hdr) hdr.appendChild(dot);
      }
      this.connect();
    },

    connect() {
      const base = (global._adaadState?.baseUrl || "http://127.0.0.1:8000")
        .replace(/^https?/, (s) => s === "https" ? "wss" : "ws");
      try {
        this.ws = new WebSocket(`${base}/ws/events`);
        this.ws.onopen    = () => this._setStatus("connected");
        this.ws.onclose   = () => { this._setStatus(""); this._scheduleReconnect(); };
        this.ws.onerror   = () => this._setStatus("error");
        this.ws.onmessage = (e) => this._onMessage(JSON.parse(e.data));
      } catch(_) { this._scheduleReconnect(); }
    },

    _setStatus(cls) {
      const dot = document.getElementById("innoWsStatus");
      if (dot) dot.className = cls;
    },

    _scheduleReconnect() {
      if (this.reconnectTimer) return;
      this.reconnectTimer = setTimeout(() => {
        this.reconnectTimer = null;
        this.connect();
      }, 5000);
    },

    _onMessage(msg) {
      if (msg.type !== "innovations") return;
      const frame = msg;
      switch (frame.type === "innovations" ? frame.channel : frame.type) {
        case "innovations":
          this._dispatch(frame);
          break;
      }
    },

    _dispatch(frame) {
      const t = frame.type || frame.innovations_type;
      if (frame.type === "innovations") {
        const inner = {...frame};
        delete inner.type; delete inner.channel;
        this._handle(inner);
      } else {
        this._handle(frame);
      }
    },

    _handle(frame) {
      switch (frame.type) {
        case "epoch_start":   this._onEpochStart(frame); break;
        case "epoch_end":     this._onEpochEnd(frame);   break;
        case "cel_step":      this._onCelStep(frame);    break;
        case "story_arc":     this._onStoryArc(frame);   break;
        case "personality":   this._onPersonality(frame);break;
        case "reflection":    this._onReflection(frame); break;
        case "seed_planted":  this._onSeed(frame);       break;
        case "gplugin":       this._onGPlugin(frame);    break;
      }
    },

    _onEpochStart(f) {
      this.epochProgress = 0;
      this._setProgress(2);
      innState.activeEpochId = f.epoch_id;
    },

    _onEpochEnd(f) {
      this._setProgress(100);
      setTimeout(() => this._setProgress(0), 900);
      innState.activeEpochId = null;
    },

    _onCelStep(f) {
      const pct = Math.round((f.step_number / CEL_STEPS_TOTAL) * 96) + 2;
      this._setProgress(pct);
    },

    _onStoryArc(f) {
      // Prepend to live story timeline if visible
      const timeline = document.querySelector(".story-timeline");
      if (!timeline) return;
      const agentClass = ["architect","dream","beast"].includes(f.agent) ? f.agent : "";
      const resultClass = f.result === "promoted" ? "promoted" : f.result === "rejected" ? "rejected" : agentClass;
      const row = document.createElement("div");
      row.className = "story-arc live-new";
      row.innerHTML = `
        <div class="story-arc-line">
          <div class="story-arc-dot ${resultClass}"></div>
          <div class="story-arc-connector"></div>
        </div>
        <div class="story-arc-content">
          <div class="story-arc-epoch">${escHtml(f.epoch || "—")}</div>
          <div class="story-arc-title">${escHtml(f.title || "Governance event")}</div>
          <div class="story-arc-meta">
            ${f.agent ? `<span class="story-arc-badge agent">${escHtml(f.agent)}</span>` : ""}
            ${f.result ? `<span class="story-arc-badge ${escHtml(f.result)}">${escHtml(f.result)}</span>` : ""}
            <span class="story-arc-badge" style="background:rgba(0,229,255,0.07);color:rgba(0,229,255,0.5);border:1px solid rgba(0,229,255,0.15);">live</span>
          </div>
        </div>`;
      timeline.insertBefore(row, timeline.firstChild);
      // Cap to 60 arcs in view
      while (timeline.children.length > 60) timeline.removeChild(timeline.lastChild);
    },

    _onPersonality(f) {
      innState.activePersonality = { agent_id: f.agent_id, philosophy: f.philosophy };
      loadPersonalityProfiles();
      const badge = document.getElementById("innoPersonaBadge");
      const label = document.getElementById("innoPersonaLabel");
      if (!badge || !label) return;

      // Update portrait in badge
      let portrait = badge.querySelector(".badge-portrait");
      if (!portrait) {
        portrait = document.createElement("img");
        portrait.className = "badge-portrait";
        portrait.style.cssText = "width:22px;height:22px;object-fit:contain;border-radius:4px;flex-shrink:0;";
        badge.insertBefore(portrait, badge.firstChild);
      }
      const imgMap = { architect: "agent_architect.png", dream: "agent_dream.png", beast: "agent_beast.png" };
      portrait.src = imgMap[f.agent_id] || "";
      portrait.onerror = () => { portrait.style.display = "none"; };

      badge.className = f.agent_id; // arch | dream | beast
      label.textContent = `${f.agent_id} · ${f.philosophy}`;
      badge.style.display = "flex";
      clearTimeout(badge._hideTimer);
      badge._hideTimer = setTimeout(() => { badge.style.display = "none"; }, 12000);
    },

    _onReflection(f) {
      this._toast("reflect", "🧠",
        `Self-Reflection · ${f.epoch_id}`,
        `Dominant: ${f.dominant_agent}  ·  Underperforming: ${f.underperforming_agent}\n${f.rebalance_hint}`
      );
    },

    _onSeed(f) {
      this._toast("seed", "🌱",
        `Seed Planted`,
        `${f.seed_id}  ·  lane: ${f.lane}\n${f.intent}`
      );
    },

    _onGPlugin(f) {
      if (!f.passed) {
        this._toast("", "🔒",
          `G-Plugin Blocked`,
          `${f.plugin_id}\n${f.message}`
        );
      }
    },

    _setProgress(pct) {
      const fill = document.getElementById("innoEpochFill");
      const bar  = document.getElementById("innoEpochBar");
      if (!fill || !bar) return;
      fill.style.width = `${pct}%`;
      if (pct === 0) bar.classList.add("idle");
      else           bar.classList.remove("idle");
    },

    _toast(cls, icon, title, text) {
      const t = document.createElement("div");
      t.className = `inno-toast ${cls}`;
      t.innerHTML = `
        <div class="inno-toast-icon">${icon}</div>
        <div class="inno-toast-body">
          <div class="inno-toast-title">${escHtml(title)}</div>
          <div class="inno-toast-text">${escHtml(text)}</div>
        </div>`;
      document.body.appendChild(t);
      setTimeout(() => {
        t.style.animation = "inno-toast-out 0.28s ease forwards";
        setTimeout(() => t.remove(), 300);
      }, 5500);
    },

    destroy() {
      if (this.ws) { try { this.ws.close(); } catch(_) {} this.ws = null; }
      if (this.reconnectTimer) { clearTimeout(this.reconnectTimer); this.reconnectTimer = null; }
    },
  };

  /* ══════════════════════════════════════════════════════════════════════
     BOOT: inject CSS, register with Aponi render loop
  ══════════════════════════════════════════════════════════════════════ */
  function boot() {
    if (!document.getElementById("innovations-css")) {
      const style = document.createElement("style");
      style.id = "innovations-css";
      style.textContent = INNOVATIONS_CSS;
      document.head.appendChild(style);
    }

    // Start live feed
    wsManager.init();

    // Expose to Aponi
    global._innovationsPanel = {
      view: viewInnovations,
      state: innState,
      ws: wsManager,
    };
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }

})(window);

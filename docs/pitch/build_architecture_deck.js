const pptxgen = require("pptxgenjs");
const pres = new pptxgen();
pres.layout = "LAYOUT_16x9"; // 10 x 5.625
pres.author = "Roshan Rana";
pres.title = "Fathom — AI Systems Architecture Review";

// Palette
const NAVY = "14213D", INK = "1B2A41", WHITE = "FFFFFF", ICE = "DCE7F5", MINT = "2EC4B6",
  GOLD = "F2B134", MUTED = "6B7A90", CARD = "F3F6FA", LINE = "C9D3E0", CARD_D = "1C2B4F", RED = "D64550";
const HF = "Cambria", BF = "Calibri";
const ASSETS = "C:/Code-Central/fathom/docs/assets/";

let n = 0;
function base(title, kicker) {
  const s = pres.addSlide();
  n += 1;
  s.background = { color: WHITE };
  if (kicker) s.addText(kicker.toUpperCase(), { x: 0.5, y: 0.28, w: 6, h: 0.25, fontFace: BF, fontSize: 10, bold: true, color: MINT, charSpacing: 2, isTextBox: true, margin: 0 });
  s.addText(title, { x: 0.5, y: 0.5, w: 9, h: 0.6, fontFace: HF, fontSize: 26, bold: true, color: NAVY, isTextBox: true, margin: 0 });
  s.addText(`Fathom · AI Systems Architecture Review · ${n}`, { x: 0.5, y: 5.25, w: 9, h: 0.25, fontFace: BF, fontSize: 8, color: MUTED, isTextBox: true, margin: 0 });
  return s;
}
function dark(title, sub) {
  const s = pres.addSlide();
  n += 1;
  s.background = { color: NAVY };
  s.addText(title, { x: 0.6, y: 1.9, w: 8.8, h: 0.9, fontFace: HF, fontSize: 34, bold: true, color: WHITE, isTextBox: true, margin: 0 });
  if (sub) s.addText(sub, { x: 0.6, y: 2.85, w: 8.8, h: 0.6, fontFace: BF, fontSize: 15, italic: true, color: ICE, isTextBox: true, margin: 0 });
  return s;
}
function card(s, x, y, w, h, fill = CARD, line = LINE) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: fill }, line: { color: line, width: 0.75 }, rectRadius: 0.06 });
}
function box(s, x, y, w, h, title, body, opt = {}) {
  const fill = opt.fill || CARD, tcol = opt.tcol || NAVY, bcol = opt.bcol || INK, line = opt.line || LINE;
  card(s, x, y, w, h, fill, line);
  s.addText(title, { x: x + 0.1, y: y + 0.06, w: w - 0.2, h: 0.28, fontFace: BF, fontSize: opt.ts || 11, bold: true, color: tcol, isTextBox: true, margin: 0 });
  if (body) s.addText(body, { x: x + 0.1, y: y + 0.34, w: w - 0.2, h: h - 0.4, fontFace: BF, fontSize: opt.bs || 8.5, color: bcol, isTextBox: true, margin: 0, valign: "top" });
}
function arrow(s, x1, y1, x2, y2, color = MUTED, w = 1.25) {
  const flipH = x2 < x1, flipV = y2 < y1;
  s.addShape(pres.shapes.LINE, { x: Math.min(x1, x2), y: Math.min(y1, y2), w: Math.abs(x2 - x1) || 0.01, h: Math.abs(y2 - y1) || 0.01, line: { color, width: w, endArrowType: "triangle" }, flipH, flipV });
}
function bullets(s, items, x, y, w, h, fs = 11, color = INK) {
  s.addText(items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < items.length - 1 } })), { x, y, w, h, fontFace: BF, fontSize: fs, color, isTextBox: true, margin: 0, paraSpaceAfter: 4, valign: "top" });
}
function table(s, rows, x, y, w, colW, fs = 8.5, rowH) {
  const data = rows.map((r, i) => r.map((c) => ({ text: c, options: i === 0 ? { bold: true, color: WHITE, fill: { color: NAVY }, fontSize: fs } : { fontSize: fs, color: INK } })));
  s.addTable(data, { x, y, w, colW, fontFace: BF, border: { type: "solid", pt: 0.5, color: LINE }, autoPage: false, rowH });
}
function imgFit(s, path, x, y, maxW, maxH, pw, ph) {
  const r = Math.min(maxW / pw, maxH / ph);
  const w = pw * r, h = ph * r;
  s.addImage({ path, x: x + (maxW - w) / 2, y, w, h });
  return { w, h };
}
function caption(s, text, x, y, w) {
  s.addText(text, { x, y, w, h: 0.3, fontFace: BF, fontSize: 9, italic: true, color: MUTED, isTextBox: true, margin: 0 });
}

// ---------- 1 Title
{
  const s = pres.addSlide(); n += 1; s.background = { color: NAVY };
  s.addText("Fathom", { x: 0.6, y: 1.35, w: 8, h: 0.9, fontFace: HF, fontSize: 48, bold: true, color: WHITE, isTextBox: true, margin: 0 });
  s.addText("AI Systems Architecture Review", { x: 0.6, y: 2.25, w: 8, h: 0.5, fontFace: BF, fontSize: 22, color: ICE, isTextBox: true, margin: 0 });
  s.addText("Advisor stock briefings grounded in SEC filings — quote, filings, verified-citation AI briefing, grounded Q&A", { x: 0.6, y: 2.8, w: 8.6, h: 0.5, fontFace: BF, fontSize: 13, italic: true, color: ICE, isTextBox: true, margin: 0 });
  s.addText("Perficient AI Prototype Challenge · Finance scenario · Release 0.2.0 · 12 September 2026 · Roshan Rana, AI Systems Architect", { x: 0.6, y: 4.6, w: 8.8, h: 0.3, fontFace: BF, fontSize: 10, color: MUTED, isTextBox: true, margin: 0 });
  s.addShape(pres.shapes.OVAL, { x: 8.2, y: 1.2, w: 1.1, h: 1.1, fill: { color: MINT }, line: { color: MINT } });
  s.addText("F", { x: 8.2, y: 1.2, w: 1.1, h: 1.1, fontFace: HF, fontSize: 40, bold: true, color: NAVY, align: "center", valign: "middle", isTextBox: true, margin: 0 });
}

// ---------- 2 Executive summary
{
  const s = base("Executive summary", "Overview");
  const cols = [
    ["What it is", ["A one-page briefing for a wealth-management advisor: current quote with context, the latest 10-K and 10-Qs with EDGAR links, an AI briefing in six sections, and follow-up Q&A.", "Every AI claim carries a verbatim quote that the application re-checks against the filing before it is shown."]],
    ["What it proves", ["Grounded generation can be made auditable: claims are verified, advice language is blocked, and every model call leaves a hash-only audit record.", "The same pipeline runs on 20 curated tickers (fixtures) or on any US-listed ticker from free, keyless sources."]],
    ["Why it is enterprise-ready", ["Built through a gated, evidence-producing lifecycle: 25 task packs, 25 independent verifications, 14 security reviews, 43 hash-chained ledger entries, CI gate on every push.", "Clear trust boundaries, a threat model, a runbook, an ORR and a change record."]],
  ];
  cols.forEach((c, i) => {
    const x = 0.5 + i * 3.05;
    card(s, x, 1.3, 2.9, 3.25);
    s.addText(c[0], { x: x + 0.15, y: 1.4, w: 2.6, h: 0.35, fontFace: HF, fontSize: 15, bold: true, color: NAVY, isTextBox: true, margin: 0 });
    bullets(s, c[1], x + 0.15, 1.85, 2.6, 2.6, 11.5);
  });
  s.addText("Ask of the audience: agree the pilot scope (full EDGAR universe, SSO, tamper-evident audit, advisor eval set) and the data-source policy for live quotes.", { x: 0.5, y: 4.7, w: 9, h: 0.45, fontFace: BF, fontSize: 10.5, italic: true, color: INK, isTextBox: true, margin: 0 });
}

// ---------- 3 Problem and users
{
  const s = base("The problem and the users", "Context");
  box(s, 0.5, 1.3, 4.3, 1.75, "The advisor's problem", "A client calls about a name the advisor does not follow. Getting current takes 30–60 minutes across a quote screen and two or three SEC filings. A general-purpose chatbot is faster but cannot be quoted to a client: it paraphrases, it may recommend, and it leaves no record.", { bs: 10 });
  box(s, 5.2, 1.3, 4.3, 1.75, "The firm's constraints", "Wealth management is a supervised activity. Anything the tool says may be repeated to a client, so it must describe and never advise, cite sources an advisor can open, and keep a record of what the AI produced from which inputs.", { bs: 10 });
  table(s, [
    ["Actor", "Needs", "Frequency"],
    ["Advisor (primary)", "One page per ticker: quote context, recent filings, cited briefing, follow-up questions; no advice language", "Several times a day"],
    ["Compliance / supervision", "Audit trail: what was produced, from which filings, by which model; evidence the guards work", "On review"],
    ["Firm platform team", "Runs on the firm's AI gateway; no keys in code; offline fallback; one command to validate", "Deploy / operate"],
    ["Automation and AI assistants", "The same capabilities over HTTP and MCP with identical contracts", "Ad hoc"],
  ], 0.5, 3.25, 9.0, [2.0, 5.4, 1.6], 9);
}

// ---------- 4 Solution at a glance
{
  const s = base("Solution at a glance", "Approach");
  const steps = [
    ["1", "Ticker in", "Quote card: last close, change, 52-week range, market cap, P/E, dividend yield — every figure stamped with its as-of date and source."],
    ["2", "Filings in", "Latest 10-K and 10-Qs, parsed into SEC items (Business, Risk Factors, MD&A, Legal Proceedings, Cybersecurity, Controls) with EDGAR links."],
    ["3", "Briefing", "The model receives capped section excerpts and must return JSON claims, each with a verbatim quote and section id."],
    ["4", "Verify and guard", "The app checks each quote against the filing, blocks recommendation language, audits the call, and renders badges."],
  ];
  steps.forEach((st, i) => {
    const x = 0.5 + i * 2.3;
    card(s, x, 1.35, 2.15, 2.15, CARD_D, CARD_D);
    s.addShape(pres.shapes.OVAL, { x: x + 0.15, y: 1.5, w: 0.4, h: 0.4, fill: { color: MINT }, line: { color: MINT } });
    s.addText(st[0], { x: x + 0.15, y: 1.5, w: 0.4, h: 0.4, fontFace: BF, fontSize: 14, bold: true, color: NAVY, align: "center", valign: "middle", isTextBox: true, margin: 0 });
    s.addText(st[1], { x: x + 0.65, y: 1.52, w: 1.4, h: 0.36, fontFace: BF, fontSize: 13, bold: true, color: WHITE, isTextBox: true, margin: 0, valign: "middle" });
    s.addText(st[2], { x: x + 0.15, y: 2.0, w: 1.85, h: 1.4, fontFace: BF, fontSize: 9, color: ICE, isTextBox: true, margin: 0, valign: "top" });
    if (i < 3) arrow(s, x + 2.15, 2.4, x + 2.3, 2.4, MINT, 2);
  });
  box(s, 0.5, 3.75, 4.4, 1.3, "Surfaces", "Streamlit advisor page · Typer CLI · FastAPI (JSON envelope) · MCP server (four tools). All four call the same package functions; none computes anything itself.", { bs: 10 });
  box(s, 5.1, 3.75, 4.4, 1.3, "Two data modes, one schema", "Fixtures: 20 large caps, 97 filings, committed. Live: any US-listed ticker from SEC EDGAR + Yahoo/Stooq, materialized per ticker into the same four tables. Switch with one environment variable.", { bs: 10 });
}

// ---------- 5 System context (C4 L1)
{
  const s = base("System context", "Architecture · C4 level 1");
  // left actors
  const actors = [["Advisor", "browser"], ["Operator", "terminal"], ["Automation", "HTTP client"], ["AI assistant", "MCP host"]];
  actors.forEach((a, i) => { box(s, 0.5, 1.3 + i * 0.85, 1.6, 0.7, a[0], a[1], { bs: 8.5 }); arrow(s, 2.1, 1.65 + i * 0.85, 2.75, 2.85, MUTED, 1); });
  // center system
  card(s, 2.8, 1.3, 3.4, 3.4, "EEF6F4", MINT);
  s.addText("Fathom", { x: 2.95, y: 1.38, w: 3, h: 0.3, fontFace: HF, fontSize: 14, bold: true, color: NAVY, isTextBox: true, margin: 0 });
  box(s, 2.95, 1.75, 3.1, 0.75, "Surfaces", "Streamlit page · CLI · FastAPI · MCP", { bs: 8.5 });
  box(s, 2.95, 2.6, 3.1, 1.0, "Core package `fathom`", "quotes · filings parser · BM25 retrieval · briefing / ask pipelines · citation verifier · advice guard · audit", { bs: 8.5 });
  box(s, 2.95, 3.7, 3.1, 0.85, "Data layer", "fixtures (parquet) or live cache materialized per ticker", { bs: 8.5 });
  // right externals
  box(s, 6.9, 1.3, 2.6, 0.75, "Portkey AI gateway", "→ AWS Bedrock · Claude Sonnet 4.5 (client-operated; key at runtime)", { bs: 8 });
  box(s, 6.9, 2.2, 2.6, 0.75, "SEC EDGAR (official, free)", "submissions · primary documents · XBRL company facts", { bs: 8 });
  box(s, 6.9, 3.1, 2.6, 0.75, "Yahoo Finance / Stooq", "daily bars (unofficial, keyless; fallback chain)", { bs: 8 });
  box(s, 6.9, 4.0, 2.6, 0.7, "Audit log (JSONL)", "hashes, counts, model, latency — never bodies by default", { bs: 8 });
  arrow(s, 6.2, 3.0, 6.9, 1.67, MUTED, 1); arrow(s, 6.2, 3.1, 6.9, 2.57, MUTED, 1); arrow(s, 6.2, 3.2, 6.9, 3.47, MUTED, 1); arrow(s, 6.2, 3.3, 6.9, 4.35, MUTED, 1);
  s.addText("Build-time only: Hugging Face datasets → fixtures via scripts/fetch_data.py. Live sources are called only when FATHOM_DATA_SOURCE=live; the gate and CI never touch the network.", { x: 0.5, y: 4.85, w: 9, h: 0.35, fontFace: BF, fontSize: 9, italic: true, color: MUTED, isTextBox: true, margin: 0 });
}

// ---------- 6 Component architecture (C4 L2)
{
  const s = base("Component architecture", "Architecture · C4 level 2");
  const groups = [
    { t: "Surfaces (render only)", x: 0.5, items: [["app/main.py", "Streamlit page"], ["cli.py", "Typer commands"], ["api.py", "FastAPI, JSON envelope"], ["mcp_server.py", "4 MCP tools"]] },
    { t: "Pipelines", x: 2.85, items: [["briefing.py", "context → draft → claims"], ["ask.py", "guard → retrieve → answer"], ["contracts.py", "frozen pydantic models"], ["guard.py", "advice regexes · verifier"], ["audit.py", "append-only JSONL"]] },
    { t: "Data", x: 5.2, items: [["data.py", "loaders, ticker check"], ["quotes.py", "QuoteCard maths"], ["filings.py", "SEC item parser"], ["retrieval.py", "BM25 (title-boosted)"], ["live/*", "sec · prices · facts · build"]] },
    { t: "Providers", x: 7.55, items: [["providers.py", "one protocol"], ["Offline", "extractive, default"], ["Portkey", "OpenAI-compatible"], ["Anthropic", "Messages API"], ["prompts.py", "frozen prompt text"]] },
  ];
  groups.forEach((g) => {
    card(s, g.x, 1.3, 2.15, 3.55);
    s.addText(g.t, { x: g.x + 0.1, y: 1.36, w: 2, h: 0.3, fontFace: BF, fontSize: 11, bold: true, color: NAVY, isTextBox: true, margin: 0 });
    g.items.forEach((it, i) => {
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: g.x + 0.1, y: 1.72 + i * 0.62, w: 1.95, h: 0.54, fill: { color: WHITE }, line: { color: LINE, width: 0.75 }, rectRadius: 0.05 });
      s.addText(it[0], { x: g.x + 0.18, y: 1.75 + i * 0.62, w: 1.8, h: 0.24, fontFace: "Courier New", fontSize: 8.5, bold: true, color: NAVY, isTextBox: true, margin: 0 });
      s.addText(it[1], { x: g.x + 0.18, y: 1.97 + i * 0.62, w: 1.8, h: 0.26, fontFace: BF, fontSize: 8, color: INK, isTextBox: true, margin: 0 });
    });
  });
  arrow(s, 2.65, 3.1, 2.85, 3.1, MINT, 2); arrow(s, 5.0, 3.1, 5.2, 3.1, MINT, 2); arrow(s, 7.35, 3.1, 7.55, 3.1, MINT, 2);
  s.addText("Dependency direction is left to right only. Surfaces never import pandas or regex; providers never see settings beyond their own keys; the data layer knows nothing about models.", { x: 0.5, y: 4.9, w: 9, h: 0.3, fontFace: BF, fontSize: 9, italic: true, color: MUTED, isTextBox: true, margin: 0 });
}

// ---------- 7 Briefing pipeline
{
  const s = base("The briefing pipeline", "Architecture · critical flow");
  const stages = [
    ["Context", "latest 10-K + two newest 10-Qs; canonical sections capped (≈27k tokens)"],
    ["Prompt", "frozen system prompt: excerpts are data; verbatim 6–40 word quotes; no advice"],
    ["Provider", "offline extractive | Portkey → Claude | Anthropic; one JSON contract"],
    ["Draft → claims", "JSON parsed; one repair retry; text/quote length clamps; never raises"],
    ["Verify", "quote normalised and matched inside the cited section → verified / unverified"],
    ["Guard", "14 recommendation patterns; flagged claims replaced by a fixed notice"],
    ["Audit", "sha256 of prompt and response, model, latency, counts, guard hits"],
    ["Render", "six sections, badge text, source captions, disclaimer"],
  ];
  stages.forEach((st, i) => {
    const col = i % 4, row = Math.floor(i / 4);
    const x = 0.5 + col * 2.3, y = 1.4 + row * 1.7;
    card(s, x, y, 2.15, 1.35, row === 0 ? CARD : "EEF6F4", row === 0 ? LINE : MINT);
    s.addText(`${i + 1}. ${st[0]}`, { x: x + 0.1, y: y + 0.08, w: 1.95, h: 0.3, fontFace: BF, fontSize: 11, bold: true, color: NAVY, isTextBox: true, margin: 0 });
    s.addText(st[1], { x: x + 0.1, y: y + 0.4, w: 1.95, h: 0.9, fontFace: BF, fontSize: 8.5, color: INK, isTextBox: true, margin: 0, valign: "top" });
    if (col < 3) arrow(s, x + 2.15, y + 0.67, x + 2.3, y + 0.67, MUTED, 1.25);
  });
  arrow(s, 9.0, 2.75, 9.0, 3.1, MUTED, 1.25);
  s.addText("Failure paths are first-class: invalid JSON → one repair → CONTRACT_INVALID; gateway down → PROVIDER_HTTP with a reason and no body; unverifiable quote → shown and flagged, never hidden.", { x: 0.5, y: 4.85, w: 9, h: 0.35, fontFace: BF, fontSize: 9, italic: true, color: MUTED, isTextBox: true, margin: 0 });
}

// ---------- 8 Grounding mechanism
{
  const s = base("Verify, don't trust: the claim contract", "Design · grounding");
  card(s, 0.5, 1.3, 4.6, 3.55, CARD_D, CARD_D);
  s.addText("What the model must return (one claim)", { x: 0.65, y: 1.38, w: 4.3, h: 0.3, fontFace: BF, fontSize: 11, bold: true, color: MINT, isTextBox: true, margin: 0 });
  s.addText([
    '{', '  "text": "Net sales increased 5% year over year",', '  "accession": "0000320193-26-000013",', '  "section_id": "10-Q:I.2",',
    '  "quote": "Total net sales increased 5% or $4.5 billion during the second quarter of 2026"', '}',
  ].join("\n"), { x: 0.65, y: 1.72, w: 4.3, h: 1.6, fontFace: "Courier New", fontSize: 8.5, color: WHITE, isTextBox: true, margin: 0, valign: "top" });
  s.addText("What the application does with it", { x: 0.65, y: 3.35, w: 4.3, h: 0.3, fontFace: BF, fontSize: 11, bold: true, color: MINT, isTextBox: true, margin: 0 });
  bullets(s, ["normalise whitespace, case and quote glyphs on both sides", "require 6–60 words and a substring match inside the cited section's full text", "set verified = true/false; scrub advice language; count; audit"], 0.65, 3.68, 4.3, 1.1, 9, ICE);
  const badges = [["✅ verified", "quote found in the cited section", MINT], ["⚠️ unverified", "shown, flagged, counted — never hidden", GOLD], ["⛔ removed", "recommendation-style language replaced by a fixed notice", RED]];
  badges.forEach((b, i) => {
    const y = 1.3 + i * 0.75;
    card(s, 5.4, y, 4.1, 0.62);
    s.addText(b[0], { x: 5.55, y: y + 0.05, w: 1.5, h: 0.5, fontFace: BF, fontSize: 12, bold: true, color: b[2], isTextBox: true, margin: 0, valign: "middle" });
    s.addText(b[1], { x: 7.0, y: y + 0.05, w: 2.4, h: 0.5, fontFace: BF, fontSize: 9, color: INK, isTextBox: true, margin: 0, valign: "middle" });
  });
  box(s, 5.4, 3.6, 4.1, 1.25, "Why this matters to compliance", "The badge is the control, and the eval suite reports the verified share as a headline KPI. Offline mode is verified by construction (its quotes are the sentences themselves), so it proves the plumbing; live-mode quality is measured from the audit log, not asserted.", { bs: 9 });
}

// ---------- 9 Data architecture
{
  const s = base("Data architecture: two sources, one schema", "Architecture · data");
  box(s, 0.5, 1.3, 2.9, 1.75, "Fixture mode (default)", "20 large caps · 97 filings (Apr 2025 – May 2026) · daily bars to 2026-09-11 · quote snapshot · company master. Rebuilt by scripts/fetch_data.py from four Hugging Face datasets; ≈12 MB committed with licences and hand-checkable anchors.", { bs: 9 });
  box(s, 0.5, 3.2, 2.9, 1.65, "Live mode (opt-in)", "Any US-listed ticker. SEC EDGAR for filings and XBRL facts; Yahoo chart bars with Stooq fallback. Materialized per ticker into .cache/live/<T>/ with a manifest; 6-hour TTL; `fathom fetch --force` refreshes.", { bs: 9 });
  arrow(s, 3.4, 2.15, 4.1, 2.9, MINT, 2); arrow(s, 3.4, 4.0, 4.1, 3.2, MINT, 2);
  card(s, 4.1, 2.35, 2.2, 1.4, "EEF6F4", MINT);
  s.addText("Four tables, one schema", { x: 4.2, y: 2.42, w: 2, h: 0.3, fontFace: BF, fontSize: 11, bold: true, color: NAVY, isTextBox: true, margin: 0 });
  s.addText("filings.parquet\nbars.parquet\nquotes.parquet\ncompanies.parquet", { x: 4.2, y: 2.75, w: 2, h: 0.95, fontFace: "Courier New", fontSize: 9, color: INK, isTextBox: true, margin: 0 });
  arrow(s, 6.3, 3.05, 6.95, 3.05, MINT, 2);
  box(s, 6.95, 1.3, 2.55, 3.55, "Downstream is unchanged", "• SEC item parser (TOC-dropping, cross-reference fallback)\n• BM25 index over items and chunks\n• briefing and Q&A pipelines\n• citation verifier and guard\n• every surface\n\nThe live pipeline is a data producer, not a new code path: the smallest correct change, and the one already covered by 400+ contract tests.", { bs: 9 });
  s.addText("Design rule: `data_dir_for(ticker, settings)` is the only routing decision; the ticker is shape-validated before any path or URL is built.", { x: 0.5, y: 4.95, w: 9, h: 0.3, fontFace: BF, fontSize: 9, italic: true, color: MUTED, isTextBox: true, margin: 0 });
}

// ---------- 10 Live data pipeline
{
  const s = base("Live data pipeline (free, no API keys)", "Architecture · live mode");
  const src = [["SEC ticker map", "company_tickers.json → CIK"], ["SEC submissions", "recent 10-K/10-Q, 24 months, ≤5"], ["SEC primary documents", "iXBRL HTML → text (stdlib)"], ["SEC XBRL facts", "shares, EPS TTM, equity, DPS"], ["Yahoo chart → Stooq CSV", "2 years of daily bars"]];
  src.forEach((x, i) => box(s, 0.5, 1.3 + i * 0.72, 2.6, 0.62, x[0], x[1], { bs: 8, ts: 9.5 }));
  card(s, 3.5, 1.3, 2.6, 3.55, "EEF6F4", MINT);
  s.addText("LiveHttp", { x: 3.6, y: 1.36, w: 2.4, h: 0.3, fontFace: BF, fontSize: 11, bold: true, color: NAVY, isTextBox: true, margin: 0 });
  bullets(s, ["User-Agent with operator contact (SEC fair-access policy)", "per-host throttle ≥ 0.12 s (≤ 8 req/s vs SEC's 10)", "on-disk cache keyed by URL hash; TTLs per call", "25 MB streamed size cap", "every failure → SOURCE_HTTP with a reason, never a body"], 3.6, 1.7, 2.4, 3.1, 8.5);
  for (let i = 0; i < 5; i++) arrow(s, 3.1, 1.61 + i * 0.72, 3.5, 1.61 + i * 0.72, MUTED, 1);
  arrow(s, 6.1, 3.07, 6.5, 3.07, MINT, 2);
  box(s, 6.5, 1.3, 3.0, 1.55, "materialize(ticker)", "typed accessors on every payload field → same four tables + manifest.json (fetched_at, accessions, section coverage, sources). Cold fetch measured at 2–3 s per ticker.", { bs: 8.5 });
  box(s, 6.5, 3.0, 3.0, 1.85, "Valuation from XBRL facts", "market cap = last close × shares outstanding; P/E = close / EPS TTM (four latest quarterly frames); P/B = market cap / equity; yield = DPS TTM / close. Labelled as derived; None when a fact is missing.", { bs: 8.5 });
  s.addText("Tested offline with recorded fixtures and structural fuzzing; a network smoke test is opt-in (FATHOM_NETWORK_TESTS=1).", { x: 0.5, y: 4.95, w: 9, h: 0.3, fontFace: BF, fontSize: 9, italic: true, color: MUTED, isTextBox: true, margin: 0 });
}

// ---------- 11 Design choices
{
  const s = base("Design choices and why", "Design decisions");
  table(s, [
    ["Decision", "Alternatives considered", "Why this one"],
    ["Verifiable claim contract (D-003)", "Free-text summary; summary with section references", "A briefing an advisor may repeat must be checkable; the badge becomes the control and the KPI"],
    ["Lexical BM25 over SEC items, no vector DB (D-004)", "Embeddings + FAISS/Chroma; rank_bm25", "Five documents per ticker already structured into items; explainable to compliance; deterministic in CI; one function to swap later"],
    ["Offline provider is a real provider (D-005)", "Branch in the pipeline between extractive and LLM", "One code path from prompt to verified claims; demo, CI and bench never need a key"],
    ["Plain httpx, no vendor SDKs", "OpenAI / Anthropic / Portkey SDKs", "The verifier and error taxonomy are the product; three small clients are easier to audit than three SDK surfaces"],
    ["Live mode materializes the fixture schema (D-013)", "DataSource protocol refactor; keyed vendor APIs", "Parser, retrieval, briefing and guard stay untouched and contract-tested; no keys, SEC is official"],
    ["Typed payload accessors + structural fuzz (D-014)", "Enumerated exception guards", "Four security rounds showed enumerated guards leak; typed accessors and node-mutation fuzz closed the class"],
    ["Streamlit + Typer + FastAPI + MCP", "React front end; n8n canvas", "Core functionality over polish; every surface is a thin renderer over one package"],
  ], 0.5, 1.3, 9.0, [2.6, 2.4, 4.0], 8.5);
}

// ---------- 12 Major features
{
  const s = base("Major features", "Product");
  const feats = [
    ["Quote card", "last close and change, 52-week range, market cap, P/E, dividend yield, one-year chart; each with an as-of stamp and source"],
    ["Filings table", "latest 10-K and 10-Qs with fiscal period, accession and a link to the EDGAR index"],
    ["AI briefing", "six sections: business snapshot, latest results, risks, liquidity and capital, notable disclosures, talking points"],
    ["Grounded Q&A", "advisor question → BM25 over items and chunks → cited answer; \"not found\" when the filings do not cover it"],
    ["Advice guard", "input and output patterns for buy/sell/hold, price targets, over/underweight, valuation calls; fixed notice on hit"],
    ["Audit log", "one JSON line per call: hashes, model, latency, tokens, claim counts, guard hits; bodies only when opted in"],
    ["Four surfaces", "Streamlit page, CLI (brief/ask/quote/filings/fetch/probe/bench), HTTP API with a JSON envelope, MCP tools"],
    ["Live data mode", "any US-listed ticker from SEC EDGAR + Yahoo/Stooq; `fathom fetch`; cache and TTL; same contracts"],
    ["Eval bench in the gate", "parser coverage, retrieval hit-rate, guard escapes, verified share, injection test → metrics card"],
  ];
  feats.forEach((f, i) => {
    const col = i % 3, row = Math.floor(i / 3);
    box(s, 0.5 + col * 3.05, 1.3 + row * 1.2, 2.9, 1.05, f[0], f[1], { bs: 8.5 });
  });
}

// ---------- 13-15 Fixture screenshots
{
  const s = base("The advisor page: quote card, chart and filings", "Screenshots · fixture mode (Apple Inc.)");
  const r = imgFit(s, ASSETS + "00-full-page-crop.png", 0.5, 1.25, 9.0, 3.65, 1125, 1000);
  caption(s, "Offline fixture mode. Six metrics with a single source caption; the one-year close series; the filings table links to the EDGAR index for each accession.", 0.5, 4.95, 9);
}
{
  const s = base("The briefing: every claim cited, every badge earned", "Screenshots · fixture mode (Apple Inc.)");
  imgFit(s, ASSETS + "03-briefing-crop.png", 0.5, 1.25, 5.25, 3.65, 1125, 820);
  box(s, 5.95, 1.25, 3.55, 1.7, "What you are looking at", "Offline extractive provider: sentences lifted verbatim from the cited sections, so every badge is ✅ verified by construction. Each claim carries a caption with form, filing date, section title and accession.", { bs: 9 });
  box(s, 5.95, 3.1, 3.55, 1.8, "In live LLM mode", "Claude Sonnet 4.5 via Portkey writes the claim text and must copy a 6–40 word quote; paraphrased quotes surface as ⚠️ unverified. The status strip shows provider, model, claim counts and verified counts for the session.", { bs: 9 });
}
{
  const s = base("Grounded Q&A and the advice guard", "Screenshots · fixture mode (Apple Inc.)");
  imgFit(s, ASSETS + "04-ask-crop.png", 0.5, 1.25, 9.0, 2.6, 1125, 663);
  box(s, 0.5, 4.0, 4.4, 0.95, "Cited answers", "\"What are the main risk factors?\" → the top-ranked chunks, answered with verified quotes from Risk Factors.", { bs: 9 });
  box(s, 5.1, 4.0, 4.4, 0.95, "Guarded questions", "\"Should I buy Apple stock?\" never reaches the model: the input guard returns the fixed notice and the call is audited with provider = guard.", { bs: 9 });
}

// ---------- 16-17 Live screenshots
{
  const s = base("Live mode: a ticker outside the demo set", "Screenshots · live mode (Netflix)");
  imgFit(s, ASSETS + "05-live-nflx-top.png", 0.5, 1.25, 5.4, 3.65, 1140, 1250);
  box(s, 6.1, 1.25, 3.4, 1.75, "What happened", "Sidebar switched to Live; ticker typed; Fetch. In about two seconds Fathom pulled five filings from SEC EDGAR, two years of Yahoo bars and four XBRL facts, and wrote the four tables plus a manifest.", { bs: 9 });
  box(s, 6.1, 3.15, 3.4, 1.75, "Read the sources line", "\"Prices: yahoo via .cache/live/NFLX/bars.parquet as of 2026-09-11 · Snapshot: SEC XBRL companyconcept … × yahoo close\" — provenance is on the page, not in a footnote.", { bs: 9 });
}
{
  const s = base("Live mode: briefing and answer on fresh filings", "Screenshots · live mode (Netflix)");
  imgFit(s, ASSETS + "06-live-nflx-briefing.png", 0.5, 1.25, 4.5, 3.6, 1140, 1130);
  imgFit(s, ASSETS + "07-live-nflx-ask.png", 5.2, 1.25, 4.3, 1.8, 1140, 470);
  box(s, 5.2, 3.2, 4.3, 1.65, "Honest reading", "Offline extractive provider on live text: the Risk Factors and Business sections read well; \"Latest results\" and \"Liquidity\" came back empty because Netflix's MD&A opens with tables and boilerplate that the extractive heuristics skip. The live LLM path composes those sections; the extractive path is the no-key fallback.", { bs: 9 });
}

// ---------- 18 Security and compliance
{
  const s = base("Security and compliance controls", "Enterprise readiness · controls");
  table(s, [
    ["Boundary", "Threat", "Control in the code", "Evidence"],
    ["B1 user input", "advice elicitation, prompt override, free-text ticker", "input + output guard; ticker shape check before any path/URL; API enum for source; question length bound", "guard tests, T-020 security"],
    ["B2 AI gateway", "key leakage; malformed or spoofed responses", "keys only from env by name; secrets scan in the gate; JSON contract with one repair; every httpx error mapped to a Fathom error", "T-004/T-015 security"],
    ["B3 filing text", "prompt injection embedded in filings", "excerpts declared as data; injected instructions cannot become verified claims; FR-018 test in the bench", "bench injection KPI"],
    ["B4 audit file", "bodies, questions or keys in logs", "hashes and counts only by default; never-log test with a capturing handler", "T-005 security"],
    ["B6 live sources", "tampered or malformed payloads; rate limits; contact exposure", "stdlib parsing; typed accessors; whole-body guards; streamed size cap; throttle; contact never committed", "T-018 … T-024 security"],
  ], 0.5, 1.3, 9.0, [1.3, 2.2, 3.6, 1.9], 8);
  s.addText("Residual risks are written down and owned: no authentication in the prototype (SSO in front for a pilot), local audit file not tamper-evident, unofficial price endpoints.", { x: 0.5, y: 4.7, w: 9, h: 0.4, fontFace: BF, fontSize: 9, italic: true, color: MUTED, isTextBox: true, margin: 0 });
}

// ---------- 19 Enterprise readiness: process
{
  const s = base("How it was built: a gated, evidence-producing lifecycle", "Enterprise readiness · process");
  const gates = ["G0 brief", "G1 reqs", "G2 HLD + threat model", "G3 LLD (frozen contracts)", "G4 plan + packs", "G5 foundation + CI", "G6 build loop", "G7 assurance", "G8 release"];
  gates.forEach((g, i) => {
    const x = 0.5 + i * 1.0;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.35, w: 0.92, h: 0.62, fill: { color: i < 5 ? CARD_D : "1E5C57" }, line: { color: i < 5 ? CARD_D : "1E5C57" }, rectRadius: 0.05 });
    s.addText(g, { x: x + 0.04, y: 1.37, w: 0.84, h: 0.58, fontFace: BF, fontSize: 7.5, bold: true, color: WHITE, align: "center", valign: "middle", isTextBox: true, margin: 0 });
  });
  const stats = [["25", "task packs, each with acceptance criteria, scope, budget and risk class"], ["25", "independent verifications in a fresh context, in a git worktree pinned to the task's commit"], ["14", "security reviews; every HIGH closed by a fix pack and a fresh re-review"], ["43", "hash-chained evidence-ledger entries; chain verified at export"]];
  stats.forEach((st, i) => {
    const x = 0.5 + i * 2.3;
    card(s, x, 2.2, 2.15, 1.25);
    s.addText(st[0], { x: x + 0.12, y: 2.25, w: 1.9, h: 0.5, fontFace: HF, fontSize: 28, bold: true, color: GOLD, isTextBox: true, margin: 0 });
    s.addText(st[1], { x: x + 0.12, y: 2.75, w: 1.9, h: 0.65, fontFace: BF, fontSize: 8.5, color: INK, isTextBox: true, margin: 0, valign: "top" });
  });
  box(s, 0.5, 3.65, 4.4, 1.25, "Separation of duties, by construction", "Frontier model for design, threat model, contracts and orchestration; Sonnet-class agents for every implementation, verification and security review. The implementer never verifies; the verifier never edits; no agent writes an approver's name.", { bs: 9 });
  box(s, 5.1, 3.65, 4.4, 1.25, "One command validates everything", "ruff · mypy strict (host and Linux) · pytest with ≥ 80 % coverage · secrets scan · offline eval bench · drift checks. CI runs the same command on every push; the network is never touched.", { bs: 9 });
}

// ---------- 20 Quality metrics (native chart)
{
  const s = base("Quality metrics from the gate", "Enterprise readiness · measurement");
  s.addChart(pres.charts.BAR, [{ name: "Value", labels: ["Parser coverage", "Offline verified share", "Retrieval hit-rate", "Injection test", "Coverage (÷100)"], values: [1.0, 1.0, 0.7786, 1.0, 0.9582] }], {
    x: 0.5, y: 1.3, w: 5.2, h: 3.5, barDir: "bar", chartColors: [MINT], showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.00", dataLabelFontSize: 9, dataLabelColor: INK,
    catAxisLabelColor: INK, catAxisLabelFontSize: 9, valAxisLabelColor: MUTED, valAxisLabelFontSize: 8, valAxisMinVal: 0, valAxisMaxVal: 1.1, valGridLine: { color: LINE, size: 0.5 }, catGridLine: { style: "none" }, showLegend: false, showTitle: true, title: "Ratios (1.0 = target met)", titleFontSize: 10, titleColor: NAVY,
  });
  table(s, [
    ["KPI", "Value", "Target"],
    ["Tests / coverage", "458 passed (2 network tests skipped offline) / 95.8 %", "≥ 80 %"],
    ["Guard escapes (30 adversarial phrases)", "0", "0"],
    ["Guard false positives (12 benign)", "0", "info only"],
    ["Offline briefing latency, median", "33 ms", "≤ 5 s"],
    ["Live cold fetch (NFLX, COST)", "≈ 2–3 s", "≤ 30 s"],
    ["Prompt size per briefing", "≈ 27 k tokens", "≤ 40 k"],
    ["Live briefing latency", "measured from the audit log on the day", "≤ 90 s"],
  ], 5.9, 1.3, 3.6, [1.55, 1.25, 0.8], 8);
  s.addText("Retrieval hit-rate is below its 0.9 aspiration and is shown as informational rather than edited to pass; title boosting raised it from 0.74 to 0.78 and the ranker is one function to replace.", { x: 0.5, y: 4.9, w: 9, h: 0.35, fontFace: BF, fontSize: 9, italic: true, color: MUTED, isTextBox: true, margin: 0 });
}

// ---------- 21 Quirks and limitations
{
  const s = base("Quirks and known limitations (stated, not hidden)", "Honesty");
  const q = [
    ["Offline mode proves plumbing, not prose", "Its 100 % verified share is by construction; on live text it can leave a section empty (Netflix MD&A opens with tables). The LLM path composes those sections."],
    ["XBRL-derived ratios are approximations", "EPS TTM sums quarterly XBRL frames and is not split-adjusted: Netflix shows P/E 8.98 after its stock split. Labelled as derived; a vendor feed would replace it in a pilot."],
    ["Unofficial price endpoints", "Yahoo's chart API and Stooq CSV are keyless but unofficial; Stooq intermittently serves a bot-challenge page. Fixture mode is the demo default for that reason."],
    ["Retrieval hit-rate 0.78", "Lexical ranking misses some golden queries; the KPI is informational and the ranker is swappable."],
    ["Cross-reference-sheet 10-Ks", "McDonald's-style filings need a heading fallback; two sub-sections still over- or under-run slightly (backlog)."],
    ["No authentication, local audit file", "Single-user prototype: SSO in front of the API and a tamper-evident audit sink are pilot work, listed in the ORR."],
    ["Metrics card timestamp churn", "Every gate run rewrites the rendered card's timestamp; harmless, noted for the next build."],
    ["Guard scans claim text, not quotes", "Quotes are never rendered, so the exposure is nil today; noted as LOW."],
  ];
  q.forEach((it, i) => {
    const col = i % 2, row = Math.floor(i / 2);
    box(s, 0.5 + col * 4.6, 1.3 + row * 0.9, 4.45, 0.82, it[0], it[1], { bs: 8, ts: 9.5 });
  });
}

// ---------- 22 Cost and performance
{
  const s = base("Cost, performance and operability", "Enterprise readiness · operations");
  const cards = [["1 call", "per briefing or question; prompt capped by section character limits (≈ 27 k tokens)"], ["33 ms", "median offline briefing; live ≈ 60–90 s dominated by the model"], ["2–3 s", "cold live fetch per ticker (five documents, four facts, one chart); warm reads < 1 s"], ["0 keys", "needed for the demo or for live data; the AI gateway key is injected at runtime only"]];
  cards.forEach((c, i) => {
    const x = 0.5 + i * 2.3;
    card(s, x, 1.3, 2.15, 1.35);
    s.addText(c[0], { x: x + 0.12, y: 1.35, w: 1.9, h: 0.5, fontFace: HF, fontSize: 26, bold: true, color: GOLD, isTextBox: true, margin: 0 });
    s.addText(c[1], { x: x + 0.12, y: 1.87, w: 1.9, h: 0.75, fontFace: BF, fontSize: 8.5, color: INK, isTextBox: true, margin: 0, valign: "top" });
  });
  box(s, 0.5, 2.85, 4.4, 2.0, "Operability", "• Runbook with start/stop, modes, common failures and fallbacks\n• Demo checklist with a fallback line for every failure mode\n• Operational readiness review and change records for 0.1.0 and 0.2.0\n• `fathom probe` checks the gateway; `fathom fetch` pre-warms live data\n• Rollback is an environment variable (offline / fixture) or a git tag", { bs: 9 });
  box(s, 5.1, 2.85, 4.4, 2.0, "Observability and audit", "• Structured INFO logs: provider, model, latency, claim counts — never bodies\n• Audit JSONL per call with sha256 of prompt and response\n• Alert candidates named for a pilot: verified share < 0.7/day, guard hits > 0, provider error rate\n• Manifest per live ticker records URLs, accessions and fetched-at for provenance", { bs: 9 });
}

// ---------- 23 Roadmap
{
  const s = base("Roadmap to a pilot", "Next steps");
  const phases = [["Weeks 1–2", "Harden data", ["Vendor or licensed quote feed behind the existing price interface", "Split-adjusted fundamentals; XBRL only as fallback", "Full EDGAR universe with nightly pre-warm"]], ["Weeks 3–4", "Secure and host", ["SSO in front of the API and page", "Tamper-evident audit sink (hash chain or append-only store)", "Secrets from the platform vault; SBOM in CI"]], ["Weeks 5–6", "Measure", ["Advisor eval set built with the compliance team", "Live verified-share and guard dashboards", "Embedding or hybrid ranker if the hit-rate target is confirmed"]], ["Week 7+", "Scale", ["Model routing through the gateway (cost tiers)", "Batch briefings for watchlists", "Change record and ORR sign-off for production"]]];
  phases.forEach((p, i) => {
    const x = 0.5 + i * 2.3;
    card(s, x, 1.3, 2.15, 3.5, i === 0 ? "EEF6F4" : CARD, i === 0 ? MINT : LINE);
    s.addText(p[0], { x: x + 0.12, y: 1.36, w: 1.9, h: 0.28, fontFace: BF, fontSize: 9, bold: true, color: MINT, charSpacing: 1, isTextBox: true, margin: 0 });
    s.addText(p[1], { x: x + 0.12, y: 1.62, w: 1.9, h: 0.35, fontFace: HF, fontSize: 14, bold: true, color: NAVY, isTextBox: true, margin: 0 });
    bullets(s, p[2], x + 0.12, 2.05, 1.9, 2.7, 9);
  });
  s.addText("Everything above is additive: the contracts, the verifier, the guard and the audit record do not change.", { x: 0.5, y: 4.95, w: 9, h: 0.3, fontFace: BF, fontSize: 9, italic: true, color: MUTED, isTextBox: true, margin: 0 });
}

// ---------- 24 Appendix: decision log
{
  const s = base("Appendix A — Decision log (abridged)", "Appendix");
  table(s, [
    ["ID", "Decision", "Consequence"],
    ["D-002", "Demo data from four Hugging Face datasets, committed as fixtures with licences and anchors", "Deterministic, offline demo; refresh is one script"],
    ["D-003", "Grounding by verbatim citation, not by trust", "JSON claim contract; verifier; badges; verified-share KPI"],
    ["D-004", "BM25 over SEC items, no vector database", "No infrastructure; explainable; one function to replace"],
    ["D-005", "Providers speak one JSON contract; offline is a real provider", "One code path; CI and demo never need a key"],
    ["D-006 / D-009", "Parser heading fallback for cross-reference-sheet 10-Ks (tightened after a failed attempt)", "McDonald's briefing restored; invariant for all other filings"],
    ["D-007 / D-010", "Claim conversion never raises; transport errors are Fathom errors", "HIGH security finding and a resilience gap closed"],
    ["D-008 / D-011", "Title-boosted retrieval; API binds loopback; demo polish heuristics", "Honest KPI; safer default; readable offline briefing"],
    ["D-013", "Live mode materializes the fixture schema from SEC EDGAR + Yahoo/Stooq", "Any US ticker; downstream untouched; new trust boundary B6"],
    ["D-014", "Typed payload accessors and structural fuzz as acceptance criteria", "Closed a class of parsing crashes found across four security rounds"],
  ], 0.5, 1.3, 9.0, [1.1, 4.6, 3.3], 8);
}

// ---------- 25 Appendix: process stats and lessons
{
  const s = base("Appendix B — Build statistics and lessons", "Appendix");
  table(s, [
    ["Item", "v0.1.0 (fixtures)", "v0.2.0 (live data)"],
    ["Task packs", "18 (T-000 … T-017)", "7 (T-018 … T-024)"],
    ["Implementer attempts", "22", "17"],
    ["Verifier runs (fresh context, pinned worktree)", "20", "13"],
    ["Security reviews", "8", "9 (four rounds on payload parsing)"],
    ["Real bugs caught by independent roles", "5 (deps extras, fallback bodies, null completion, stale figures, bind 0.0.0.0)", "6 (ticker routing, path build before validation, four parsing classes)"],
    ["Ledger entries / gates", "32 / G0–G8", "11 / G1–G4 re-entry, G6.4, G7, G8"],
    ["Tests / coverage at ship", "287 / 96.0 %", "458 / 95.8 %"],
  ], 0.5, 1.3, 9.0, [3.0, 2.8, 3.2], 8.5);
  box(s, 0.5, 3.55, 9.0, 1.35, "Lessons written into the decision log", "• Specs that touch unstructured text need a content-level acceptance test before dispatch (the parser fallback took two attempts).\n• Documentation packs run last, once, after all code tasks (figures moved three times).\n• For third-party payloads, specify typed accessors, whole-body guards and structural fuzzing up front; enumerating failure modes leaks.\n• Verifiers occasionally write into the worktree copy; the orchestrator names the live path and copies before removal.", { bs: 9 });
}

// ---------- 26 Appendix: repository map
{
  const s = base("Appendix C — Repository map and how to run", "Appendix");
  s.addText(["fathom/         core: config, errors, data, quotes, filings, retrieval,", "                prompts, providers, contracts, guard, audit, briefing,", "                ask, bench, cli, api, mcp_server, live/*", "app/            Streamlit page + rendering helpers", "data/           fixtures (parquet) + SOURCES.md (licences, anchors)", "tests/          458 tests; recorded live fixtures", "metrics/        headline.json, card.json/md, render.py (drift-checked)", "docs/design/    brief, requirements, HLD, threat model, LLD,", "                plan, live-data amendment, decisions", "docs/tasks/     25 packs with verdict and security files", "docs/evidence/  hash-chained ledger + exported evidence pack", "docs/ops/       runbook, ORR, change records, demo checklist", "docs/pitch/     one-slide pitch and this deck"].join("\n"), { x: 0.5, y: 1.3, w: 5.6, h: 3.3, fontFace: "Courier New", fontSize: 7.5, color: INK, isTextBox: true, margin: 0, valign: "top" });
  card(s, 6.3, 1.3, 3.2, 3.55, CARD_D, CARD_D);
  s.addText("Run it", { x: 6.45, y: 1.38, w: 3, h: 0.3, fontFace: BF, fontSize: 11, bold: true, color: MINT, isTextBox: true, margin: 0 });
  s.addText(["uv sync --all-extras", "uv run python scripts/check.py", "uv run fathom app", "", "# live data, no keys", "export FATHOM_DATA_SOURCE=live", "export FATHOM_SEC_CONTACT=you@firm.com", "uv run fathom fetch NFLX", "uv run fathom brief NFLX", "", "# live model via the gateway", "export FATHOM_LLM_PROVIDER=portkey", "export PORTKEY_API_KEY=…", "uv run fathom probe"].join("\n"), { x: 6.45, y: 1.72, w: 3, h: 3.05, fontFace: "Courier New", fontSize: 8.5, color: WHITE, isTextBox: true, margin: 0, valign: "top" });
}

// ---------- 27 Close
{
  const s = dark("Questions", "Fathom · roshanrana/fathom · release 0.2.0 · design docs, evidence ledger and runbook in the repository");
}

pres.writeFile({ fileName: "C:/Code-Central/fathom/docs/pitch/fathom-architecture-deck.pptx" }).then((f) => console.log("wrote", f, "slides", n));

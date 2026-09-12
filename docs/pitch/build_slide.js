const pptxgen = require("pptxgenjs");
const pres = new pptxgen();
pres.layout = "LAYOUT_16x9"; // 10 x 5.625 in

const NAVY = "14213D";
const INK = "0B1220";
const ICE = "DCE7F5";
const WHITE = "FFFFFF";
const MINT = "2EC4B6";
const GOLD = "F2B134";
const MUTED = "9FB3C8";
const CARD = "1C2B4F";

const slide = pres.addSlide();
slide.background = { color: NAVY };

// Title block
slide.addText("Fathom", {
  x: 0.5, y: 0.35, w: 3.2, h: 0.7, fontFace: "Cambria", fontSize: 40, bold: true,
  color: WHITE, isTextBox: true, margin: 0,
});
slide.addText("Get to the bottom of any stock before the client calls.", {
  x: 0.5, y: 1.0, w: 6.2, h: 0.45, fontFace: "Calibri", fontSize: 17, italic: true,
  color: ICE, isTextBox: true, margin: 0,
});
slide.addText("Prototype for a wealth-management advisory desk · Perficient AI Prototype Challenge, Finance scenario", {
  x: 0.5, y: 1.42, w: 6.4, h: 0.3, fontFace: "Calibri", fontSize: 10.5, color: MUTED,
  isTextBox: true, margin: 0,
});

// Left: problem + how it works (flow of 4 steps)
slide.addText("THE PROBLEM", {
  x: 0.5, y: 1.9, w: 3, h: 0.28, fontFace: "Calibri", fontSize: 11, bold: true,
  color: MINT, charSpacing: 2, isTextBox: true, margin: 0,
});
slide.addText(
  "An advisor gets a call about a name they don't follow. Getting current takes 30–60 minutes of quote lookups and 10-K/10-Q reading — and a generic chatbot can't be quoted to a client.",
  { x: 0.5, y: 2.18, w: 4.55, h: 0.9, fontFace: "Calibri", fontSize: 12.5, color: WHITE,
    isTextBox: true, margin: 0, valign: "top" }
);

slide.addText("HOW FATHOM WORKS", {
  x: 0.5, y: 3.18, w: 3, h: 0.28, fontFace: "Calibri", fontSize: 11, bold: true,
  color: MINT, charSpacing: 2, isTextBox: true, margin: 0,
});

const steps = [
  ["1", "Ticker in", "Quote card: price, range, valuation, 52-week context, as-of stamped"],
  ["2", "Filings in", "Latest 10-K + 10-Qs, parsed into SEC items, linked to EDGAR"],
  ["3", "Briefing", "Claude Sonnet 4.5 via Portkey writes claims — each with a verbatim quote"],
  ["4", "Verified", "Quotes checked against the filing; advice language blocked; call audited"],
];
const sx = 0.5, sy = 3.5, sw = 1.08, sh = 1.45, gap = 0.08;
steps.forEach((s, i) => {
  const x = sx + i * (sw + gap);
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x, y: sy, w: sw, h: sh, fill: { color: CARD }, line: { color: CARD }, rectRadius: 0.08,
  });
  slide.addShape(pres.shapes.OVAL, {
    x: x + 0.1, y: sy + 0.1, w: 0.32, h: 0.32, fill: { color: MINT }, line: { color: MINT },
  });
  slide.addText(s[0], {
    x: x + 0.1, y: sy + 0.1, w: 0.32, h: 0.32, fontFace: "Calibri", fontSize: 12, bold: true,
    color: INK, align: "center", valign: "middle", isTextBox: true, margin: 0,
  });
  slide.addText(s[1], {
    x: x + 0.1, y: sy + 0.47, w: sw - 0.2, h: 0.28, fontFace: "Calibri", fontSize: 11.5, bold: true,
    color: WHITE, isTextBox: true, margin: 0,
  });
  slide.addText(s[2], {
    x: x + 0.1, y: sy + 0.75, w: sw - 0.2, h: 0.66, fontFace: "Calibri", fontSize: 8.5,
    color: ICE, isTextBox: true, margin: 0, valign: "top",
  });
});

// Right: stat callouts (2x2) + "why it matters" + next step
const rx = 5.45, rw = 4.05;
slide.addText("WHAT THE PROTOTYPE PROVES", {
  x: rx, y: 1.9, w: rw, h: 0.28, fontFace: "Calibri", fontSize: 11, bold: true,
  color: MINT, charSpacing: 2, isTextBox: true, margin: 0,
});
const stats = [
  ["100%", "of briefing claims verified\nagainst the filing (offline eval, 20 tickers)"],
  ["0", "advice-language escapes on a\n30-phrase adversarial set"],
  ["97", "recent 10-K / 10-Q filings,\n20 large caps, 2025–2026"],
  ["36 ms", "median briefing build offline;\nlive path ≈ 60–90 s via Portkey"],
];
const cw = 1.95, ch = 0.9, cg = 0.12;
stats.forEach((st, i) => {
  const col = i % 2, row = Math.floor(i / 2);
  const x = rx + col * (cw + cg), y = 2.2 + row * (ch + cg);
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x, y, w: cw, h: ch, fill: { color: CARD }, line: { color: CARD }, rectRadius: 0.08,
  });
  slide.addText(st[0], {
    x: x + 0.12, y: y + 0.08, w: cw - 0.24, h: 0.42, fontFace: "Cambria", fontSize: 26, bold: true,
    color: GOLD, isTextBox: true, margin: 0,
  });
  slide.addText(st[1], {
    x: x + 0.12, y: y + 0.5, w: cw - 0.24, h: 0.44, fontFace: "Calibri", fontSize: 8.5,
    color: ICE, isTextBox: true, margin: 0, valign: "top",
  });
});

slide.addText("WHY A COMPLIANCE TEAM CAN SAY YES", {
  x: rx, y: 4.22, w: rw, h: 0.28, fontFace: "Calibri", fontSize: 11, bold: true,
  color: MINT, charSpacing: 2, isTextBox: true, margin: 0,
});
slide.addText(
  [
    { text: "Every claim cites a verbatim passage the app re-checks; unverified claims are flagged, never hidden.", options: { bullet: true, breakLine: true } },
    { text: "Describes, never recommends: input and output guards, disclaimer everywhere, audit log per call.", options: { bullet: true, breakLine: true } },
    { text: "Runs on your gateway (Portkey → Bedrock); with no key or network an offline mode still works.", options: { bullet: true } },
  ],
  { x: rx, y: 4.5, w: rw, h: 0.95, fontFace: "Calibri", fontSize: 8.6, color: WHITE,
    isTextBox: true, margin: 0, paraSpaceAfter: 2, valign: "top" }
);

// Footer next step
slide.addText(
  "Next 4 weeks to pilot: full EDGAR universe + live quote feed · SSO in front of the API · tamper-evident audit sink · advisor eval set with your compliance team",
  { x: 0.5, y: 5.12, w: 4.55, h: 0.4, fontFace: "Calibri", fontSize: 8.8, color: MUTED,
    isTextBox: true, margin: 0, valign: "top" }
);

slide.addNotes(
  "Fathom pitch: problem (advisor prep time, unquotable chatbots) → how it works (quote, filings, grounded briefing, verification + guard) → what the prototype proves (offline eval numbers from metrics/card.md) → why compliance can accept it → pilot path. Numbers: 97 filings, 20 tickers, verified share 1.0 offline, 0 guard escapes, 36 ms median offline. Live-mode verified share is reported from the audit log during the demo."
);

pres.writeFile({ fileName: "C:/Code-Central/fathom/docs/pitch/fathom-pitch.pptx" }).then((f) => console.log("wrote", f));

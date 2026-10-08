#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");

function resolveExport(value) {
  if (typeof value === "function") return value;
  if (value && typeof value.default === "function") return value.default;
  return null;
}

async function main() {
  const input = fs.readFileSync(0, "utf8");
  const payload = JSON.parse(input || "[]");
  const texts = Array.isArray(payload) ? payload.map(String) : [String(payload || "")];

  const Kuroshiro = resolveExport(require(path.join(__dirname, "kuroshiro.min.js")));
  const Analyzer = resolveExport(require(path.join(__dirname, "kuroshiro-analyzer-kuromoji.min.js")));
  if (!Kuroshiro || !Analyzer) throw new Error("Kuroshiro/Kuromoji vendor exports are unavailable.");

  const dictPath = path.join(__dirname, "kuromoji", "dict");
  const kuroshiro = new Kuroshiro();
  const analyzer = new Analyzer({ dictPath });
  await kuroshiro.init(analyzer);

  const result = [];
  for (const text of texts) {
    // Kuroshiro is the canonical Japanese -> reading converter.
    // "normal" gives the plain Hiragana sentence; "spaced" exposes
    // morphological boundaries; "furigana" preserves the source/reading
    // relationship for the editor/debugger.
    const reading = await kuroshiro.convert(text, { to: "hiragana", mode: "normal" });
    const spaced = await kuroshiro.convert(text, { to: "hiragana", mode: "spaced" });
    const furigana = await kuroshiro.convert(text, { to: "hiragana", mode: "furigana" });
    const raw = await analyzer.parse(text);
    const tokens = raw.map((token) => ({
      surface: token.surface_form || "",
      reading: token.reading || "",
      pronunciation: token.pronunciation || "",
      lemma: token.basic_form || token.surface_form || "",
      pos: token.pos || "",
      pos_detail: [
        token.pos_detail_1 || "",
        token.pos_detail_2 || "",
        token.pos_detail_3 || ""
      ].filter(Boolean).join("/"),
      word_position: Number(token.word_position || 1)
    }));
    result.push({
      text,
      reading: String(reading || ""),
      spaced: String(spaced || ""),
      furigana: String(furigana || ""),
      tokens
    });
  }

  process.stdout.write(JSON.stringify(result));
}

main().catch((error) => {
  process.stderr.write(String(error && error.stack || error));
  process.exit(1);
});

#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");

async function main() {
  const input = fs.readFileSync(0, "utf8");
  const payload = JSON.parse(input || '""');
  const texts = Array.isArray(payload) ? payload : [payload];

  const Analyzer = require(path.join(__dirname, "kuroshiro-analyzer-kuromoji.min.js"));
  const dictPath = path.join(__dirname, "kuromoji", "dict");
  const analyzer = new Analyzer({ dictPath });
  await analyzer.init();

  const result = [];
  for (const value of texts) {
    const raw = await analyzer.parse(String(value || ""));
    result.push(raw.map((token) => ({
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
    })));
  }

  process.stdout.write(JSON.stringify(Array.isArray(payload) ? result : result[0]));
}

main().catch((error) => {
  process.stderr.write(String(error && error.stack || error));
  process.exit(1);
});

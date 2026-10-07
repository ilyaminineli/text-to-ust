#!/usr/bin/env node
"use strict";

/*
 * Hiro UST Kuromoji bridge.
 *
 * Reads one JSON string from stdin and writes a JSON token array to stdout.
 * The tokenizer is the vendored Kuroshiro/Kuromoji build; no npm install is
 * required for the analyzer itself.
 */
const fs = require("fs");
const path = require("path");

async function main() {
  const input = fs.readFileSync(0, "utf8");
  const text = JSON.parse(input || '""');

  const Analyzer = require(path.join(__dirname, "kuroshiro-analyzer-kuromoji.min.js"));
  const dictPath = path.join(__dirname, "kuromoji", "dict");
  const analyzer = new Analyzer({ dictPath });
  await analyzer.init();

  const raw = await analyzer.parse(String(text));
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

  process.stdout.write(JSON.stringify(tokens));
}

main().catch((error) => {
  process.stderr.write(String(error && error.stack || error));
  process.exit(1);
});

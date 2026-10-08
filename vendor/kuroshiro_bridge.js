#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");

function resolveExport(value) {
  if (typeof value === "function") return value;
  if (value && typeof value.default === "function") return value.default;
  return null;
}

const KANJI_RE = /[\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF]/;

function containsKanji(value) {
  return KANJI_RE.test(String(value || ""));
}

function katakanaToHiragana(value) {
  return String(value || "").replace(/[\u30A1-\u30F6]/g, (ch) => {
    return String.fromCharCode(ch.charCodeAt(0) - 0x60);
  });
}

function loadNodeModule(name) {
  try {
    return require(name);
  } catch (error) {
    throw new Error(
      `Missing Node dependency "${name}". Run "npm install" in the repository root.\n` +
      `${error && error.stack ? error.stack : error}`
    );
  }
}

function normalizeTokens(raw) {
  return raw.map((token) => ({
    surface: token.surface_form || "",
    reading: token.reading || "",
    pronunciation: token.pronunciation || "",
    lemma: token.basic_form || token.surface_form || "",
    word_type: token.word_type || "",
    pos: token.pos || "",
    pos_detail: [
      token.pos_detail_1 || "",
      token.pos_detail_2 || "",
      token.pos_detail_3 || "",
    ].filter(Boolean).join("/"),
    conjugated_type: token.conjugated_type || "",
    conjugated_form: token.conjugated_form || "",
    word_position: Number(token.word_position || 1),
  }));
}

async function main() {
  const input = fs.readFileSync(0, "utf8");
  const payload = JSON.parse(input || "[]");
  const texts = Array.isArray(payload)
    ? payload.map(String)
    : [String(payload || "")];

  const KuroshiroModule = loadNodeModule("kuroshiro");
  const AnalyzerModule = loadNodeModule("kuroshiro-analyzer-kuromoji");

  const Kuroshiro = resolveExport(KuroshiroModule);
  const Analyzer = resolveExport(AnalyzerModule);

  if (!Kuroshiro || !Analyzer) {
    throw new Error(
      "Could not resolve CommonJS Kuroshiro/KuroshiroAnalyzer exports."
    );
  }

  const dictPath = path.resolve(__dirname, "kuromoji", "dict");
  if (!fs.existsSync(dictPath)) {
    throw new Error(`Kuromoji dictionary directory not found: ${dictPath}`);
  }

  const dictionaryFiles = fs.readdirSync(dictPath)
    .filter((name) => name.endsWith(".dat.gz"));

  if (dictionaryFiles.length === 0) {
    throw new Error(`Kuromoji dictionary contains no .dat.gz archives: ${dictPath}`);
  }

  const kuroshiro = new Kuroshiro();
  const analyzer = new Analyzer({
    dictPath: `${dictPath}${path.sep}`,
  });

  await kuroshiro.init(analyzer);

  const result = [];

  for (const text of texts) {
    const raw = await analyzer.parse(text);
    const tokens = normalizeTokens(raw);

    const reading = String(
      await kuroshiro.convert(text, {
        to: "hiragana",
        mode: "normal",
      }) || ""
    );

    const spaced = String(
      await kuroshiro.convert(text, {
        to: "hiragana",
        mode: "spaced",
      }) || ""
    );

    const furigana = String(
      await kuroshiro.convert(text, {
        to: "hiragana",
        mode: "furigana",
      }) || ""
    );

    result.push({
      text,
      reading,
      reading_complete: !containsKanji(reading),
      spaced,
      furigana,
      tokens,
    });
  }

  process.stdout.write(JSON.stringify(result));
}

main().catch((error) => {
  process.stderr.write(
    String((error && error.stack) || error) + "\n"
  );
  process.exit(1);
});

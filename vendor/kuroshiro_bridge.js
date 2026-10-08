#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");

function resolveExport(value) {
  if (typeof value === "function") return value;
  if (value && typeof value.default === "function") return value.default;
  return null;
}

function assertNoKanji(label, value) {
  const kanjiPattern = /[\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF]/;
  if (kanjiPattern.test(value)) {
    throw new Error(
      `${label} contains Kanji when kana was required: ${JSON.stringify(value)}`
    );
  }
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

async function main() {
  const input = fs.readFileSync(0, "utf8");
  const payload = JSON.parse(input || "[]");
  const texts = Array.isArray(payload)
    ? payload.map(String)
    : [String(payload || "")];

  // IMPORTANT:
  // Do NOT require the browserified vendor analyzer here.
  //
  // kuroshiro-analyzer-kuromoji.min.js bundles BrowserDictionaryLoader,
  // which uses XMLHttpRequest. This process is Node.js, so it must use the
  // CommonJS analyzer package, whose dependency on kuromoji uses the Node
  // dictionary loader and reads the .dat.gz files from disk.
  const KuroshiroModule = loadNodeModule("kuroshiro");
  const AnalyzerModule = loadNodeModule("kuroshiro-analyzer-kuromoji");

  const Kuroshiro = resolveExport(KuroshiroModule);
  const Analyzer = resolveExport(AnalyzerModule);

  if (!Kuroshiro || !Analyzer) {
    throw new Error(
      "Could not resolve CommonJS Kuroshiro/KuroshiroAnalyzer exports."
    );
  }

  const dictPath = path.resolve(
    __dirname,
    "kuromoji",
    "dict"
  );

  if (!fs.existsSync(dictPath)) {
    throw new Error(`Kuromoji dictionary directory not found: ${dictPath}`);
  }

  const dictionaryFiles = fs
    .readdirSync(dictPath)
    .filter((name) => name.endsWith(".dat.gz"));

  if (dictionaryFiles.length === 0) {
    throw new Error(
      `Kuromoji dictionary contains no .dat.gz archives: ${dictPath}`
    );
  }

  const kuroshiro = new Kuroshiro();

  // This CommonJS analyzer uses kuromoji's NodeDictionaryLoader.
  // The existing vendored .dat.gz archives remain the dictionary source.
  const analyzer = new Analyzer({
    dictPath: `${dictPath}${path.sep}`,
  });

  await kuroshiro.init(analyzer);

  const result = [];

  for (const text of texts) {
    const reading = await kuroshiro.convert(text, {
      to: "hiragana",
      mode: "normal",
    });

    const spaced = await kuroshiro.convert(text, {
      to: "hiragana",
      mode: "spaced",
    });

    const furigana = await kuroshiro.convert(text, {
      to: "hiragana",
      mode: "furigana",
    });

    assertNoKanji("Kuroshiro normal reading", String(reading || ""));

    // Kuromoji analyzer instance exposes parse() after initialization.
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
        token.pos_detail_3 || "",
      ].filter(Boolean).join("/"),
      word_position: Number(token.word_position || 1),
    }));

    result.push({
      text,
      reading: String(reading || ""),
      spaced: String(spaced || ""),
      furigana: String(furigana || ""),
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

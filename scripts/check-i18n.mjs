import fs from "node:fs";
import babel from "prettier/plugins/babel";
const files = [
  "src/App.tsx",
  "src/Portal.tsx",
  "src/components/IncidentResponse.tsx",
  "src/components/CoordinateAssessment.tsx",
  "src/components/Basemap.tsx",
  "src/components/ReferenceMap.tsx",
  "src/components/RequestError.tsx",
];
const catalogs = Object.fromEntries(
  ["en", "hi", "as"].map((lang) => [
    lang,
    JSON.parse(fs.readFileSync(`src/locales/${lang}.json`, "utf8")),
  ]),
);
function walk(node, visit) {
  if (!node || typeof node !== "object") return;
  if (Array.isArray(node)) {
    node.forEach((v) => walk(v, visit));
    return;
  }
  if (node.type) visit(node);
  for (const [k, v] of Object.entries(node))
    if (
      !["loc", "extra", "tokens", "comments"].includes(k) &&
      typeof v === "object"
    )
      walk(v, visit);
}
const keys = new Set(Object.keys(catalogs.en));
let issues = [];
for (const path of files) {
  walk(
    babel.parsers["babel-ts"].parse(fs.readFileSync(path, "utf8")),
    (node) => {
      if (node.type === "JSXText" && /[A-Za-z]/.test(node.value))
        issues.push(
          `${path}: untranslated interface text: ${node.value.trim()}`,
        );
      if (
        node.type === "CallExpression" &&
        ["t"].includes(node.callee.name) &&
        node.arguments[0]?.type === "StringLiteral"
      )
        keys.add(node.arguments[0].value);
      if (
        node.type === "CallExpression" &&
        node.callee.name === "t" &&
        node.arguments[0]?.type === "ConditionalExpression"
      ) {
        for (const value of [
          node.arguments[0].consequent,
          node.arguments[0].alternate,
        ])
          if (value.type === "StringLiteral") keys.add(value.value);
      }
      if (
        node.type === "JSXAttribute" &&
        node.value?.type === "StringLiteral" &&
        ["title", "sub", "label", "placeholder", "aria-label"].includes(
          node.name.name,
        )
      )
        keys.add(node.value.value);
      if (
        node.type === "ObjectProperty" &&
        ["label", "message"].includes(node.key.name) &&
        node.value?.type === "StringLiteral"
      )
        keys.add(node.value.value);
    },
  );
}
for (const key of keys) {
  const expected = [...key.matchAll(/\{(\w+)\}/g)]
    .map((m) => m[1])
    .sort()
    .join(",");
  for (const [lang, catalog] of Object.entries(catalogs)) {
    if (!catalog[key]) issues.push(`${lang}: missing ${JSON.stringify(key)}`);
    else {
      const actual = [...catalog[key].matchAll(/\{(\w+)\}/g)]
        .map((m) => m[1])
        .sort()
        .join(",");
      if (actual !== expected)
        issues.push(
          `${lang}: mismatched placeholders for ${JSON.stringify(key)}`,
        );
    }
  }
}
if (issues.length) {
  console.error(issues.join("\n"));
  process.exitCode = 1;
} else
  console.log(
    `Translation checks passed: ${keys.size} interface keys, 3 languages, no untranslated JSX copy or missing placeholders.`,
  );

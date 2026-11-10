import test from "node:test";
import assert from "node:assert/strict";
import {
  codespacesHost,
  developmentEnvironment,
} from "../scripts/codespaces.mjs";

test("local development environment is preserved", () => {
  const local = {
    APP_ORIGINS: "https://existing.example",
    COOKIE_SECURE: "false",
  };
  assert.equal(codespacesHost(local), undefined);
  assert.deepEqual(developmentEnvironment(local), local);
});
test("Codespaces gets its exact trusted origin and HTTPS cookies", () => {
  const env = { CODESPACE_NAME: "sample-name-123" };
  assert.equal(codespacesHost(env), "sample-name-123-5173.app.github.dev");
  const result = developmentEnvironment(env);
  assert.equal(result.COOKIE_SECURE, "true");
  assert.ok(
    result.APP_ORIGINS.split(",").includes(
      "https://sample-name-123-5173.app.github.dev",
    ),
  );
  assert.ok(result.APP_ORIGINS.split(",").includes("http://localhost:5173"));
});
test("custom origins, forwarding domain and explicit cookie setting are preserved", () => {
  const env = {
    CODESPACE_NAME: "example",
    GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN: "preview.example.com",
    APP_ORIGINS: "https://existing.example",
    COOKIE_SECURE: "false",
  };
  const result = developmentEnvironment(env);
  assert.equal(
    result.APP_ORIGINS,
    "https://existing.example,https://example-5173.preview.example.com",
  );
  assert.equal(result.COOKIE_SECURE, "false");
});
test("invalid forwarded hostname is rejected", () => {
  assert.throws(() => codespacesHost({ CODESPACE_NAME: "bad/name" }));
  assert.throws(() =>
    codespacesHost({
      CODESPACE_NAME: "example",
      GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN: "*.example.com",
    }),
  );
});

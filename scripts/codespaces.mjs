/** Use only this Codespace's exact forwarded hostname, never a wildcard. */
export function codespacesHost(env = process.env) {
  if (!env.CODESPACE_NAME) return undefined;
  const domain =
    env.GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN || "app.github.dev";
  if (
    !/^[a-z0-9-]+$/i.test(env.CODESPACE_NAME) ||
    !/^[a-z0-9.-]+$/i.test(domain)
  ) {
    throw new Error("Invalid Codespaces hostname configuration");
  }
  return `${env.CODESPACE_NAME}-5173.${domain}`;
}

export function developmentEnvironment(env = process.env) {
  const host = codespacesHost(env);
  if (!host) return { ...env };
  const origins = new Set(
    (env.APP_ORIGINS || "http://127.0.0.1:5173,http://localhost:5173")
      .split(",")
      .filter(Boolean),
  );
  origins.add(`https://${host}`);
  return {
    ...env,
    APP_ORIGINS: [...origins].join(","),
    COOKIE_SECURE: env.COOKIE_SECURE ?? "true",
  };
}

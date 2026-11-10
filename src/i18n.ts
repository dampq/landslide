import en from "./locales/en.json";
import hi from "./locales/hi.json";
import as from "./locales/as.json";
export const languages = { en: "English", hi: "हिन्दी", as: "অসমীয়া" };
export type TranslationParams = Record<string, string | number>;
export const catalogs: Record<string, Record<string, string>> = { en, hi, as };
export function translate(
  lang: string,
  key: string,
  params: TranslationParams = {},
) {
  const template =
    (catalogs[lang] || en)[key] || en[key as keyof typeof en] || key;
  return template.replace(/\{(\w+)\}/g, (original, name) =>
    name in params ? String(params[name]) : original,
  );
}
export const locale = (lang: string) =>
  ({ en: "en-IN", hi: "hi-IN", as: "as-IN" })[lang] || "en-IN";

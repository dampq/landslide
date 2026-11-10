import { useApp } from "../App";
import { catalogs } from "../i18n";
/** Keep diagnostics available without presenting untranslated server text as UI. */
export default function RequestError({ message }: { message: string }) {
  const { lang, t } = useApp();
  const known = lang === "en" || !!catalogs[lang]?.[message];
  return (
    <>
      <span>
        {known
          ? t(message)
          : t(
              "The request could not be completed. Check your input and connection, then try again.",
            )}
      </span>
      {!known && (
        <details className="mt-2 text-xs">
          <summary>{t("Technical details (original language)")}</summary>
          <code className="whitespace-pre-wrap break-words">{message}</code>
        </details>
      )}
    </>
  );
}

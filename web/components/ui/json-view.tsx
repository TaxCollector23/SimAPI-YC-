/** Minimal, dependency-free JSON syntax highlighter. */
export function JsonView({ text, className }: { text: string; className?: string }) {
  const html = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(
      /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)/g,
      (m) => {
        let cls = "text-emerald-300";
        if (/^"/.test(m)) cls = /:$/.test(m) ? "text-sky-300" : "text-emerald-300";
        else if (/true|false/.test(m)) cls = "text-accent-violet";
        else if (/null/.test(m)) cls = "text-white/40";
        else cls = "text-amber-200";
        return `<span class="${cls}">${m}</span>`;
      },
    );
  return (
    <pre
      className={`whitespace-pre-wrap font-mono text-[12.5px] leading-relaxed text-white/60 ${className ?? ""}`}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

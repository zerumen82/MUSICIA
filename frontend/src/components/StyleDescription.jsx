import { descriptionSourceUrl } from '../style_description';

const TEXT = {
  available: 'CON DESCRIPCIÓN · VER FICHA',
  catalog: 'Descripción del catálogo de Musicia',
  sources: 'FUENTES',
};

/** The same source-backed text is readable before selecting and after applying. */
export default function StyleDescription({ description, label, collapsible = false }) {
  if (!description?.text) return null;
  const provenance = description.provenance;
  const content = <div className="flex flex-col gap-1 py-1">
    <p className="text-[11px] leading-snug text-[var(--text)] whitespace-normal break-words">{description.text}</p>
    <p className="mono text-[9px] text-[var(--faint)]">{provenance?.label || TEXT.catalog}</p>
    {provenance?.sources?.length > 0 && <details>
      <summary className="label cursor-pointer">{TEXT.sources}</summary>
      <ul className="flex flex-col gap-1 py-1">
        {provenance.sources.map((source, index) => {
          const url = descriptionSourceUrl(source.url);
          return <li key={`${source.url ?? source.title}:${index}`} className="text-[10px] break-words">
            {url ? <a href={url} target="_blank" rel="noopener noreferrer" className="underline text-[var(--acc)]">{source.title || url}</a> : <span>{source.title || source.url}</span>}
          </li>;
        })}
      </ul>
    </details>}
  </div>;
  return collapsible ? <details aria-label={`Descripción de ${label}`} className="px-2 pb-1">
    <summary className="mono text-[8px] cursor-pointer text-[var(--acc)]">{TEXT.available}</summary>
    {content}
  </details> : content;
}

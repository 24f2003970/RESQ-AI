import { ChevronRight, CircleHelp } from "lucide-react";
import type { ReactNode } from "react";

export function Panel({
  title,
  eyebrow,
  children,
  className = "",
  action,
}: {
  title: string;
  eyebrow?: string;
  children: ReactNode;
  className?: string;
  action?: ReactNode;
}) {
  return (
    <section className={`panel ${className}`}>
      <div className="panel-heading">
        <div>
          {eyebrow && <span className="eyebrow">{eyebrow}</span>}
          <h2>{title}</h2>
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}
export function Badge({
  children,
  tone = "",
}: {
  children: ReactNode;
  tone?: string;
}) {
  return <span className={`badge ${tone}`}>{children}</span>;
}
export function Help({ text }: { text: string }) {
  return (
    <span className="help" tabIndex={0} aria-label={text}>
      <CircleHelp size={13} />
      <span role="tooltip">{text}</span>
    </span>
  );
}
export function Row({
  title,
  subtitle,
  value,
  onClick,
}: {
  title: string;
  subtitle?: string;
  value?: ReactNode;
  onClick?: () => void;
}) {
  const content = (
    <>
      <div>
        <strong>{title}</strong>
        {subtitle && <small>{subtitle}</small>}
      </div>
      <span>{value ?? <ChevronRight size={15} />}</span>
    </>
  );
  return onClick ? (
    <button className="data-row" onClick={onClick}>
      {content}
    </button>
  ) : (
    <div className="data-row">{content}</div>
  );
}

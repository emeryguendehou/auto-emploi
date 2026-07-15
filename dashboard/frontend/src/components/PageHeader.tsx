interface Props {
  title: string;
  description?: string;
}

export default function PageHeader({ title, description }: Props) {
  return (
    <header className="page-header">
      <h2 className="page-title">{title}</h2>
      {description && <p className="page-desc">{description}</p>}
    </header>
  );
}

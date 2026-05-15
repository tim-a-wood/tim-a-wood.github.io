interface Props {
  message: string;
  onDismiss: () => void;
}

export function ErrorPanel({ message, onDismiss }: Props) {
  return (
    <div className="error-panel">
      <div style={{ fontWeight: 700, color: 'var(--red)', marginBottom: 6, fontSize: 13 }}>Import failed</div>
      <div style={{ fontSize: 12, color: 'var(--text-1)', marginBottom: 10, lineHeight: 1.5 }}>{message}</div>
      <button className="btn btn-ghost btn-sm" onClick={onDismiss}>Dismiss</button>
    </div>
  );
}

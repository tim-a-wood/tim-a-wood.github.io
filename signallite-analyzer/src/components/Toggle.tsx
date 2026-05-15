interface Props {
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
}

export function Toggle({ checked, onChange, disabled }: Props) {
  return (
    <label className={`toggle-root${disabled ? ' disabled' : ''}`}>
      <input
        type="checkbox"
        checked={checked}
        onChange={e => !disabled && onChange(e.target.checked)}
        style={{ display: 'none' }}
      />
      <div style={{ width: 30, height: 17, borderRadius: 9, background: checked ? 'var(--blue)' : 'var(--border-strong)', position: 'relative', transition: 'background 150ms', flexShrink: 0 }}>
        <div style={{ position: 'absolute', top: 2, left: checked ? 13 : 2, width: 13, height: 13, borderRadius: '50%', background: '#fff', transition: 'left 150ms' }} />
      </div>
    </label>
  );
}

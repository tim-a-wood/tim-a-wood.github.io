import React from 'react';

interface Props {
  value: string;
  onChange: (v: string) => void;
  error?: string;
  placeholder?: string;
  className?: string;
  onEnter?: () => void;
  style?: React.CSSProperties;
}

export function NumberInput({ value, onChange, error, placeholder, className, onEnter, style }: Props) {
  return (
    <div className="number-input-wrapper">
      <input
        className={`focus-input${className ? ' ' + className : ''}`}
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        style={style}
        onKeyDown={e => { if (e.key === 'Enter' && onEnter) onEnter(); }}
      />
      {error && <div className="focus-error">{error}</div>}
    </div>
  );
}

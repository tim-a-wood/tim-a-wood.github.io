import React from 'react';

interface Props {
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
  disabled?: boolean;
  style?: React.CSSProperties;
}

export function Select({ value, onChange, options, disabled, style }: Props) {
  return (
    <select
      className="select-ctrl"
      value={value}
      onChange={e => onChange(e.target.value)}
      disabled={disabled}
      style={style}
    >
      {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
}

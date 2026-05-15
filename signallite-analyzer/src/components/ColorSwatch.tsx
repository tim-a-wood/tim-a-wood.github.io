interface Props {
  color: string;
  onChange: (c: string) => void;
}

export function ColorSwatch({ color, onChange }: Props) {
  return (
    <input
      type="color"
      value={color}
      onChange={e => onChange(e.target.value)}
      className="color-swatch"
      title="Choose color"
      style={{ background: color }}
    />
  );
}

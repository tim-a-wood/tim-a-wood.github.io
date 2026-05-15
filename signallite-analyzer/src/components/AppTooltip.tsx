import React, { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';

interface Props {
  children: React.ReactNode;
  content: string;
}

export function AppTooltip({ children, content }: Props) {
  const [visible, setVisible] = useState(false);
  const [pos, setPos] = useState({ x: 0, y: 0 });
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const show = (e: React.MouseEvent) => {
    const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
    timer.current = setTimeout(() => {
      setPos({ x: r.left, y: r.bottom + 6 });
      setVisible(true);
    }, 400);
  };

  const hide = () => {
    clearTimeout(timer.current);
    setVisible(false);
  };

  useEffect(() => {
    const onEsc = (e: KeyboardEvent) => { if (e.key === 'Escape') setVisible(false); };
    window.addEventListener('keydown', onEsc);
    return () => window.removeEventListener('keydown', onEsc);
  }, []);

  if (!content) return <>{children}</>;

  return (
    <span onMouseEnter={show} onMouseLeave={hide} style={{ display: 'contents' }}>
      {children}
      {visible && createPortal(
        <div className="app-tooltip" style={{ left: pos.x, top: pos.y }}>{content}</div>,
        document.body
      )}
    </span>
  );
}

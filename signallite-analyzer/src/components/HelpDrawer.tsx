import React, { useState, useEffect, useRef } from 'react';
import { X, ChevronDown, ChevronRight } from 'lucide-react';
import { helpSections } from '../config/helpContent';

interface Props {
  onClose: () => void;
}

export function HelpDrawer({ onClose }: Props) {
  const [openSections, setOpenSections] = useState<Set<number>>(new Set([0]));
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => { closeRef.current?.focus(); }, []);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  const toggle = (i: number) => setOpenSections(prev => {
    const n = new Set(prev);
    n.has(i) ? n.delete(i) : n.add(i);
    return n;
  });

  return (
    <>
      <div className="drawer-backdrop" onClick={onClose} />
      <div className="drawer" role="dialog" aria-modal="true" aria-label="SignalLite Help">
        <div className="drawer-header">
          <span className="drawer-title">SignalLite Help</span>
          <button ref={closeRef} className="btn btn-icon" onClick={onClose} aria-label="Close help">
            <X size={15} />
          </button>
        </div>
        <div className="drawer-body">
          {helpSections.map((sec, i) => (
            <div key={i} className="help-section">
              <button className="help-section-btn" onClick={() => toggle(i)} aria-expanded={openSections.has(i)}>
                {sec.title}
                {openSections.has(i) ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
              </button>
              {openSections.has(i) && <div className="help-section-body">{sec.body}</div>}
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

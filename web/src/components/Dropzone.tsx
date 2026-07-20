import { useCallback, useRef, useState } from "react";

interface Props {
  onFile: (file: File) => void;
  onDemo: () => void;
  busy: boolean;
  /** Collapse to a slim bar once a result is on screen. */
  compact: boolean;
}

const ACCEPTED = /^image\//;

/**
 * Upload / paste dropzone. Accepts a dropped or picked screenshot, or a pasted image
 * (Cmd+V from a fresh Arena screenshot). Shrinks to a slim bar once a result is shown.
 */
export function Dropzone({ onFile, onDemo, busy, compact }: Props) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const take = useCallback(
    (file: File | undefined | null) => {
      if (file && ACCEPTED.test(file.type)) onFile(file);
    },
    [onFile],
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      take(e.dataTransfer.files?.[0]);
    },
    [take],
  );

  const onPaste = useCallback(
    (e: React.ClipboardEvent) => {
      const item = Array.from(e.clipboardData.items).find((i) => ACCEPTED.test(i.type));
      if (item) take(item.getAsFile());
    },
    [take],
  );

  return (
    <div
      className={`dropzone${dragging ? " dragging" : ""}${compact ? " compact" : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      onPaste={onPaste}
      tabIndex={0}
    >
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        hidden
        onChange={(e) => take(e.target.files?.[0])}
      />
      <div className="dropzone-body">
        <div className="dropzone-copy">
          <strong>Drop, paste, or choose an Arena draft screenshot</strong>
          <span className="muted">A single shot showing your pool + the current pack.</span>
        </div>
        <div className="dropzone-actions">
          <button className="btn" onClick={() => inputRef.current?.click()} disabled={busy}>
            Choose file
          </button>
          <button className="btn ghost" onClick={onDemo} disabled={busy}>
            Try the demo draft
          </button>
        </div>
      </div>
      {busy && <div className="dropzone-progress" aria-label="Working" />}
    </div>
  );
}

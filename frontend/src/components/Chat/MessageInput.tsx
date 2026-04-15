import { Send, Square } from "lucide-react";
import { useEffect, useRef, useState } from "react";

interface Props {
  isStreaming: boolean;
  onSend: (text: string) => void;
  onAbort?: () => void;
  disabled?: boolean;
  placeholder?: string;
}

export default function MessageInput({
  isStreaming,
  onSend,
  onAbort,
  disabled = false,
  placeholder = "Workflow tarif edin… (Enter = gönder, Shift+Enter = yeni satır)",
}: Props) {
  const [text, setText] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  // Auto-resize the textarea up to a max height
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 140)}px`;
  }, [text]);

  const submit = () => {
    const trimmed = text.trim();
    if (!trimmed || isStreaming || disabled) return;
    onSend(trimmed);
    setText("");
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className="border-t border-neutral-200 bg-white p-2">
      <div className="flex items-end gap-2 border border-neutral-300 bg-white p-1.5 focus-within:border-accent">
        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
          placeholder={placeholder}
          disabled={disabled}
          className="min-h-[24px] flex-1 resize-none bg-transparent px-1 py-1 text-[12.5px] leading-relaxed outline-none placeholder:text-neutral-400 disabled:opacity-50"
        />
        {isStreaming ? (
          <button
            onClick={onAbort}
            className="flex h-7 w-7 shrink-0 items-center justify-center border border-neutral-300 bg-white text-neutral-700 hover:bg-neutral-50"
            title="Durdur"
          >
            <Square className="h-3 w-3" strokeWidth={2} />
          </button>
        ) : (
          <button
            onClick={submit}
            disabled={disabled || !text.trim()}
            className="flex h-7 w-7 shrink-0 items-center justify-center border border-accent bg-accent text-white hover:bg-accent-hover disabled:opacity-40"
            title="Gönder"
          >
            <Send className="h-3 w-3" strokeWidth={2} />
          </button>
        )}
      </div>
    </div>
  );
}

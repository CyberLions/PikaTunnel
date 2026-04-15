interface Props {
  status: "enabled" | "disabled" | "connected" | "connecting" | "disconnected" | "error" | "running" | "stopped";
}

const colors: Record<string, string> = {
  enabled: "bg-emerald-500/15 text-emerald-400 border-emerald-500/25",
  connected: "bg-emerald-500/15 text-emerald-400 border-emerald-500/25",
  running: "bg-emerald-500/15 text-emerald-400 border-emerald-500/25",
  disabled: "bg-stone-500/15 text-stone-400 border-stone-500/25",
  disconnected: "bg-stone-500/15 text-stone-400 border-stone-500/25",
  stopped: "bg-red-500/15 text-red-400 border-red-500/25",
  connecting: "bg-orange-500/15 text-orange-400 border-orange-500/25",
  error: "bg-red-500/15 text-red-400 border-red-500/25",
};

export default function StatusBadge({ status }: Props) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold capitalize ${colors[status] || colors.disabled}`}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${
          status === "connecting"
            ? "animate-pulse bg-orange-400"
            : status === "enabled" || status === "connected" || status === "running"
              ? "bg-emerald-400"
              : status === "error" || status === "stopped"
                ? "bg-red-400"
                : "bg-stone-400"
        }`}
      />
      {status}
    </span>
  );
}

interface Props {
  status: "enabled" | "disabled" | "connected" | "connecting" | "disconnected" | "error" | "running" | "stopped";
}

const colors: Record<string, string> = {
  enabled: "bg-green-500/20 text-green-400 border-green-500/30",
  connected: "bg-green-500/20 text-green-400 border-green-500/30",
  running: "bg-green-500/20 text-green-400 border-green-500/30",
  disabled: "bg-slate-500/20 text-slate-400 border-slate-500/30",
  disconnected: "bg-slate-500/20 text-slate-400 border-slate-500/30",
  stopped: "bg-red-500/20 text-red-400 border-red-500/30",
  connecting: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  error: "bg-red-500/20 text-red-400 border-red-500/30",
};

export default function StatusBadge({ status }: Props) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${colors[status] || colors.disabled}`}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${
          status === "connecting"
            ? "animate-pulse bg-yellow-400"
            : status === "enabled" || status === "connected" || status === "running"
              ? "bg-green-400"
              : status === "error" || status === "stopped"
                ? "bg-red-400"
                : "bg-slate-400"
        }`}
      />
      {status}
    </span>
  );
}

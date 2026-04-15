import { useEffect } from "react";

interface Props {
  message: string;
  type?: "info" | "success" | "error";
  onClose: () => void;
}

const styles = {
  info: "border-orange-500/30 bg-orange-500/10 text-orange-300",
  success: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
  error: "border-red-500/30 bg-red-500/10 text-red-300",
};

export default function Toast({ message, type = "info", onClose }: Props) {
  useEffect(() => {
    const timer = setTimeout(onClose, 4000);
    return () => clearTimeout(timer);
  }, [onClose]);

  return (
    <div className="fixed bottom-6 right-6 z-[70] animate-[slideUp_0.3s_ease-out]">
      <div className={`rounded-xl border px-4 py-3 text-sm font-medium shadow-lg backdrop-blur-sm ${styles[type]}`}>
        {message}
      </div>
      <style>{`
        @keyframes slideUp {
          from { opacity: 0; transform: translateY(10px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}

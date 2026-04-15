interface Props {
  title: string;
  description: string;
  action?: {
    label: string;
    onClick: () => void;
  };
}

export default function EmptyState({ title, description, action }: Props) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-stone-700/30 py-16 bg-neutral-900/30">
      <img src="/logo.png" alt="" className="mb-4 h-16 w-16 rounded-2xl opacity-30 grayscale" />
      <h3 className="text-lg font-semibold text-stone-300">{title}</h3>
      <p className="mt-1 text-sm text-stone-500">{description}</p>
      {action && (
        <button onClick={action.onClick} className="btn-primary mt-5">
          {action.label}
        </button>
      )}
    </div>
  );
}

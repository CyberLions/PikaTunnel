import type { ReactNode } from "react";

interface Column<T> {
  key: string;
  header: string;
  render: (item: T) => ReactNode;
}

interface Props<T> {
  columns: Column<T>[];
  data: T[];
  keyField: keyof T;
}

export default function DataTable<T>({ columns, data, keyField }: Props<T>) {
  return (
    <div className="overflow-x-auto rounded-2xl border border-stone-800/20 bg-neutral-900/50">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-stone-800/20">
          <tr>
            {columns.map((col) => (
              <th key={col.key} className="px-4 py-3.5 text-xs font-semibold uppercase tracking-wider text-stone-500">
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-stone-800/10">
          {data.map((item) => (
            <tr key={String(item[keyField])} className="transition-colors hover:bg-orange-500/[0.03]">
              {columns.map((col) => (
                <td key={col.key} className="px-4 py-3.5 text-stone-300">
                  {col.render(item)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

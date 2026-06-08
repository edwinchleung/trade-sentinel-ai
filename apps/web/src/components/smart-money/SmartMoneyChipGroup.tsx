"use client";

type Chip = { id: string; label: string };

type Props = {
  chips: Chip[];
  activeId: string;
  onSelect: (id: string) => void;
};

export function SmartMoneyChipGroup({ chips, activeId, onSelect }: Props) {
  return (
    <div className="flex flex-wrap gap-2">
      {chips.map((c) => (
        <button
          key={c.id}
          type="button"
          onClick={() => onSelect(c.id)}
          className={`rounded-full border px-3 py-1 text-xs transition-colors ${
            activeId === c.id
              ? "border-emerald-700 bg-emerald-950/40 text-emerald-300"
              : "border-zinc-700 text-zinc-400 hover:border-zinc-500"
          }`}
        >
          {c.label}
        </button>
      ))}
    </div>
  );
}

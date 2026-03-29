export default function LoadingSkeleton({ variant = 'card', count = 1 }) {
  const shimmer = 'skeleton rounded';

  const Card = () => (
    <div className="rounded-xl bg-[#111827] border border-[#1f2937] p-4 h-20 flex flex-col justify-between">
      <div className={`${shimmer} h-3 w-20 rounded-md`} />
      <div className={`${shimmer} h-5 w-32 rounded-md`} />
      <div className={`${shimmer} h-2.5 w-24 rounded-md`} />
    </div>
  );

  const Chart = () => (
    <div className="rounded-xl bg-[#111827] border border-[#1f2937] p-5 h-[300px] flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div className={`${shimmer} h-3 w-28 rounded-md`} />
        <div className="flex gap-2">
          <div className={`${shimmer} h-6 w-12 rounded-md`} />
          <div className={`${shimmer} h-6 w-12 rounded-md`} />
          <div className={`${shimmer} h-6 w-12 rounded-md`} />
        </div>
      </div>
      <div className="flex-1 flex items-end gap-1.5">
        {Array.from({ length: 24 }).map((_, i) => (
          <div
            key={i}
            className={`${shimmer} flex-1 rounded-sm`}
            style={{ height: `${15 + Math.sin(i * 0.5) * 30 + 40}%` }}
          />
        ))}
      </div>
    </div>
  );

  const Table = () => (
    <div className="rounded-xl bg-[#111827] border border-[#1f2937] p-5 space-y-3">
      {/* Header row */}
      <div className="flex gap-4 pb-3 border-b border-[#1f2937]">
        <div className={`${shimmer} h-3 w-24 rounded-md`} />
        <div className={`${shimmer} h-3 w-16 rounded-md`} />
        <div className={`${shimmer} h-3 w-20 rounded-md`} />
        <div className={`${shimmer} h-3 w-14 rounded-md`} />
        <div className={`${shimmer} h-3 w-18 rounded-md`} />
      </div>
      {/* Data rows */}
      {Array.from({ length: 5 }).map((_, row) => (
        <div key={row} className="flex gap-4 py-2">
          <div className={`${shimmer} h-4 rounded-md`} style={{ width: `${100 + row * 8}px` }} />
          <div className={`${shimmer} h-4 w-16 rounded-md`} />
          <div className={`${shimmer} h-4 rounded-md`} style={{ width: `${80 - row * 6}px` }} />
          <div className={`${shimmer} h-4 w-14 rounded-md`} />
          <div className={`${shimmer} h-4 rounded-md`} style={{ width: `${72 + row * 4}px` }} />
        </div>
      ))}
    </div>
  );

  const Gauge = () => (
    <div className="flex flex-col items-center gap-2.5">
      <div
        className={`${shimmer} w-36 h-[72px] rounded-t-full`}
        style={{ borderBottomLeftRadius: 0, borderBottomRightRadius: 0 }}
      />
      <div className={`${shimmer} h-5 w-12 rounded-md`} />
      <div className={`${shimmer} h-4 w-20 rounded-full`} />
    </div>
  );

  const Hero = () => (
    <div className="rounded-xl bg-[#111827] border border-[#1f2937] p-6 space-y-5">
      {/* Top row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={`${shimmer} h-5 w-24 rounded-md`} />
          <div className={`${shimmer} h-4 w-40 rounded-md`} />
        </div>
        <div className={`${shimmer} h-5 w-20 rounded-full`} />
      </div>
      {/* Price area */}
      <div className="flex items-baseline gap-3">
        <div className={`${shimmer} h-10 w-40 rounded-md`} />
        <div className={`${shimmer} h-5 w-24 rounded-md`} />
      </div>
      {/* Stat blocks */}
      <div className="grid grid-cols-4 gap-4 pt-3 border-t border-[#1f2937]">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="space-y-2">
            <div className={`${shimmer} h-2.5 w-14 rounded-md`} />
            <div className={`${shimmer} h-5 w-20 rounded-md`} />
          </div>
        ))}
      </div>
    </div>
  );

  const variants = { card: Card, chart: Chart, table: Table, gauge: Gauge, hero: Hero };
  const Component = variants[variant] || Card;

  return (
    <>
      {Array.from({ length: count }).map((_, i) => (
        <Component key={i} />
      ))}
    </>
  );
}

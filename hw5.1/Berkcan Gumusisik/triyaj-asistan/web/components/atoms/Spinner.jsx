// Atom: yükleniyor göstergesi (üç zıplayan nokta).
export default function Spinner() {
  return (
    <span className="inline-flex items-center gap-1" aria-label="yazıyor">
      {[0, 150, 300].map((gecikme) => (
        <span
          key={gecikme}
          className="h-2 w-2 animate-bounce rounded-full bg-slate-400"
          style={{ animationDelay: `${gecikme}ms` }}
        />
      ))}
    </span>
  );
}

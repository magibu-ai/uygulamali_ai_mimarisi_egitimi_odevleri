// Atom: yeniden kullanılabilir buton.
export default function Button({
  children,
  onClick,
  type = "button",
  variant = "primary",
  disabled = false,
  className = "",
}) {
  const stiller = {
    primary:
      "bg-brand-600 text-white hover:bg-brand-700 disabled:bg-slate-300",
    ghost:
      "bg-white text-brand-700 border border-brand-100 hover:bg-brand-50 disabled:opacity-50",
    danger: "bg-acil text-white hover:brightness-95 disabled:opacity-50",
  };
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`rounded-xl px-4 py-2 text-sm font-semibold transition disabled:cursor-not-allowed ${stiller[variant]} ${className}`}
    >
      {children}
    </button>
  );
}

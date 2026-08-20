import Logo from "@/components/atoms/Logo";
import Button from "@/components/atoms/Button";

// Organizma: üst bar — logo + "Yeni sohbet" düğmesi.
export default function Header({ onReset }) {
  return (
    <header className="flex items-center justify-between border-b border-slate-200 bg-white/80 px-5 py-3 backdrop-blur">
      <Logo />
      <Button variant="ghost" onClick={onReset}>
        Yeni sohbet
      </Button>
    </header>
  );
}

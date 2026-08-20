import "./globals.css";

export const metadata = {
  title: "Triyaj Asistanı",
  description: "Türkçe yerel LLM tabanlı sağlık triyaj (yönlendirme) asistanı",
};

export default function RootLayout({ children }) {
  return (
    <html lang="tr">
      <body>{children}</body>
    </html>
  );
}

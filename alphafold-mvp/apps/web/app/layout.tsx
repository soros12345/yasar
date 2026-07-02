export const metadata = {
  title: "AlphaFold MVP"
};

export default function RootLayout({ children }: any) {
  return (
    <html lang="tr">
      <body>{children}</body>
    </html>
  );
}

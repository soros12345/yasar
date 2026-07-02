const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function HomePage() {
  return (
    <main style={{ fontFamily: "Arial, sans-serif", padding: 32, maxWidth: 980, margin: "0 auto" }}>
      <section style={{ marginBottom: 32 }}>
        <p style={{ color: "#555" }}>AlphaFold Protein 3D Viewer</p>
        <h1 style={{ fontSize: 42, margin: "8px 0" }}>Protein yapilarini ara, incele ve 3D goruntule</h1>
        <p style={{ fontSize: 18, lineHeight: 1.6 }}>
          Bu MVP ekrani AlphaFold DB, UniProt ve PDB baglantilari icin hazirlanan ilk arayuz taslagidir.
          Faz 2 ile gercek veri kaynagi ve 3D viewer baglantisi eklenecek.
        </p>
      </section>

      <section style={{ border: "1px solid #ddd", borderRadius: 16, padding: 24, marginBottom: 24 }}>
        <h2>Protein arama</h2>
        <input
          placeholder="Ornek: insulin, spike protein, P12345"
          style={{ width: "100%", padding: 14, borderRadius: 10, border: "1px solid #ccc", fontSize: 16 }}
        />
        <p style={{ color: "#666" }}>API hedefi: {API_BASE_URL}</p>
      </section>

      <section style={{ border: "1px dashed #aaa", borderRadius: 16, padding: 24, minHeight: 260 }}>
        <h2>3D Viewer alani</h2>
        <p>Molstar veya NGL Viewer burada yapi dosyasini gosterecek.</p>
      </section>
    </main>
  );
}

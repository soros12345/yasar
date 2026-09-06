# PolyArb Bot

Gerçek halka açık Polymarket BTC/Bitcoin market verisini okuyup **paper-trading** yapan Up/Down envanter eşleştirme uygulaması.

## Ne yapıyor?

- Gamma API üzerinden aktif Bitcoin/BTC marketlerini bulur.
- CLOB order book üzerinden token bazlı ask/bid verisini çeker.
- UP ve DOWN paper fill kayıtlarını lot bazında saklar.
- FIFO ile `matched = min(Qup, Qdown)` mantığını uygular.
- Çift ekonomisini gerçek fill fiyatı + fee varsayımı üzerinden hesaplar.
- Eşleşmemiş yönlü envanteri ayrı gösterir; bunu arbitraj diye etiketlemez.
- `max pair cost`, `max unmatched inventory`, fee varsayımı, pause ve kill switch içerir.
- Sahte trade history veya sahte kâr üretmez.

## Çalıştırma

```bash
npm install
npm run dev
```

Test:

```bash
npm test
```

Production build:

```bash
npm run build
npm run preview
```

## Güvenlik

Bu branch **yalnızca paper trading** yapar. Canlı emir gönderme, private key, API secret veya para transferi kodu içermez. Canlı işlem modu eklenirse secret'lar client tarafında tutulmamalı; ayrı server-side execution servisi, açık kullanıcı onayı, risk limitleri ve kill switch zorunlu olmalıdır.

## Veri erişimi

Uygulama public Polymarket endpoint'lerine istemciden bağlanır. Tarayıcı/network ortamı CORS veya ağ erişimini engellerse arayüz bunu hata olarak gösterir; veri uydurmaz.

---
status: "needs_approval"
source_name: "CNN Indonesia"
source_url: "https://www.cnnindonesia.com/ekonomi/20261106134338-78-1424115/survei-bi-harga-rumah-naik-tipis-penjualan-anjlok-843-persen"
published: "2026-11-06T08:29:02+00:00"
variants_passing: 2
variants_attempted: 3
variants_passing_ids: "B, C"
---

# Survei BI: Harga Rumah Naik Tipis, Penjualan Anjlok 8,43 Persen

> Draft for human approval. Nothing here is published automatically.

## Caption variants

### Variant B

*Passed validation and the claim check on attempt 3 after 2 retry(ies).*

```
Pernah merasa cicilan rumah itu sulit dicapai? Kamu tidak sendiri.

Menurut CNN Indonesia, harga rumah di pasar primer naik tipis 0,58 persen per tahun pada kuartal III 2026. Tapi, penjualan hunian justru turun 8,43 persen.

Suku bunga KPR tercatat relatif stabil di level 7,47 persen, dan mayoritas pembelian rumah dilakukan lewat KPR.

Coba lihat-lihat di Rumah123 untuk tahu pilihanmu.

Bagaimana menurut kamu kondisi pasar rumah saat ini?

#Rumah123 #HargaRumah
```

**Image text suggestion:** Harga properti naik 0,58 persen kuartal III 2026

### Variant C

*Passed validation and the claim check on attempt 3 after 2 retry(ies).*

```
Kadang kamu merasa kemauan punya rumah nggak seiring sama keadaan ya?

Menurut CNN Indonesia, harga rumah di pasar primer naik tipis 0,58 persen pada kuartal III 2026 dibanding tahun lalu.

Penjualan hunian turun 8,43 persen pada kuartal III 2026 dibanding tahun sebelumnya.

Mayoritas pembeli masih pakai KPR dengan pangsa 70,68 persen.

Kamu bisa santai jelajahi pilihan di Rumah123 tanpa tekanan.

Menurut kamu, apa yang bikin proses beli rumah terasa berat?

#Rumah123 #HargaRumah
```

**Image text suggestion:** Harga Rumah Naik Tipis Penjualan Turun

## Verified facts

1. **Harga properti residensial di pasar primer tumbuh 0,58 persen pada kuartal III 2026 secara tahunan.**
   - supporting quote: "Bank Indonesia (BI) mencatat harga properti residensial alias rumah di pasar primer tumbuh 0,58 persen pada kuartal III 2026 secara tahunan (yoy)."

2. **Penjualan hunian turun 8,43 persen pada kuartal III 2026 dibandingkan tahun sebelumnya.**
   - supporting quote: "penjualan hunian justru anjlok 8,43 persen pada kuartal III 2026 dibandingkan periode yang sama tahun lalu."

3. **Suku bunga Kredit Pemilikan Rumah (KPR) stabil di level 7,47 persen pada kuartal III 2026.**
   - supporting quote: "suku bunga KPR tercatat relatif stabil di level 7,47 persen pada kuartal III 2026."

4. **Mayoritas pembelian rumah di pasar primer dilakukan melalui skema KPR dengan pangsa 70,68 persen.**
   - supporting quote: "mayoritas pembelian rumah di pasar primer dilakukan melalui skema KPR dengan pangsa 70,68 persen."

5. **Penjualan rumah tipe besar merosot 10,78 persen secara tahunan pada kuartal III 2026.**
   - supporting quote: "Penjualan rumah tipe besar merosot 10,78 persen."

6. **Nilai KPR secara tahunan tumbuh 4,80 persen pada kuartal III 2026.**
   - supporting quote: "nilai KPR secara tahunan justru tumbuh 4,80 persen pada kuartal III 2026"

## Validation results

- **Variant A: FAILED** (3 attempt(s))
  - attempt 1: 1 failure(s)
    - [dropped_hedge] Sentence "Meski begitu, suku bunga KPR tetap stabil di 7,47 persen." states ['7,47'] as fact, but the verified fact hedges it with "relatif". Keep the hedge, for example with "ditargetkan", "direncanakan" or "sekitar".
  - attempt 2: 1 failure(s)
    - [mislabelled_claim] Sentence "Pernah merasa harga rumah terus naik sementara kamu masih menabung?" was labelled non-factual but it asserts change ['naik']. It is a factual claim and must be supported by the verified facts, or removed.
  - attempt 3: 2 failure(s)
    - [mislabelled_claim] Sentence "Kadang kamu lihat harga rumah naik pelan-pelan, tapi masih merasa jauh dari siap." was labelled non-factual but it asserts change ['naik']. It is a factual claim and must be supported by the verified facts, or removed.
    - [unverifiable_claim] Claim "Penjualan rumah turun 8,43 persen, sementara suku bunga KPR relatif stabil di 7,47 persen." was marked supported but its supporting quote is not found in the verified facts. Treat it as unsupported and remove it.
- **Variant B: passed** (3 attempt(s))
  - attempt 1: 1 failure(s)
    - [dropped_hedge] Sentence "Suku bunga KPR stabil di 7,47 persen, dan 70,68 persen pembelian rumah menggunakan KPR." states ['7,47'] as fact, but the verified fact hedges it with "relatif". Keep the hedge, for example with "ditargetkan", "direncanakan" or "sekitar".
  - attempt 2: 1 failure(s)
    - [unsupported_figure] Claim "Suku bunga KPR tercatat relatif stabil di sekitar 7,47 persen, dan 70,68 persen pembelian rumah menggunakan KPR." cites figures ['70,68'] that do not appear in its own supporting quote. Use only figures the quote states.
  - attempt 3: passed
- **Variant C: passed** (3 attempt(s))
  - attempt 1: 2 failure(s)
    - [dropped_hedge] Sentence "Mayoritas pembeli masih pakai KPR, bunganya stabil di 7,47 persen, dan nilai KPR tumbuh 4,80 persen." states ['7,47'] as fact, but the verified fact hedges it with "relatif". Keep the hedge, for example with "ditargetkan", "direncanakan" or "sekitar".
    - [block_too_long] block 2 has 49 words. Keep every block to 45 words or fewer by splitting it with a blank line.
  - attempt 2: 2 failure(s)
    - [unverifiable_claim] Claim "Penjualan rumah turun 8,43 persen, termasuk untuk rumah tipe besar yang turun 10,78 persen." was marked supported but its supporting quote is not found in the verified facts. Treat it as unsupported and remove it.
    - [unverifiable_claim] Claim "Bunganya relatif stabil di sekitar 7,47 persen, dan nilai KPR tumbuh 4,80 persen." was marked supported but its supporting quote is not found in the verified facts. Treat it as unsupported and remove it.
  - attempt 3: passed

## Source

- CNN Indonesia: https://www.cnnindonesia.com/ekonomi/20261106134338-78-1424115/survei-bi-harga-rumah-naik-tipis-penjualan-anjlok-843-persen

---

*Generated by rumah123-ig-weekly-generator. Status: needs_approval. No auto-posting.*

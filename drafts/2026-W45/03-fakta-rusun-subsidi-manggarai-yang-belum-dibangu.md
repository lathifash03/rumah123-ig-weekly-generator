---
status: "needs_approval"
source_name: "detikProperti"
source_url: "https://www.detik.com/properti/berita/d-8738846/fakta-rusun-subsidi-manggarai-yang-belum-dibangun-tapi-sudah-diburu-1-500-orang"
published: "2026-11-05T00:02:48+00:00"
variants_passing: 3
variants_attempted: 3
variants_passing_ids: "A, B, C"
---

# Fakta Rusun Subsidi Manggarai yang Belum Dibangun tapi Sudah Diburu 1.500 Orang

> Draft for human approval. Nothing here is published automatically.

## Caption variants

### Variant A

*Passed validation and the claim check on attempt 2 after 1 retry(ies).*

```
Kamu pernah merasa harga rumah bergerak jauh saat kamu masih menabung?

Rusun Manggarai direncanakan mulai dibangun Januari 2027 dan selesai Agustus 2028, lapor detikProperti. Unit terkecilnya 21 meter persegi dijual mulai Rp 294 juta, terbesar 45 meter persegi seharga Rp 630 juta.

Sekitar 57 persen peminatnya adalah usia 25-35 tahun seperti kamu. Kamu bisa santai lihat-lihat dulu di Rumah123.

Menurut kamu, apa yang penting saat memilih rumah pertama?

#Rumah123 #Rusun
```

**Image text suggestion:** Pembangunan Rusun Manggarai Mulai 2027

### Variant B

*Passed validation and the claim check on attempt 2 after 1 retry(ies).*

```
Pernah kamu hitung-hitung pengeluaran bulanan dan bertanya-tanya kapan bisa punya rumah sendiri?

Rusun Manggarai direncanakan mulai dibangun Januari 2027 dan selesai Agustus 2028, lapor detikProperti. Unit terkecil 21 meter persegi dijual mulai dari Rp 294 juta.

Area bangunnya luas, 6.925 meter persegi. Sekitar 57 persen peminatnya ditargetkan berusia 25-35 tahun dan belum menikah.

Cek rumahnya di Rumah123 saat kamu siap melangkah.

Menurut kamu, apa yang kamu pertimbangkan saat memilih rumah pertama?

#Rumah123 #Rusun
```

**Image text suggestion:** Rusun Manggarai mulai 294 juta

### Variant C

*Passed validation and the claim check on attempt 3 after 2 retry(ies).*

```
Kalau kamu merasa membeli rumah masih jauh, itu wajar.

Pembangunan rumah susun Manggarai direncanakan mulai Januari 2027 dengan estimasi selesai Agustus 2028. Harga unit tipe terkecil 21 meter persegi mulai dari Rp 294 juta.

Menurut detikProperti, sekitar 57 persen peminat rumah susun ini berusia 25-35 tahun dan belum menikah.

Coba lihat-lihat saja dulu di Rumah123. Siapa tahu kamu menemukan sesuatu yang cocok.

Gimana, kamu tertarik dengan rumah susun seperti ini?

#Rumah123 #RumahSubsidi
```

**Image text suggestion:** Rumah susun Manggarai mulai dibangun 2027

## Verified facts

1. **Rumah susun Manggarai akan mulai dibangun Januari 2027 dan selesai Agustus 2028.**
   - supporting quote: "Sesuai rencana, proses pemilihan kontraktor dijadwalkan pada Desember 2026, sedangkan pembangunan fisik ditargetkan mulai Januari 2027 dengan estimasi penyelesaian pada Agustus 2028"

2. **Lahan Blok G untuk pembangunan rusun Manggarai seluas 6.925 meter persegi.**
   - supporting quote: "Untuk lahan Blok G seluas 6.925 meter persegi, proses pembersihan lahan telah selesai dan saat ini telah siap untuk tahapan pembangunan berikutnya"

3. **Unit tipe 21 meter persegi dijual mulai Rp 294 juta dan tipe 45 meter persegi Rp 630 juta per unit.**
   - supporting quote: "Tipe terkecil 21 meter persegi dijual mulai dari Rp 294 juta per unit dan unit terbesar 45 meter persegi Rp 630 juta per unit"

4. **Ada 1.500 peminat rusun Manggarai, 57 persen berusia 25-35 tahun dan belum menikah.**
   - supporting quote: "Berdasarkan data peminatan yang dikumpulkan KAI Properti, rentang usia peminatnya 25-35 tahun dan sekitar 57 persen di antaranya belum menikah"

*2 extracted fact(s) were dropped because the supporting quote was not found in the fetched article text.*

## Validation results

- **Variant A: passed** (2 attempt(s))
  - attempt 1: 1 failure(s)
    - [unsupported_superlative] These superlative or absolute words are not used by the verified facts: ['paling']. The facts do not establish a ranking or a certainty, so remove the word or restate it as the facts do.
  - attempt 2: passed
- **Variant B: passed** (2 attempt(s))
  - attempt 1: 2 failure(s)
    - [unsupported_superlative] These superlative or absolute words are not used by the verified facts: ['paling']. The facts do not establish a ranking or a certainty, so remove the word or restate it as the facts do.
    - [dropped_hedge] Sentence "Menariknya, 57 persen peminatnya adalah kamu yang berusia 25-35 tahun dan belum menikah." states ['25', '35', '57'] as fact, but the verified fact hedges it with "sekitar". Keep the hedge, for example with "ditargetkan", "direncanakan" or "sekitar".
  - attempt 2: passed
- **Variant C: passed** (3 attempt(s))
  - attempt 1: 2 failure(s)
    - [missing_source] Caption must name the source "detikProperti". It does not appear.
    - [dropped_hedge] Sentence "Banyak peminat di usia 25-35 tahun, sebagian besar belum menikah juga." states ['25', '35'] as fact, but the verified fact hedges it with "sekitar". Keep the hedge, for example with "ditargetkan", "direncanakan" or "sekitar".
  - attempt 2: 1 failure(s)
    - [unsupported_figure] Claim "Rencana pembangunan rusun Manggarai mulai Januari 2027, dengan harga unit mulai Rp 294 juta." cites figures ['294'] that do not appear in its own supporting quote. Use only figures the quote states.
  - attempt 3: passed

## Source

- detikProperti: https://www.detik.com/properti/berita/d-8738846/fakta-rusun-subsidi-manggarai-yang-belum-dibangun-tapi-sudah-diburu-1-500-orang

---

*Generated by rumah123-ig-weekly-generator. Status: needs_approval. No auto-posting.*

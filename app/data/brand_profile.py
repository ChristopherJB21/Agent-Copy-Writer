from __future__ import annotations

"""Brand Voice Guide: profil toko sebagai config file (bukan tabel, hasil keputusan MVP).

Diinjeksi ke prompt copywriter & reviewer agar gaya bahasa konsisten dengan brand.
"""

BRAND_PROFILE: dict = {
    "store_name": "Reswara Fashion",
    "tone": (
        "Casual, hangat, enerjik, bahasa Indonesia sehari-hari yang tidak kaku "
        "tapi tetap sopan. Hindari kalimat terlalu formal/kaku (mis. 'dengan ini kami informasikan')."
    ),
    "audience": "Anak muda & pekerja usia 20-35 yang cari outfit nyaman untuk kerja/hangout.",
    "primary_products": ["Kemeja", "Kaos", "Celana", "Dress", "Outerwear"],
    "cta_rules": (
        "CTA harus langsung dan spesifik ke channel: video -> 'klik keranjang kuning', "
        "feed -> 'tap link di bio', broadcast -> 'klik link di chat / link produk'."
    ),
    "hashtags": ["#OOTDIndo", "#FashionUMKM", "#LocalBrand", "#KemejaLinen", "#ClearanceSale"],
    "product_link_placeholder": "[Link Produk]",
    "promo_rule": (
        "Setiap klaim promo/stok WAJIB berasal dari data yang diberikan (stok, diskon, "
        "rating, testimoni, jumlah order). Dilarang membuat angka sendiri (anti-hallucination)."
    ),
    "forbidden": [
        "klaim angka promo/stok yang tidak ada di data",
        "klaim '-100%' atau 'gratis semua' tanpa data",
        "overclaim bahan (mis. 'anti luntur selamanya') tanpa bukti",
    ],
}

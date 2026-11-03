# Panduan Setup Notifikasi WhatsApp Resmi (Twilio)

Dokumen ini memuat langkah lengkap mengaktifkan notifikasi absensi MagangHub langsung ke WhatsApp pribadi Anda menggunakan **Twilio WhatsApp Business API**.

---

## 1. Keuntungan Menggunakan Twilio
* **Resmi dari Meta**: Menggunakan infrastruktur Meta WhatsApp Business Solution Provider (BSP) resmi.
* **Murni Bayar Per Pesan (Pay-as-you-go)**: Saldo hanya dipotong ketika ada pesan terkirim (~Rp 500 – Rp 800 per pesan).
* **Saldo Uji Coba Gratis**: Pendaftaran akun baru otomatis mendapatkan saldo trial gratis ($\approx$ \$15) yang cukup untuk pengujian berbulan-bulan.
* **Instan Tanpa Verifikasi Bisnis**: Fitur **Twilio Sandbox** memungkinkan Anda menghubungkan nomor WhatsApp pribadi dalam waktu 2 menit.

---

## 2. Langkah-Langkah Aktivasi

### Langkah 1: Pendaftaran Akun Twilio
1. Buka halaman registrasi: [https://www.twilio.com/try-twilio](https://www.twilio.com/try-twilio).
2. Isi formulir pendaftaran:
   * **First Name & Last Name**
   * **Email**
   * **Password**
3. Klik **Start your free trial**.
4. Buka email Anda, lalu klik tautan **Verify Email**.
5. Masukkan nomor ponsel Anda untuk verifikasi melalui kode SMS (OTP).
6. Pada pertanyaan onboarding awal:
   * *Which product are you using?* $\rightarrow$ Pilih **WhatsApp** (atau **SMS / Messaging**).
   * *What are you building?* $\rightarrow$ Pilih **Alerts & Notifications**.
   * *Preferred coding language?* $\rightarrow$ Pilih **Python**.

---

### Langkah 2: Menyalin Kredensial API (Account SID & Auth Token)
1. Buka dashboard utama Twilio: [https://console.twilio.com](https://console.twilio.com).
2. Scroll ke bagian bawah pada kotak **Account Info**.
3. Di sana Anda akan menemukan:
   * **Account SID**: String panjang berawalan `AC` (contoh: `ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`).
   * **Auth Token**: Klik tombol **Show** (ikon mata) untuk melihat token rahasia 32 karakter.
4. Salin kedua nilai tersebut.

---

### Langkah 3: Menghubungkan Nomor WhatsApp (Twilio Sandbox)
Karena nomor baru harus terdaftar sebelum bot dapat mengirimkan pesan:
1. Di menu navigasi sebelah kiri konsol Twilio, buka:  
   **Messaging** $\rightarrow$ **Try it out** $\rightarrow$ **Send a WhatsApp message**.
2. Pada tab **Sandbox Settings**, Anda akan melihat:
   * **Nomor Pengirim Twilio**: Biasanya `+1 415 523 8886`.
   * **Kode Join Unik**: Berformat `join <kata-kunci>` (contoh: `join apple-banana`).
3. Buka aplikasi **WhatsApp di ponsel Anda**:
   * Simpan kontak nomor bot `+1 415 523 8886` atau scan kode QR yang tampil di layar.
   * Kirim pesan teks berisi kode join tersebut (misal ketik: `join apple-banana`).
4. Bot Twilio akan membalas otomatis:
   > *"You are all set! Sandbox is now active. Reply 'stop' to leave."*
5. Nomor WhatsApp Anda kini sudah resmi terhubung dengan sandbox.

---

### Langkah 4: Konfigurasi Berkas `.env`
Buka berkas `.env` di direktori proyek `auto-absen-maganghub` Anda, lalu lengkapi variabel berikut:

```ini
# Notifikasi WhatsApp Resmi (Twilio)
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=masukkan_auth_token_anda_disini
TWILIO_WHATSAPP_FROM=+14155238886
WHATSAPP_TO=+6281234567890
```

> [!IMPORTANT]
> **Format Nomor WhatsApp (`WHATSAPP_TO`)**:
> Wajib menggunakan format internasional yang diawali kode negara `+62` tanpa angka `0` di depannya.  
> * Contoh Benar: `+6281234567890`
> * Contoh Salah: `081234567890` atau `6281234567890` (tanpa tanda plus)

---

### Langkah 5: Uji Coba Pengiriman Pesan
Jalankan perintah pengujian mandiri melalui terminal Laragon atau PowerShell:

```powershell
.\.venv\Scripts\python.exe main.py doctor
```

Jika konfigurasi benar, baris berikut akan muncul di terminal:
```text
[OK] Pesan tes WhatsApp terkirim, cek WhatsApp Anda.
```
Dan pesan tes resmi dari bot Twilio akan langsung masuk ke WhatsApp Anda!

---

## 3. Catatan Penting Mengenai Twilio Sandbox

1. **Masa Aktif Sesi Sandbox (72 Jam)**:
   * Kebijakan keamanan sandbox Meta mengharuskan pengguna mengirim pesan ulang setiap 72 jam jika sesi kedaluwarsa.
   * Jika sewaktu-waktu bot gagal mengirim pesan dengan keterangan session expired, cukup kirim pesan apa saja (misal: `halo` atau kirim ulang kode `join ...`) ke nomor bot Twilio dari HP Anda untuk memperpanjang sesi aktif.
2. **Kerahasiaan Kredensial**:
   * Jangan pernah membagikan atau mengunggah `TWILIO_AUTH_TOKEN` ke GitHub publik. Berkas `.env` sudah otomatis masuk ke dalam `.gitignore`.


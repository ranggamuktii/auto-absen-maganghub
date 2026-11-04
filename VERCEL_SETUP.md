# Panduan Deploy Vercel & Otomasi Cron Job

Project ini sudah siap dideploy ke **Vercel** dengan fitur **Vercel Serverless Python** dan **Vercel Cron Jobs**.

---

## 1. Arsitektur Vercel di Project Ini

* **`vercel.json`**: Mengatur jadwal cron job otomatis pada **08:00 UTC (15:00 WIB)** setiap hari Senin–Jumat:
  ```json
  {
    "version": 2,
    "functions": {
      "api/*.py": {
        "maxDuration": 60
      }
    },
    "crons": [
      {
        "path": "/api/cron",
        "schedule": "0 8 * * 1-5"
      }
    ]
  }
  ```
* **`api/cron.py`**: Serverless function yang dipanggil oleh cron Vercel untuk memicu proses absen otomatis.
* **`api/status.py`**: Serverless function untuk mengecek apakah absen hari ini sudah terkirim.
* **`public/index.html`**: Antarmuka web monitoring di Vercel (bisa diakses langsung di URL `https://nama-project.vercel.app`).

---

## 2. Langkah-Langkah Deploy ke Vercel

### Langkah 1: Push Perubahan ke GitHub
Di terminal Anda, push commit terbaru ke repository GitHub Anda:
```bash
git push -u origin main
```

### Langkah 2: Import Project di Vercel
1. Buka [https://vercel.com](https://vercel.com) dan login.
2. Klik **Add New...** ➜ **Project**.
3. Hubungkan akun GitHub Anda dan pilih repository **`auto-absen-maganghub`**.

### Langkah 3: Konfigurasi Environment Variables di Vercel
Sebelum klik **Deploy**, buka bagian **Environment Variables** di halaman pengaturan Vercel, lalu tambahkan variabel berikut (sesuaikan dengan nilai `.env` lokal Anda):

| Variable Name | Keterangan / Contoh Nilai |
| :--- | :--- |
| `SIAPKERJA_USERNAME` | Email akun Kemnaker / SIAPkerja |
| `SIAPKERJA_PASSWORD` | Password akun Kemnaker / SIAPkerja |
| `ACTIVITY_LOG` | Deskripsi aktivitas harian magang |
| `LESSON_LEARNED` | Pembelajaran yang didapat |
| `OBSTACLES` | Kendala yang dihadapi |
| `LOCATION` | Lokasi penempatan (misal: `Karawang`) |
| `LATITUDE` | Latitude lokasi penempatan (misal: `-6.3227303`) |
| `LONGITUDE` | Longitude lokasi penempatan (misal: `107.3375791`) |
| `HARI_LIBUR` | `Sabtu,Minggu` |
| `LIBUR_NASIONAL` | `true` |
| `TWILIO_ACCOUNT_SID` | SID akun Twilio Anda |
| `TWILIO_AUTH_TOKEN` | Auth Token Twilio Anda |
| `TWILIO_WHATSAPP_FROM` | Nomor WhatsApp pengirim Twilio (contoh: `+14155238886`) |
| `WHATSAPP_TO` | Nomor WhatsApp penerima notifikasi (contoh: `+628xxxxxxxxxx`) |
| `CRON_SECRET` | *(Opsional)* Token keamanan jika ingin memproteksi URL `/api/cron` |

### Langkah 4: Deploy
Klik tombol **Deploy**. Vercel akan otomatis menginstal dependensi (`pydantic-settings`, `requests`) dan mengaktifkan Serverless API.

---

## 3. Cara Memeriksa & Menguji

1. **Buka Web Dashboard**:
   Akses domain Vercel Anda: `https://<nama-project>.vercel.app`.
   Anda akan melihat status hari ini dan tombol untuk memicu absen secara manual.
2. **Cek Jadwal Cron di Vercel**:
   Di Vercel dashboard, buka tab **Settings** ➜ **Cron Jobs**. Anda akan melihat cron job terdaftar aktif pada jadwal `0 8 * * 1-5`.
3. **Uji Endpoint Langsung**:
   Buka URL: `https://<nama-project>.vercel.app/api/status` untuk melihat respons JSON status presensi hari ini.

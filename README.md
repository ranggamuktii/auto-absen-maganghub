# Auto Absen MagangHub

Biar gak panik kalau lupa absen MagangHub. Cukup satu perintah, program login, kirim absen, selesai. Data absen diambil dari berkas `.env` dan gak disimpan di mana pun.

Anggap program ini ban serep: dipakai saat kepepet, bukan tiap hari. Kalau ingat, absen sendiri tepat waktu.

> Program ini tanpa jaminan apa pun. Gunakan dengan risiko sendiri — lihat bagian [Peringatan](#peringatan).

Kalau program ini membantu Anda, pertimbangkan memberi ⭐ pada repositori ini.

## Daftar Isi

- [Auto Absen MagangHub](#auto-absen-maganghub)
  - [Daftar Isi](#daftar-isi)
  - [Memulai](#memulai)
    - [Cara Kerja](#cara-kerja)
    - [Prasyarat](#prasyarat)
    - [Instalasi](#instalasi)
    - [Konfigurasi](#konfigurasi)
    - [Penggunaan](#penggunaan)
  - [Penjadwalan Otomatis](#penjadwalan-otomatis)
    - [Task Scheduler (Windows)](#task-scheduler-windows)
    - [Cron / Systemd Timer (Linux/VPS)](#cron--systemd-timer-linuxvps)
    - [GitHub Actions](#github-actions)
  - [Notifikasi WhatsApp (Twilio)](#notifikasi-whatsapp-twilio)
  - [Informasi Proyek](#informasi-proyek)
    - [Struktur Proyek](#struktur-proyek)
    - [Keamanan](#keamanan)
    - [Peringatan](#peringatan)
    - [Kontribusi](#kontribusi)
    - [Atribusi](#atribusi)
    - [Lisensi](#lisensi)

## Memulai

### Cara Kerja

1. Program membaca berkas `.env`.
2. Program login ke SSO Kemnaker dengan kredensial (nama pengguna dan kata sandi) dari `.env`.
3. Program meminta `access token` dari API Monev.
4. Program mengirim permintaan POST ke `/attendances/with-daily-log` dengan status `PRESENT` dan log harian.
5. Bila login atau pengiriman gagal karena gangguan jaringan, program mencoba ulang maksimal 3 kali dengan jeda 1 menit.

### Prasyarat

- Python 3.10 atau versi lebih baru.
- Akun MagangHub (login Siap Kerja) beserta kata sandi.
- Penjadwalan lokal: Windows (Task Scheduler) atau Linux/VPS (cron/systemd). GitHub Actions tersedia sebagai alternatif tanpa komputer sendiri. Perintah manual berjalan di sistem operasi apa pun.

### Instalasi

1. Salin repositori ini.
2. Salin `.env.example` menjadi `.env`, lalu isi nilai setiap variabel.
3. Pasang dependensi dengan salah satu dari dua cara berikut.

**Cara A, dengan uv:**

1. Pasang uv:

   Windows:

   ```
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

   Linux/VPS:

   ```
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. Buat lingkungan virtual, lalu pasang dependensi:

   ```
   uv venv
   uv pip install -r requirements.txt
   ```

**Cara B, dengan pip:**

1. Buat lingkungan virtual:

   ```
   python -m venv .venv
   ```

2. Aktifkan lingkungan virtual:

   Windows:

   ```
   .venv\Scripts\activate
   ```

   Linux/VPS:

   ```
   source .venv/bin/activate
   ```

3. Pasang dependensi:

   ```
   pip install -r requirements.txt
   ```

### Konfigurasi

Berkas `.env` menyimpan seluruh konfigurasi. Tabel berikut memuat setiap variabel.

| Variabel | Wajib | Keterangan |
|---|---|---|
| `SIAPKERJA_USERNAME` | Ya | NIK, email, atau nomor telepon akun Anda |
| `SIAPKERJA_PASSWORD` | Ya | Kata sandi akun Anda |
| `CLOCK_IN_TIME` | Tidak | Jam tugas untuk skrip penjadwalan (`setup_task`, `setup_cron.sh`), format `HH:MM`. Kosong berarti `16:00`. Jadwal manual (crontab edit sendiri, systemd, GitHub Actions) memakai jadwalnya sendiri |
| `REMINDER_TIMES` | Tidak | Jam pengingat Telegram bila hari ini belum absen, pisahkan dengan koma, format `HH:MM`. Nilai bawaan: `16:00,21:00` |
| `HARI_LIBUR` | Tidak | Nama hari libur, pisahkan dengan koma. Nilai bawaan: `Sabtu,Minggu` |
| `LIBUR_NASIONAL` | Tidak | Cek kalender libur nasional dari API Monev sebelum absen. Nilai bawaan: `true` |
| `LATITUDE` | Tidak | Lintang lokasi absen, dikirim dalam payload absen. Nilai bawaan: `-6.2088` |
| `LONGITUDE` | Tidak | Bujur lokasi absen, dikirim dalam payload absen. Nilai bawaan: `106.8456` |
| `LOCATION` | Tidak | Nama lokasi absen, dikirim dalam payload absen. Nilai bawaan: `Jakarta` |
| `ACTIVITY_LOG` | Ya | Isian kolom aktivitas harian |
| `LESSON_LEARNED` | Ya | Isian kolom pelajaran hari ini |
| `OBSTACLES` | Ya | Isian kolom kendala harian |
| `TELEGRAM_BOT_TOKEN` | Tidak | Token bot Telegram untuk notifikasi. Kosong berarti notifikasi mati |
| `TELEGRAM_CHAT_ID` | Tidak | ID chat Telegram tujuan notifikasi. Kosong berarti notifikasi mati |

Program juga membaca `API_BASE` dan `AUTH_BASE`. Nilai bawaan kedua variabel itu sudah mengarah ke API Monev resmi. Ubah kedua nilai itu hanya jika alamat API berubah.

### Libur Nasional

Selain `HARI_LIBUR`, program membaca kalender libur resmi dari `GET /api/v1/holidays` sebelum mengirim absen. Bila hari ini berstatus libur nasional, absen dilewati tanpa notifikasi.

- Hanya libur dengan `scope: NATIONAL` yang dipakai. Libur provinsi dan kabupaten diabaikan.
- Kalender diambil sekali per eksekusi, jadi memeriksa beberapa tanggal hanya memakai satu permintaan.
- Bila API libur tidak bisa dihubungi, program mencatat `[WARN]` lalu tetap mengirim absen. Kalender libur bersifat pelengkap, bukan syarat absen.
- Set `LIBUR_NASIONAL=false` untuk mematikan pengecekan dan kembali ke `HARI_LIBUR` saja.

Semua nilai di atas dapat Anda ubah sesuai kebutuhan. Contoh isi `.env` dengan nilai bawaan:

```
SIAPKERJA_USERNAME=your_nik_or_email_or_phone
SIAPKERJA_PASSWORD=your_password
CLOCK_IN_TIME=16:00
REMINDER_TIMES=16:00,21:00
HARI_LIBUR=Sabtu,Minggu
LIBUR_NASIONAL=true
LATITUDE=-6.2088
LONGITUDE=106.8456
LOCATION=Jakarta
ACTIVITY_LOG=Menjalankan kegiatan magang hari ini dengan mengikuti arahan mentor dan menyelesaikan aktivitas yang berkaitan dengan tugas serta kebutuhan proyek yang sedang dikerjakan.
LESSON_LEARNED=Memperoleh pengalaman dan pemahaman baru dari kegiatan magang hari ini, terutama terkait proses kerja, koordinasi, serta penerapan pengetahuan dalam penyelesaian tugas proyek.
OBSTACLES=Tidak terdapat kendala berarti selama kegiatan magang hari ini. Aktivitas dapat dilaksanakan dengan baik sesuai arahan mentor dan kebutuhan pekerjaan yang sedang dilakukan.
# Opsional: notifikasi Telegram
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```


### Penggunaan

Kirim absen masuk (status `PRESENT`) untuk hari ini:

```
python main.py absen
```

Tampilkan log absen hari ini:

```
python main.py status
```

Kirim pengingat Telegram bila hari ini belum absen:

```
python main.py remind
```

Pengingat dilewati pada hari libur. Bila absen hari ini sudah tercatat, perintah ini hanya mencatat `[OK]` dan tidak mengirim pesan. Notifikasi hanya terkirim bila `TELEGRAM_BOT_TOKEN` dan `TELEGRAM_CHAT_ID` sudah diisi.

Bila menggunakan uv, jalankan `uv run main.py absen` atau `uv run main.py status`. Perintah itu langsung menggunakan lingkungan `.venv` tanpa aktivasi.

Periksa kelayakan setup (variabel, login, Telegram, scheduler):

```
python main.py doctor
```

Tampilkan payload absen tanpa mengirim:

```
python main.py absen --dry-run
```

Tampilkan absen 7 hari terakhir:

```
python main.py status --days 7
```

Setiap run mencatat hasilnya ke `absen.log` di folder proyek, lengkap dengan stempel waktu.

Program mengirim data berikut ke `POST /attendances/with-daily-log`:

```json
{
  "date": "2026-09-21",
  "status": "PRESENT",
  "activity_log": "...",
  "lesson_learned": "...",
  "obstacles": "..."
}
```

Contoh keluaran perintah `status`:

```
Status: 2026-09-21
  Aktivitas:  Menjalankan kegiatan magang hari ini.
  Pelajaran:  Memperoleh pengalaman baru.
  Kendala:    Tidak ada kendala.
```

## Penjadwalan Otomatis

### Task Scheduler (Windows)

Dua skrip terpisah mengurus jadwal Windows:

- `setup_task.bat` membuat tugas `AutoAbsenMaganghub` yang menjalankan `python main.py absen`.
- `setup_reminder.bat` membuat tugas `AutoAbsenMaganghubReminder` yang menjalankan `python main.py remind`.

Keduanya memakai Python dari `.venv` bila ada. Bila tidak ada, keduanya memakai Python dari PATH.

Catatan soal jadwal ini:

- Laptop boleh tidur. Pada jam absen, tugas mengaktifkan kembali laptop yang tidur, asalkan laptop sedang tercolok ke pengisi daya.
- Bila laptop mati total atau tidak tercolok, tugas menunggu sampai laptop menyala lagi, lalu absen terkirim saat itu juga.

1. Isi `CLOCK_IN_TIME` di `.env` dengan format `HH:MM`. Skrip `setup_task` menggunakan nilai itu sebagai jam absen. Bila kosong, skrip menggunakan `16:00`.
2. Isi `REMINDER_TIMES` di `.env` dengan format `HH:MM,HH:MM`. Skrip `setup_reminder` membuat satu tugas dengan beberapa pemicu. Bila kosong, skrip menggunakan `16:00,21:00`.
3. Klik dua kali `setup_task.bat`, lalu `setup_reminder.bat`. Setiap skrip meminta akses Administrator sendiri. Tanpa Administrator, pendaftaran tugas gagal.

   Alternatif via PowerShell Administrator:

   ```
   powershell -ExecutionPolicy Bypass -File .\setup_task.ps1
   powershell -ExecutionPolicy Bypass -File .\setup_reminder.ps1
   ```

Untuk mematikan otomatisasi, hapus tugas:

```
Unregister-ScheduledTask -TaskName 'AutoAbsenMaganghub' -Confirm:$false
Unregister-ScheduledTask -TaskName 'AutoAbsenMaganghubReminder' -Confirm:$false
```

Untuk memeriksa status tugas:

```
Get-ScheduledTask -TaskName 'AutoAbsenMaganghub'
Get-ScheduledTask -TaskName 'AutoAbsenMaganghubReminder'
```

### Cron / Systemd Timer (Linux/VPS)

Cocok untuk VPS yang selalu menyala. Cara termudah: jalankan skrip `setup_cron.sh`. Skrip membaca jam dari `CLOCK_IN_TIME` dan `REMINDER_TIMES` di `.env`, lalu memakai Python dari `.venv` bila ada.

1. Isi `CLOCK_IN_TIME` di `.env` dengan format `HH:MM`. Bila kosong, skrip memakai `16:00`.
2. Isi `REMINDER_TIMES` di `.env` dengan format `HH:MM,HH:MM`. Bila kosong, skrip memakai `16:00,21:00`.
3. Jalankan skrip:

   ```
   chmod +x setup_cron.sh
   ./setup_cron.sh
   ```

   Skrip memberi peringatan bila zona waktu bukan `Asia/Jakarta`. Bila perlu, samakan dulu:

   ```
   sudo timedatectl set-timezone Asia/Jakarta
   ```

3. Pastikan perintah manual berhasil sebelum mengandalkan jadwal:

   ```
   ./.venv/bin/python main.py absen --dry-run
   ./.venv/bin/python main.py remind
   ./.venv/bin/python main.py doctor
   ```

Untuk memeriksa jadwal dan log:

```
crontab -l
tail -f absen.log
```

Untuk mematikan otomatisasi:

```
crontab -l | grep -v '# AutoAbsenMaganghub' | crontab -
```

Setiap ganti `CLOCK_IN_TIME` atau `REMINDER_TIMES`, jalankan ulang `./setup_cron.sh`.

**Alternatif manual tanpa skrip:**

1. Buka crontab:

   ```
   crontab -e
   ```

2. Tambahkan baris berikut untuk absen tiap hari pukul 16:00 (sesuaikan path):

   ```
   0 16 * * * cd /opt/auto-absen && /opt/auto-absen/.venv/bin/python main.py absen >> /opt/auto-absen/absen.log 2>&1
   ```

   Tambahkan juga baris pengingat untuk pukul 16:00 dan 21:00:

   ```
   0 16 * * * cd /opt/auto-absen && /opt/auto-absen/.venv/bin/python main.py remind >> /opt/auto-absen/absen.log 2>&1
   0 21 * * * cd /opt/auto-absen && /opt/auto-absen/.venv/bin/python main.py remind >> /opt/auto-absen/absen.log 2>&1
   ```

   Gunakan path absolut. Ubah `0 16` atau `0 21` untuk mengganti jam.

**Alternatif lanjut, dengan systemd timer (log rapi via `journalctl`):**

1. Buat berkas service `/etc/systemd/system/auto-absen.service`:

   ```
   [Unit]
   Description=Auto Absen MagangHub
   After=network-online.target
   Wants=network-online.target

   [Service]
   Type=oneshot
   WorkingDirectory=/opt/auto-absen
   ExecStart=/opt/auto-absen/.venv/bin/python main.py absen
   ```

2. Buat berkas timer `/etc/systemd/system/auto-absen.timer`:

   ```
   [Unit]
   Description=Auto Absen MagangHub tiap hari 16:00 WIB

   [Timer]
   OnCalendar=*-*-* 16:00:00
   Persistent=true

   [Install]
   WantedBy=timers.target
   ```

3. Nyalakan timer:

   ```
   sudo systemctl daemon-reload
   sudo systemctl enable --now auto-absen.timer
   ```

Untuk memeriksa status dan log:

```
systemctl status auto-absen.timer
systemctl list-timers auto-absen.timer
journalctl -u auto-absen.service --since today
```

Untuk mematikan otomatisasi:

```
sudo systemctl disable --now auto-absen.timer
```

Tiga hal yang perlu Anda ketahui:

- `CLOCK_IN_TIME` dibaca oleh `setup_task.ps1`/`setup_task.bat` dan `setup_cron.sh`. `REMINDER_TIMES` dibaca oleh `setup_reminder.ps1`/`setup_reminder.bat` dan `setup_cron.sh`. Jadwal cron manual, systemd timer, dan GitHub Actions memakai jadwalnya sendiri — ubah baris crontab (`0 16 ...`), `OnCalendar=`, atau baris cron workflow untuk mengganti jam.
- Pada hari libur (`HARI_LIBUR`) maupun libur nasional, program berhenti sendiri tanpa mengirim absen. Pengingat juga dilewati. Program tidak mengirim notifikasi pada hari itu.
- Bila VPS berada di luar Indonesia, request berjalan dari IP luar negeri, sementara data lokasi absen mengklaim Jakarta. Pakai VPS region Indonesia bila hal ini penting bagi Anda.

Catatan: bila `CLOCK_IN_TIME` dan salah satu jam di `REMINDER_TIMES` sama (misalnya sama-sama `16:00`), absen otomatis dan pengingat berjalan berdekatan. Pengingat tetap aman karena hanya mengirim pesan bila absen hari itu belum tercatat.

### GitHub Actions

Berkas `.github/workflows/absen.yml` menjalankan `python main.py absen` setiap hari pukul 16:00 WIB. Berkas `.github/workflows/reminder.yml` menjalankan `python main.py remind` pada pukul 16:00 dan 21:00 WIB. Jadwal ditulis dalam UTC: `0 9 * * *` dan `0 14 * * *`.

1. Unggah proyek ini ke repositori GitHub.
2. Buka Settings > Secrets and variables > Actions > New repository secret. Buat secret berikut:
   - `SIAPKERJA_USERNAME`
   - `SIAPKERJA_PASSWORD`
   - `ACTIVITY_LOG`
   - `LESSON_LEARNED`
   - `OBSTACLES`
   - `TELEGRAM_BOT_TOKEN` (opsional, untuk notifikasi)
   - `TELEGRAM_CHAT_ID` (opsional, untuk notifikasi)
3. Jalankan manual sekali lewat Actions > Absen atau Actions > Pengingat Absen > Run workflow untuk memastikan semuanya bekerja.

Untuk mematikan otomatisasi, buka Actions > Absen atau Actions > Pengingat Absen > tombol `...` > Disable workflow. Untuk menyalakan lagi, pilih Enable workflow di tempat yang sama.

Empat hal yang perlu Anda ketahui:

- GitHub tidak menjamin cron berjalan tepat waktu.
- Request berjalan dari server GitHub di luar Indonesia, sementara data lokasi absen mengklaim Jakarta.
- Jam eksekusi dikunci di baris cron berkas workflow. `CLOCK_IN_TIME` dan `REMINDER_TIMES` tidak berpengaruh pada jadwal GitHub Actions. Ubah baris cron untuk mengganti jam.
- Pada hari libur (`HARI_LIBUR`) maupun libur nasional, program berhenti sendiri tanpa mengirim absen. Pengingat juga dilewati. Program tidak mengirim notifikasi pada hari itu.

## Notifikasi WhatsApp (Twilio)

Program mengirim pesan WhatsApp setiap kali absen berhasil atau gagal, serta mengirim pengingat bila hari ini belum absen pada jam-jam di `REMINDER_TIMES`. Notifikasi menggunakan layanan resmi **Twilio WhatsApp Business API**.

Panduan lengkap setup akun Twilio, aktivasi WhatsApp Sandbox, hingga konfigurasi variabel tersedia di berkas terpisah:
👉 **[Lihat Panduan Setup Twilio (TWILIO_SETUP.md)](TWILIO_SETUP.md)**.

## Informasi Proyek

### Struktur Proyek

```
auto-absen-maganghub/
├── main.py                   titik masuk CLI (absen, status, remind, doctor)
├── app/
│   ├── commands.py           perintah absen, status, remind, doctor, dry-run
│   ├── config.py             konfigurasi dari .env
│   ├── auth/
│   │   └── sso.py            login SSO Kemnaker dan access token
│   ├── api/
│   │   └── client.py         klien HTTP API Monev
│   ├── models/
│   │   ├── attendance.py     logika absen dan pembacaan log
│   │   └── holiday.py        kalender libur nasional dari API
│   └── utils/
│       ├── log.py            console dan berkas absen.log
│       ├── net.py            error jaringan dan retry
│       ├── telegram.py       notifikasi Telegram
│       └── time.py           waktu zona WIB
├── tests/
│   └── test_main.py          tes otomatis (pytest)
├── .github/
│   └── workflows/
│       ├── absen.yml         penjadwalan absen GitHub Actions
│       ├── reminder.yml      penjadwalan pengingat GitHub Actions
│       └── tests.yml         tes tiap push
├── setup_common.ps1          helper bersama skrip setup Windows
├── setup_task.ps1            tugas absen Windows Task Scheduler
├── setup_task.bat            klik-dua-kali untuk setup_task.ps1
├── setup_reminder.ps1        tugas pengingat Windows Task Scheduler
├── setup_reminder.bat        klik-dua-kali untuk setup_reminder.ps1
├── setup_cron.sh             jadwal cron Linux/VPS
├── .env.example              contoh berkas .env
├── requirements.txt          dependensi Python
├── requirements-dev.txt      dependensi pengembangan
├── LICENSE                   lisensi MIT
└── .gitattributes            akhir baris Git
```

### Keamanan

- Berkas `.env` memuat kata sandi akun Anda. Jangan mengunggah berkas itu ke repositori publik.
- Jangan membagikan isi berkas `.env` kepada siapa pun.
- Untuk GitHub Actions, simpan kredensial sebagai Secrets. Jangan menulis kredensial di berkas workflow.

### Peringatan

Penulis menyediakan program ini "sebagaimana adanya", tanpa jaminan apa pun. Gunakan program ini dengan risiko sendiri ("use at your own risk").

Program mengotomatiskan pengiriman absen. Program ini dirancang sebagai pengaman saat lupa absen, bukan sebagai pengganti absen manual. Pastikan cara pakai ini sesuai dengan aturan di tempat magang Anda.

Penulis tidak bertanggung jawab atas akibat apa pun dari penggunaan program ini. Akibat itu mencakup penangguhan akun, sanksi, atau kerugian lain.

### Kontribusi

Kontribusi berupa issue dan pull request terbuka untuk siapa pun.

1. Fork repositori ini, lalu buat branch untuk perubahan Anda.
2. Jangan commit berkas `.env` ke repositori.
3. Pasang dependensi pengembangan, lalu pastikan tes lolos sebelum membuka pull request:

   ```
   pip install -r requirements-dev.txt
   python -m pytest
   ```

4. Buka pull request dengan penjelasan singkat tentang perubahan Anda.

### Atribusi

Gaya bahasa Indonesia di README ini mengikuti [indonesian-writing-skills](https://github.com/pataanggs/indonesian-writing-skills) oleh pataanggs.

### Lisensi

Proyek ini berlisensi MIT. Lihat berkas `LICENSE` untuk teks lengkapnya.

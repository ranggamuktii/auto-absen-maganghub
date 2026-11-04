<?php

/**
 * Auto Absen MagangHub - Local Control Dashboard
 * Minimalis, solid color, tanpa gradasi. Vanilla JS (tanpa jQuery/Bootstrap).
 *
 * Opsional: isi DASHBOARD_PASSWORD di .env untuk mengaktifkan login/logout dashboard.
 * Kosongkan (atau hapus) untuk menonaktifkan login.
 */

session_set_cookie_params(['httponly' => true, 'samesite' => 'Lax']);
session_start();

$envFile = __DIR__ . '/.env';
$logFile = __DIR__ . '/absen.log';
$pyBinary = __DIR__ . '/.venv/Scripts/python.exe';
$mainScript = __DIR__ . '/main.py';

// Baca seluruh pasangan KEY=VALUE dari .env
function readEnv($filePath)
{
    $out = [];
    if (!file_exists($filePath)) return $out;
    foreach (file($filePath, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) as $line) {
        $line = trim($line);
        if (strpos($line, '#') === 0 || strpos($line, '=') === false) continue;
        list($key, $val) = explode('=', $line, 2);
        $out[trim($key)] = trim($val, " \t\n\r\0\x0B\"'");
    }
    return $out;
}

// Hanya field aman yang dikirim ke browser (kredensial tidak ikut)
function getSafeEnvData($filePath)
{
    $e = readEnv($filePath);
    return [
        'clock_in_time'  => $e['CLOCK_IN_TIME'] ?? '15:00',
        'location'       => $e['LOCATION'] ?? 'Karawang',
        'latitude'       => $e['LATITUDE'] ?? '',
        'longitude'      => $e['LONGITUDE'] ?? '',
        'activity_log'   => $e['ACTIVITY_LOG'] ?? '',
        'lesson_learned' => $e['LESSON_LEARNED'] ?? '',
        'obstacles'      => $e['OBSTACLES'] ?? '',
    ];
}

// Simpan nilai ke .env secara aman
function updateSafeEnvData($filePath, $updates)
{
    if (!file_exists($filePath)) return false;
    $content = file_get_contents($filePath);
    foreach ($updates as $key => $val) {
        $cleanVal = str_replace(["\r", "\n"], ' ', trim($val));
        $pattern = "/^" . preg_quote($key, '/') . "=.*$/m";
        if (preg_match($pattern, $content)) {
            // callback: mencegah "$1" / "\" di teks dianggap backreference
            $content = preg_replace_callback($pattern, function () use ($key, $cleanVal) {
                return "{$key}={$cleanVal}";
            }, $content);
        } else {
            $content .= "\n{$key}={$cleanVal}";
        }
    }
    return file_put_contents($filePath, $content) !== false;
}

$dashPass = readEnv($envFile)['DASHBOARD_PASSWORD'] ?? '';
$authOn = $dashPass !== '';
$authed = !$authOn || !empty($_SESSION['auth']);

// API Handler (AJAX)
if (isset($_GET['api'])) {
    header('Content-Type: application/json; charset=utf-8');
    $action = $_GET['api'] ?? '';

    if ($action === 'login') {
        $ok = $authOn && hash_equals($dashPass, (string)($_POST['password'] ?? ''));
        if ($ok) {
            session_regenerate_id(true);
            $_SESSION['auth'] = true;
        } else {
            sleep(1); // perlambat tebak-tebakan kata sandi
        }
        echo json_encode(['status' => $ok, 'message' => $ok ? '' : 'Kata sandi salah.']);
        exit;
    }

    if ($action === 'logout' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $_SESSION = [];
        session_destroy();
        echo json_encode(['status' => true]);
        exit;
    }

    if (!$authed) {
        http_response_code(401);
        echo json_encode(['status' => false, 'message' => 'Sesi berakhir. Silakan masuk kembali.']);
        exit;
    }

    if ($action === 'status') {
        $env = getSafeEnvData($envFile);
        $output = shell_exec("\"{$pyBinary}\" \"{$mainScript}\" status 2>&1");
        $isAttended = (strpos($output, 'Belum ada absen') === false && strpos($output, 'Status:') !== false);
        echo json_encode([
            'status' => true, 'is_attended' => $isAttended, 'env' => $env,
            'output' => trim($output ?? ''), 'today' => date('Y-m-d'),
        ]);
        exit;
    }

    if ($action === 'absen') {
        $output = shell_exec("\"{$pyBinary}\" \"{$mainScript}\" absen 2>&1");
        $success = (strpos($output, '[OK]') !== false);
        echo json_encode([
            'status'  => $success,
            'message' => $success ? 'Presensi berhasil diproses.' : 'Eksekusi presensi selesai.',
            'output'  => trim($output ?? ''),
        ]);
        exit;
    }

    if ($action === 'dry_run') {
        $output = shell_exec("\"{$pyBinary}\" \"{$mainScript}\" absen --dry-run 2>&1");
        echo json_encode(['status' => true, 'output' => trim($output ?? '')]);
        exit;
    }

    if ($action === 'save_log') {
        $ok = updateSafeEnvData($envFile, [
            'ACTIVITY_LOG'   => $_POST['activity_log'] ?? '',
            'LESSON_LEARNED' => $_POST['lesson_learned'] ?? '',
            'OBSTACLES'      => $_POST['obstacles'] ?? '',
            'CLOCK_IN_TIME'  => $_POST['clock_in_time'] ?? '15:00',
        ]);
        echo json_encode([
            'status'  => $ok,
            'message' => $ok ? 'Catatan harian tersimpan.' : 'Gagal menyimpan ke .env',
        ]);
        exit;
    }

    if ($action === 'save_location') {
        $name = trim(preg_replace('/\s+/', ' ', $_POST['location'] ?? ''));
        $lat = $_POST['latitude'] ?? '';
        $lng = $_POST['longitude'] ?? '';
        $valid = $name !== '' && mb_strlen($name) <= 120
            && is_numeric($lat) && is_numeric($lng)
            && abs((float)$lat) <= 90 && abs((float)$lng) <= 180;
        $ok = $valid && updateSafeEnvData($envFile, [
            'LOCATION'  => $name,
            'LATITUDE'  => (string)(float)$lat,
            'LONGITUDE' => (string)(float)$lng,
        ]);
        echo json_encode([
            'status'  => $ok,
            'message' => $ok ? 'Lokasi absen diperbarui.' : ($valid ? 'Gagal menyimpan ke .env' : 'Data lokasi tidak valid.'),
            'env'     => getSafeEnvData($envFile),
        ]);
        exit;
    }

    if ($action === 'get_logs') {
        $lines = [];
        if (file_exists($logFile)) {
            $lines = array_slice(file($logFile, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES), -25);
        }
        echo json_encode(['status' => true, 'logs' => implode("\n", $lines)]);
        exit;
    }

    echo json_encode(['status' => false, 'message' => 'Aksi tidak dikenal']);
    exit;
}

$env = getSafeEnvData($envFile);
$h = fn ($s) => htmlspecialchars($s, ENT_QUOTES, 'UTF-8');
$locNow = $env['location'] . ($env['latitude'] !== '' && $env['longitude'] !== ''
    ? ' (' . number_format((float)$env['latitude'], 4) . ', ' . number_format((float)$env['longitude'], 4) . ')' : '');
?>
<!DOCTYPE html>
<html lang="id">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Auto Absen MagangHub</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Schibsted+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #EDF0EE;
            --surface: #FFFFFF;
            --field: #F6F8F7;
            --ink: #16201C;
            --muted: #5C6963;
            --line: #D9DFDC;
            --ok: #0B6E5A;
            --warn: #B45309;
            --err: #B42318;
            --term: #121A16;
            --term-ink: #CFE0D6;
            --sans: 'Schibsted Grotesk', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
            --mono: 'JetBrains Mono', Consolas, 'Courier New', monospace;
        }

        @media (prefers-color-scheme: dark) {
            :root {
                --bg: #0D1210;
                --surface: #151C19;
                --field: #101613;
                --ink: #E9F0EC;
                --muted: #92A199;
                --line: #26312C;
                --ok: #4FD1AE;
                --warn: #F2B35E;
                --err: #F97066;
                --term: #080C0A;
            }
        }

        *,
        *::before,
        *::after {
            box-sizing: border-box;
        }

        [hidden] {
            display: none !important;
        }

        html {
            -webkit-text-size-adjust: 100%;
        }

        body {
            margin: 0;
            background: var(--bg);
            color: var(--ink);
            font: 400 15px/1.55 var(--sans);
        }

        .wrap {
            max-width: 880px;
            margin: 0 auto;
            padding: 28px 20px 64px;
        }

        :focus-visible {
            outline: 2px solid var(--ink);
            outline-offset: 2px;
        }

        .sr {
            position: absolute;
            width: 1px;
            height: 1px;
            overflow: hidden;
            clip: rect(0 0 0 0);
            white-space: nowrap;
        }

        /* Top bar */
        .top {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            margin-bottom: 56px;
        }

        .top-r {
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .brand {
            font-weight: 600;
            letter-spacing: -.01em;
        }

        .brand span {
            color: var(--muted);
            font-weight: 400;
        }

        .chip {
            font-size: 13px;
            color: var(--muted);
            border: 1px solid var(--line);
            border-radius: 999px;
            padding: 5px 12px;
        }

        /* Hero: status adalah fokus halaman */
        .hero {
            margin-bottom: 56px;
        }

        .date {
            margin: 0 0 14px;
            color: var(--muted);
        }

        .hero h1 {
            display: flex;
            align-items: center;
            gap: 14px;
            margin: 0;
            font-size: clamp(2rem, 6vw, 3.4rem);
            line-height: 1.05;
            font-weight: 600;
            letter-spacing: -.035em;
        }

        .dot {
            flex: none;
            width: .36em;
            height: .36em;
            border-radius: 50%;
            background: var(--muted);
        }

        .dot[data-s="ok"] {
            background: var(--ok);
        }

        .dot[data-s="warn"] {
            background: var(--warn);
        }

        .dot[data-s="err"] {
            background: var(--err);
        }

        .detail {
            margin: 12px 0 0;
            min-height: 1.55em;
            color: var(--muted);
            max-width: 60ch;
        }

        .meta {
            display: flex;
            flex-wrap: wrap;
            gap: 8px 36px;
            margin: 28px 0;
        }

        .meta div {
            min-width: 0;
        }

        .meta dt {
            font-size: 13px;
            color: var(--muted);
        }

        .meta dd {
            margin: 0;
            font-weight: 500;
        }

        .actions {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }

        /* Buttons */
        .btn {
            font: inherit;
            font-weight: 600;
            font-size: 14px;
            border-radius: 10px;
            padding: 11px 18px;
            border: 1px solid transparent;
            cursor: pointer;
            transition: opacity .15s, border-color .15s;
        }

        .btn:disabled {
            opacity: .45;
            cursor: not-allowed;
        }

        .btn-primary {
            background: var(--ink);
            color: var(--surface);
        }

        .btn-primary:not(:disabled):hover {
            opacity: .88;
        }

        .btn-lg {
            padding: 14px 24px;
            font-size: 15px;
        }

        .btn-sm {
            padding: 7px 14px;
            font-size: 13px;
        }

        .btn-ghost {
            background: transparent;
            color: var(--ink);
            border-color: var(--line);
        }

        .btn-ghost:not(:disabled):hover {
            border-color: var(--ink);
        }

        /* Sections */
        .section {
            margin-top: 48px;
        }

        .section-head {
            display: flex;
            align-items: baseline;
            justify-content: space-between;
            gap: 12px;
            margin-bottom: 14px;
        }

        .section-head h2 {
            margin: 0;
            font-size: 19px;
            font-weight: 600;
            letter-spacing: -.02em;
        }

        .hint {
            font-size: 13px;
            color: var(--muted);
        }

        .panel {
            background: var(--surface);
            border: 1px solid var(--line);
            border-radius: 16px;
            padding: 24px;
        }

        .field {
            margin-bottom: 18px;
        }

        .field label {
            display: block;
            font-weight: 500;
            margin-bottom: 6px;
        }

        textarea,
        input:not([type=checkbox]) {
            width: 100%;
            font: inherit;
            color: var(--ink);
            background: var(--field);
            border: 1px solid var(--line);
            border-radius: 10px;
            padding: 11px 13px;
        }

        textarea {
            resize: vertical;
            min-height: 110px;
            line-height: 1.6;
        }

        textarea:focus,
        input:focus {
            outline: none;
            border-color: var(--ink);
        }

        .foot {
            display: flex;
            align-items: flex-end;
            justify-content: space-between;
            gap: 16px;
            margin-top: 6px;
        }

        .foot .field {
            margin: 0;
            width: 170px;
        }

        .foot-r {
            display: flex;
            justify-content: flex-end;
            margin-top: 16px;
        }

        /* Pencarian lokasi */
        .loc-search {
            display: flex;
            gap: 10px;
        }

        .loc-search input {
            flex: 1;
            min-width: 0;
        }

        .loc-list {
            list-style: none;
            margin: 14px 0 0;
            padding: 0;
            border: 1px solid var(--line);
            border-radius: 10px;
            overflow: hidden;
        }

        .loc-list li {
            display: grid;
            gap: 2px;
            padding: 11px 14px;
            cursor: pointer;
            border-top: 1px solid var(--line);
        }

        .loc-list li:first-child {
            border-top: 0;
        }

        .loc-list li span {
            font-size: 13px;
            color: var(--muted);
        }

        .loc-list li:hover,
        .loc-list li[aria-selected=true] {
            background: var(--field);
        }

        .loc-list li[aria-selected=true] {
            box-shadow: inset 3px 0 0 var(--ink);
        }

        .loc-msg {
            margin: 12px 0 0;
        }

        /* Login */
        .login {
            max-width: 440px;
            padding-top: 14vh;
        }

        .login h1 {
            margin: 28px 0 8px;
            font-size: 2.25rem;
            font-weight: 600;
            letter-spacing: -.035em;
            line-height: 1.1;
        }

        .login .panel {
            margin-top: 24px;
        }

        .err {
            min-height: 1.55em;
            margin: 0 0 10px;
            color: var(--err);
            font-size: 14px;
        }

        /* Console */
        .term {
            margin: 0;
            background: var(--term);
            color: var(--term-ink);
            font: 400 12.5px/1.65 var(--mono);
            border-radius: 16px;
            padding: 18px 20px;
            max-height: 280px;
            overflow: auto;
            white-space: pre-wrap;
            word-break: break-all;
        }

        /* Dialog + toast */
        dialog {
            width: min(560px, calc(100% - 32px));
            border: 1px solid var(--line);
            border-radius: 16px;
            padding: 0;
            background: var(--surface);
            color: var(--ink);
        }

        dialog::backdrop {
            background: rgba(10, 16, 13, .55);
        }

        dialog header {
            padding: 16px 20px;
            font-weight: 600;
        }

        dialog .dlg-body {
            margin: 0;
            padding: 0 20px 4px;
            color: var(--muted);
        }

        dialog .term {
            border-radius: 0;
            max-height: 50vh;
        }

        dialog footer {
            display: flex;
            justify-content: flex-end;
            gap: 10px;
            padding: 14px 20px;
        }

        dialog form {
            margin: 0;
        }

        .toast {
            position: fixed;
            left: 50%;
            bottom: 24px;
            transform: translate(-50%, 20px);
            opacity: 0;
            pointer-events: none;
            background: var(--ink);
            color: var(--surface);
            padding: 11px 18px;
            border-radius: 10px;
            font-weight: 500;
            font-size: 14px;
            transition: opacity .2s, transform .2s;
            max-width: calc(100% - 32px);
        }

        .toast.show {
            opacity: 1;
            transform: translate(-50%, 0);
        }

        .toast[data-t="err"] {
            background: var(--err);
            color: #fff;
        }

        @media (max-width:600px) {
            .top {
                margin-bottom: 40px;
            }

            .chip {
                display: none;
            }

            .loc-search {
                flex-direction: column;
            }

            .foot {
                flex-direction: column;
                align-items: stretch;
            }

            .foot .field {
                width: 100%;
            }

            .actions .btn-lg {
                width: 100%;
            }
        }

        @media (prefers-reduced-motion: reduce) {
            * {
                transition: none !important;
            }
        }
    </style>
</head>

<body>
    <?php if (!$authed) : ?>
        <main class="wrap login">
            <div class="brand">Auto Absen <span>MagangHub</span></div>
            <h1>Masuk ke dashboard</h1>
            <p class="detail">Masukkan kata sandi dashboard untuk mengelola presensi.</p>
            <form class="panel" id="form-login">
                <div class="field">
                    <label for="pw">Kata sandi</label>
                    <input type="password" id="pw" name="password" autocomplete="current-password" required autofocus>
                </div>
                <p class="err" id="login-err" role="alert"></p>
                <button type="submit" class="btn btn-primary btn-lg" id="btn-login" style="width:100%">Masuk</button>
            </form>
        </main>
        <script>
            document.getElementById('form-login').addEventListener('submit', e => {
                e.preventDefault();
                const btn = document.getElementById('btn-login'),
                    err = document.getElementById('login-err');
                btn.disabled = true;
                btn.textContent = 'Memeriksa…';
                err.textContent = '';
                fetch('index.php?api=login', {
                        method: 'POST',
                        body: new FormData(e.target)
                    })
                    .then(r => r.json())
                    .then(res => {
                        if (res.status) return location.reload();
                        err.textContent = res.message || 'Gagal masuk.';
                        document.getElementById('pw').select();
                    })
                    .catch(() => {
                        err.textContent = 'Tidak bisa terhubung ke server lokal.';
                    })
                    .finally(() => {
                        btn.disabled = false;
                        btn.textContent = 'Masuk';
                    });
            });
        </script>
    <?php else : ?>
        <main class="wrap">

            <header class="top">
                <div class="brand">Auto Absen <span>MagangHub</span></div>
                <div class="top-r">
                    <div class="chip" id="chip-time">Otomatis pukul <?= $h($env['clock_in_time']) ?> WIB</div>
                    <?php if ($authOn) : ?>
                        <button type="button" class="btn btn-ghost btn-sm" id="btn-logout">Keluar</button>
                    <?php endif; ?>
                </div>
            </header>

            <section class="hero" aria-live="polite">
                <p class="date" id="val-date"><?= date('d F Y') ?></p>
                <h1><i class="dot" id="dot" data-s=""></i><span id="hero-title">Memeriksa status…</span></h1>
                <p class="detail" id="hero-detail"></p>

                <dl class="meta">
                    <div>
                        <dt>Lokasi</dt>
                        <dd id="val-location"><?= $h($env['location']) ?></dd>
                    </div>
                    <div>
                        <dt>Absen otomatis</dt>
                        <dd id="val-time"><?= $h($env['clock_in_time']) ?> WIB</dd>
                    </div>
                </dl>

                <div class="actions">
                    <button type="button" class="btn btn-primary btn-lg" id="btn-run-absen">Absen sekarang</button>
                    <button type="button" class="btn btn-ghost btn-lg" id="btn-dry-run">Simulasi</button>
                    <button type="button" class="btn btn-ghost btn-lg" id="btn-refresh-status">Perbarui status</button>
                </div>
            </section>

            <section class="section">
                <div class="section-head">
                    <h2>Lokasi absen</h2>
                    <span class="hint" id="loc-current">Saat ini: <?= $h($locNow) ?></span>
                </div>
                <div class="panel">
                    <form class="loc-search" id="form-loc" role="search">
                        <label for="loc-q" class="sr">Cari lokasi</label>
                        <input type="search" id="loc-q" placeholder="Nama tempat atau alamat, misalnya Karawang Barat" autocomplete="off" maxlength="120">
                        <button type="submit" class="btn btn-ghost" id="btn-loc-search">Cari</button>
                    </form>
                    <ul class="loc-list" id="loc-list" role="listbox" aria-label="Hasil pencarian lokasi" hidden></ul>
                    <p class="hint loc-msg" id="loc-msg" aria-live="polite">Tekan Enter atau Cari, lalu pilih hasil yang sesuai.</p>
                    <div class="foot-r">
                        <button type="button" class="btn btn-primary" id="btn-loc-save" disabled>Gunakan lokasi ini</button>
                    </div>
                </div>
            </section>

            <section class="section">
                <div class="section-head">
                    <h2>Catatan harian</h2>
                    <span class="hint">Disimpan ke .env, dipakai saat absen berjalan</span>
                </div>
                <form class="panel" id="form-activity">
                    <div class="field">
                        <label for="activity_log">Aktivitas hari ini</label>
                        <textarea id="activity_log" name="activity_log" rows="4" placeholder="Apa yang kamu kerjakan hari ini?"><?= $h($env['activity_log']) ?></textarea>
                    </div>
                    <div class="field">
                        <label for="lesson_learned">Yang dipelajari</label>
                        <textarea id="lesson_learned" name="lesson_learned" rows="3" placeholder="Hal baru yang kamu pelajari"><?= $h($env['lesson_learned']) ?></textarea>
                    </div>
                    <div class="field">
                        <label for="obstacles">Kendala</label>
                        <textarea id="obstacles" name="obstacles" rows="3" placeholder="Hambatan yang kamu temui"><?= $h($env['obstacles']) ?></textarea>
                    </div>
                    <div class="foot">
                        <div class="field">
                            <label for="clock_in_time">Jam absen otomatis</label>
                            <input type="time" id="clock_in_time" name="clock_in_time" value="<?= $h($env['clock_in_time']) ?>">
                        </div>
                        <button type="submit" class="btn btn-primary" id="btn-save-log" disabled>Simpan catatan</button>
                    </div>
                </form>
            </section>

            <section class="section">
                <div class="section-head">
                    <h2>Riwayat eksekusi</h2>
                    <button type="button" class="btn btn-ghost btn-sm" id="btn-refresh-logs">Muat ulang</button>
                </div>
                <pre class="term" id="log-console" tabindex="0">Memuat log…</pre>
                <p class="hint" style="margin:10px 0 0">25 baris terakhir dari absen.log</p>
            </section>
        </main>

        <dialog id="modalDryRun">
            <header>Hasil simulasi absen</header>
            <pre class="term" id="dry-run-content"></pre>
            <footer><button type="button" class="btn btn-ghost" id="btn-close-dry">Tutup</button></footer>
        </dialog>

        <dialog id="dlgConfirm">
            <form method="dialog">
                <header>Kirim presensi sekarang?</header>
                <p class="dlg-body">Presensi dikirim ke MagangHub dengan lokasi dan catatan yang tersimpan saat ini.</p>
                <footer>
                    <button type="submit" value="cancel" class="btn btn-ghost">Batal</button>
                    <button type="submit" value="ok" class="btn btn-primary">Kirim presensi</button>
                </footer>
            </form>
        </dialog>

        <div class="toast" id="toast" role="status"></div>

        <script>
            (() => {
                const $ = s => document.querySelector(s);
                const api = (a, opt) => fetch('index.php?api=' + a, opt).then(r => {
                    if (r.status === 401) {
                        location.reload();
                        throw new Error('401');
                    }
                    if (!r.ok) throw new Error(r.status);
                    return r.json();
                });

                // Tanggal dalam bahasa Indonesia
                $('#val-date').textContent = new Intl.DateTimeFormat('id-ID', {
                    weekday: 'long',
                    day: 'numeric',
                    month: 'long',
                    year: 'numeric'
                }).format(new Date());

                // Toast
                let toastTimer;

                function toast(msg, type) {
                    const t = $('#toast');
                    t.textContent = msg;
                    t.dataset.t = type || '';
                    t.classList.add('show');
                    clearTimeout(toastTimer);
                    toastTimer = setTimeout(() => t.classList.remove('show'), 3200);
                }

                // Tombol sibuk / normal
                function busy(btn, on, label) {
                    if (on) {
                        btn.dataset.label = btn.textContent;
                        btn.textContent = label;
                    } else {
                        btn.textContent = btn.dataset.label;
                    }
                    btn.disabled = on;
                }

                function setHero(state, title, detail) {
                    $('#dot').dataset.s = state;
                    $('#hero-title').textContent = title;
                    $('#hero-detail').textContent = detail || '';
                }

                // Tampilkan lokasi & jam dari data .env
                function applyEnv(env) {
                    if (!env) return;
                    if (env.location) {
                        $('#val-location').textContent = env.location;
                        const coords = env.latitude && env.longitude ? ' (' + (+env.latitude).toFixed(4) + ', ' + (+env.longitude).toFixed(4) + ')' : '';
                        $('#loc-current').textContent = 'Saat ini: ' + env.location + coords;
                    }
                    if (env.clock_in_time) {
                        $('#val-time').textContent = env.clock_in_time + ' WIB';
                        $('#chip-time').textContent = 'Otomatis pukul ' + env.clock_in_time + ' WIB';
                    }
                }

                function checkStatus() {
                    return api('status').then(res => {
                        if (!res.status) throw new Error('status');
                        const line = (res.output || '').split('\n').find(l => l.includes('Status:')) || '';
                        if (res.is_attended) setHero('ok', 'Sudah absen hari ini', line.trim());
                        else setHero('warn', 'Belum absen hari ini', 'Absen otomatis berjalan pukul ' + (res.env.clock_in_time || '15:00') + ' WIB, atau kirim sekarang.');
                        applyEnv(res.env);
                    }).catch(err => {
                        if (err.message !== '401') setHero('err', 'Status tidak terbaca', 'Tidak bisa menjalankan main.py. Periksa path Python dan server lokal.');
                    });
                }

                function fetchLogs() {
                    return api('get_logs').then(res => {
                        const el = $('#log-console');
                        el.textContent = res.logs || 'Belum ada log.';
                        el.scrollTop = el.scrollHeight;
                    }).catch(() => {
                        $('#log-console').textContent = 'Log tidak bisa dimuat.';
                    });
                }

                checkStatus();
                fetchLogs();

                $('#btn-refresh-status').addEventListener('click', e => {
                    const b = e.currentTarget;
                    busy(b, true, 'Memeriksa…');
                    checkStatus().finally(() => {
                        busy(b, false);
                        toast('Status diperbarui');
                    });
                });
                $('#btn-refresh-logs').addEventListener('click', e => {
                    const b = e.currentTarget;
                    busy(b, true, 'Memuat…');
                    fetchLogs().finally(() => busy(b, false));
                });

                // Keluar (hanya ada jika login aktif)
                const logoutBtn = $('#btn-logout');
                if (logoutBtn) logoutBtn.addEventListener('click', () => {
                    busy(logoutBtn, true, 'Keluar…');
                    fetch('index.php?api=logout', {
                        method: 'POST'
                    }).finally(() => location.reload());
                });

                // ---------- Pencarian lokasi (OpenStreetMap Nominatim) ----------
                // Pencarian hanya dijalankan saat Enter/Cari (bukan saat mengetik), sesuai kebijakan Nominatim.
                const locForm = $('#form-loc'),
                    locList = $('#loc-list'),
                    locSave = $('#btn-loc-save');
                let picked = null;
                const locMsg = t => {
                    $('#loc-msg').textContent = t;
                };

                function renderResults(items) {
                    locList.innerHTML = '';
                    picked = null;
                    locSave.disabled = true;
                    items.forEach(r => {
                        const title = r.name || r.display_name.split(',')[0];
                        const li = document.createElement('li');
                        li.setAttribute('role', 'option');
                        li.setAttribute('aria-selected', 'false');
                        li.tabIndex = 0;
                        const strong = document.createElement('strong');
                        strong.textContent = title;
                        const sub = document.createElement('span');
                        sub.textContent = r.display_name;
                        li.append(strong, sub);
                        const pick = () => {
                            locList.querySelectorAll('li').forEach(x => x.setAttribute('aria-selected', 'false'));
                            li.setAttribute('aria-selected', 'true');
                            picked = {
                                location: title,
                                latitude: r.lat,
                                longitude: r.lon
                            };
                            locSave.disabled = false;
                            locMsg('Dipilih: ' + title + '. Klik "Gunakan lokasi ini" untuk menyimpan.');
                        };
                        li.addEventListener('click', pick);
                        li.addEventListener('keydown', e => {
                            if (e.key === 'Enter' || e.key === ' ') {
                                e.preventDefault();
                                pick();
                            }
                        });
                        locList.append(li);
                    });
                    locList.hidden = !items.length;
                }

                locForm.addEventListener('submit', async e => {
                    e.preventDefault();
                    const q = $('#loc-q').value.trim();
                    if (q.length < 3) {
                        locMsg('Ketik minimal 3 huruf untuk mencari.');
                        return;
                    }
                    const btn = $('#btn-loc-search');
                    busy(btn, true, 'Mencari…');
                    try {
                        const r = await fetch('https://nominatim.openstreetmap.org/search?' + new URLSearchParams({
                            q,
                            format: 'jsonv2',
                            limit: '6',
                            countrycodes: 'id',
                            'accept-language': 'id'
                        }));
                        if (!r.ok) throw new Error(r.status);
                        const items = await r.json();
                        renderResults(items);
                        locMsg(items.length ? items.length + ' hasil ditemukan. Pilih yang sesuai.' : 'Tidak ada hasil. Coba nama kota atau kecamatan.');
                    } catch (err) {
                        renderResults([]);
                        locMsg('Pencarian gagal. Periksa koneksi internet lalu coba lagi.');
                    } finally {
                        busy(btn, false);
                    }
                });

                locSave.addEventListener('click', () => {
                    if (!picked) return;
                    busy(locSave, true, 'Menyimpan…');
                    const body = new FormData();
                    Object.entries(picked).forEach(([k, v]) => body.append(k, v));
                    api('save_location', {
                            method: 'POST',
                            body
                        })
                        .then(res => {
                            toast(res.message, res.status ? '' : 'err');
                            if (res.status) {
                                applyEnv(res.env);
                                renderResults([]);
                                $('#loc-q').value = '';
                                locMsg('Lokasi tersimpan. Cari lagi jika ingin mengganti.');
                            }
                        })
                        .catch(err => {
                            if (err.message !== '401') toast('Koneksi ke server gagal.', 'err');
                        })
                        .finally(() => {
                            busy(locSave, false);
                            locSave.disabled = !picked;
                        });
                });

                // ---------- Catatan harian ----------
                const form = $('#form-activity'),
                    saveBtn = $('#btn-save-log');
                const snapshot = () => new URLSearchParams(new FormData(form)).toString();
                let saved = snapshot();
                form.addEventListener('input', () => {
                    saveBtn.disabled = snapshot() === saved;
                });

                form.addEventListener('submit', e => {
                    e.preventDefault();
                    busy(saveBtn, true, 'Menyimpan…');
                    api('save_log', {
                            method: 'POST',
                            body: new FormData(form)
                        })
                        .then(res => {
                            toast(res.message, res.status ? '' : 'err');
                            if (res.status) {
                                saved = snapshot();
                                checkStatus();
                            }
                        })
                        .catch(err => {
                            if (err.message !== '401') toast('Koneksi ke server gagal.', 'err');
                        })
                        .finally(() => {
                            busy(saveBtn, false);
                            saveBtn.disabled = snapshot() === saved;
                        });
                });

                // ---------- Absen manual (dengan dialog konfirmasi) ----------
                const dlgC = $('#dlgConfirm');
                const confirmAbsen = () => new Promise(resolve => {
                    dlgC.returnValue = '';
                    dlgC.addEventListener('close', () => resolve(dlgC.returnValue === 'ok'), {
                        once: true
                    });
                    dlgC.showModal();
                });

                $('#btn-run-absen').addEventListener('click', async e => {
                    if (!(await confirmAbsen())) return;
                    const b = e.currentTarget;
                    busy(b, true, 'Mengirim…');
                    api('absen')
                        .then(res => toast(res.message, res.status ? '' : 'err'))
                        .catch(err => {
                            if (err.message !== '401') toast('Gagal menjalankan skrip.', 'err');
                        })
                        .finally(() => {
                            busy(b, false);
                            checkStatus();
                            fetchLogs();
                        });
                });

                // ---------- Simulasi ----------
                const dlg = $('#modalDryRun');
                $('#btn-dry-run').addEventListener('click', e => {
                    const b = e.currentTarget;
                    busy(b, true, 'Menyiapkan…');
                    api('dry_run')
                        .then(res => {
                            $('#dry-run-content').textContent = res.output || 'Tidak ada data.';
                            dlg.showModal();
                        })
                        .catch(err => {
                            if (err.message !== '401') toast('Gagal mengambil data simulasi.', 'err');
                        })
                        .finally(() => busy(b, false));
                });
                $('#btn-close-dry').addEventListener('click', () => dlg.close());
                [dlg, dlgC].forEach(d => d.addEventListener('click', e => {
                    if (e.target === d) d.close();
                }));
            })();
        </script>
    <?php endif; ?>
</body>

</html>
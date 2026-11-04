<?php

/**
 * Auto Absen MagangHub - Local Control Dashboard
 * Minimalis, solid color, tanpa gradasi. Vanilla JS (tanpa jQuery/Bootstrap).
 */

$envFile = __DIR__ . '/.env';
$logFile = __DIR__ . '/absen.log';
$pyBinary = __DIR__ . '/.venv/Scripts/python.exe';
$mainScript = __DIR__ . '/main.py';

// Baca field tertentu dari .env tanpa mengekspos kredensial
function getSafeEnvData($filePath)
{
    $data = [
        'clock_in_time'  => '15:00',
        'location'       => 'Karawang',
        'activity_log'   => '',
        'lesson_learned' => '',
        'obstacles'      => '',
    ];
    if (!file_exists($filePath)) return $data;
    $map = [
        'CLOCK_IN_TIME' => 'clock_in_time', 'LOCATION' => 'location',
        'ACTIVITY_LOG' => 'activity_log', 'LESSON_LEARNED' => 'lesson_learned',
        'OBSTACLES' => 'obstacles',
    ];
    foreach (file($filePath, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) as $line) {
        $line = trim($line);
        if (strpos($line, '#') === 0 || strpos($line, '=') === false) continue;
        list($key, $val) = explode('=', $line, 2);
        $key = trim($key);
        if (isset($map[$key])) $data[$map[$key]] = trim($val, " \t\n\r\0\x0B\"'");
    }
    return $data;
}

// Simpan catatan harian ke .env secara aman
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

// API Handler (AJAX)
if (isset($_GET['api'])) {
    header('Content-Type: application/json; charset=utf-8');
    $action = $_GET['api'] ?? '';

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

        /* Top bar */
        .top {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            margin-bottom: 56px;
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
        input[type=time] {
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

        .grid2 {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 18px;
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
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 16px 20px;
            font-weight: 600;
        }

        dialog .term {
            border-radius: 0;
            max-height: 50vh;
        }

        dialog footer {
            padding: 14px 20px;
            text-align: right;
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

            .grid2 {
                grid-template-columns: 1fr;
                gap: 0;
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
    <main class="wrap">

        <header class="top">
            <div class="brand">Auto Absen <span>MagangHub</span></div>
            <div class="chip" id="chip-time">Otomatis pukul <?= $h($env['clock_in_time']) ?> WIB</div>
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
                <button type="button" class="btn btn-ghost" id="btn-refresh-logs" style="padding:7px 14px">Muat ulang</button>
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

    <div class="toast" id="toast" role="status"></div>

    <script>
        (() => {
            const $ = s => document.querySelector(s);
            const api = (a, opt) => fetch('index.php?api=' + a, opt).then(r => {
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

            function checkStatus() {
                return api('status').then(res => {
                    if (!res.status) throw new Error('status');
                    const line = (res.output || '').split('\n').find(l => l.includes('Status:')) || '';
                    if (res.is_attended) setHero('ok', 'Sudah absen hari ini', line.trim());
                    else setHero('warn', 'Belum absen hari ini', 'Absen otomatis berjalan pukul ' + (res.env.clock_in_time || '15:00') + ' WIB, atau kirim sekarang.');
                    if (res.env) {
                        if (res.env.location) $('#val-location').textContent = res.env.location;
                        if (res.env.clock_in_time) {
                            $('#val-time').textContent = res.env.clock_in_time + ' WIB';
                            $('#chip-time').textContent = 'Otomatis pukul ' + res.env.clock_in_time + ' WIB';
                        }
                    }
                }).catch(() => setHero('err', 'Status tidak terbaca', 'Tidak bisa menjalankan main.py. Periksa path Python dan server lokal.'));
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

            // Catatan: tombol simpan aktif hanya jika ada perubahan
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
                    .catch(() => toast('Koneksi ke server gagal.', 'err'))
                    .finally(() => {
                        busy(saveBtn, false);
                        saveBtn.disabled = snapshot() === saved;
                    });
            });

            // Absen manual
            $('#btn-run-absen').addEventListener('click', e => {
                if (!confirm('Kirim presensi sekarang?')) return;
                const b = e.currentTarget;
                busy(b, true, 'Mengirim…');
                api('absen')
                    .then(res => toast(res.message, res.status ? '' : 'err'))
                    .catch(() => toast('Gagal menjalankan skrip.', 'err'))
                    .finally(() => {
                        busy(b, false);
                        checkStatus();
                        fetchLogs();
                    });
            });

            // Simulasi
            const dlg = $('#modalDryRun');
            $('#btn-dry-run').addEventListener('click', e => {
                const b = e.currentTarget;
                busy(b, true, 'Menyiapkan…');
                api('dry_run')
                    .then(res => {
                        $('#dry-run-content').textContent = res.output || 'Tidak ada data.';
                        dlg.showModal();
                    })
                    .catch(() => toast('Gagal mengambil data simulasi.', 'err'))
                    .finally(() => busy(b, false));
            });
            $('#btn-close-dry').addEventListener('click', () => dlg.close());
            dlg.addEventListener('click', e => {
                if (e.target === dlg) dlg.close();
            });
        })();
    </script>
</body>

</html>
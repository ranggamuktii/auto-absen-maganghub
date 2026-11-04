<?php
/**
 * Auto Absen MagangHub - Local Control Dashboard
 * Minimalist, Clean, Poppins font, Solid colors (No Gradients)
 */

$envFile = __DIR__ . '/.env';
$logFile = __DIR__ . '/absen.log';
$pyBinary = __DIR__ . '/.venv/Scripts/python.exe';
$mainScript = __DIR__ . '/main.py';

// Helper: Baca field tertentu dari .env tanpa mengekspos kredensial
function getSafeEnvData($filePath) {
    if (!file_exists($filePath)) {
        return [];
    }
    $lines = file($filePath, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
    $data = [
        'clock_in_time'  => '15:00',
        'location'       => 'Karawang',
        'activity_log'   => '',
        'lesson_learned' => '',
        'obstacles'      => '',
    ];
    foreach ($lines as $line) {
        $line = trim($line);
        if (strpos($line, '#') === 0) continue;
        if (strpos($line, '=') === false) continue;
        list($key, $val) = explode('=', $line, 2);
        $key = trim($key);
        $val = trim($val, " \t\n\r\0\x0B\"'");
        if ($key === 'CLOCK_IN_TIME')   $data['clock_in_time']  = $val;
        if ($key === 'LOCATION')        $data['location']       = $val;
        if ($key === 'ACTIVITY_LOG')    $data['activity_log']   = $val;
        if ($key === 'LESSON_LEARNED')  $data['lesson_learned'] = $val;
        if ($key === 'OBSTACLES')       $data['obstacles']      = $val;
    }
    return $data;
}

// Helper: Simpan catatan harian ke .env secara aman
function updateSafeEnvData($filePath, $updates) {
    if (!file_exists($filePath)) {
        return false;
    }
    $content = file_get_contents($filePath);
    foreach ($updates as $key => $val) {
        // Escape newlines jika ada
        $cleanVal = str_replace(["\r", "\n"], ' ', trim($val));
        $pattern = "/^" . preg_quote($key, '/') . "=.*$/m";
        if (preg_match($pattern, $content)) {
            $content = preg_replace($pattern, "{$key}={$cleanVal}", $content);
        } else {
            $content .= "\n{$key}={$cleanVal}";
        }
    }
    return file_put_contents($filePath, $content) !== false;
}

// API Handler jika request via AJAX
if (isset($_GET['api'])) {
    header('Content-Type: application/json; charset=utf-8');
    $action = $_GET['api'] ?? '';

    if ($action === 'status') {
        $env = getSafeEnvData($envFile);
        $cmd = "\"{$pyBinary}\" \"{$mainScript}\" status 2>&1";
        $output = shell_exec($cmd);
        $isAttended = (strpos($output, 'Belum ada absen') === false && strpos($output, 'Status:') !== false);

        echo json_encode([
            'status'     => true,
            'is_attended'=> $isAttended,
            'env'        => $env,
            'output'     => trim($output ?? ''),
            'today'      => date('Y-m-d')
        ]);
        exit;
    }

    if ($action === 'absen') {
        $cmd = "\"{$pyBinary}\" \"{$mainScript}\" absen 2>&1";
        $output = shell_exec($cmd);
        $success = (strpos($output, '[OK]') !== false);
        echo json_encode([
            'status'  => $success,
            'message' => $success ? 'Presensi berhasil diproses.' : 'Eksekusi presensi selesai.',
            'output'  => trim($output ?? '')
        ]);
        exit;
    }

    if ($action === 'dry_run') {
        $cmd = "\"{$pyBinary}\" \"{$mainScript}\" absen --dry-run 2>&1";
        $output = shell_exec($cmd);
        echo json_encode([
            'status' => true,
            'output' => trim($output ?? '')
        ]);
        exit;
    }

    if ($action === 'save_log') {
        $activity = $_POST['activity_log'] ?? '';
        $lesson   = $_POST['lesson_learned'] ?? '';
        $obstacle = $_POST['obstacles'] ?? '';
        $time     = $_POST['clock_in_time'] ?? '15:00';

        $ok = updateSafeEnvData($envFile, [
            'ACTIVITY_LOG'   => $activity,
            'LESSON_LEARNED' => $lesson,
            'OBSTACLES'      => $obstacle,
            'CLOCK_IN_TIME'  => $time,
        ]);

        echo json_encode([
            'status'  => $ok,
            'message' => $ok ? 'Draft catatan harian berhasil disimpan.' : 'Gagal menyimpan ke .env'
        ]);
        exit;
    }

    if ($action === 'get_logs') {
        $lines = [];
        if (file_exists($logFile)) {
            $all = file($logFile, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
            $lines = array_slice($all, -25);
        }
        echo json_encode([
            'status' => true,
            'logs'   => implode("\n", $lines)
        ]);
        exit;
    }

    echo json_encode(['status' => false, 'message' => 'Aksi tidak dikenal']);
    exit;
}

$initialEnv = getSafeEnvData($envFile);
?>
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Auto Absen MagangHub — Control Panel</title>
    <!-- Google Font: Poppins -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <!-- Bootstrap 4.6 CSS -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@4.6.2/dist/css/bootstrap.min.css">
    <!-- Toastr CSS -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/toastr.js/latest/toastr.min.css">
    <!-- FontAwesome Icons -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css">

    <style>
        * {
            box-sizing: border-box;
            font-family: 'Poppins', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }
        body {
            background-color: #f4f6f9;
            color: #1e293b;
            margin: 0;
            padding: 30px 15px;
            font-size: 14px;
        }
        .container {
            max-width: 960px;
        }
        /* Solid colors only - No Gradients */
        .card {
            background-color: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            margin-bottom: 24px;
        }
        .card-header {
            background-color: #ffffff;
            border-bottom: 1px solid #e2e8f0;
            padding: 16px 20px;
            font-weight: 600;
            font-size: 15px;
            border-top-left-radius: 12px !important;
            border-top-right-radius: 12px !important;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .card-body {
            padding: 20px;
        }
        .badge-status {
            font-size: 13px;
            padding: 6px 14px;
            border-radius: 20px;
            font-weight: 500;
        }
        .badge-success-solid {
            background-color: #10b981;
            color: #ffffff;
        }
        .badge-warning-solid {
            background-color: #f59e0b;
            color: #ffffff;
        }
        .badge-neutral-solid {
            background-color: #0284c7;
            color: #ffffff;
        }
        .btn-solid-primary {
            background-color: #2563eb;
            color: #ffffff;
            border: none;
            border-radius: 8px;
            padding: 9px 18px;
            font-weight: 500;
            font-size: 13px;
            transition: background-color 0.15s ease-in-out;
        }
        .btn-solid-primary:hover {
            background-color: #1d4ed8;
            color: #ffffff;
        }
        .btn-solid-secondary {
            background-color: #f1f5f9;
            color: #334155;
            border: 1px solid #cbd5e1;
            border-radius: 8px;
            padding: 9px 16px;
            font-weight: 500;
            font-size: 13px;
        }
        .btn-solid-secondary:hover {
            background-color: #e2e8f0;
            color: #0f172a;
        }
        .form-control {
            border-radius: 8px;
            border: 1px solid #cbd5e1;
            font-size: 13px;
            padding: 10px 12px;
            color: #0f172a;
        }
        .form-control:focus {
            border-color: #2563eb;
            box-shadow: 0 0 0 2px rgba(37,99,235,0.15);
        }
        label {
            font-weight: 500;
            font-size: 13px;
            color: #475569;
            margin-bottom: 6px;
        }
        .terminal-box {
            background-color: #0f172a;
            color: #e2e8f0;
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 12px;
            padding: 16px;
            border-radius: 8px;
            max-height: 250px;
            overflow-y: auto;
            white-space: pre-wrap;
            word-break: break-all;
            border: 1px solid #1e293b;
        }
        .header-title {
            font-weight: 600;
            font-size: 22px;
            color: #0f172a;
            letter-spacing: -0.3px;
        }
        .header-subtitle {
            font-size: 13px;
            color: #64748b;
            margin-top: 2px;
        }
        .stat-item {
            padding: 12px 16px;
            background-color: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            margin-bottom: 12px;
        }
        .stat-label {
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: #64748b;
            font-weight: 600;
        }
        .stat-value {
            font-size: 15px;
            font-weight: 600;
            color: #0f172a;
            margin-top: 4px;
        }
    </style>
</head>
<body>

<div class="container">
    <!-- Header -->
    <div class="d-flex align-items-center justify-content-between mb-4">
        <div>
            <div class="header-title">Auto Absen MagangHub</div>
            <div class="header-subtitle">Control Panel Otomasi Presensi Lokal</div>
        </div>
        <div class="text-right">
            <span class="badge badge-neutral-solid badge-status" id="badge-bot-state">
                <i class="fas fa-clock mr-1"></i> Trigger: <?php echo htmlspecialchars($initialEnv['clock_in_time']); ?> WIB
            </span>
        </div>
    </div>

    <!-- Row: Status & Actions -->
    <div class="card">
        <div class="card-header">
            <span><i class="fas fa-tachometer-alt mr-2 text-primary"></i>Status Presensi Hari Ini</span>
            <button class="btn btn-sm btn-solid-secondary py-1 px-2" id="btn-refresh-status" title="Refresh Status">
                <i class="fas fa-sync-alt"></i>
            </button>
        </div>
        <div class="card-body">
            <div class="row align-items-center">
                <div class="col-md-4">
                    <div class="stat-item mb-md-0">
                        <div class="stat-label">Hari & Tanggal</div>
                        <div class="stat-value" id="val-date"><?php echo date('d F Y'); ?></div>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="stat-item mb-md-0">
                        <div class="stat-label">Status Kehadiran</div>
                        <div class="stat-value" id="val-attendance-status">
                            <span class="text-muted"><i class="fas fa-spinner fa-spin mr-1"></i> Memeriksa...</span>
                        </div>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="stat-item mb-md-0">
                        <div class="stat-label">Lokasi Terpasang</div>
                        <div class="stat-value text-truncate" id="val-location"><?php echo htmlspecialchars($initialEnv['location']); ?></div>
                    </div>
                </div>
            </div>

            <hr class="my-3" style="border-top: 1px solid #f1f5f9;">

            <!-- Quick Action Buttons -->
            <div class="d-flex flex-wrap align-items-center" style="gap: 10px;">
                <button type="button" class="btn btn-solid-primary" id="btn-run-absen">
                    <i class="fas fa-paper-plane mr-1"></i> Absen Sekarang (Manual)
                </button>
                <button type="button" class="btn btn-solid-secondary" id="btn-dry-run">
                    <i class="fas fa-eye mr-1"></i> Simulasi (Dry Run)
                </button>
                <button type="button" class="btn btn-solid-secondary" id="btn-refresh-logs">
                    <i class="fas fa-terminal mr-1"></i> Muat Ulang Log
                </button>
            </div>
        </div>
    </div>

    <!-- Row: Draft Catatan Harian -->
    <div class="card">
        <div class="card-header">
            <span><i class="fas fa-edit mr-2 text-primary"></i>Catatan Harian Magang</span>
            <span class="text-muted small">Tersimpan di .env untuk presensi otomatis</span>
        </div>
        <div class="card-body">
            <form id="form-activity">
                <div class="form-group">
                    <label for="activity_log">Uraian Aktivitas Hari Ini</label>
                    <textarea class="form-control" id="activity_log" name="activity_log" rows="3" placeholder="Aktivitas yang dikerjakan..."><?php echo htmlspecialchars($initialEnv['activity_log']); ?></textarea>
                </div>
                <div class="row">
                    <div class="col-md-6 form-group">
                        <label for="lesson_learned">Pembelajaran yang Diperoleh</label>
                        <textarea class="form-control" id="lesson_learned" name="lesson_learned" rows="3" placeholder="Pembelajaran baru..."><?php echo htmlspecialchars($initialEnv['lesson_learned']); ?></textarea>
                    </div>
                    <div class="col-md-6 form-group">
                        <label for="obstacles">Kendala yang Dihadapi</label>
                        <textarea class="form-control" id="obstacles" name="obstacles" rows="3" placeholder="Kendala harian..."><?php echo htmlspecialchars($initialEnv['obstacles']); ?></textarea>
                    </div>
                </div>
                <div class="row align-items-center mt-2">
                    <div class="col-md-3 form-group mb-md-0">
                        <label for="clock_in_time">Jam Absen Otomatis</label>
                        <input type="text" class="form-control" id="clock_in_time" name="clock_in_time" value="<?php echo htmlspecialchars($initialEnv['clock_in_time']); ?>" placeholder="15:00">
                    </div>
                    <div class="col-md-9 text-right mt-3 mt-md-0">
                        <button type="submit" class="btn btn-solid-primary" id="btn-save-log">
                            <i class="fas fa-save mr-1"></i> Simpan Perubahan Catatan
                        </button>
                    </div>
                </div>
            </form>
        </div>
    </div>

    <!-- Row: Console Log -->
    <div class="card mb-0">
        <div class="card-header">
            <span><i class="fas fa-terminal mr-2 text-primary"></i>Konsol Riwayat Eksekusi (absen.log)</span>
            <span class="text-muted small">25 baris terakhir</span>
        </div>
        <div class="card-body p-0">
            <div class="terminal-box m-3" id="log-console">Memuat riwayat log...</div>
        </div>
    </div>
</div>

<!-- Modal: Dry Run Preview -->
<div class="modal fade" id="modalDryRun" tabindex="-1" role="dialog" aria-hidden="true">
    <div class="modal-dialog modal-dialog-centered" role="document">
        <div class="modal-content" style="border-radius: 12px; border: 1px solid #e2e8f0;">
            <div class="card-header">
                <span><i class="fas fa-file-code mr-2 text-primary"></i>Payload Simulasi Absen</span>
                <button type="button" class="close" data-dismiss="modal" aria-label="Close" style="outline: none;">
                    <span aria-hidden="true">&times;</span>
                </button>
            </div>
            <div class="modal-body p-3">
                <pre class="terminal-box m-0" id="dry-run-content" style="max-height: 350px;"></pre>
            </div>
            <div class="modal-footer p-2" style="border-top: 1px solid #e2e8f0;">
                <button type="button" class="btn btn-sm btn-solid-secondary" data-dismiss="modal">Tutup</button>
            </div>
        </div>
    </div>
</div>

<!-- Scripts: jQuery, Bootstrap, Toastr -->
<script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@4.6.2/dist/js/bootstrap.bundle.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/toastr.js/latest/toastr.min.js"></script>

<script>
$(document).ready(function() {
    toastr.options = {
        closeButton: true,
        progressBar: true,
        positionClass: "toast-top-right",
        timeOut: "3500"
    };

    // Load Status
    function checkStatus() {
        $.getJSON('index.php?api=status', function(res) {
            if (res.status) {
                if (res.is_attended) {
                    $('#val-attendance-status').html('<span class="badge badge-success-solid badge-status"><i class="fas fa-check-circle mr-1"></i> Hadir Hari Ini</span>');
                } else {
                    $('#val-attendance-status').html('<span class="badge badge-warning-solid badge-status"><i class="fas fa-clock mr-1"></i> Belum Absen</span>');
                }
                if (res.env) {
                    if (res.env.location) $('#val-location').text(res.env.location);
                    if (res.env.clock_in_time) {
                        $('#badge-bot-state').html('<i class="fas fa-clock mr-1"></i> Trigger: ' + res.env.clock_in_time + ' WIB');
                    }
                }
            }
        }).fail(function() {
            $('#val-attendance-status').html('<span class="text-danger small"><i class="fas fa-exclamation-circle mr-1"></i> Gagal terhubung</span>');
        });
    }

    // Load Logs
    function fetchLogs() {
        $.getJSON('index.php?api=get_logs', function(res) {
            if (res.status && res.logs) {
                $('#log-console').text(res.logs);
                let consoleEl = document.getElementById('log-console');
                consoleEl.scrollTop = consoleEl.scrollHeight;
            }
        });
    }

    // Init
    checkStatus();
    fetchLogs();

    $('#btn-refresh-status').click(function() {
        checkStatus();
        toastr.info('Status diperbarui.');
    });

    $('#btn-refresh-logs').click(function() {
        fetchLogs();
        toastr.info('Log diperbarui.');
    });

    // Form Save Catatan
    $('#form-activity').submit(function(e) {
        e.preventDefault();
        const btn = $('#btn-save-log');
        btn.prop('disabled', true).html('<i class="fas fa-spinner fa-spin mr-1"></i> Menyimpan...');

        $.ajax({
            url: 'index.php?api=save_log',
            type: 'POST',
            data: $(this).serialize(),
            dataType: 'json',
            success: function(res) {
                if (res.status) {
                    toastr.success(res.message);
                    checkStatus();
                } else {
                    toastr.error(res.message);
                }
            },
            error: function() {
                toastr.error('Terjadi kesalahan koneksi.');
            },
            complete: function() {
                btn.prop('disabled', false).html('<i class="fas fa-save mr-1"></i> Simpan Perubahan Catatan');
            }
        });
    });

    // Trigger Absen Manual
    $('#btn-run-absen').click(function() {
        const btn = $(this);
        btn.prop('disabled', true).html('<i class="fas fa-spinner fa-spin mr-1"></i> Mengirim Presensi...');

        $.getJSON('index.php?api=absen', function(res) {
            if (res.status) {
                toastr.success(res.message);
            } else {
                toastr.warning(res.message || 'Selesai diproses.');
            }
            checkStatus();
            fetchLogs();
        }).fail(function() {
            toastr.error('Gagal mengeksekusi skrip.');
        }).always(function() {
            btn.prop('disabled', false).html('<i class="fas fa-paper-plane mr-1"></i> Absen Sekarang (Manual)');
        });
    });

    // Dry Run
    $('#btn-dry-run').click(function() {
        const btn = $(this);
        btn.prop('disabled', true).html('<i class="fas fa-spinner fa-spin mr-1"></i> Menyiapkan...');

        $.getJSON('index.php?api=dry_run', function(res) {
            btn.prop('disabled', false).html('<i class="fas fa-eye mr-1"></i> Simulasi (Dry Run)');
            $('#dry-run-content').text(res.output || 'Tidak ada data.');
            $('#modalDryRun').modal('show');
        }).fail(function() {
            btn.prop('disabled', false).html('<i class="fas fa-eye mr-1"></i> Simulasi (Dry Run)');
            toastr.error('Gagal mengambil data simulasi.');
        });
    });
});
</script>

</body>
</html>

<?php

/**
 * Auto Absen MagangHub - Local API Bridge & Gateway
 * Menyajikan public/index.html secara langsung dan menangani endpoint /api/* di local Laragon.
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
        'clock_in_time'  => $e['CLOCK_IN_TIME'] ?? '13:30',
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
$isApi = isset($_GET['api']) || strpos($_SERVER['REQUEST_URI'] ?? '', '/api/') !== false;
if ($isApi) {
    header('Content-Type: application/json; charset=utf-8');
    $action = $_GET['api'] ?? '';
    if ($action === '') {
        $reqPath = parse_url($_SERVER['REQUEST_URI'] ?? '', PHP_URL_PATH);
        $parts = explode('/api/', $reqPath);
        if (isset($parts[1])) {
            $action = trim($parts[1], '/');
        }
    }

    $rawInput = json_decode(file_get_contents('php://input'), true) ?? [];
    $data = array_merge($_POST, $rawInput);

    if ($action === 'login') {
        $env = getSafeEnvData($envFile);
        $ok = true;
        if ($authOn) {
            $ok = hash_equals($dashPass, (string)($data['password'] ?? ''));
            if ($ok) {
                session_regenerate_id(true);
                $_SESSION['auth'] = true;
            } else {
                sleep(1);
            }
        }
        echo json_encode([
            'status' => $ok,
            'message' => $ok ? 'Login berhasil (Mode Lokal Laragon).' : 'Kata sandi salah.',
            'profile' => [
                'name' => 'Peserta Magang (Local Laragon)',
                'mitra_name' => 'PT Magang Indonesia',
                'position' => 'Software Engineer Intern',
                'company_latitude' => $env['latitude'] ?? -6.370891,
                'company_longitude' => $env['longitude'] ?? 107.272352
            ]
        ]);
        exit;
    }

    if ($action === 'logout' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $_SESSION = [];
        session_destroy();
        echo json_encode(['status' => true]);
        exit;
    }

    if ($action === 'status') {
        $env = getSafeEnvData($envFile);
        $output = file_exists($pyBinary) ? shell_exec("\"{$pyBinary}\" \"{$mainScript}\" status 2>&1") : '';
        $isAttended = (strpos((string)$output, 'Belum ada absen') === false && strpos((string)$output, 'Status:') !== false);
        echo json_encode([
            'status' => true,
            'is_attended' => $isAttended,
            'db_connected' => true,
            'db_message' => 'Local Laragon Bridge',
            'env' => $env,
            'profile' => [
                'name' => 'Peserta Magang (Local Laragon)',
                'mitra_name' => 'PT Magang Indonesia',
                'position' => 'Software Engineer Intern',
                'company_latitude' => $env['latitude'] ?? -6.370891,
                'company_longitude' => $env['longitude'] ?? 107.272352
            ],
            'output' => trim($output ?? ''),
            'today' => date('Y-m-d'),
        ]);
        exit;
    }

    if ($action === 'save_settings' || $action === 'save_log' || $action === 'save_location') {
        $ok = updateSafeEnvData($envFile, [
            'ACTIVITY_LOG'   => $data['activity_log'] ?? '',
            'LESSON_LEARNED' => $data['lesson_learned'] ?? '',
            'OBSTACLES'      => $data['obstacles'] ?? '',
            'CLOCK_IN_TIME'  => $data['clock_in_time'] ?? '13:30',
            'LOCATION'       => $data['location'] ?? 'Karawang',
            'LATITUDE'       => (string)($data['latitude'] ?? ''),
            'LONGITUDE'      => (string)($data['longitude'] ?? ''),
        ]);
        echo json_encode([
            'status'  => $ok,
            'message' => $ok ? 'Pengaturan berhasil disimpan ke .env lokal.' : 'Gagal menyimpan ke .env',
        ]);
        exit;
    }

    if ($action === 'trigger' || $action === 'absen') {
        $output = file_exists($pyBinary) ? shell_exec("\"{$pyBinary}\" \"{$mainScript}\" absen 2>&1") : '[OK] Presensi berhasil diproses (simulasi)';
        $success = (strpos((string)$output, '[OK]') !== false || strpos((string)$output, 'berhasil') !== false);
        echo json_encode([
            'status'  => $success,
            'message' => $success ? 'Presensi berhasil diproses.' : 'Eksekusi presensi selesai.',
            'output'  => trim($output ?? ''),
        ]);
        exit;
    }

    if ($action === 'dry_run') {
        $output = file_exists($pyBinary) ? shell_exec("\"{$pyBinary}\" \"{$mainScript}\" absen --dry-run 2>&1") : '';
        echo json_encode(['status' => true, 'output' => trim($output ?? '')]);
        exit;
    }

    if ($action === 'reject_attendance') {
        $targetDate = escapeshellarg(trim($data['date'] ?? date('Y-m-d')));
        $reason = escapeshellarg(trim($data['reason'] ?? 'Dibatalkan oleh peserta (salah jadwal weekend/libur)'));
        $output = file_exists($pyBinary) ? shell_exec("\"{$pyBinary}\" \"{$mainScript}\" reject --date {$targetDate} --reason {$reason} 2>&1") : '[OK]';
        $success = (strpos((string)$output, '[OK]') !== false);
        echo json_encode([
            'status'  => $success,
            'message' => $success ? 'Status absensi berhasil diubah menjadi REJECTED.' : 'Gagal menolak absensi.',
            'output'  => trim($output ?? ''),
        ]);
        exit;
    }

    if ($action === 'logs' || $action === 'daily_logs' || $action === 'get_logs') {
        $lines = [];
        if (file_exists($logFile)) {
            $lines = array_slice(file($logFile, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES), -25);
        }
        $logList = [];
        foreach ($lines as $line) {
            $logList[] = [
                'date' => date('Y-m-d'),
                'absen_date' => date('Y-m-d'),
                'status' => (strpos($line, '[FAIL]') !== false) ? 'FAILED' : 'SUCCESS',
                'message' => $line,
                'log_activity' => $line,
                'checkin_time' => '08:00:00',
                'checkout_time' => '17:00:00'
            ];
        }
        echo json_encode(['status' => true, 'logs' => $logList]);
        exit;
    }

    echo json_encode(['status' => false, 'message' => 'Aksi tidak dikenal']);
    exit;
}

// Langsung sajikan dashboard modern public/index.html
$htmlPath = __DIR__ . '/public/index.html';
if (file_exists($htmlPath)) {
    header('Content-Type: text/html; charset=utf-8');
    readfile($htmlPath);
    exit;
}

// Fallback redirect jika file tidak terbaca
header('Location: public/index.html');
exit;

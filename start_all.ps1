<#
.SYNOPSIS
    Khởi động toàn bộ hệ thống SOA (4 Django Backends, Dev API Gateway, Vite Frontend) không cần Docker.
.DESCRIPTION
    Script tự động kiểm tra và chuẩn bị môi trường:
    - Kiểm tra Python, Node.js, npm
    - Tự động tạo venv và cài đặt dependencies nếu chưa có
    - Tự động cài đặt node_modules cho frontend nếu chưa có
    - Cấu hình chạy độc lập không phụ thuộc Consul
    - Mở 6 cửa sổ console riêng biệt cho từng thành phần
.PARAMETER DryRun
    Chỉ kiểm tra điều kiện tiên quyết và in các lệnh mà không chạy thật.
.PARAMETER SetupOnly
    Chỉ cài đặt môi trường ảo (venv) và dependencies rồi thoát.
#>

[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$SetupOnly
)

$ErrorActionPreference = "Stop"
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  SOA GRADUATION PROJECT - KHỞI ĐỘNG HỆ THỐNG (NO DOCKER) " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Kiểm tra công cụ cơ bản
Write-Host "[1/4] Kiểm tra các công cụ hệ thống..." -ForegroundColor Yellow

$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    Write-Error "Không tìm thấy Python trên PATH. Vui lòng cài đặt Python 3.10+."
    exit 1
}
Write-Host "  [OK] Python: $($pythonCmd.Source)" -ForegroundColor Green

$nodeCmd = Get-Command node -ErrorAction SilentlyContinue
if (-not $nodeCmd) {
    Write-Error "Không tìm thấy Node.js trên PATH. Vui lòng cài đặt Node.js 18+."
    exit 1
}
Write-Host "  [OK] Node.js: $($nodeCmd.Source)" -ForegroundColor Green

$npmCmd = Get-Command npm.cmd -ErrorAction SilentlyContinue
if (-not $npmCmd) {
    $npmCmd = Get-Command npm -ErrorAction SilentlyContinue
}
if (-not $npmCmd) {
    Write-Error "Không tìm thấy npm trên PATH."
    exit 1
}
Write-Host "  [OK] npm: $($npmCmd.Source)" -ForegroundColor Green

# 2. Chuẩn bị Python Virtual Environment
Write-Host "[2/4] Kiểm tra môi trường ảo Python (venv)..." -ForegroundColor Yellow

$sharedVenvPath = Join-Path $ScriptRoot ".venv"
$venvPython = Join-Path $sharedVenvPath "Scripts\python.exe"

# Kiểm tra nếu chưa có venv chung
if (-not (Test-Path $venvPython)) {
    # Kiểm tra xem có service nào đã có venv chưa
    $existingVenv = $null
    foreach ($svc in @('auth-service', 'academic-services', 'regist-service', 'topic-service')) {
        $candidate = Join-Path $ScriptRoot "services\$svc\venv\Scripts\python.exe"
        if (Test-Path $candidate) {
            $existingVenv = $candidate
            break
        }
    }

    if ($existingVenv) {
        $venvPython = $existingVenv
        Write-Host "  [OK] Tìm thấy venv có sẵn: $venvPython" -ForegroundColor Green
    } else {
        if ($DryRun) {
            Write-Host "  [DRY RUN] Sẽ tạo venv tại: $sharedVenvPath và cài đặt requirements.txt" -ForegroundColor Magenta
        } else {
            Write-Host "  [*] Đang khởi tạo môi trường ảo Python tại .venv..." -ForegroundColor Cyan
            & python -m venv $sharedVenvPath
            if (-not (Test-Path $venvPython)) {
                Write-Error "Khởi tạo venv thất bại!"
                exit 1
            }
            Write-Host "  [*] Đang cài đặt thư viện backend (Django, DRF, PyJWT...)..." -ForegroundColor Cyan
            $reqFile = Join-Path $ScriptRoot "services\auth-service\requirements.txt"
            & $venvPython -m pip install --upgrade pip --quiet
            & $venvPython -m pip install -r $reqFile
            Write-Host "  [OK] Đã hoàn thành cài đặt thư viện Python!" -ForegroundColor Green
        }
    }
} else {
    Write-Host "  [OK] Sử dụng venv tại: $sharedVenvPath" -ForegroundColor Green
}

# Tạo liên kết tượng trưng (junction) cho từng service venv nếu chưa có để tương thích start-services.bat
if (-not $DryRun) {
    foreach ($svc in @('auth-service', 'academic-services', 'regist-service', 'topic-service')) {
        $svcVenv = Join-Path $ScriptRoot "services\$svc\venv"
        if (-not (Test-Path $svcVenv) -and (Test-Path $sharedVenvPath)) {
            cmd.exe /c "mklink /J `"$svcVenv`" `"$sharedVenvPath`"" | Out-Null
        }
    }
}

# 3. Chuẩn bị Frontend (node_modules)
Write-Host "[3/4] Kiểm tra thư viện Frontend (fe)..." -ForegroundColor Yellow
$feNodeModules = Join-Path $ScriptRoot "fe\node_modules"
if (-not (Test-Path $feNodeModules)) {
    if ($DryRun) {
        Write-Host "  [DRY RUN] Sẽ chạy 'npm install' trong thư mục fe" -ForegroundColor Magenta
    } else {
        Write-Host "  [*] Chưa tìm thấy fe/node_modules. Đang chạy npm install..." -ForegroundColor Cyan
        Push-Location (Join-Path $ScriptRoot "fe")
        try {
            & $npmCmd install
        } finally {
            Pop-Location
        }
        Write-Host "  [OK] Đã cài đặt xong frontend dependencies!" -ForegroundColor Green
    }
} else {
    Write-Host "  [OK] Frontend dependencies đã sẵn sàng." -ForegroundColor Green
}

if ($SetupOnly) {
    Write-Host "`nĐã hoàn thành chuẩn bị môi trường! (SetupOnly flag activated)" -ForegroundColor Green
    exit 0
}

# 4. Khởi chạy các service
Write-Host "[4/4] Khởi chạy các dịch vụ..." -ForegroundColor Yellow

$sharedKey = "soa-shared-jwt-secret-key-2026-local-testing"
$devGatewayScript = Join-Path $ScriptRoot "api-gateway\dev_gateway.py"

$servicesToLaunch = @(
    @{
        Name = "SOA API Gateway :8000"
        Dir = $ScriptRoot
        Cmd = "`"$venvPython`" `"$devGatewayScript`" 8000"
        Env = @{}
    },
    @{
        Name = "SOA Auth Service :8001"
        Dir = (Join-Path $ScriptRoot "services\auth-service")
        Cmd = "`"$venvPython`" manage.py runserver 0.0.0.0:8001"
        Env = @{
            "CONSUL_AUTO_REGISTER" = "false"
            "JWT_SIGNING_KEY" = $sharedKey
            "INTERNAL_SERVICE_TOKEN" = "Y@ngKlee18072005"
        }
    },
    @{
        Name = "SOA Academic Service :8002"
        Dir = (Join-Path $ScriptRoot "services\academic-services")
        Cmd = "`"$venvPython`" manage.py runserver 0.0.0.0:8002"
        Env = @{
            "CONSUL_AUTO_REGISTER" = "false"
            "AUTH_NAMES_DISCOVERY_ENABLED" = "false"
            "AUTH_IDENTITY_DISCOVERY_ENABLED" = "false"
            "AUTH_NAMES_BASE_URL" = "http://localhost:8001"
            "AUTH_IDENTITY_BASE_URL" = "http://localhost:8001"
            "JWT_SIGNING_KEY" = $sharedKey
            "INTERNAL_SERVICE_TOKEN" = "Y@ngKlee18072005"
        }
    },
    @{
        Name = "SOA Regist Service :8003"
        Dir = (Join-Path $ScriptRoot "services\regist-service")
        Cmd = "`"$venvPython`" manage.py runserver 0.0.0.0:8003"
        Env = @{
            "CONSUL_AUTO_REGISTER" = "false"
            "ACADEMIC_DISCOVERY_ENABLED" = "false"
            "TOPIC_DISCOVERY_ENABLED" = "false"
            "ACADEMIC_BASE_URL" = "http://localhost:8002"
            "TOPIC_BASE_URL" = "http://localhost:8004"
            "JWT_SIGNING_KEY" = $sharedKey
            "INTERNAL_SERVICE_TOKEN" = "Y@ngKlee18072005"
        }
    },
    @{
        Name = "SOA Topic Service :8004"
        Dir = (Join-Path $ScriptRoot "services\topic-service")
        Cmd = "`"$venvPython`" manage.py runserver 0.0.0.0:8004"
        Env = @{
            "CONSUL_AUTO_REGISTER" = "false"
            "ACADEMIC_DISCOVERY_ENABLED" = "false"
            "REGISTRATION_DISCOVERY_ENABLED" = "false"
            "ACADEMIC_BASE_URL" = "http://localhost:8002"
            "REGISTRATION_BASE_URL" = "http://localhost:8003"
            "JWT_SIGNING_KEY" = $sharedKey
            "INTERNAL_SERVICE_TOKEN" = "Y@ngKlee18072005"
        }
    },
    @{
        Name = "SOA Frontend :5173"
        Dir = (Join-Path $ScriptRoot "fe")
        Cmd = "npm.cmd run dev"
        Env = @{
            "VITE_API_PROXY_TARGET" = "http://localhost:8000"
        }
    }
)

foreach ($item in $servicesToLaunch) {
    $envPrefix = ""
    foreach ($k in $item.Env.Keys) {
        $envPrefix += "set $k=$($item.Env[$k]) && "
    }
    $fullCmd = "cd /d `"$($item.Dir)`" && title $($item.Name) && $envPrefix$($item.Cmd)"

    if ($DryRun) {
        Write-Host "  [DRY RUN] $($item.Name):" -ForegroundColor Magenta
        Write-Host "    $fullCmd" -ForegroundColor DarkGray
    } else {
        Write-Host "  [*] Đang mở: $($item.Name)..." -ForegroundColor Cyan
        Start-Process "cmd.exe" -ArgumentList "/d", "/k", "`"$fullCmd`""
    }
}

Write-Host "`n==========================================================" -ForegroundColor Green
if ($DryRun) {
    Write-Host "  DRY RUN HOÀN TẤT: Tất cả điều kiện tiên quyết hợp lệ! " -ForegroundColor Green
} else {
    Write-Host "  HỆ THỐNG ĐÃ ĐƯỢC KHỞI CHẠY THÀNH CÔNG TRÊN CÁC CỬA SỔ!  " -ForegroundColor Green
}
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "  Frontend Web App:   http://localhost:5173" -ForegroundColor White
Write-Host "  API Gateway:        http://localhost:8000" -ForegroundColor White
Write-Host "  Swagger UI / Docs:  http://localhost:8000/docs/ (hoặc /swagger/)" -ForegroundColor White
Write-Host "  --------------------------------------------------------" -ForegroundColor DarkGray
Write-Host "  Health check các dịch vụ:" -ForegroundColor White
Write-Host "  - Gateway:             http://localhost:8000/health/" -ForegroundColor DarkCyan
Write-Host "  - Auth Service:        http://localhost:8001/health/" -ForegroundColor DarkCyan
Write-Host "  - Academic Service:    http://localhost:8002/health/" -ForegroundColor DarkCyan
Write-Host "  - Regist Service:      http://localhost:8003/health/" -ForegroundColor DarkCyan
Write-Host "  - Topic Service:       http://localhost:8004/health/" -ForegroundColor DarkCyan
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "[*] Để dừng một dịch vụ: Nhấn Ctrl+C tại cửa sổ tương ứng." -ForegroundColor Yellow

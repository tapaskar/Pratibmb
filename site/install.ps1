# Pratibmb Installer for Windows
# Usage: irm https://pratibmb.com/install.ps1 | iex
# Or:   powershell -ExecutionPolicy Bypass -File install.ps1

$ErrorActionPreference = "Stop"
$VERSION = "0.2.1"
$REPO = "tapaskar/Pratibmb"
$INSTALL_DIR = "$env:USERPROFILE\Pratibmb"

function Write-Info($msg)  { Write-Host "[pratibmb] $msg" -ForegroundColor Cyan }
function Write-Ok($msg)    { Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Warn($msg)  { Write-Host "[!] $msg" -ForegroundColor Yellow }
function Write-Fail($msg)  { Write-Host "[X] $msg" -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "  Pratibmb - Chat with your 10-years-younger self" -ForegroundColor Cyan
Write-Host "  100% local. No cloud. No telemetry." -ForegroundColor DarkGray
Write-Host ""

# ── Step 1: Check Python ──────────────────────────────────────────────
Write-Info "Checking Python..."

$PYTHON = $null
foreach ($cmd in @("python", "python3", "py -3")) {
    try {
        $pyVersion = & cmd /c "$cmd --version 2>&1"
        if ($pyVersion -match "Python (\d+)\.(\d+)") {
            $major = [int]$Matches[1]
            $minor = [int]$Matches[2]
            if ($major -eq 3 -and $minor -ge 10) {
                $PYTHON = $cmd
                Write-Ok "Found $cmd ($pyVersion)"
                break
            } else {
                Write-Warn "$cmd is $pyVersion (need 3.10+), skipping"
            }
        }
    } catch {
        # Not found, try next
    }
}

# Try Microsoft Store Python
if (-not $PYTHON) {
    try {
        $pyVersion = & python3 --version 2>&1
        if ($pyVersion -match "Python 3\.(\d+)") {
            if ([int]$Matches[1] -ge 10) {
                $PYTHON = "python3"
                Write-Ok "Found python3 ($pyVersion)"
            }
        }
    } catch {}
}

if (-not $PYTHON) {
    Write-Host ""
    Write-Warn "Python 3.10+ not found."
    Write-Host ""
    Write-Host "  Install Python from: https://www.python.org/downloads/" -ForegroundColor White
    Write-Host ""
    Write-Host "  IMPORTANT: Check 'Add Python to PATH' during installation!" -ForegroundColor Yellow
    Write-Host ""

    $response = Read-Host "Would you like to open the Python download page? (Y/n)"
    if ($response -ne "n" -and $response -ne "N") {
        Start-Process "https://www.python.org/downloads/"
    }
    Write-Fail "Install Python 3.10+, then run this script again."
}

# ── Step 2: Check Git ─────────────────────────────────────────────────
Write-Info "Checking Git..."

$hasGit = $false
try {
    git --version | Out-Null
    $hasGit = $true
    Write-Ok "Git found"
} catch {
    Write-Warn "Git not found. Will download as ZIP instead."
}

# ── Step 3: Get the repo ──────────────────────────────────────────────
Write-Info "Setting up Pratibmb at $INSTALL_DIR..."

if (Test-Path "$INSTALL_DIR\pratibmb\__init__.py") {
    Write-Ok "Pratibmb package already exists"
    if ($hasGit -and (Test-Path "$INSTALL_DIR\.git")) {
        Write-Info "Pulling latest..."
        Push-Location $INSTALL_DIR
        git pull origin main 2>$null
        Pop-Location
    }
} elseif ($hasGit) {
    Write-Info "Cloning repository..."
    git clone --depth 1 "https://github.com/$REPO.git" $INSTALL_DIR
    Write-Ok "Repository cloned"
} else {
    Write-Info "Downloading as ZIP..."
    $zipUrl = "https://github.com/$REPO/archive/refs/heads/main.zip"
    $zipPath = "$env:TEMP\pratibmb-main.zip"
    Invoke-WebRequest -Uri $zipUrl -OutFile $zipPath
    Expand-Archive -Path $zipPath -DestinationPath $env:TEMP -Force
    if (Test-Path $INSTALL_DIR) { Remove-Item $INSTALL_DIR -Recurse -Force }
    Move-Item "$env:TEMP\Pratibmb-main" $INSTALL_DIR
    Remove-Item $zipPath -Force
    Write-Ok "Downloaded and extracted"
}

# ── Step 4: Install Python dependencies ───────────────────────────────
Write-Info "Installing Python dependencies..."
Write-Info "(This may take a few minutes on first install)"

Push-Location $INSTALL_DIR

# Upgrade pip first
& $PYTHON -m pip install --quiet --upgrade pip 2>$null

# Install the package
# Use --prefer-binary to avoid compiling llama-cpp-python from source
Write-Info "Installing pratibmb package (using pre-built wheels where possible)..."
& $PYTHON -m pip install --prefer-binary -e . 2>&1 | Select-Object -Last 5

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Warn "pip install failed. This usually means llama-cpp-python couldn't find a pre-built wheel."
    Write-Host ""
    Write-Host "  Option 1: Install pre-built llama-cpp-python wheel:" -ForegroundColor White
    Write-Host "    pip install llama-cpp-python --prefer-binary" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Option 2: If you have an NVIDIA GPU, install with CUDA:" -ForegroundColor White
    Write-Host "    set CMAKE_ARGS=-DGGML_CUDA=on" -ForegroundColor Cyan
    Write-Host "    pip install llama-cpp-python --no-cache-dir" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Option 3: Install Visual Studio Build Tools first:" -ForegroundColor White
    Write-Host "    https://visualstudio.microsoft.com/visual-cpp-build-tools/" -ForegroundColor Cyan
    Write-Host "    (select 'Desktop development with C++')" -ForegroundColor DarkGray
    Write-Host ""
    Write-Fail "Fix the above, then run this script again."
}

# Verify import
try {
    & $PYTHON -c "import pratibmb; print('ok')" 2>$null
    Write-Ok "Python package installed and importable"
} catch {
    Write-Warn "Package installed but import check failed (may still work)"
}

Pop-Location

# ── Step 5: Install the desktop app ───────────────────────────────────
Write-Info "Installing desktop app..."

$exeUrl = "https://github.com/$REPO/releases/download/v$VERSION/Pratibmb_${VERSION}_x64-setup.exe"
$exePath = "$env:TEMP\Pratibmb_setup.exe"

Write-Info "Downloading Pratibmb installer..."
try {
    Invoke-WebRequest -Uri $exeUrl -OutFile $exePath
    Write-Ok "Downloaded installer"
} catch {
    Write-Warn "Download failed. You can download manually from:"
    Write-Host "  https://github.com/$REPO/releases/latest" -ForegroundColor Cyan
    $exePath = $null
}

if ($exePath -and (Test-Path $exePath)) {
    Write-Info "Running installer (you may see a UAC prompt)..."
    Start-Process -FilePath $exePath -Wait
    Remove-Item $exePath -Force -ErrorAction SilentlyContinue
    Write-Ok "Desktop app installed"
}

# ── Step 6: Set PRATIBMB_ROOT for the desktop app ─────────────────────
Write-Info "Configuring environment..."

# Set PRATIBMB_ROOT so the Tauri app can find the Python package
[System.Environment]::SetEnvironmentVariable("PRATIBMB_ROOT", $INSTALL_DIR, "User")
$env:PRATIBMB_ROOT = $INSTALL_DIR
Write-Ok "PRATIBMB_ROOT set to $INSTALL_DIR"

# ── Step 7: Verify ────────────────────────────────────────────────────
Write-Info "Running diagnostics..."

try {
    & $PYTHON -m pratibmb.cli doctor 2>$null
} catch {
    Write-Warn "Could not run diagnostics (non-critical)"
}

# ── Done ──────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  Installation complete!" -ForegroundColor Green
Write-Host ""
Write-Host "  To launch: search 'Pratibmb' in the Start menu" -ForegroundColor White
Write-Host "  Or CLI:    pratibmb --help" -ForegroundColor White
Write-Host ""
Write-Host "  First launch downloads AI models (~2.5GB)." -ForegroundColor DarkGray
Write-Host "  After that, it works fully offline." -ForegroundColor DarkGray
Write-Host ""
Write-Host "  https://pratibmb.com" -ForegroundColor Cyan
Write-Host ""

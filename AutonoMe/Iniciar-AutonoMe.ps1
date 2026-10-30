$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backend = Join-Path $root "AutonoMe-Backend"
$frontend = Join-Path $root "AutonoMe-Frontend"
$envFile = Join-Path $backend ".env"
$envExample = Join-Path $backend ".env.example"

function Stop-WithMessage([string]$message) {
    Write-Host ""
    Write-Host $message -ForegroundColor Yellow
    exit 1
}

if (-not (Test-Path -LiteralPath $envFile)) {
    Stop-WithMessage "Arquivo .env nao encontrado. Copie AutonoMe-Backend\.env.example para AutonoMe-Backend\.env e configure AUTONOME_SECRET_KEY."
}

$secretLine = Get-Content -LiteralPath $envFile | Where-Object { $_ -match '^\s*AUTONOME_SECRET_KEY\s*=' } | Select-Object -First 1
$secret = if ($secretLine) { ($secretLine -split '=', 2)[1].Trim().Trim('"').Trim("'") } else { "" }
if ($secret.Length -lt 32) {
    Stop-WithMessage "AUTONOME_SECRET_KEY ausente ou invalida. Configure no .env uma chave com pelo menos 32 caracteres. Se precisar, copie .env.example para .env e siga as instrucoes de SEGURANCA.md."
}
Remove-Variable secret, secretLine

$python = $null
$pythonPrefix = @()
$pythonCandidates = @()
$venvPython = Join-Path $backend ".venv\Scripts\python.exe"
if (Test-Path -LiteralPath $venvPython) {
    $pythonCandidates += [PSCustomObject]@{ Path = $venvPython; Prefix = @(); Packages = $null }
}

$launcher = Get-Command py.exe -ErrorAction SilentlyContinue
if ($launcher) {
    $pythonCandidates += [PSCustomObject]@{ Path = $launcher.Source; Prefix = @("-3"); Packages = $null }
}

$runtimePython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$runtimePackages = Join-Path $backend ".server-deps"
if ((Test-Path -LiteralPath $runtimePython) -and (Test-Path -LiteralPath $runtimePackages)) {
    $pythonCandidates += [PSCustomObject]@{ Path = $runtimePython; Prefix = @(); Packages = $runtimePackages }
}

foreach ($candidate in $pythonCandidates) {
    try {
        $checkArgs = @($candidate.Prefix) + @("-c", "import uvicorn, sqlalchemy, dotenv")
        if ($candidate.Packages) { $env:PYTHONPATH = $candidate.Packages }
        & $candidate.Path @checkArgs *> $null
        if ($LASTEXITCODE -eq 0) {
            $python = $candidate.Path
            $pythonPrefix = @($candidate.Prefix)
            break
        }
    } catch {
    }
}

if (-not $python) {
    Stop-WithMessage "Python com as dependencias do projeto nao foi encontrado. Instale AutonoMe-Backend\requirements.txt ou configure o ambiente local do projeto."
}

$chrome = $null
$chromeBases = @($env:ProgramFiles, ${env:ProgramFiles(x86)}, $env:LOCALAPPDATA)
foreach ($base in $chromeBases) {
    if (-not $base) { continue }
    $candidate = Join-Path $base "Google\Chrome\Application\chrome.exe"
    if (Test-Path -LiteralPath $candidate) { $chrome = $candidate; break }
}
if (-not $chrome) {
    $chromeCommand = Get-Command chrome.exe -ErrorAction SilentlyContinue
    if ($chromeCommand) { $chrome = $chromeCommand.Source }
}
if (-not $chrome) { Stop-WithMessage "Google Chrome nao foi encontrado. Instale o Chrome e tente novamente." }

function Test-Port([int]$port) {
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $client.Connect("127.0.0.1", $port)
        return $true
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

function Test-ApiReady {
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:8000/categorias" -UseBasicParsing -TimeoutSec 2
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

if (-not (Test-Port 8000)) {
    $apiArgs = $pythonPrefix + @("-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000", "--reload")
    Start-Process -FilePath $python -ArgumentList $apiArgs -WorkingDirectory $backend -WindowStyle Hidden
}
if (-not (Test-Port 5500)) {
    $webArgs = $pythonPrefix + @("-m", "http.server", "5500", "--bind", "127.0.0.1")
    Start-Process -FilePath $python -ArgumentList $webArgs -WorkingDirectory $frontend -WindowStyle Hidden
}

Write-Host "Iniciando AutonoMe..."
$deadline = (Get-Date).AddSeconds(45)
while ((-not (Test-ApiReady) -or -not (Test-Port 5500)) -and (Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 1
}
if (-not (Test-ApiReady)) {
    Stop-WithMessage "A API nao respondeu em http://127.0.0.1:8000. Confira se a porta 8000 esta livre e se as dependencias estao instaladas. Nenhum segredo foi exibido."
}
if (-not (Test-Port 5500)) {
    Stop-WithMessage "O site nao iniciou em http://127.0.0.1:5500. Confira se a porta 5500 esta livre."
}

Write-Host "API e site prontos. Abrindo o AutonoMe no Google Chrome."
Start-Process -FilePath $chrome -ArgumentList @("--new-tab", "http://127.0.0.1:5500/")

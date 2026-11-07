$ErrorActionPreference = "Stop"
$project = Join-Path $PSScriptRoot "../Alimenta/marachef_mvp_funcional/marachef_mvp"
$envPath = Join-Path $project ".env"

if (Test-Path -LiteralPath $envPath) {
    Write-Output "O .env existente foi preservado."
    exit 0
}

function New-HexSecret {
    $bytes = New-Object byte[] 32
    $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $generator.GetBytes($bytes)
        return [BitConverter]::ToString($bytes).Replace("-", "").ToLowerInvariant()
    } finally {
        $generator.Dispose()
    }
}

$dbPassword = New-HexSecret
$sessionSecret = New-HexSecret
$template = Get-Content -LiteralPath (Join-Path $project ".env.example") -Raw -Encoding UTF8
$template = $template -replace "(?m)^POSTGRES_PASSWORD=(?=\r?$)", "POSTGRES_PASSWORD=$dbPassword"
$template = $template -replace "(?m)^DATABASE_URL=(?=\r?$)", "DATABASE_URL=postgresql://marachef:${dbPassword}@127.0.0.1:5433/marachef"
$template = $template -replace "(?m)^MARACHEF_SESSION_SECRET=(?=\r?$)", "MARACHEF_SESSION_SECRET=$sessionSecret"

$stream = [System.IO.File]::Open($envPath, [System.IO.FileMode]::CreateNew)
try {
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($template)
    $stream.Write($bytes, 0, $bytes.Length)
} finally {
    $stream.Dispose()
}
Write-Output ".env local criado. Configure GEMINI_API_KEY nesse arquivo para usar o chat e o Gemini."

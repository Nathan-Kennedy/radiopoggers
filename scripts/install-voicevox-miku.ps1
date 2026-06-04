$ErrorActionPreference = "Continue"

Write-Host "RadioPoggers - voz Miku com entonacao (VOICEVOX, gratis e local)"
Write-Host ""
Write-Host "A voz OFICIAL da Hatsune Miku (Vocaloid) e paga e protegida por direitos autorais."
Write-Host "O caminho gratis/legal mais proximo e o VOICEVOX Engine com speakers Song"
Write-Host "(tom idol/anime + entonacao expressiva)."
Write-Host ""

$voicevoxUrl = "https://voicevox.hiroshiba.jp/"
$releasesUrl = "https://github.com/VOICEVOX/voicevox/releases/latest"

Write-Host "[1/3] Abrindo pagina de download do VOICEVOX..."
Start-Process $voicevoxUrl

Write-Host "[2/3] Abrindo releases (Windows installer)..."
Start-Process $releasesUrl

Write-Host ""
Write-Host "Depois de instalar:"
Write-Host "  - Abra o VOICEVOX Engine (icone na bandeja)"
Write-Host "  - Confirme: http://127.0.0.1:50021/version"
Write-Host ""
Write-Host "Opcional (forcar so VOICEVOX, sem edge-tts):"
Write-Host '  $env:RADIOPOGGERS_MIKU_TTS = "voicevox"'
Write-Host '  $env:RADIOPOGGERS_MIKU_REQUIRE_VOICEVOX = "1"'
Write-Host ""
Write-Host "Speaker automatico (padrao): Song 3000/3002 (tom doce + entonacao)."
Write-Host "Fixar um speaker:"
Write-Host '  $env:RADIOPOGGERS_VOICEVOX_SPEAKER = "3000"'
Write-Host ""

try {
  $version = Invoke-RestMethod -Uri "http://127.0.0.1:50021/version" -TimeoutSec 2
  Write-Host "[ok] VOICEVOX ja esta rodando: $version"
}
catch {
  Write-Host "[aguardando] VOICEVOX ainda nao respondeu em :50021 — instale e abra o engine."
}

Write-Host ""
Write-Host "[3/3] Reinicie a API: .\scripts\start-local-api.ps1"

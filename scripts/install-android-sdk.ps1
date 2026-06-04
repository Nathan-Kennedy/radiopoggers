# Instala JDK 17 + Android SDK (cmdline-tools) para flutter build apk.
# Uso: .\scripts\install-android-sdk.ps1
param(
  [string]$SdkRoot = "$env:LOCALAPPDATA\Android\Sdk",
  [switch]$SkipJdk
)

$ErrorActionPreference = "Stop"

function Resolve-JdkHome {
  if ($env:JAVA_HOME -and (Test-Path (Join-Path $env:JAVA_HOME "bin\java.exe"))) {
    return $env:JAVA_HOME
  }
  $patterns = @(
    "C:\Program Files\Microsoft\jdk-*",
    "C:\Program Files\Eclipse Adoptium\jdk-*",
    "C:\Program Files\Java\jdk-*"
  )
  foreach ($pattern in $patterns) {
    $dir = Get-ChildItem -Path (Split-Path $pattern -Parent) -Directory -Filter (Split-Path $pattern -Leaf) -ErrorAction SilentlyContinue |
      Sort-Object Name -Descending |
      Select-Object -First 1
    if ($dir -and (Test-Path (Join-Path $dir.FullName "bin\java.exe"))) {
      return $dir.FullName
    }
  }
  return $null
}

function Use-JdkInSession {
  $jdkHome = Resolve-JdkHome
  if (-not $jdkHome) { return $false }
  $env:JAVA_HOME = $jdkHome
  $bin = Join-Path $jdkHome "bin"
  if ($env:Path -notlike "*$bin*") { $env:Path = "$bin;$env:Path" }
  return $true
}

function Ensure-Jdk17 {
  if (Use-JdkInSession -and (Get-Command java -ErrorAction SilentlyContinue)) {
    $v = (java -version 2>&1 | Out-String).Trim().Split("`n")[0]
    Write-Host "[ok] Java ja instalado: $v (JAVA_HOME=$env:JAVA_HOME)"
    return
  }

  if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    throw "Java nao encontrado e winget indisponivel. Instale JDK 17 (Microsoft OpenJDK ou Temurin)."
  }

  Write-Host "Instalando Microsoft OpenJDK 17 (winget)..."
  winget install Microsoft.OpenJDK.17 `
    --accept-package-agreements `
    --accept-source-agreements `
    --disable-interactivity
  $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
    [System.Environment]::GetEnvironmentVariable("Path", "User")

  if (-not (Get-Command java -ErrorAction SilentlyContinue)) {
    $candidates = @(
      "C:\Program Files\Microsoft\jdk-17*\bin\java.exe",
      "C:\Program Files\Eclipse Adoptium\jdk-17*\bin\java.exe"
    )
    foreach ($pattern in $candidates) {
      $found = Get-ChildItem -Path (Split-Path $pattern -Parent) -Filter java.exe -ErrorAction SilentlyContinue |
        Select-Object -First 1
      if ($found) {
        $jdkBin = Split-Path $found.FullName -Parent
        $env:Path = "$jdkBin;$env:Path"
        break
      }
    }
  }

  if (-not (Get-Command java -ErrorAction SilentlyContinue)) {
    throw "JDK 17 instalado mas java ainda nao esta no PATH. Feche e reabra o terminal."
  }
  $jv = (java -version 2>&1 | Out-String).Trim().Split("`n")[0]
  Write-Host "[ok] Java: $jv"
}

function Ensure-AndroidCmdlineTools {
  param([string]$Root)

  $latestDir = Join-Path $Root "cmdline-tools\latest"
  $sdkmanager = Join-Path $latestDir "bin\sdkmanager.bat"
  if (Test-Path $sdkmanager) {
    Write-Host "[ok] Android cmdline-tools ja em $latestDir"
    return $sdkmanager
  }

  New-Item -ItemType Directory -Force -Path $Root | Out-Null
  $zipUrl = "https://dl.google.com/android/repository/commandlinetools-win-11076708_latest.zip"
  $zipPath = Join-Path $env:TEMP "commandlinetools-win.zip"
  $extractRoot = Join-Path $env:TEMP "android-cmdline-extract"

  Write-Host "Baixando Android command-line tools..."
  if (Test-Path $extractRoot) { Remove-Item $extractRoot -Recurse -Force }
  Invoke-WebRequest -Uri $zipUrl -OutFile $zipPath -UseBasicParsing
  Expand-Archive -Path $zipPath -DestinationPath $extractRoot -Force

  # Zip traz pasta cmdline-tools/bin — mover para Sdk\cmdline-tools\latest
  New-Item -ItemType Directory -Force -Path (Join-Path $Root "cmdline-tools") | Out-Null
  if (Test-Path $latestDir) { Remove-Item $latestDir -Recurse -Force }
  $inner = Join-Path $extractRoot "cmdline-tools"
  if (Test-Path $inner) {
    Move-Item $inner $latestDir
  }
  else {
    New-Item -ItemType Directory -Force -Path $latestDir | Out-Null
    Move-Item (Join-Path $extractRoot "*") $latestDir
  }

  if (-not (Test-Path $sdkmanager)) {
    throw "sdkmanager nao encontrado apos extrair. Verifique $latestDir"
  }
  Write-Host "[ok] cmdline-tools em $latestDir"
  return $sdkmanager
}

function Install-SdkPackages {
  param([string]$SdkmanagerPath, [string]$Root)

  if (-not (Use-JdkInSession)) {
    throw "JAVA_HOME nao encontrado. Rode Ensure-Jdk17 ou instale Microsoft OpenJDK 17."
  }

  $env:ANDROID_HOME = $Root
  $env:ANDROID_SDK_ROOT = $Root

  Write-Host "Aceitando licencas Android..."
  $yes = 1..80 | ForEach-Object { "y" }
  $yes | & $SdkmanagerPath --sdk_root=$Root --licenses 2>&1 | Out-Host

  $packages = @(
    "platform-tools",
    "platforms;android-35",
    "platforms;android-36",
    "build-tools;35.0.0",
    "build-tools;36.0.0"
  )
  foreach ($pkg in $packages) {
    Write-Host "Instalando $pkg ..."
    & $SdkmanagerPath --sdk_root=$Root $pkg
    if ($LASTEXITCODE -ne 0) {
      throw "sdkmanager falhou em $pkg (exit $LASTEXITCODE)"
    }
  }
}

if (-not $SkipJdk) { Ensure-Jdk17 }
else { Use-JdkInSession | Out-Null }

$sdkmanager = Ensure-AndroidCmdlineTools -Root $SdkRoot
Install-SdkPackages -SdkmanagerPath $sdkmanager -Root $SdkRoot

if (Get-Command flutter -ErrorAction SilentlyContinue) {
  flutter config --android-sdk $SdkRoot
  Write-Host ""
  Write-Host "Flutter android-sdk -> $SdkRoot"
  flutter doctor -v
}
else {
  Write-Host "[aviso] Flutter nao no PATH. Depois rode: flutter config --android-sdk `"$SdkRoot`""
}

Write-Host ""
Write-Host "[ok] Android SDK pronto. Proximo passo:"
Write-Host "  .\scripts\package-app-release.ps1"

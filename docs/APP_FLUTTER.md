# App nativo Flutter — RADIO NO GRALE

App **Windows + Android** em Flutter/Dart (sem npm). Paleta e vibe rock do site; API `:8765` e stream AzuraCast.

**Guias para ouvintes:** `APP_OUVINTE.md` · **Features:** `APP_FEATURES.md` · **Releases:** `APP_RELEASE.md`

## O que o app faz

| Aba | Função |
| --- | --- |
| **Rádio** | Stream, player deck, visualizador NCS, ASCII, narradora, mesa DJ (chamada) |
| **Estante** | Catálogo em prateleiras, prévia, pedir faixa |
| **Spotify** | Importar playlist |
| **Mais** | Histórico, rede, updates GitHub, AzuraCast |

### Chamada de voz (detalhe)

- Gravação 15 s, prévia = envio (ganho, efeitos, ruído, drops).
- **Redução de ruído:** FFmpeg `arnndn` (RNNoise) ou fallback espectral.
- **Drops:** intro/outro independentes (Mixkit ou custom até 5 s); mix com crossfade.
- Ver `APP_FEATURES.md`.

## Arquitetura

```text
main.dart → RadioPoggersApp → AppController
  ├── StreamPlayerService (media_kit)
  ├── RadiopoggersApiClient
  ├── SettingsStore
  ├── VoiceDropProcessor / StingerMix / NoiseSuppress
  ├── AppUpdateService
  └── OverlayAudioService (prévia voz, narrador)
```

Telas em `lib/features/`; widgets em `lib/widgets/`; tema em `lib/core/theme/`.

## Instalar Flutter (Windows)

```powershell
cd "C:\Projetos Dev\RadioPoggers"
.\scripts\install-flutter.ps1
```

Ou manual: https://docs.flutter.dev/get-started/install/windows

## Primeira configuração

```powershell
.\scripts\sync-app-assets.ps1
.\scripts\flutter-pub-get.ps1
cd apps\radiopoggers_app
flutter create . --platforms=windows,android   # se faltar windows/
```

## Rodar em desenvolvimento

```powershell
.\scripts\start-full-stack.ps1
.\scripts\start-app-dev.ps1
```

Preset **Radmin**: o app pede o IP na VPN (não vai IP real no binário público). **Localhost** só neste PC. Build privado com IP: `--dart-define=RADIOPOGGERS_RADMIN_HOST=SEU.IP`.

## Build release

```powershell
.\scripts\build-app-windows.ps1
.\scripts\build-app-android.ps1
# ou pacote completo para GitHub:
.\scripts\package-app-release.ps1
```

- Windows: `build/windows/x64/runner/Release/radiopoggers_app.exe`
- Android: `build/app/outputs/flutter-apk/app-release.apk`

## Auto-update

Configure `githubRepo` em `lib/core/app_release_config.dart`. Tags `v*` disparam CI — ver `APP_RELEASE.md`.

## Firewall (Radmin / celular)

```powershell
.\scripts\open-lan-firewall.ps1
```

## Segurança de dependências

- Sem npm no app; `pubspec.lock` versionado.
- Updates: HTTPS GitHub + SHA256.
- Revise `pubspec.yaml` antes de atualizar pacotes.

## Site web

`frontend/` não é alterado pelo app. Use o app para stream, microfone e estante sem Chrome.

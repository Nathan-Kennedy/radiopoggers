# radiopoggers_app

App nativo **RADIO NO GRALE** (Flutter — Windows + Android).

## Documentação

| Guia | Uso |
| --- | --- |
| [APP_OUVINTE.md](../../docs/APP_OUVINTE.md) | Instalar, Radmin, troubleshooting |
| [APP_FEATURES.md](../../docs/APP_FEATURES.md) | Funcionalidades |
| [APP_FLUTTER.md](../../docs/APP_FLUTTER.md) | Desenvolvimento |
| [APP_RELEASE.md](../../docs/APP_RELEASE.md) | Releases e updates |

## Comandos rápidos

```powershell
# na raiz do repo
.\scripts\flutter-pub-get.ps1
.\scripts\start-app-dev.ps1
.\scripts\build-app-windows.ps1
.\scripts\package-app-release.ps1
```

## Configurar updates

Edite `lib/core/app_release_config.dart` → `githubRepo`.

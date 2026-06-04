# Releases e atualizações do app

Como versionar, publicar e instalar updates do **RadioPoggers** via **GitHub Releases**.

## Versionamento

- Fonte: `apps/radiopoggers_app/pubspec.yaml` → `version: MAJOR.MINOR.PATCH+BUILD`
- Exemplo: `1.1.0+2` → app mostra **1.1.0**, build **2**.
- A cada release pública: incrementar PATCH (correções) ou MINOR (features).

## Publicar uma release

### Automático (GitHub Actions)

1. Atualize `version` no `pubspec.yaml`.
2. Commit e tag:
   ```powershell
   git tag v1.1.0
   git push origin v1.1.0
   ```
3. Workflow `.github/workflows/app-release.yml` gera:
   - `RadioPoggers-Windows-x64.zip`
   - `RadioPoggers-android.apk`
   - `SHA256SUMS.txt`
4. Anexe notas na release (changelog curto).

### Manual (sua máquina)

```powershell
cd "C:\Projetos Dev\RadioPoggers"
.\scripts\package-app-release.ps1
```

Artefatos em `dist/app-release/`. Envie para GitHub Releases na mão.

## Configurar repositório no app

Em `lib/core/app_release_config.dart`:

```dart
static const String githubRepo = 'SEU_USUARIO/RadioPoggers';
```

Substitua pelo repositório real onde as Releases ficam públicas.

## Segurança antes de publicar

### O que **não** pode ir no zip/APK

| Item | Motivo |
| --- | --- |
| `data/gemini-api-key.txt`, `discord-bot-token.txt`, etc. | Chaves de API |
| `data/dev-ssl/`, `frontend/config.js` com IP real | Rede e certificados |
| Arquivos `.pdb` | Expõem caminhos do seu PC |
| IP Radmin fixo no código | Qualquer um extrai do exe |

### O que o app público faz hoje

- **Sem IP embutido** — amigos informam o IP na primeira configuração (dialog Radmin).
- Build **só seu** com IP opcional:  
  `flutter build windows --release --dart-define=RADIOPOGGERS_RADMIN_HOST=SEU.IP`
- `scripts/package-app-release.ps1` exclui `.pdb` e falha se achar padrões de chave em arquivos de texto no pacote.

### Repositório Git

Raiz tem [`.gitignore`](../.gitignore) para `data/*-key.txt`, `discord-bot-config.json`, `frontend/config.js`.  
**Se esses arquivos já foram commitados**, remova do histórico ou troque as chaves antes de tornar o repo público.

### Checklist rápido

1. `git status` — nada de `data/*-key.txt` ou `config.js` staged  
2. Rodar `.\scripts\package-app-release.ps1`  
3. Testar app do zip em PC limpo (pedir IP Radmin)  
4. Publicar tag `v*` só depois disso

## Checksums

- `SHA256SUMS.txt` lista hash do zip Windows.
- O app valida antes de extrair/instalar.
- Nunca execute update se o hash não bater.

## Windows — SmartScreen

Sem **certificado de assinatura de código** pago, o Windows pode mostrar “Windows protegeu seu PC”. Isso é esperado para app caseiro:

- Primeira instalação: **Mais informações → Executar mesmo assim**
- Updates pelo app: mesma pasta de instalação reduz avisos repetidos

Assinatura opcional futura: certificado Authenticode (~custo anual).

## Android — keystore

Release assinado com keystore local (não commitar):

1. `keytool -genkey -v -keystore radiopoggers-release.jks ...`
2. `apps/radiopoggers_app/android/key.properties` (gitignored)
3. `flutter build apk --release`

Sem keystore, só APK debug funciona em outros aparelhos.

## Política de update no app

| Momento | Comportamento |
| --- | --- |
| Abertura | Verifica release latest (silencioso se já na versão) |
| Nova versão | Dialog: Instalar agora / Depois |
| Mais → Verificar atualizações | Força checagem |
| Falha de rede | Snackbar; link para Releases no navegador |

## Inno Setup (opcional)

Para um único `RadioPoggers-Setup.exe`, adicione script Inno que empacota a pasta `Release/`. Não obrigatório — zip já funciona.

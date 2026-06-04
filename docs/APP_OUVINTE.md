# App ouvinte — RADIO NO GRALE

Guia para **você e seus amigos** instalarem o app nativo (Windows e Android), entrarem na rede **Radmin** e ouvirem a rádio caseira com chamadas de voz, estante e votação — sem depender do navegador.

## O que é

- App **oficial do grupo** (não está na Microsoft Store nem na Play Store).
- Conecta na **API** da rádio (`:8765`) e no **stream** AzuraCast.
- Mesma identidade visual rock/industrial do site, com animações e interface repaginada.

## Requisitos

| Plataforma | Requisito |
| --- | --- |
| **Windows** | Windows 10/11, pasta ou zip da release (exe + DLLs) |
| **Android** | Android 8+ (API 26+), APK da release |
| **Rede** | **Radmin VPN** na mesma rede do operador da rádio |
| **Operador** | PC da rádio ligado (Docker/AzuraCast + API) |

## Instalação — Windows

1. Baixe **`RadioPoggers-Windows-x64.zip`** na página de Releases do GitHub (link que o operador passar) ou receba o zip diretamente.
2. Extraia em uma pasta fixa, por exemplo `C:\RadioPoggers\`.
3. Execute **`radiopoggers_app.exe`**.
4. Na primeira abertura: escolha **Preset Radmin** (ou configure IP da VPN em **Mais → Configuração de rede**).
5. Se o Windows SmartScreen avisar: é normal sem certificado pago — **Mais informações → Executar mesmo assim** (veja `APP_RELEASE.md`).

## Instalação — Android

1. Baixe **`RadioPoggers-android.apk`** na mesma página de Releases.
2. Permita **instalar apps desconhecidos** para o navegador ou gerenciador de arquivos.
3. Abra o APK e instale.
4. No app: **Preset Radmin** com o IP que o operador passar.

## Primeira conexão (Radmin)

1. Instale [Radmin VPN](https://www.radmin-vpn.com/) e entre na **mesma rede** que o operador.
2. No app: **Mais → Usar preset Radmin** (reaplica API + stream no IP da VPN).
3. Aba **Rádio**: toque **PLAY** — deve aparecer a faixa atual e o visualizador animado.
4. Se falhar: confirme firewall no PC da rádio (`scripts/open-lan-firewall.ps1`) e IP em `docs/RADMIN_OUVINTES.md`.

## Atualizações automáticas

- Ao abrir o app, ele consulta **GitHub Releases** por versão nova.
- Se houver update: banner ou diálogo **Instalar agora / Depois**.
- **Windows:** baixa zip, valida checksum e reinicia o app atualizado.
- **Android:** baixa APK e pede confirmação de instalação.

Detalhes para quem publica releases: **`docs/APP_RELEASE.md`**.

## Funcionalidades (resumo)

| Aba | Uso |
| --- | --- |
| **Rádio** | Stream, capa, player estilo deck, ASCII, narradora, **mesa de chamada** (microfone) |
| **Estante** | Catálogo em prateleiras, prévia, pedir faixa |
| **Spotify** | Importar playlist (operador) |
| **Mais** | Histórico, rede, AzuraCast, **verificar atualizações**, sobre |

Lista completa: **`docs/APP_FEATURES.md`**.

## Problemas comuns

| Sintoma | O que fazer |
| --- | --- |
| API offline | Radmin conectado? IP certo? API ligada no PC da rádio? |
| Stream não toca | Porta 80/stream liberada no firewall; testar URL no navegador da VPN |
| Chamada não envia | Microfone permitido; gravar de novo; volume > 0% |
| Update falha | Baixar manualmente na página Releases; conferir internet |

## Legal

Áudios autorais da rádio caseira — uso restrito ao grupo. Veja **`docs/LEGAL_AUDIO.md`**.

## Mais documentação

- **`docs/RADMIN_OUVINTES.md`** — convidar amigos, portas, firewall  
- **`docs/APP_FEATURES.md`** — todas as funções do app  
- **`docs/APP_FLUTTER.md`** — desenvolvimento e arquitetura  

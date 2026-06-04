# Setup no Windows

Este guia coloca a RadioPoggers no ar localmente usando AzuraCast em Docker.

## Requisitos

- Windows 10/11 atualizado.
- Docker Desktop instalado.
- WSL2 habilitado no Docker Desktop.
- Pelo menos 4 GB de RAM livres quando a radio estiver rodando.
- Upload estavel se amigos forem ouvir pela internet.
- Musicas locais que voce tenha direito de transmitir.

## Testar a interface antes do AzuraCast

Voce pode testar a interface imediatamente em modo demo. Ela usa dados locais e um audio de teste gerado pelo navegador.

No PowerShell:

```powershell
.\scripts\check-env.ps1
.\scripts\serve-frontend.ps1 -Open
```

Abra:

```text
http://localhost:5500/frontend/
```

Se o AzuraCast ainda nao estiver rodando, o frontend entra em `Demo` automaticamente. Quando o AzuraCast estiver online e `frontend/config.js` apontar para ele, a mesma interface passa a usar o stream real.

## Portas recomendadas

| Uso | Porta |
| --- | --- |
| Painel AzuraCast HTTP | `80` |
| Painel AzuraCast HTTPS local | `443` |
| SFTP AzuraCast | `2022` |
| Streams da estacao | `8000-8099` |
| Frontend local estatico | `5500` |
| API local RadioPoggers | `8765` |

Esta instalacao local usou as portas padrao do AzuraCast: `80` e `443`. Se algum programa ocupar essas portas, da para trocar depois pelo utilitario do AzuraCast.

## Instalar o AzuraCast

O AzuraCast recomenda usar o instalador oficial. No Windows, o caminho mais estavel e rodar os comandos dentro de uma distro WSL2, como Ubuntu. A documentacao oficial tambem indica Docker Desktop + WSL2 + distro Linux para Windows.

Antes de instalar:

1. Abra `Ubuntu 24.04` pelo Menu Iniciar.
2. Espere a primeira inicializacao terminar.
3. Crie o usuario e senha Linux quando ele pedir.
4. Feche o terminal do Ubuntu.
5. No Docker Desktop, abra `Settings > Resources > WSL Integration`.
6. Ative `Enable integration with my default WSL distro`.
7. Ative tambem a chave de `Ubuntu-24.04`.
8. Clique em `Apply & Restart`.

Depois rode, no PowerShell dentro do projeto:

```powershell
.\scripts\install-azuracast-wsl.ps1
```

Quando o instalador perguntar portas, use:

```text
HTTP: 80
HTTPS: 443
SFTP: 2022
```

### Caminho manual equivalente

1. Abra o terminal do Ubuntu/WSL.
2. Crie uma pasta persistente:

```bash
mkdir -p ~/azuracast
cd ~/azuracast
```

3. Baixe o script oficial:

```bash
curl -fsSL https://raw.githubusercontent.com/AzuraCast/AzuraCast/main/docker.sh > docker.sh
chmod a+x docker.sh
```

4. Rode a instalacao:

```bash
./docker.sh install
```

5. Quando o instalador perguntar as portas, prefira:

```text
HTTP: 80
HTTPS: 443
SFTP: 2022
```

6. Acesse:

```text
http://localhost
```

## Criar a estacao

No painel do AzuraCast:

1. Complete o setup inicial.
2. Crie uma estacao chamada `RadioPoggers`.
3. Use um shortcode simples, por exemplo `radiopoggers`.
4. Habilite a pagina publica da estacao.
5. Envie suas musicas pela biblioteca do AzuraCast.
6. Crie uma playlist padrao e adicione as musicas.
7. Inicie ou reinicie a transmissao da estacao.

## Conectar o frontend (Alta Cupula)

Edite `frontend/config.js` — exemplo da instalacao atual:

```js
window.RADIOPOGGERS_CONFIG = {
  azuracastBaseUrl: "http://localhost",
  azuracastPanelUrl: "http://localhost",
  stationShortcode: "radio-no-grale",
  stationId: 1,
  streamUrl: "http://localhost/listen/radio-no-grale/radio.mp3",
  nowPlayingMode: "auto",
  localApiUrl: "http://127.0.0.1:8765",
  spotifyManifestUrl: "../data/spotify-imported.json",
  pollIntervalMs: 3000,
  stationDisplayName: "ALTA CUPULA",
  reloadOnTrackChange: false
};
```

**Now Playing:** nesta instalacao use `stationId: 1`. A URL `/api/nowplaying/radio-no-grale` retorna 404.

O frontend prefere a **API local** (`localApiUrl`) para musica atual, progresso e manifesto. Mantenha `.\scripts\start-local-api.ps1` rodando junto com o site.

## API local e importacao Spotify

Dois terminais apos subir AzuraCast:

```powershell
.\scripts\start-local-api.ps1
.\scripts\serve-frontend.ps1 -Open
```

No site, **Tocar** envia playlist para download (spotdl). Aguarde terminar antes de enviar outra.

Apos primeira importacao ou se metadados travarem no AzuraCast:

```powershell
.\scripts\fix-azuracast-station.ps1
```

## Abrir o frontend

Para testar rapidamente, abra `frontend/index.html` no navegador.

Para testar como PWA, use um servidor local. Com Python instalado:

```powershell
.\scripts\serve-frontend.ps1 -Open
```

Depois abra:

```text
http://localhost:5500/frontend/
```

## Qualidade de audio recomendada

Comece com:

- Codec: MP3 ou AAC, dependendo do suporte desejado.
- Bitrate: `128kbps` para qualidade boa.
- Bitrate alternativo: `96kbps` se seu upload for limitado.
- Sample rate: `44.1kHz`.

## Rotina basica

Iniciar AzuraCast:

```bash
cd ~/azuracast
./docker.sh start
```

Parar AzuraCast:

```bash
cd ~/azuracast
./docker.sh stop
```

Atualizar AzuraCast:

```bash
cd ~/azuracast
./docker.sh update-self
./docker.sh update
```

Faca backup antes de atualizar.

## Proximos passos (player completo)

Depois do AzuraCast e da API local:

- HLS no site: `.\scripts\enable-azuracast-hls.ps1` — ver `docs/RUNBOOK_ATUAL.md`.
- Voice drop e narradora Miku: `docs/MELHORIAS_PLAYER_E_MIKU.md` e `docs/MIKU_NARRATOR.md`.
- Operacao diaria: `docs/RUNBOOK_ATUAL.md`.

# Funcionalidades do app Flutter

Referência das capacidades do app em `apps/radiopoggers_app/` (junho 2026).

## Navegação

| Aba | Tela | Descrição |
| --- | --- | --- |
| Rádio | `OnAirScreen` | Transmissão ao vivo, player, ASCII, chamada de voz |
| Estante | `LibraryScreen` | Biblioteca local com prévia e pedidos |
| Spotify | `SpotifyScreen` | Importação de playlist via API |
| Mais | `MoreScreen` | Histórico, rede, updates, AzuraCast |

## Avisos ao ouvinte (status / manutenção)

| Situação | App Flutter | Site (`frontend`) |
| --- | --- | --- |
| API offline | Banner global + play desativado | `setMessage` + voz/API status |
| Estação offline (`is_online: false`) | Banner + título “Transmissão desligada” | `applyTransmissionState` / Fora do ar |
| Now playing indisponível | Banner “Sem sinal” | Offline + mensagem em `refreshNowPlaying` |
| Falha ao abrir stream | Banner com aviso | Monitor de stream / mensagens de play |
| Manutenção do operador | Banner + play bloqueado se `level: maintenance` | `applyMaintenanceNotice` via `/api/health` |

**Ativar manutenção (operador):** copie `data/maintenance.example.json` para `data/maintenance.json`, ajuste e defina `"active": true`. Campos:

- `message` — texto exibido ao ouvinte (obrigatório para clareza).
- `level` — `maintenance` (bloqueia play) ou `warning` (só aviso, play liberado).
- `updated_at` — opcional, para sua referência.

A API expõe o estado em `GET /api/health` → `maintenance`. O app e o site consultam a cada ~20 s.

## Rádio (No ar)

| Recurso | Detalhe |
| --- | --- |
| Stream | HLS/MP3 via `media_kit`; compressão leve (`StreamLoudness`) |
| Now playing | Título, artista, capa, progresso, tempo |
| Visualizador | Barras estilo NCS (animadas quando online) |
| Player deck | UI tipo MP3/vinil com play/pause, volume, votação skip |
| ASCII | Palco animado (`AsciiStage`) |
| Narradora | Miku / Hoshino, legenda, picker |
| Ducking | Volume do stream reduzido durante voice drop / narradora |

## Chamada de voz (voice drop)

| Recurso | Detalhe |
| --- | --- |
| Gravação | Até 15 s, microfone nativo (`record`) |
| Fluxo | Gravar → prévia → enviar ou descartar |
| UI | **Mesa DJ** (modal mixer) — faders decorativos + controles reais |
| Volume no ar | 0–200% (`VoiceDropProcessor`) |
| Redução de ruído | Liga/desliga (estilo Discord); FFmpeg **arnndn** (RNNoise) ou fallback Wiener |
| Efeitos | Eco, autotune, robô, megafone, coro — presets e sliders |
| Drops início/fim | Mixkit (catálogo) ou **arquivo custom** (MP3 etc. → WAV), máx. 5 s por lado |
| Mix imersivo | Crossfade: voz entra antes do fim do intro; outro entra antes do fim da voz |
| Envio | WAV misturado para API; reprodução local usa mesmo arquivo |

Modelos: `VoiceDropEffectsConfig`, `VoiceDropStingerConfig` (v2 intro/outro).

## Estante de discos

| Recurso | Detalhe |
| --- | --- |
| Busca | Título, artista, álbum |
| Filtros | Artista, álbum |
| UI | Prateleiras visuais (`RecordShelfView`) |
| Prévia | Ouvir faixa local sem ir ao ar |
| Pedir | Enfileirar na rádio via API |

## Spotify

Importação de link de playlist; manifesto e sync (mesma API do site).

## Mais

| Recurso | Detalhe |
| --- | --- |
| Histórico | Últimas faixas da API |
| Presets | Localhost (dev), Radmin (amigos) |
| Configuração | IP API, stream, AzuraCast |
| Atualizações | Verificação GitHub Releases + instalação |
| Sobre | Versão do app (`package_info_plus`) |

## Votação

Overlay para pular faixa (regras em `docs/VOTACAO_OUVINTES.md`).

## Persistência local

`SettingsStore` (SharedPreferences): rede, narradora, efeitos de voz, stingers, volume chamada.

## Segurança de rede

| Aspecto | Comportamento |
| --- | --- |
| Radmin | HTTP na LAN/VPN — adequado para grupo fechado |
| Updates | Apenas `github.com` / `githubusercontent.com`; SHA256 do zip |
| Secrets | Nenhuma chave de API no app; IP Radmin informado pelo usuário; `listenerId` gerado localmente no aparelho |
| Tunnel público | Opcional via Cloudflare (`docs/CLOUDFLARE_TUNNEL.md`) |

## Serviços principais (código)

| Arquivo | Papel |
| --- | --- |
| `app_controller.dart` | Estado global, stream, voz, biblioteca |
| `radiopoggers_api.dart` | HTTP API :8765 |
| `voice_drop_processor.dart` | Ganho + efeitos + ruído |
| `voice_drop_stinger_mix.dart` | Mix intro/voz/outro |
| `voice_drop_noise_suppress.dart` | RNNoise via FFmpeg / fallback |
| `app_update_service.dart` | Updates GitHub |
| `stream_player_service.dart` | Player HLS |

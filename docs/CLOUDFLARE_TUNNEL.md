# Cloudflare Tunnel

Use Cloudflare Tunnel quando quiser que amigos acessem a RadioPoggers fora da sua rede sem abrir portas no roteador.

## Modelo recomendado

Publique duas rotas separadas:

```text
radio.seudominio.com      -> frontend estatico
azura.seudominio.com      -> AzuraCast publico/stream
```

Se quiser simplificar no inicio, publique apenas o AzuraCast e use o frontend local para testes.

## Regras de seguranca

- Nao exponha o painel administrativo sem senha forte.
- Ative 2FA na Cloudflare.
- Nao compartilhe credenciais do AzuraCast.
- Prefira expor a pagina publica/stream em vez do painel inteiro.
- Se possivel, proteja rotas administrativas com Cloudflare Access.

## Instalar cloudflared

No Windows, instale pelo metodo oficial da Cloudflare. Depois autentique:

```powershell
cloudflared tunnel login
```

Crie o tunnel:

```powershell
cloudflared tunnel create radiopoggers
```

Crie o arquivo de configuracao em uma pasta segura do usuario:

```yaml
tunnel: radiopoggers
credentials-file: C:\Users\SEU_USUARIO\.cloudflared\ID_DO_TUNNEL.json

ingress:
  - hostname: azura.seudominio.com
    service: http://localhost:8080
  - hostname: radio.seudominio.com
    service: http://localhost:5500
  - service: http_status:404
```

Rode:

```powershell
cloudflared tunnel run radiopoggers
```

## Ajustar o frontend

Quando usar tunnel, ajuste `frontend/config.js`:

```js
window.RADIOPOGGERS_CONFIG = {
  azuracastBaseUrl: "https://azura.seudominio.com",
  stationShortcode: "radiopoggers",
  streamUrl: "",
  nowPlayingMode: "auto",
  pollIntervalMs: 15000,
  stationDisplayName: "RadioPoggers",
  fallbackCover: "assets/img/cover-fallback.svg"
};
```

## Servir o frontend localmente

Para o tunnel apontar para `localhost:5500`:

```powershell
cd "c:\Projetos Dev\RadioPoggers\frontend"
python -m http.server 5500
```

## Quando migrar para VPS

Na VPS, o tunnel fica parecido, mas os servicos deixam de apontar para seu PC e passam a apontar para o servidor.

Exemplo:

```yaml
ingress:
  - hostname: azura.seudominio.com
    service: http://localhost:8080
  - hostname: radio.seudominio.com
    service: http://localhost:5500
  - service: http_status:404
```

A vantagem e que as URLs publicas podem continuar iguais. O frontend muda pouco ou nada.


# Infraestrutura AzuraCast

Esta pasta guarda referencias seguras para operar o AzuraCast sem editar diretamente o `docker-compose.yml` oficial que o instalador gera.

## Regra de ouro

Nao altere o `docker-compose.yml` principal do AzuraCast manualmente. O updater do AzuraCast espera controlar esse arquivo.

Use:

- `.env` para portas e variaveis do Docker Compose.
- `azuracast.env` para configuracoes da aplicacao.
- `docker-compose.override.yml` apenas quando uma customizacao for realmente necessaria.

## Instalacao esperada

No WSL2:

```bash
sudo mkdir -p /var/azuracast
sudo chown -R "$USER":"$USER" /var/azuracast
cd /var/azuracast
curl -fsSL https://raw.githubusercontent.com/AzuraCast/AzuraCast/main/docker.sh > docker.sh
chmod a+x docker.sh
./docker.sh install
```

## Portas locais recomendadas

```text
AZURACAST_HTTP_PORT=8080
AZURACAST_HTTPS_PORT=8443
AZURACAST_SFTP_PORT=2022
AUTO_ASSIGN_PORT_MIN=8000
AUTO_ASSIGN_PORT_MAX=8099
```

## Station shortcode

Use `radiopoggers` como shortcode da estacao. Isso deixa as URLs previsiveis:

```text
http://localhost:8080/api/nowplaying/radiopoggers
http://localhost:8080/api/nowplaying_static/radiopoggers.json
```

## Operacao

Iniciar:

```bash
cd /var/azuracast
./docker.sh start
```

Parar:

```bash
cd /var/azuracast
./docker.sh stop
```

Logs:

```bash
cd /var/azuracast
./docker.sh cli azuracast:radio:restart radiopoggers
docker compose logs -f --tail=100
```

Backup:

```bash
cd /var/azuracast
./docker.sh backup
```

Atualizacao:

```bash
cd /var/azuracast
./docker.sh update-self
./docker.sh update
```

## Qualidade inicial

Comece com 128kbps. Se a internet engasgar, teste 96kbps.

Evite criar multiplas estacoes antes de estabilizar a primeira, porque cada estacao aumenta consumo de CPU, portas e disco.


"""
Narradora Hoshino — locucoes via Gemini TTS (voz Kore, pt-BR expressivo).
Tom variado: animada, suave ou direta — locutora de radio, nao auto-seducao.
"""

from __future__ import annotations

import os
import random
import re
from typing import Any

from gemini_narrator import STYLE_LOCUTORA, TTS_MODELS, synthesize_gemini_mp3
from miku_narrator import (
    MIKU_CITY_NAME,
    MIKU_DAYTIME_TEMPLATE_CHANCE,
    MIKU_HOT_BEER_POOL_WEIGHT,
    MIKU_MAX_SECONDS,
    MIKU_MOMENTS,
    STATION_NAME,
    STATION_TAGLINE,
    _clean_phrase,
    ariquemes_weather,
    build_broadcast_context,
    build_hot_beer_funny_line,
    build_weather_compare,
    build_weather_funny_commentary,
    compute_regional_weather_stats,
    fetch_rondonia_weather,
    format_clock_pt,
    greeting_for_hour,
    infer_genre_label,
    is_ariguemes_scorching,
    resolve_broadcast_clock,
    resolve_info_clock,
    weekday_pt,
)

HOSHINO_LISTENER_ID = "hoshino-narrator"
HOSHINO_VOICE = os.environ.get("RADIOPOGGERS_HOSHINO_VOICE", "Kore").strip() or "Kore"
HOSHINO_MAX_SECONDS = int(os.environ.get("RADIOPOGGERS_HOSHINO_MAX_SECONDS", str(MIKU_MAX_SECONDS)))
HOSHINO_DAYTIME_TEMPLATE_CHANCE = float(
    os.environ.get("RADIOPOGGERS_HOSHINO_DAYTIME_TEMPLATE_CHANCE", str(MIKU_DAYTIME_TEMPLATE_CHANCE))
)
HOSHINO_STYLE_PROMPT = os.environ.get(
    "RADIOPOGGERS_HOSHINO_STYLE_PROMPT",
    (
        "Voce e Hoshino, locutora de radio FM brasileira, feminina, calorosa e madura. "
        "Fale em portugues do Brasil como quem esta ao vivo na antena — proxima do ouvinte, sem exagero de idol. "
        "Use primeira pessoa (eu, minha voz, voltei com voce). Se se apresentar, faca como locutora FM: "
        "exemplo 'Ola, eu sou a Hoshino — voce esta ouvindo a {station}'. "
        "Nao repita seu proprio nome em terceira pessoa (evite 'Hoshino no ar', 'Hoshino curte'). "
        "Ritmo natural, sem arrastar. Risadas ([laughing]) ocasionais."
    ),
).strip()
HOSHINO_STYLE_VARIANTS = (
    "Tom desta locucao: calorosa e leve, como locutora FM de fim de tarde.",
    "Tom desta locucao: suave e acolhedora, voz calma, sem exagero.",
    "Tom desta locucao: direta e animada, ritmo firme de locutora FM.",
)
HOSHINO_LAUGH_CHANCE = float(os.environ.get("RADIOPOGGERS_HOSHINO_LAUGH_CHANCE", "0.22"))
HOSHINO_IDOL_CHANCE = float(os.environ.get("RADIOPOGGERS_HOSHINO_IDOL_CHANCE", "0.22"))
HOSHINO_SPEED_FACTOR = float(os.environ.get("RADIOPOGGERS_HOSHINO_SPEED_FACTOR", "1.0"))

HOSHINO_MOMENTS = MIKU_MOMENTS

_TRACK_CHANGE_TEMPLATES = (
    "E ai! Voce ta na {station} — entrou {title}, de {artist}! [laughing]",
    "Boa! {station} no ar com {title}, de {artist}. {tagline} mandando ver! [short pause]",
    "Ola, eu sou a Hoshino — voce esta ouvindo a {station}. [short pause] Agora {title}, de {artist}! [short pause]",
    "Prepara o fone! {title}, de {artist}, na {station}! [laughing]",
    "Voce sintonizou {station}. Seguinte: {title}, de {artist}! [short pause]",
    "Que faixa! {title} na {station} — {artist} mandou bem! [laughing]",
    "Ao vivo de {tagline}! {station} toca {title}, de {artist}! [short pause]",
    "Pra quem acabou de chegar: eu sou a Hoshino, da {station}. [short pause] {title}, de {artist}, no ar! [short pause]",
    "Energia total: {title} com {artist} na {station}! [short pause]",
    "Isso e {genre} raiz! {title}, de {artist}, na {station}! [laughing]",
    "Atencao, fera! {title}, de {artist}, chegou na {station}! [short pause]",
    "Som pesado na {station}! {title}, de {artist} — segura! [laughing]",
    "Brabo demais! {artist} com {title} aqui na {station}. [short pause]",
    "Musica boa no radar: {title} na {station}! [laughing]",
    "Esta e a {station}! {title}, de {artist}, na sua sintonia. [short pause]",
    "Galera da {station} ligada? {title}, de {artist}, estourando! [laughing]",
    "{greeting}! Voce ouve {station} — agora {title}, de {artist}. [short pause]",
    "Adoro essa! {title} na {station}, de {artist}. [laughing]",
    "Entrou {title} na {station}! {artist} mandou ver! [short pause]",
    "Na {station} rola {title} com {artist}. Volume no talo! [laughing]",
    "Boa noite na {station}. [short pause] Agora soa {title}, com {artist}.",
    "Calma e som bom: {title}, de {artist}, na {station}. [sigh]",
    "Noite de radio em {tagline}. {station} apresenta {title}, de {artist}. [short pause]",
    "Fica na {station} ouvindo {title}, de {artist}. [short pause] Isso aqui e {genre}!",
    "Quer saber como a {station} so toca musica boa? [short pause] Isso e se-gre-do. [short pause] Agora entra {title}, de {artist}! [laughing]",
    "Eu sou a Hoshino, ao vivo na {station}. [short pause] Proxima faixa: {title}, de {artist}! [short pause]",
    "Psst… quer o segredo da {station}? [short pause] So musica boa. [short pause] Tipo {title}, de {artist}! [laughing]",
)

_IDOL_TRACK_CHANGE_TEMPLATES = (
    "Quer saber como a {station} so toca musica boa? [short pause] Isso e se-gre-do. [short pause] Entrou {title}, de {artist}! [laughing]",
    "Yatta! [short pause] {title} na {station}, de {artist}. [laughing] Playlist certeira!",
    "Minha missao hoje: te manter na {station}! [short pause] No ar: {title}, de {artist}! [laughing]",
    "Ei, fã da {station}! [short pause] Quer o segredo do som bom? [short pause] Curadoria. [short pause] Agora {title}, de {artist}! [laughing]",
    "Ola, eu sou a Hoshino — voce sintonizou a {station}. [short pause] {title}, de {artist}, chegou! [laughing]",
)

_MID_TRACK_TEMPLATES = (
    "Voltei com voce na {station} — ainda rola {title}. [short pause]",
    "Ei, lembra: voce ouve {station} — {title}, de {artist}! [short pause]",
    "Segura! {title} continua na {station}. [laughing] Energia pura!",
    "Voce ta na {station} com {artist}. Isso aqui e {genre}: {title}! [short pause]",
    "Ainda e {title} na {station}, o melhor de {tagline}! [laughing]",
    "Break rapido da locutora: voce ouve {station} e {title} segue no ar. [short pause]",
    "Continua comigo! {title}, de {artist}, aqui na {station}. [laughing]",
    "Voce ouve {station} e {title} nao parou. Curto junto com voce! [short pause]",
    "LED piscando: ainda rola {title} na {station}. {tagline}! [laughing]",
    "Break da locutora! {title}, de {artist}, continua na {station}. [short pause]",
    "Ouvintes da {station}: {title} ainda no ar. [laughing] Grita ai!",
    "Transmitindo de {tagline}: {title} segue na {station}. Voce e demais! [short pause]",
    "Quem ficou na {station} ouvindo {title} manda bem! [laughing]",
    "{title} continua e a {station} nao para. [short pause] Yatta!",
    "Ainda e {title} na {station}. [sigh] {genre} gostoso com {artist}.",
    "So lembrando: {title} ainda detona na {station}! [laughing]",
    "Som pesado nao para! {title}, de {artist}, na {station}! [short pause]",
    "Rock de verdade! {title} continua em {tagline}! [laughing]",
    "Ainda rola {title}! [short pause] Quer saber o segredo da {station}? [short pause] So musica boa. [short pause] Isso e se-gre-do. [laughing]",
)

_IDOL_MID_TRACK_TEMPLATES = (
    "Voltei com voce na {station}! [short pause] {title} ainda no ar! [laughing]",
    "Quer saber por que {title} continua aqui? [short pause] Porque a {station} so toca musica boa. [short pause] Segredo! [laughing]",
    "Yatta, voce ficou! [short pause] {title}, de {artist}, ainda rola na {station}! [laughing]",
)

_TRACK_DAYTIME_NIGHT = (
    "Que noite boa pra ouvir a {station}! Agora entra {title}, de {artist}! [short pause]",
    "{greeting}! Que noite boa na {station} — {title}, de {artist}, no ar! [short pause]",
    "Noite perfeita de radio: {station} toca {title}, de {artist}. [sigh]",
    "Essa noite combina com {station}. Apresento {title}, de {artist}! [laughing]",
)

_TRACK_DAYTIME_MORNING = (
    "{greeting}! Comeca o dia ouvindo {station} — {title}, de {artist}! [short pause]",
    "Manha na {station}! To aqui pra animar seu dia com {title}, de {artist}! [laughing]",
    "{weekday} de manha pede {station} no fone. Entra {title}, de {artist}! [short pause]",
)

_TRACK_DAYTIME_AFTERNOON = (
    "{greeting}! {weekday} a tarde e {station} no ar com {title}, de {artist}! [short pause]",
    "Tarde boa pra sintonizar {station}! Agora {title}, de {artist}! [laughing]",
)

_TRACK_DAYTIME_FRIDAY = (
    "Sextou! Bora ouvir {station} — {title}, de {artist}! [laughing]",
    "Sextou na {station}! {title}, de {artist}. {tagline} manda ver! [short pause]",
    "E sextou! Fica comigo na {station} — {title}, de {artist}. [laughing] Resenha e som bom!",
    "Sextou, ouvinte! {station} no volume com {title}, de {artist}! [short pause]",
)

_TRACK_DAYTIME_SATURDAY = (
    "Sabado pede {station}! {title}, de {artist}, pra animar o fim de semana! [laughing]",
    "Fim de semana na {station}! Te trago {title}, de {artist}! [short pause]",
    "Sabado na {station} — {title}, de {artist}, no ar! [short pause]",
)

_TRACK_DAYTIME_SUNDAY = (
    "Domingo na {station}! {title}, de {artist}, pra fechar o dia com estilo! [short pause]",
    "Domingo pede calma e som bom: {station} com {title}, de {artist}. [sigh]",
)

_TRACK_DAYTIME_SUNDAY_NIGHT = (
    "Domingo a noite! Continua na {station} com {title}, de {artist}. [short pause]",
    "Domingo a noite e {station} na veia! {title}, de {artist}, pra fechar o fim de semana! [sigh]",
    "Domingo a noite, {greeting}! {station} com {title}, de {artist}. [short pause]",
)

_TRACK_DAYTIME_MONDAY = (
    "Segunda com {station} fica menos pesada! {title}, de {artist}, no ar! [short pause]",
    "Segunda-feira? A {station} salva com {title}, de {artist}! [laughing]",
)

_MID_DAYTIME_NIGHT = (
    "Que noite boa pra ouvir a {station}! {title} continua rolando ai! [short pause]",
    "{greeting}! Que noite boa na {station} — {title}, de {artist}, segue no ar! [short pause]",
    "Noite perfeita de radio: voce ainda esta na {station} com {title}! [sigh]",
)

_MID_DAYTIME_MORNING = (
    "{greeting}! Manha com {station} e {title}, de {artist}. [short pause] Continua ai!",
    "{weekday} de manha e {station} no fone — {title} ainda rola! [laughing]",
)

_MID_DAYTIME_AFTERNOON = (
    "{greeting}! {weekday} a tarde e {station} com {title}, de {artist}! [short pause]",
    "Tarde boa na {station}! {title} continua com voce! [laughing]",
)

_MID_DAYTIME_FRIDAY = (
    "Sextou e voce ainda ta na {station}! {title}, de {artist}, segue com a gente! [laughing]",
    "Sextou! Ouvindo {station} — {title} no ar! [short pause]",
    "E sextou! Fica na {station} com {title}. [laughing] Resenha e radio, ne?",
)

_MID_DAYTIME_SATURDAY = (
    "Sabado na {station}! {title}, de {artist}, continua animando! [laughing]",
    "Fim de semana e voce na {station} ouvindo {title}. Curto demais! [short pause]",
)

_MID_DAYTIME_SUNDAY = (
    "Domingo na {station}! {title} continua — [sigh] bom demais.",
)

_MID_DAYTIME_SUNDAY_NIGHT = (
    "Domingo a noite! Continua ouvindo {station}! {title} rola ai! [short pause]",
    "Domingo a noite e {station} na veia! {title}, de {artist}, segue no ar! [sigh]",
    "Domingo a noite, {greeting}! {station} com {title} no ar. [short pause]",
)

_MID_DAYTIME_MONDAY = (
    "Segunda com {station} e {title} fica menos pesada. [short pause] Continua ai!",
)

_INFO_TIME_TEMPLATES = (
    "Break da locutora! {greeting}! Em {city} sao {time}. [short pause] Voce ouve {station}!",
    "Informacao rapida: agora sao {time} em {city}, horario de Rondonia. [short pause]",
    "{greeting}, ouvinte! {weekday}, {time} em {city}. {title} continua no ar! [laughing]",
    "Relogio da {station}: {time} em {city}. {greeting} e deixa o som rolar! [short pause]",
    "Ola, eu sou a Hoshino — voce esta na {station}. [short pause] Em {city} sao {time}. [short pause]",
)

_INFO_WEATHER_TEMPLATES = (
    "Clima em {city}: {weather}, cerca de {temp} graus. [short pause] Na {station} te mantenho informado!",
    "Previsao rapida em {city}: {weather}, {temp} graus. [laughing] Hidrate-se e curte {station}!",
    "Tempo agora em {city}: {weather} com {temp} graus. {station} no ar com {title}! [short pause]",
    "Previsao do tempo: em {city} esta {weather}, {temp} graus. [short pause] Segue {station}!",
)

_INFO_WEATHER_COMPARE_TEMPLATES = (
    "Clima em {city}: {weather}, {temp} graus. Na regiao: {weather_compare}! [short pause]",
    "Em {city} faz {temp} graus e {weather}. Comparativo Rondonia: {weather_compare}! [laughing]",
    "Previsao da locutora! {city} com {temp} graus, {weather}. Tambem: {weather_compare}! [short pause]",
    "{greeting}! {city} marca {temp} graus. Por la: {weather_compare}. [short pause]",
    "Panorama de Rondonia: em {city} {weather}, {temp} graus. {weather_compare}! [short pause]",
)

_INFO_WEATHER_FUNNY_TEMPLATES = (
    "{weather_funny}",
    "Previsao com humor na {station}: {weather_funny} [laughing]",
    "No clima de hoje: {weather_funny} [short pause]",
    "{weather_funny} [laughing] {title} continua rolando na {station}!",
    "{greeting}! {weather_funny} [short pause]",
    "Servico util e engraçado: {weather_funny} [short pause]",
)

_INFO_HOT_BEER_TEMPLATES = (
    "Em {city} com {temp} graus ta um otimo dia pra tomar uma cerveja gelada! [laughing] Ouvindo {station}!",
    "Calor de {temp} graus em {city}! [short pause] Dia perfeito de cervejinha na sombra com {station}!",
    "Com esse calorao em {city}, {temp} graus, nada melhor que cerveja bem gelada e rock na {station}! [laughing]",
    "Confesso: com {temp} graus em {city}, ta pedindo cerveja gelada e musica boa na {station}! [laughing]",
    "Ta {temp} graus em {city}! [short pause] Bom dia pra churrasco, piscina e cerveja gelada ouvindo {station}!",
    "{greeting}! {temp} graus em {city} — dia ideal pra cervejinha bem gelada, ne? [laughing] Fica na {station}!",
    "Aviso da locutora: calor de {temp} graus em {city}! [short pause] Cerveja gelada com moderacao e {station} no volume!",
    "Sol forte em {city}, {temp} graus! [laughing] Cerveja gelada, {title} na {station} — combinacao aprovada!",
    "Em {city} esta {weather} com {temp} graus. [short pause] Dia bonito pra cervejinha gelada e {station}!",
)

_INFO_TIME_WEATHER_TEMPLATES = (
    "{greeting}! Sao {time} em {city}, tempo {weather} com {temp} graus. {station} segue no ar! [short pause]",
    "Horario e clima: {time} em {city}, {weather}, {temp} graus. [short pause] Segue na {station}!",
    "Servico completo da locutora: {time} em {city}, {weather} e {temp} graus. [laughing] Fica na {station}!",
)

_INFO_DAY_TEMPLATES = (
    "Hoje e {weekday} em {city}! [short pause] Voce esta na {station} ouvindo {title}. Bora!",
    "Dica da locutora em {tagline}: hidrate-se no calor de Rondonia e curte a {station}! [short pause]",
    "Informacao util: {weekday}, {time} em {city}. A {station} nao para, ne? [laughing]",
    "{weekday} pede energia! [short pause] Voce ouve {station} e {title} continua rolando!",
)

_INFO_STATION_TEMPLATES = (
    "Voce ouve a {station}, direto de {tagline}. [short pause] Agora sao {time} em {city}!",
    "Recado da locutora: a programacao continua na {station}. {time} em {city}! [short pause]",
    "Ola, eu sou a Hoshino — voce esta ouvindo a {station}, ao vivo de Rondonia. [short pause] Sao {time} em {city}!",
    "Ao vivo na {station}, direto de {tagline}. [short pause] Relogio marca {time} em {city}!",
)

_VOTE_SKIP_YES_TEMPLATES = (
    "Voto aprovado! [laughing] Tchau, {title}! Vou pular essa faixa na {station}. Segura o fone!",
    "Democracia rock! {title}, de {artist}, caiu fora. [short pause] Proxima, baby!",
    "A galera gritou sim! {title} nao aguentou e sai da {station}! [laughing]",
    "Pulou! {title} saiu pela esquerda na {station}. [laughing] Tchau musica!",
    "Skip na veia! {title}, de {artist}, voou da programacao da {station}! [medium pause]",
    "Obedecendo a galera: {title} foi pro saco. {station} segue no grito! [laughing]",
    "Adeus, {title}! [short pause] A {station} girou a chave e vem som novo!",
)

_VOTE_SKIP_YES_REPEAT_TEMPLATES = (
    "De novo?! {title} foi pulada outra vez na {station}. [sigh] To de olho, hein!",
    "Oi, outro skip? {title}, de {artist}, nem respirou direito! [short pause] Nao curti isso...",
    "Segundo pulo seguido! {title} saiu correndo. [short pause] Na {station} a gente respeita o som, ne?",
    "Ta brincando? {title} caiu de novo! [laughing] To comecando a ficar irritada, ouvinte!",
    "Outra vez {title} no lixo! [sigh] Quem manda pular tanto, pensa no {artist}!",
)

_VOTE_SKIP_YES_ANGRY_TEMPLATES = (
    "CHEGA! {title} voou DE NOVO! [laughing] To IRRITADA na {station}! Para de pular!",
    "De novo esse ouvinte! {title} nem completou! [short pause] To com RAIVA, ouviu?!",
    "PARA de pular musica! {title} saiu outra vez e eu nao aguento mais! [laughing]",
    "IRRITADA! {title}, de {artist}, pro lixo DE NOVO! {station} nao e controle remoto! [medium pause]",
    "Explodi! Quantos skips mais em {title}?! [laughing] Chega, ouvinte! RAIVA total!",
    "Hmph! {title} pulada outra vez! [short pause] To furiosa na {station}! Respeita o som!",
)

_VOTE_SKIP_NO_TEMPLATES = (
    "Voto negado! A faixa continua rolando na {station}. [short pause] Deixa rolar!",
    "Nao vai pular! Respeito a {station} e o som segue! [short pause]",
    "A galera quis ficar! {title} continua no ar! [laughing]",
)

_VOTE_SKIP_LOTTERY_YES_TEMPLATES = (
    "Sorteio da sorte! [laughing] A roleta disse pula! Tchau, {title}, na {station}!",
    "Empate no voto, mas o rock decidiu: {title}, de {artist}, caiu fora! [short pause]",
    "A roleta girou! {title} saiu no sorteio da {station}! [laughing]",
)

_VOTE_SKIP_LOTTERY_YES_REPEAT_TEMPLATES = (
    "Sorteio de novo e {title} caiu OUTRA VEZ! [sigh] To comecando a irritar, hein!",
    "A roleta pulou {title} de novo na {station}. [short pause] Ta exagerando, ouvinte!",
)

_VOTE_SKIP_LOTTERY_YES_ANGRY_TEMPLATES = (
    "SORTEIO FURIOSO! {title} voou DE NOVO! [laughing] To IRRITADA com tanto skip!",
    "A roleta gritou pula e {title} caiu OUTRA VEZ! [medium pause] CHEGA de pular na {station}!",
)

_VOTE_SKIP_LOTTERY_NO_TEMPLATES = (
    "Sorteio maluco! [laughing] A roleta disse nao! A faixa fica no ar na {station}!",
    "Empate e a sorte mandou segurar! [short pause] Deixa rolar, {tagline}!",
)

_VOTE_SPOTIFY_NOW_TEMPLATES = (
    "Playlist aprovada! [laughing] Yatta! {title}, de {artist}, na {station}!",
    "A galera quis e entrou! [short pause] {title}, de {artist}, no ar na {station}! [laughing]",
)

_VOTE_SPOTIFY_QUEUE_TEMPLATES = (
    "Playlist na fila da {station}! [short pause] {title} espera a vez. [laughing]",
    "Sem pressa — {title} entrou na fila. [short pause] Ja ja chega na {station}! [laughing]",
)

_VOTE_LIBRARY_NOW_TEMPLATES = (
    "Pedido aprovado! [laughing] Yatta! Tocando ja {title}, de {artist}, na {station}!",
    "Voce pediu e a galera quis! [short pause] {title}, de {artist}, no ar na {station}! [laughing]",
    "O pedido passou! [short pause] {title} so na {station} — musica boa e segredo nosso! [laughing]",
)

_VOTE_LIBRARY_QUEUE_TEMPLATES = (
    "Pedido na fila da {station}! [short pause] {title}, de {artist}, chega em breve. [laughing]",
    "Sem furar fila — {title} na espera da {station}. [short pause] Paciencia, ne? [laughing]",
)

_MOMENT_TEMPLATES: dict[str, tuple[str, ...]] = {
    "track_change": _TRACK_CHANGE_TEMPLATES,
    "mid_track": _MID_TRACK_TEMPLATES,
    "vote_skip_yes": _VOTE_SKIP_YES_TEMPLATES,
    "vote_skip_yes_repeat": _VOTE_SKIP_YES_REPEAT_TEMPLATES,
    "vote_skip_yes_angry": _VOTE_SKIP_YES_ANGRY_TEMPLATES,
    "vote_skip_no": _VOTE_SKIP_NO_TEMPLATES,
    "vote_skip_lottery_yes": _VOTE_SKIP_LOTTERY_YES_TEMPLATES,
    "vote_skip_lottery_yes_repeat": _VOTE_SKIP_LOTTERY_YES_REPEAT_TEMPLATES,
    "vote_skip_lottery_yes_angry": _VOTE_SKIP_LOTTERY_YES_ANGRY_TEMPLATES,
    "vote_skip_lottery_no": _VOTE_SKIP_LOTTERY_NO_TEMPLATES,
    "vote_spotify_now": _VOTE_SPOTIFY_NOW_TEMPLATES,
    "vote_spotify_queue": _VOTE_SPOTIFY_QUEUE_TEMPLATES,
    "vote_library_now": _VOTE_LIBRARY_NOW_TEMPLATES,
    "vote_library_queue": _VOTE_LIBRARY_QUEUE_TEMPLATES,
}


def collect_hoshino_daytime_templates(now, *, mid_track: bool) -> tuple[str, ...]:
    hour = now.hour
    weekday = now.weekday()
    pools: list[tuple[str, ...]] = []

    if mid_track:
        if hour >= 18 or hour < 5:
            pools.append(_MID_DAYTIME_NIGHT)
        if 5 <= hour < 12:
            pools.append(_MID_DAYTIME_MORNING)
        if 12 <= hour < 18:
            pools.append(_MID_DAYTIME_AFTERNOON)
        if weekday == 4 and hour >= 14:
            pools.append(_MID_DAYTIME_FRIDAY)
        if weekday == 5:
            pools.append(_MID_DAYTIME_SATURDAY)
        if weekday == 6:
            pools.append(_MID_DAYTIME_SUNDAY)
            if hour >= 18:
                pools.append(_MID_DAYTIME_SUNDAY_NIGHT)
        if weekday == 0:
            pools.append(_MID_DAYTIME_MONDAY)
    else:
        if hour >= 18 or hour < 5:
            pools.append(_TRACK_DAYTIME_NIGHT)
        if 5 <= hour < 12:
            pools.append(_TRACK_DAYTIME_MORNING)
        if 12 <= hour < 18:
            pools.append(_TRACK_DAYTIME_AFTERNOON)
        if weekday == 4 and hour >= 14:
            pools.append(_TRACK_DAYTIME_FRIDAY)
        if weekday == 5:
            pools.append(_TRACK_DAYTIME_SATURDAY)
        if weekday == 6:
            pools.append(_TRACK_DAYTIME_SUNDAY)
            if hour >= 18:
                pools.append(_TRACK_DAYTIME_SUNDAY_NIGHT)
        if weekday == 0:
            pools.append(_TRACK_DAYTIME_MONDAY)

    merged: list[str] = []
    for pool in pools:
        merged.extend(pool)
    return tuple(merged)


_IDOL_MOMENT_POOLS: dict[str, tuple[str, ...]] = {
    "track_change": _IDOL_TRACK_CHANGE_TEMPLATES,
    "mid_track": _IDOL_MID_TRACK_TEMPLATES,
}


def _maybe_idol_template(moment: str) -> str | None:
    pool = _IDOL_MOMENT_POOLS.get(moment)
    if not pool or random.random() >= HOSHINO_IDOL_CHANCE:
        return None
    return random.choice(pool)


def _moderate_hoshino_expressiveness(text: str) -> str:
    """Reduz risadas repetitivas; preserva [sigh] e parte dos [whispering] em frases suaves."""
    cleaned = re.sub(r"\[medium pause\]", "[short pause]", text, flags=re.IGNORECASE)
    if random.random() > 0.72:
        cleaned = re.sub(r"\s*\[whispering\]", "", cleaned, flags=re.IGNORECASE)

    had_laugh = bool(re.search(r"\[laughing\]", cleaned, re.IGNORECASE))
    cleaned = re.sub(r"\s*\[laughing\]", "", cleaned, flags=re.IGNORECASE)
    if had_laugh and random.random() < HOSHINO_LAUGH_CHANCE:
        cleaned = f"{cleaned.rstrip()} [laughing]"
    return re.sub(r"\s+", " ", cleaned).strip()


def resolve_hoshino_style_prompt(custom: str = "") -> str:
    base = (custom or HOSHINO_STYLE_PROMPT).strip() or HOSHINO_STYLE_PROMPT
    variant = random.choice(HOSHINO_STYLE_VARIANTS)
    return f"{base} {variant}"


def _speed_up_hoshino_mp3(mp3_bytes: bytes, factor: float = HOSHINO_SPEED_FACTOR) -> bytes:
    if factor <= 1.01 or not mp3_bytes:
        return mp3_bytes

    import io

    from pydub import AudioSegment

    audio = AudioSegment.from_file(io.BytesIO(mp3_bytes), format="mp3")
    faster_rate = int(audio.frame_rate * factor)
    faster = audio._spawn(audio.raw_data, overrides={"frame_rate": faster_rate})
    faster = faster.set_frame_rate(audio.frame_rate)
    out = io.BytesIO()
    faster.export(out, format="mp3", bitrate="192k")
    return out.getvalue()


def build_hoshino_mid_info_narration_text(
    *,
    title: str,
    artist: str,
    album: str = "",
    genre: str = "",
) -> str:
    safe_title = _clean_phrase(title, "essa faixa")
    safe_artist = _clean_phrase(artist, "banda desconhecida")
    safe_album = _clean_phrase(album, "")
    genre_label = _clean_phrase(genre, "") or infer_genre_label(safe_title, safe_artist, safe_album)
    weather_bundle = fetch_rondonia_weather()
    primary_city = str(weather_bundle.get("primary") or MIKU_CITY_NAME)
    cities = weather_bundle.get("cities") if isinstance(weather_bundle.get("cities"), dict) else {}
    now = resolve_info_clock(weather_bundle, cities, primary_city)
    regional_stats = compute_regional_weather_stats(cities)
    weather_compare = build_weather_compare(primary_city, cities)
    weather_funny = build_weather_funny_commentary(primary_city, cities)

    ariquemes_data = ariquemes_weather(cities)
    station_data = ariquemes_data or cities.get(primary_city, {}) or {}
    station_city = MIKU_CITY_NAME if ariquemes_data else primary_city
    station_temp = int(station_data.get("temp") or weather_bundle.get("temp") or 0)
    station_weather = str(station_data.get("weather") or weather_bundle.get("weather") or "tempo variavel")

    context = {
        "station": STATION_NAME,
        "tagline": STATION_TAGLINE,
        "city": station_city,
        "time": format_clock_pt(now),
        "greeting": greeting_for_hour(now.hour),
        "weekday": weekday_pt(now),
        "title": safe_title,
        "artist": safe_artist,
        "genre": genre_label,
        "temp": str(station_temp),
        "weather": station_weather,
        "weather_compare": weather_compare,
        "weather_funny": weather_funny,
        "regional_avg": str(regional_stats.get("regional_avg_int") or ""),
    }

    pools: list[tuple[str, ...]] = [
        _INFO_TIME_TEMPLATES,
        _INFO_DAY_TEMPLATES,
        _INFO_STATION_TEMPLATES,
    ]
    if weather_bundle.get("ok"):
        pools.append(_INFO_WEATHER_TEMPLATES)
        pools.append(_INFO_TIME_WEATHER_TEMPLATES)
        if weather_compare:
            pools.append(_INFO_WEATHER_COMPARE_TEMPLATES)
        if weather_funny:
            pools.extend([_INFO_WEATHER_FUNNY_TEMPLATES] * 5)

        ariquemes_data = ariquemes_weather(cities)
        if is_ariguemes_scorching(cities) and ariquemes_data:
            ariquemes_temp = int(ariquemes_data["temp"])
            context["city"] = "Ariquemes"
            context["temp"] = str(ariquemes_temp)
            context["weather"] = str(ariquemes_data.get("weather") or context["weather"])
            beer_line = build_hot_beer_funny_line(ariquemes_temp)
            if not context["weather_funny"] or random.random() < 0.65:
                context["weather_funny"] = beer_line
            pools.extend([_INFO_HOT_BEER_TEMPLATES] * MIKU_HOT_BEER_POOL_WEIGHT)

    template = random.choice(random.choice(pools))
    text = template.format(**context)
    return _moderate_hoshino_expressiveness(text)


def build_hoshino_narration_text(
    *,
    title: str,
    artist: str,
    album: str = "",
    genre: str = "",
    moment: str = "track_change",
) -> str:
    if moment == "mid_info":
        return build_hoshino_mid_info_narration_text(
            title=title,
            artist=artist,
            album=album,
            genre=genre,
        )

    safe_title = _clean_phrase(title, "essa faixa")
    safe_artist = _clean_phrase(artist, "banda desconhecida")
    safe_album = _clean_phrase(album, "")
    genre_label = _clean_phrase(genre, "") or infer_genre_label(safe_title, safe_artist, safe_album)

    base_pool = _MOMENT_TEMPLATES.get(moment) or _TRACK_CHANGE_TEMPLATES
    now = resolve_broadcast_clock()
    context = build_broadcast_context(
        now,
        title=safe_title,
        artist=safe_artist,
        genre=genre_label,
    )

    daytime_pool = collect_hoshino_daytime_templates(now, mid_track=(moment == "mid_track"))
    idol_template = _maybe_idol_template(moment)
    if idol_template:
        template = idol_template
    elif (
        daytime_pool
        and random.random() < HOSHINO_DAYTIME_TEMPLATE_CHANCE
        and not str(moment).startswith("vote_")
    ):
        template = random.choice(daytime_pool)
    else:
        template = random.choice(base_pool)

    text = template.format(**context)
    return _moderate_hoshino_expressiveness(text)


def _estimate_mp3_duration_ms(text: str, raw_len: int) -> int:
    word_estimate = max(int((len(text.split()) / 2.2) * 1000), 1200)
    byte_estimate = max(int((raw_len / 24000) * 1000), 800)
    duration_ms = max(word_estimate, byte_estimate)
    return max(min(duration_ms, HOSHINO_MAX_SECONDS * 1000), 800)


def hoshino_status() -> dict[str, Any]:
    api_ok = False
    api_error = ""
    try:
        from gemini_narrator import resolve_gemini_api_key

        resolve_gemini_api_key()
        api_ok = True
    except Exception as error:
        api_error = str(error)

    return {
        "enabled": os.environ.get("RADIOPOGGERS_HOSHINO_NARRATOR", "1").strip().lower()
        not in {"0", "false", "no", "off"},
        "listener_id": HOSHINO_LISTENER_ID,
        "voice": HOSHINO_VOICE,
        "station_name": STATION_NAME,
        "gemini": {
            "api_key_configured": api_ok,
            "api_error": api_error,
            "models": list(TTS_MODELS),
        },
    }


def generate_hoshino_narration(
    *,
    title: str,
    artist: str,
    album: str = "",
    genre: str = "",
    moment: str = "track_change",
    voice: str = "",
    style_prompt: str = "",
) -> dict[str, Any]:
    safe_moment = moment if moment in HOSHINO_MOMENTS else "track_change"
    text = build_hoshino_narration_text(
        title=title,
        artist=artist,
        album=album,
        genre=genre,
        moment=safe_moment,
    )
    mp3, mime_type, model = synthesize_gemini_mp3(
        text=text,
        voice_name=(voice or HOSHINO_VOICE).strip() or HOSHINO_VOICE,
        style_prompt=resolve_hoshino_style_prompt(style_prompt),
    )
    mp3 = _speed_up_hoshino_mp3(mp3)
    speed = max(HOSHINO_SPEED_FACTOR, 1.0)
    duration_ms = max(int(_estimate_mp3_duration_ms(text, len(mp3)) / speed), 800)
    return {
        "text": text,
        "audio": mp3,
        "mime_type": mime_type,
        "duration_ms": duration_ms,
        "backend": f"gemini:{model}",
        "listener_id": HOSHINO_LISTENER_ID,
        "moment": safe_moment,
        "model": model,
        "voice": voice or HOSHINO_VOICE,
    }

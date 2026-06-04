"""
Narradora IA Miku — locucoes criativas + TTS local (VOICEVOX / Piper / edge-tts).
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import random
import re
import shutil
import subprocess
import threading
import time
import wave
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from pt_katakana import (
    integer_to_spoken_pt,
    portuguese_to_voicevox_katakana,
    prepare_proper_noun_for_speech,
)
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

MIKU_LISTENER_ID = "miku-narrator"
STATION_NAME = os.environ.get("RADIOPOGGERS_MIKU_STATION_NAME", "RADIO NO GRALE").strip()
STATION_TAGLINE = os.environ.get(
    "RADIOPOGGERS_MIKU_TAGLINE",
    "RONDONIA STATE OF BRAZIL",
).strip()
MIKU_MAX_SECONDS = int(os.environ.get("RADIOPOGGERS_MIKU_MAX_SECONDS", "28"))
MIKU_MID_TRACK_CHANCE = float(os.environ.get("RADIOPOGGERS_MIKU_MID_TRACK_CHANCE", "0.58"))
MIKU_MID_COOLDOWN_SEC = float(os.environ.get("RADIOPOGGERS_MIKU_MID_COOLDOWN_SEC", "22"))
MIKU_MIN_TRACK_SECONDS = int(os.environ.get("RADIOPOGGERS_MIKU_MIN_TRACK_SECONDS", "48"))
MIKU_TRACK_CHANGE_DELAY_SEC = float(os.environ.get("RADIOPOGGERS_MIKU_TRACK_CHANGE_DELAY_SEC", "10"))
MIKU_MID_INFO_CHANCE = float(os.environ.get("RADIOPOGGERS_MIKU_MID_INFO_CHANCE", "0.4"))
MIKU_CITY_NAME = os.environ.get("RADIOPOGGERS_MIKU_CITY_NAME", "Ariquemes").strip()
MIKU_WEATHER_PRIMARY = os.environ.get("RADIOPOGGERS_MIKU_WEATHER_PRIMARY", MIKU_CITY_NAME).strip()
MIKU_TIMEZONE = os.environ.get("RADIOPOGGERS_MIKU_TIMEZONE", "America/Porto_Velho").strip()
MIKU_WEATHER_CACHE_SEC = int(os.environ.get("RADIOPOGGERS_MIKU_WEATHER_CACHE_SEC", "900"))
MIKU_HOT_ABOVE_AVG_DELTA = float(os.environ.get("RADIOPOGGERS_MIKU_HOT_ABOVE_AVG_DELTA", "2"))
MIKU_HOT_BEER_MIN_TEMP = int(os.environ.get("RADIOPOGGERS_MIKU_HOT_BEER_MIN_TEMP", "26"))
MIKU_HOT_BEER_POOL_WEIGHT = int(os.environ.get("RADIOPOGGERS_MIKU_HOT_BEER_POOL_WEIGHT", "9"))
MIKU_DAYTIME_TEMPLATE_CHANCE = float(os.environ.get("RADIOPOGGERS_MIKU_DAYTIME_TEMPLATE_CHANCE", "0.38"))
RONDONIA_WEATHER_CITIES: dict[str, tuple[float, float]] = {
    "Ariquemes": (-9.9136, -63.0408),
    "Ji-Parana": (-10.8853, -61.9516),
    "Porto Velho": (-8.7619, -63.9039),
    "Vilhena": (-12.7406, -60.1458),
}
RONDONIA_UTC_OFFSET = timedelta(hours=-4)
MIKU_KATAKANA_PT = os.environ.get("RADIOPOGGERS_MIKU_KATAKANA_PT", "1").strip().lower() not in {"0", "false", "no", "off"}
VOICEVOX_URL = os.environ.get("RADIOPOGGERS_VOICEVOX_URL", "http://127.0.0.1:50021").rstrip("/")
VOICEVOX_SPEAKER = int(os.environ.get("RADIOPOGGERS_VOICEVOX_SPEAKER", "0"))
VOICEVOX_REQUIRE = os.environ.get("RADIOPOGGERS_MIKU_REQUIRE_VOICEVOX", "0").strip().lower() in {"1", "true", "yes", "on"}
# Vozes normais primeiro — leitura PT com sotaque japones natural, sem tom amaama/idol agudo.
VOICEVOX_SPEAKER_FALLBACKS = (
    2,     # 四国めたん ノーマル
    8,     # 春日部つむぎ ノーマル
    3002,  # 四国めたん ノーマル (song)
    3003,  # ずんだもん ノーマル (song)
    3000,  # 四国めたん あまあま (song) — fallback se so song pack
    3001,  # ずんだもん あまあま (song)
)
VOICEVOX_PROSODY: dict[str, dict[str, float]] = {
    "track_change": {
        "speedScale": 0.98,
        "pitchScale": -0.02,
        "intonationScale": 1.08,
        "volumeScale": 1.0,
        "prePhonemeLength": 0.04,
        "postPhonemeLength": 0.06,
        "pauseLengthScale": 0.88,
        "moraPitchBoost": 0.0,
    },
    "mid_track": {
        "speedScale": 0.96,
        "pitchScale": -0.03,
        "intonationScale": 1.05,
        "volumeScale": 1.0,
        "prePhonemeLength": 0.05,
        "postPhonemeLength": 0.06,
        "pauseLengthScale": 0.9,
        "moraPitchBoost": 0.0,
    },
    "mid_info": {
        "speedScale": 0.95,
        "pitchScale": -0.02,
        "intonationScale": 1.04,
        "volumeScale": 1.0,
        "prePhonemeLength": 0.06,
        "postPhonemeLength": 0.07,
        "pauseLengthScale": 0.92,
        "moraPitchBoost": 0.0,
    },
}
_VOTE_PROSODY_DEFAULT = {
    "speedScale": 1.0,
    "pitchScale": -0.01,
    "intonationScale": 1.12,
    "volumeScale": 1.02,
    "prePhonemeLength": 0.05,
    "postPhonemeLength": 0.08,
    "pauseLengthScale": 0.92,
    "moraPitchBoost": 0.0,
}
for _vote_moment in (
    "vote_skip_yes",
    "vote_skip_yes_repeat",
    "vote_skip_yes_angry",
    "vote_skip_no",
    "vote_skip_lottery_yes",
    "vote_skip_lottery_yes_repeat",
    "vote_skip_lottery_yes_angry",
    "vote_skip_lottery_no",
    "vote_spotify_now",
    "vote_spotify_queue",
    "vote_library_now",
    "vote_library_queue",
):
    VOICEVOX_PROSODY[_vote_moment] = dict(_VOTE_PROSODY_DEFAULT)

VOICEVOX_PROSODY["vote_skip_yes_repeat"] = {
    **_VOTE_PROSODY_DEFAULT,
    "speedScale": 1.03,
    "pitchScale": -0.05,
    "intonationScale": 1.24,
    "volumeScale": 1.04,
}
VOICEVOX_PROSODY["vote_skip_lottery_yes_repeat"] = dict(VOICEVOX_PROSODY["vote_skip_yes_repeat"])
VOICEVOX_PROSODY["vote_skip_yes_angry"] = {
    **_VOTE_PROSODY_DEFAULT,
    "speedScale": 1.08,
    "pitchScale": 0.05,
    "intonationScale": 1.4,
    "volumeScale": 1.1,
    "pauseLengthScale": 0.82,
}
VOICEVOX_PROSODY["vote_skip_lottery_yes_angry"] = dict(VOICEVOX_PROSODY["vote_skip_yes_angry"])

MIKU_MOMENTS = frozenset({
    "track_change",
    "mid_track",
    "mid_info",
    "vote_skip_yes",
    "vote_skip_yes_repeat",
    "vote_skip_yes_angry",
    "vote_skip_no",
    "vote_skip_lottery_yes",
    "vote_skip_lottery_yes_repeat",
    "vote_skip_lottery_yes_angry",
    "vote_skip_lottery_no",
    "vote_spotify_now",
    "vote_spotify_queue",
    "vote_library_now",
    "vote_library_queue",
})
PIPER_BIN = os.environ.get("RADIOPOGGERS_PIPER_BIN", "").strip()
PIPER_MODEL = os.environ.get("RADIOPOGGERS_PIPER_MODEL", "").strip()
EDGE_VOICE = os.environ.get("RADIOPOGGERS_MIKU_EDGE_VOICE", "pt-BR-FranciscaNeural").strip()
TTS_MODE = os.environ.get("RADIOPOGGERS_MIKU_TTS", "auto").strip().lower()

_GENRE_HINTS = (
    ("metal", "metal"),
    ("rock", "rock"),
    ("punk", "punk"),
    ("grunge", "grunge"),
    ("hardcore", "hardcore"),
    ("alternative", "alternativo"),
    ("indie", "indie"),
    ("hip hop", "hip hop"),
    ("rap", "rap"),
    ("pop", "pop"),
    ("eletron", "eletronico"),
    ("electronic", "eletronico"),
    ("jazz", "jazz"),
    ("blues", "blues"),
    ("country", "country"),
    ("reggae", "reggae"),
    ("samba", "samba"),
    ("mpb", "MPB"),
    ("forro", "forro"),
    ("sertanejo", "sertanejo"),
)

_TRACK_CHANGE_TEMPLATES = (
    "Ei, ei! Voce esta ouvindo {station}! Agora e {title}, de {artist}. Miku na area!",
    "Miku aqui! Voce esta na {station} ouvindo {title}. Bora, {tagline}!",
    "Atencao, ouvinte! Voce esta ouvindo {station} e vem {title}, de {artist}!",
    "Locucao da Miku: {title}, de {artist}, so na {station}. Segura o fone!",
    "Voce esta na {station} ouvindo {title}. Ouve {genre} com {artist} aqui comigo!",
    "Hihi! {station} no ar com {title}. {artist} mandando ver em {tagline}!",
    "Miku aprova essa! Voce esta ouvindo {station} — agora {title}, de {artist}!",
    "Pisca o alerta: {title}, de {artist}, na {station}. O melhor som de {tagline}!",
    "Voce esta ouvindo {station}! Prepara o coracao: {title}, de {artist}!",
    "Na {station}, eu te jogo {title} com {artist}. Isso e {genre} na veia!",
    "Miku na voz! Voce esta na {station} ouvindo {title}. Nao troca de canal!",
    "Ei, lembra: voce esta ouvindo {station}. Agora toca {title}, de {artist}!",
    # Locutora de radio
    "Ao vivo de {tagline}! Esta e a {station} no ar. Seguinte na programacao: {title}, de {artist}!",
    "Boa noite, ouvintes! Voce sintonizou a {station}. Agora soa {title}, com {artist}. Miku no comando!",
    "Transmitindo ao vivo para todo {tagline}! Na {station}, entra {title}, de {artist}. Fica comigo!",
    "Locutora Miku na antena! Voce esta na {station} ouvindo {genre} raiz. No ar: {title}!",
    "Pessoal da {station}, ligados? Miku aqui! Prepara o fone: {title}, de {artist}, estourando!",
    "Esta e a voz da {station}! {title}, de {artist}, entrando na sua sintonia. Nao desliga!",
    # Anime / kawaii
    "Daisuki, daisuki! Amo demais os ouvintes da {station}! Agora {title}, de {artist}!",
    "Kawaii demais! {title} na {station} — Miku fica feliz ouvindo {genre} com voce!",
    "Yatta yatta! Entrou {title} na {station}! Sugoii, ne? {artist} mandou bem!",
    "Muito kawaii esse som! {artist} com {title} aqui na {station}. Miku curte junto!",
    "Ouw! Daisuki da {station}! Voce ouve {title} e a gente vibra junto em {tagline}!",
    "Ne, ne! {title} na {station} ficou sugoi! Miku aprova com carinho!",
    # Tom irado / rock
    "Atencao, som pesado! {title} explodindo na {station}! Nao abaixa, fera!",
    "Isso e {genre} raiz, ouvinte! {title}, de {artist}, estourando em {tagline}!",
    "Miku irada no ar! {title} no volume maximo na {station}! Segura a onda!",
    "Som insano na {station}! {title}, de {artist}. Isso aqui e puro rock, baby!",
    "Brabo demais! {artist} com {title} na {station}. Miku no grito: deixa rolar!",
    "Alerta vermelho na {station}! {title} chegou pesado. Voce pediu {genre}, toma!",
)

_MID_TRACK_TEMPLATES = (
    "Miku de volta! Voce ainda esta na {station} ouvindo {title}. Continua ai!",
    "Ei, nao esquece: voce esta ouvindo {station} — {title}, de {artist}!",
    "Segura! {title} continua rolando na {station}. Miku manda energia!",
    "Voce esta na {station} ouvindo {artist}. Isso aqui e {genre} com {title}!",
    "Hihi! Ainda e {title} na {station}, o melhor som de {tagline}!",
    "Miku passando pra lembrar: voce esta ouvindo {station}. Ouve {genre} com {artist}!",
    "Continua comigo! {title}, de {artist}, aqui na {station}. Bora bora!",
    "Voce esta ouvindo {station} e {title} nao parou. Miku curte junto!",
    "Pisca o LED! Ainda rola {title} na {station}. {tagline}, baby!",
    "Miku na linha: voce esta na {station} ouvindo {title}. Grita ai no quarto!",
    # Locutora
    "Break rapido da locutora! Voce continua na {station} com {title}, de {artist}!",
    "Ouvintes da {station}, Miku na antena: {title} ainda no ar. Fica sintonizado!",
    "Transmitindo de {tagline}: ainda rola {title} na {station}. Voce e demais!",
    # Anime / kawaii
    "Daisuki! Amo demais quem fica na {station} ouvindo {title}! Kawaii demais!",
    "Sugoii! {title} continua e Miku nao sai da {station}. Yatta, fica comigo!",
    "Ne? Ainda e {title} na {station}. Muito kawaii esse {genre} com {artist}!",
    # Tom irado
    "Miku irada lembrando: {title} ainda detona na {station}! Segura, fera!",
    "Som pesado nao para! {title}, de {artist}, na veia da {station}!",
    "Isso e rock de verdade! {title} continua estourando em {tagline}!",
)

# Locutora por dia / horario (troca de faixa)
_TRACK_DAYTIME_NIGHT = (
    "Que noite boa pra ouvir a {station}! Agora entra {title}, de {artist}!",
    "{greeting}! Que noite boa na {station} — {title}, de {artist}, no ar!",
    "Noite perfeita de radio: {station} te joga {title}, de {artist}. Fica comigo!",
    "Essa noite combina com {station}. Miku apresenta {title}, de {artist}!",
)

_TRACK_DAYTIME_MORNING = (
    "{greeting}! Comeca o dia ouvindo {station} — {title}, de {artist}!",
    "Manha na {station}! Miku acorda voce com {title}, de {artist}!",
    "{weekday} de manha pede {station} no fone. Entra {title}, de {artist}!",
)

_TRACK_DAYTIME_AFTERNOON = (
    "{greeting}! {weekday} a tarde e {station} no ar com {title}, de {artist}!",
    "Tarde boa pra sintonizar {station}! Agora {title}, de {artist}!",
)

_TRACK_DAYTIME_FRIDAY = (
    "Sextou, meus amigos! Hoje e dia de beber uma ouvindo {station} — {title}, de {artist}!",
    "Sextou na {station}! Bora com {title}, de {artist}. {tagline} manda ver!",
    "E sextou! Miku na {station} com {title}, de {artist}. Hoje pede resenha e som bom!",
    "Sextou, ouvinte! {station} no volume com {title}, de {artist}!",
)

_TRACK_DAYTIME_SATURDAY = (
    "Sabado pede {station}! {title}, de {artist}, pra animar o fim de semana!",
    "Fim de semana na {station}! Miku te joga {title}, de {artist}!",
    "Sabado a noite ou de tarde — {station} segue com {title}, de {artist}!",
)

_TRACK_DAYTIME_SUNDAY = (
    "Domingo na {station}! {title}, de {artist}, pra fechar o dia com estilo!",
    "Domingo pede calma e som bom: {station} com {title}, de {artist}!",
)

_TRACK_DAYTIME_SUNDAY_NIGHT = (
    "Domingo a noite! Nao passe por essa situacao sozinho — continua na {station} com {title}, de {artist}!",
    "Domingo a noite e {station} na veia! {title}, de {artist}, pra fechar o fim de semana!",
    "Domingo a noite, {greeting}! Fica na {station} ouvindo {title} — Miku te faz companhia!",
)

_TRACK_DAYTIME_MONDAY = (
    "Segunda com {station} fica menos pesada! {title}, de {artist}, no ar!",
    "Segunda-feira? A {station} salva com {title}, de {artist}!",
)

# Locutora por dia / horario (meio da faixa)
_MID_DAYTIME_NIGHT = (
    "Que noite boa pra ouvir a {station}! {title} continua rolando ai!",
    "{greeting}! Que noite boa na {station} — {title}, de {artist}, segue no ar!",
    "Noite perfeita de radio: voce ainda esta na {station} com {title}!",
)

_MID_DAYTIME_MORNING = (
    "{greeting}! Manha com {station} e {title}, de {artist}. Continua ai!",
    "{weekday} de manha e {station} no fone — {title} ainda rola!",
)

_MID_DAYTIME_AFTERNOON = (
    "{greeting}! {weekday} a tarde e {station} com {title}, de {artist}!",
    "Tarde boa na {station}! {title} continua com voce!",
)

_MID_DAYTIME_FRIDAY = (
    "Sextou e voce ainda ta na {station}! {title}, de {artist}, segue com a gente!",
    "Sextou, meus amigos! Hoje e dia de beber uma ouvindo {station} — {title} no ar!",
    "E sextou! Fica na {station} com {title}. Resenha e radio, ne?",
)

_MID_DAYTIME_SATURDAY = (
    "Sabado na {station}! {title}, de {artist}, continua animando!",
    "Fim de semana e voce na {station} ouvindo {title}. Miku curte!",
)

_MID_DAYTIME_SUNDAY = (
    "Domingo na {station}! {title} continua — fica comigo!",
)

_MID_DAYTIME_SUNDAY_NIGHT = (
    "Domingo a noite! Nao fica sozinho — continua ouvindo {station}! {title} rola ai!",
    "Domingo a noite e {station} na veia! {title}, de {artist}, segue no ar!",
    "Domingo a noite, {greeting}! Nao passe por essa situacao sozinho — fica na {station}!",
)

_MID_DAYTIME_MONDAY = (
    "Segunda com {station} e {title} fica menos pesada. Continua ai!",
)

_INFO_TIME_TEMPLATES = (
    "Break da locutora! {greeting}! Em {city} sao {time}. Voce ouve {station}!",
    "Miku informa: agora sao {time} em {city}, horario de Rondonia. Fica na {station}!",
    "{greeting}, ouvinte! {weekday}, {time} em {city}. {title} continua no ar!",
    "Relogio da {station}: {time} em {city}. {greeting} e deixa o som rolar!",
)

_INFO_WEATHER_TEMPLATES = (
    "Clima em {city}: {weather}, cerca de {temp} graus. Miku na {station} te mantem informado!",
    "Previsao rapida em {city}: {weather}, {temp} graus. Hidrate-se e curte {station}!",
    "Tempo agora em {city}: {weather} com {temp} graus. {station} no ar com {title}!",
    "Miku meteorologa! Em {city} esta {weather}, {temp} graus. Segue {station}!",
)

_INFO_WEATHER_COMPARE_TEMPLATES = (
    "Clima em {city}: {weather}, {temp} graus. Na regiao: {weather_compare}!",
    "Em {city} faz {temp} graus e {weather}. Comparativo Rondonia: {weather_compare}!",
    "Previsao da locutora! {city} com {temp} graus, {weather}. Tambem: {weather_compare}!",
    "{greeting}! {city} marca {temp} graus. Por la: {weather_compare}. Fica na {station}!",
    "Miku monitora Rondonia! Em {city} {weather}, {temp} graus. {weather_compare}!",
)

_INFO_WEATHER_FUNNY_TEMPLATES = (
    "{weather_funny}",
    "Miku meteorologa irada: {weather_funny}",
    "Previsao com humor na {station}: {weather_funny}",
    "{weather_funny} Hihi! {title} continua rolando na {station}!",
    "{greeting}! {weather_funny} Voce ouve {station}!",
    "Servico util e engraçado: {weather_funny}",
)

_INFO_HOT_BEER_TEMPLATES = (
    "Em {city} com {temp} graus ta um otimo dia pra tomar uma cerveja gelada! Miku aprova ouvindo {station}!",
    "Calor de {temp} graus em {city}! Hihi! Dia perfeito de cervejinha na sombra com {station}!",
    "Com esse calorao em {city}, {temp} graus, nada melhor que cerveja bem gelada e rock na {station}!",
    "Miku confessa: com {temp} graus em {city}, ta pedindo cerveja gelada e musica boa na {station}!",
    "Ta {temp} graus em {city}! Bom dia pra churrasco, piscina e cerveja gelada ouvindo {station}!",
    "{greeting}! {temp} graus em {city} — dia ideal pra cervejinha bem gelada, ne? Fica na {station}!",
    "Locutora Miku avisa: calor de {temp} graus em {city}! Cerveja gelada com moderacao e {station} no volume!",
    "Sol forte em {city}, {temp} graus! Cerveja gelada, {title} na {station} — combinacao aprovada pela Miku!",
    "Em {city} esta {weather} com {temp} graus. Miku diz: dia bonito pra cervejinha gelada e {station}!",
)

_HOT_BEER_FUNNY_LINES = (
    "Em Ariquemes com {temp} graus ta pegando fogo — dia perfeito pra cerveja gelada, bicho!",
    "Com {temp} graus em Ariquemes, Miku so pensa em cervejinha gelada na sombra!",
    "Calorao de {temp} graus em Ariquemes! Ta pedindo churrasco, piscina e cerveja bem gelada!",
    "Em Ariquemes faz {temp} graus — otimo dia pra cerveja gelada ouvindo radio, ne?",
    "Miku no calor de Ariquemes, {temp} graus: cervejinha gelada e {station}, combinacao da vitoria!",
)

_PLEASANT_LABELS = (
    "um clima agradavel",
    "tudo tranquilo",
    "clima gostoso",
    "tempo de boa",
    "clima bem de boa",
)

_HOT_PUNCH_MILD = (
    "ta quente hein",
    "sol castigando",
    "quem pode fica na sombra",
)

_HOT_PUNCH_WARM = (
    "esta esquentando demais",
    "sol sem piedade",
    "derretendo o asfalto",
)

_HOT_PUNCH_SCORCHING = (
    "esta pegando fogo bicho",
    "isso ai parece forno de pizza",
    "ate a Miku derrete la",
    "sol castigando sem do",
    "quem pode ta na piscina",
)

_RAIN_PUNCH = (
    "chove que nao para",
    "tempo caprichoso demais",
    "guarda-chuva obrigatorio",
)

_WEATHER_TWIST_PUNCH = (
    "cada canto um clima, ne",
    "Rondonia nao perdoa",
    "plot twist meteorologico",
    "só em Rondonia mesmo",
)

_INFO_TIME_WEATHER_TEMPLATES = (
    "{greeting}! Sao {time} em {city}, tempo {weather} com {temp} graus. {station} segue no ar!",
    "Horario e clima: {time} em {city}, {weather}, {temp} graus. Miku cuida de voce na {station}!",
    "Servico completo da locutora: {time} em {city}, {weather} e {temp} graus. Fica na {station}!",
)

_INFO_DAY_TEMPLATES = (
    "Hoje e {weekday} em {city}! Miku lembra: voce esta na {station} ouvindo {title}. Bora!",
    "Dica da Miku em {tagline}: hidrate-se no calor de Rondonia e fica na {station}!",
    "Informacao util: {weekday}, {time} em {city}. A {station} nao para, ne?",
    "Ne? {weekday} pede energia! Voce ouve {station} e {title} continua rolando!",
)

_INFO_STATION_TEMPLATES = (
    "Voce ouve a {station}, direto de {tagline}. Agora sao {time} em {city}!",
    "Recado da locutora: a melhor programacao continua na {station}. {time} em {city}!",
    "Miku passando: {station} ao vivo de Rondonia. Relogio marca {time} em {city}!",
)

_WEEKDAYS_PT = (
    "segunda-feira",
    "terca-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sabado",
    "domingo",
)

_WEATHER_CACHE: dict[str, Any] = {}
_WEATHER_CACHE_AT = 0.0
_WEATHER_CACHE_LOCK = threading.Lock()

_VOTE_SKIP_YES_TEMPLATES = (
    "Voto aprovado! Tchau, {title}! Miku pula essa faixa na {station}. Segura o fone!",
    "Democracia rock! {title}, de {artist}, caiu fora. Proxima, baby!",
    "A galera gritou sim! {title} nao aguentou e Miku manda embora da {station}!",
    "Pulou! {title} saiu pela esquerda na {station}. Hihi, tchau musica!",
    "Skip na veia! {title}, de {artist}, voou da programacao da {station}!",
    "Miku obedece a galera: {title} foi pro saco. {station} segue no grito!",
    "Adeus, {title}! A {station} girou a chave e vem som novo!",
)

_VOTE_SKIP_YES_REPEAT_TEMPLATES = (
    "De novo?! {title} foi pulada outra vez na {station}. Miku ta de olho, hein!",
    "Oi, outro skip? {title}, de {artist}, nem respirou direito! Miku nao curtiu...",
    "Segundo pulo seguido! {title} saiu correndo. Na {station} a gente respeita o som, ne?",
    "Ta brincando? {title} caiu de novo! Miku comeca a ficar irritada, ouvinte!",
    "Outra vez {title} no lixo! Quem manda pular tanto, pensa no {artist}!",
)

_VOTE_SKIP_YES_ANGRY_TEMPLATES = (
    "CHEGA! {title} voou DE NOVO! Miku ta IRRITADA na {station}! Para de pular!",
    "De novo esse ouvinte! {title} nem completou! Miku ta com RAIVA, ouviu?!",
    "PARA de pular musica! {title} saiu outra vez e a Miku nao aguenta mais!",
    "IRRITADA! {title}, de {artist}, pro lixo DE NOVO! {station} nao e controle remoto!",
    "Miku EXPLODIU! Quantos skips mais em {title}?! Chega, ouvinte! RAIVA total!",
    "Hmph! {title} pulada outra vez! Miku ta furiosa na {station}! Respeita o som!",
)

_VOTE_SKIP_NO_TEMPLATES = (
    "Voto negado! A faixa continua rolando na {station}. Deixa rolar!",
    "Nao vai pular! Miku respeita a {station} e o som segue!",
    "A galera quis ficar! {title} continua no ar!",
)

_VOTE_SKIP_LOTTERY_YES_TEMPLATES = (
    "Sorteio da sorte! A roleta disse pula! Tchau, {title}, na {station}!",
    "Empate no voto, mas o rock decidiu: {title}, de {artist}, caiu fora!",
    "Miku girou o destino! {title} saiu no sorteio da {station}!",
)

_VOTE_SKIP_LOTTERY_YES_REPEAT_TEMPLATES = (
    "Sorteio de novo e {title} caiu OUTRA VEZ! Miku ta comecando a irritar, hein!",
    "A roleta pulou {title} de novo na {station}. Ta exagerando, ouvinte!",
)

_VOTE_SKIP_LOTTERY_YES_ANGRY_TEMPLATES = (
    "SORTEIO FURIOSO! {title} voou DE NOVO! Miku ta IRRITADA com tanto skip!",
    "A roleta gritou pula e {title} caiu OUTRA VEZ! CHEGA de pular na {station}!",
)

_VOTE_SKIP_LOTTERY_NO_TEMPLATES = (
    "Sorteio maluco! A roleta disse nao! A faixa fica no ar na {station}!",
    "Empate e a sorte mandou segurar! Deixa rolar, {tagline}!",
)

_VOTE_SPOTIFY_NOW_TEMPLATES = (
    "Playlist aprovada no grito! Agora e {title}, de {artist}, na {station}!",
    "Votacao rock! Entrou {title} na veia! Miku curte essa!",
)

_VOTE_SPOTIFY_QUEUE_TEMPLATES = (
    "Playlist na fila! {title} espera a vez na {station}. Paz no front!",
    "Sem pressa! {title} entrou na fila da {station}. Miku aprova!",
)

_VOTE_LIBRARY_NOW_TEMPLATES = (
    "Pedido aprovado! Tocando ja {title}, de {artist}, na {station}!",
    "A estante mandou ver! {title} no ar agora! Miku comemora!",
)

_VOTE_LIBRARY_QUEUE_TEMPLATES = (
    "Pedido na fila! {title}, de {artist}, chega depois na {station}!",
    "Sem furar fila! {title} entrou na espera da {station}!",
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


def _clean_phrase(value: str, fallback: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    text = re.sub(r"\([^)]*\)", "", text).strip()
    text = re.sub(r"\[[^\]]*\]", "", text).strip()
    if not text:
        return fallback
    text = prepare_proper_noun_for_speech(text)
    if not text:
        return fallback
    if len(text) > 96:
        return text[:93].rstrip() + "..."
    return text


def infer_genre_label(*parts: str) -> str:
    haystack = " ".join(part.lower() for part in parts if part)
    for needle, label in _GENRE_HINTS:
        if needle in haystack:
            return label
    return "som pesado"


def build_track_key(
    title: str,
    artist: str,
    sh_id: str = "",
    song_id: str = "",
    played_at: str = "",
) -> str:
    return "|".join([
        sh_id.strip(),
        song_id.strip(),
        played_at.strip(),
        _clean_phrase(title, "").lower(),
        _clean_phrase(artist, "").lower(),
    ])


def pick_mid_break_moment() -> str:
    """Escolhe bumper musical ou informativo no mesmo slot de meio de faixa."""
    if random.random() < MIKU_MID_INFO_CHANCE:
        return "mid_info"
    return "mid_track"


def station_timezone():
    try:
        return ZoneInfo(MIKU_TIMEZONE)
    except Exception:
        return timezone(RONDONIA_UTC_OFFSET)


def porto_velho_now() -> datetime:
    return station_local_now()


def station_local_now() -> datetime:
    return datetime.now(station_timezone())


def parse_observed_time(time_value: str) -> datetime | None:
    raw = str(time_value or "").strip()
    if not raw:
        return None
    try:
        observed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if observed.tzinfo is None:
            observed = observed.replace(tzinfo=station_timezone())
        return observed.astimezone(station_timezone())
    except Exception:
        return None


def greeting_for_hour(hour: int) -> str:
    if 5 <= hour < 12:
        return "Bom dia"
    if 12 <= hour < 18:
        return "Boa tarde"
    return "Boa noite"


def format_clock_pt(moment: datetime) -> str:
    hour = moment.hour
    minute = moment.minute
    if hour == 1:
        head = "uma hora"
    else:
        head = f"{integer_to_spoken_pt(hour)} horas"
    if minute == 0:
        return head
    if minute == 30:
        return f"{head} e meia"
    if minute == 1:
        return f"{head} e um minuto"
    return f"{head} e {integer_to_spoken_pt(minute)} minutos"


def format_temp_spoken_pt(temp: int) -> str:
    return integer_to_spoken_pt(int(temp))


def weekday_pt(moment: datetime) -> str:
    return _WEEKDAYS_PT[moment.weekday()]


def daypart_pt(hour: int) -> str:
    if 5 <= hour < 12:
        return "manha"
    if 12 <= hour < 18:
        return "tarde"
    if 18 <= hour < 24:
        return "noite"
    return "madrugada"


def resolve_broadcast_clock() -> datetime:
    with _WEATHER_CACHE_LOCK:
        cached = dict(_WEATHER_CACHE) if _WEATHER_CACHE else {}
        cache_age = time.time() - _WEATHER_CACHE_AT if _WEATHER_CACHE_AT else 9999.0
    observed = cached.get("observed_at")
    if isinstance(observed, datetime) and cache_age < MIKU_WEATHER_CACHE_SEC:
        return observed
    return station_local_now()


def build_broadcast_context(
    now: datetime,
    *,
    title: str,
    artist: str,
    genre: str,
) -> dict[str, str]:
    return {
        "station": STATION_NAME,
        "tagline": STATION_TAGLINE,
        "title": title,
        "artist": artist,
        "genre": genre,
        "weekday": weekday_pt(now),
        "time": format_clock_pt(now),
        "greeting": greeting_for_hour(now.hour),
        "daypart": daypart_pt(now.hour),
    }


def collect_daytime_templates(now: datetime, *, mid_track: bool) -> tuple[str, ...]:
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


def weather_label_from_code(code: int) -> str:
    if code == 0:
        return "ceu limpo"
    if code in {1, 2, 3}:
        return "parcialmente nublado"
    if code in {45, 48}:
        return "neblina"
    if 51 <= code <= 57:
        return "garoa"
    if 61 <= code <= 67:
        return "chuva"
    if 71 <= code <= 77:
        return "tempo frio"
    if 80 <= code <= 82:
        return "pancadas de chuva"
    if code >= 95:
        return "tempestade"
    return "tempo instavel"


def _parse_weather_entry(payload: dict[str, Any]) -> dict[str, Any]:
    current = payload.get("current") if isinstance(payload.get("current"), dict) else {}
    temp_raw = current.get("temperature_2m")
    code_raw = current.get("weather_code", 0)
    temp = int(round(float(temp_raw))) if temp_raw is not None else 0
    code = int(code_raw) if code_raw is not None else 0
    observed_at = parse_observed_time(str(current.get("time") or ""))
    return {
        "ok": True,
        "temp": temp,
        "weather": weather_label_from_code(code),
        "humidity": int(current.get("relative_humidity_2m") or 0),
        "observed_at": observed_at,
    }


def compute_regional_weather_stats(cities: dict[str, dict[str, Any]]) -> dict[str, Any]:
    valid = {name: data for name, data in cities.items() if data.get("ok")}
    temps = [int(data["temp"]) for data in valid.values()]
    if not temps:
        return {"ok": False}

    regional_avg = sum(temps) / len(temps)
    others = [int(data["temp"]) for name, data in valid.items() if name != "Ariquemes"]
    others_avg = (sum(others) / len(others)) if others else regional_avg
    hottest_city = max(valid, key=lambda name: int(valid[name]["temp"]))

    return {
        "ok": True,
        "regional_avg": regional_avg,
        "regional_avg_int": int(round(regional_avg)),
        "regional_max": max(temps),
        "regional_min": min(temps),
        "others_avg": others_avg,
        "others_avg_int": int(round(others_avg)),
        "hottest_city": hottest_city,
        "city_count": len(temps),
    }


def resolve_info_clock(
    weather_bundle: dict[str, Any],
    cities: dict[str, dict[str, Any]],
    primary_city: str,
) -> datetime:
    observed = weather_bundle.get("observed_at")
    if isinstance(observed, datetime):
        return observed

    primary_data = cities.get(primary_city, {})
    if isinstance(primary_data, dict):
        primary_observed = primary_data.get("observed_at")
        if isinstance(primary_observed, datetime):
            return primary_observed

    ariquemes_data = ariquemes_weather(cities)
    ariquemes_observed = ariquemes_data.get("observed_at")
    if isinstance(ariquemes_observed, datetime):
        return ariquemes_observed

    return station_local_now()


def fetch_rondonia_weather() -> dict[str, Any]:
    global _WEATHER_CACHE, _WEATHER_CACHE_AT

    now = time.time()
    with _WEATHER_CACHE_LOCK:
        if _WEATHER_CACHE and (now - _WEATHER_CACHE_AT) < MIKU_WEATHER_CACHE_SEC:
            return dict(_WEATHER_CACHE)

    primary = MIKU_WEATHER_PRIMARY if MIKU_WEATHER_PRIMARY in RONDONIA_WEATHER_CITIES else "Ariquemes"
    city_names = list(RONDONIA_WEATHER_CITIES.keys())
    latitudes = ",".join(str(RONDONIA_WEATHER_CITIES[name][0]) for name in city_names)
    longitudes = ",".join(str(RONDONIA_WEATHER_CITIES[name][1]) for name in city_names)

    try:
        tz = quote(MIKU_TIMEZONE, safe="")
        url = (
            "https://api.open-meteo.com/v1/forecast?"
            f"latitude={latitudes}&longitude={longitudes}"
            f"&current=temperature_2m,relative_humidity_2m,weather_code"
            f"&timezone={tz}"
        )
        payload = _http_json(url, timeout=10)
        if not isinstance(payload, list):
            raise RuntimeError("Resposta de clima invalida.")

        cities: dict[str, dict[str, Any]] = {}
        for index, name in enumerate(city_names):
            if index >= len(payload):
                cities[name] = {"ok": False}
                continue
            entry = payload[index]
            if isinstance(entry, dict) and entry.get("current"):
                cities[name] = _parse_weather_entry(entry)
            else:
                cities[name] = {"ok": False}

        primary_weather = cities.get(primary, {"ok": False})
        observed_at = None
        if isinstance(primary_weather, dict):
            observed_at = primary_weather.get("observed_at")
        if not isinstance(observed_at, datetime):
            for city_data in cities.values():
                if isinstance(city_data, dict) and isinstance(city_data.get("observed_at"), datetime):
                    observed_at = city_data["observed_at"]
                    break

        result = {
            "ok": bool(primary_weather.get("ok")),
            "primary": primary,
            "cities": cities,
            "observed_at": observed_at,
            **({} if not primary_weather.get("ok") else primary_weather),
        }
        stats = compute_regional_weather_stats(cities)
        if stats.get("ok"):
            result["regional_avg_int"] = stats["regional_avg_int"]
            result["regional_max"] = stats["regional_max"]
            result["regional_min"] = stats["regional_min"]
        with _WEATHER_CACHE_LOCK:
            _WEATHER_CACHE = result
            _WEATHER_CACHE_AT = now
        return dict(result)
    except Exception:
        return {"ok": False, "primary": primary, "cities": {}}


def build_weather_compare(primary: str, cities: dict[str, dict[str, Any]]) -> str:
    others = [name for name in RONDONIA_WEATHER_CITIES if name != primary]
    random.shuffle(others)
    snippets: list[str] = []
    for name in others:
        data = cities.get(name, {})
        if not data.get("ok"):
            continue
        snippets.append(
            f"em {name} {format_temp_spoken_pt(int(data['temp']))} graus e {data['weather']}"
        )
        if len(snippets) >= 3:
            break
    return "; ".join(snippets)


def pleasant_weather_label(temp: int, weather: str, regional_avg: int) -> str:
    if "chuva" in weather or "tempestade" in weather or "garoa" in weather:
        return random.choice(["tempo caprichoso", "clima de chuva", "tempo instavel"])
    if temp >= regional_avg + 4:
        return "clima quente demais"
    if temp >= regional_avg + 2:
        return random.choice(["clima quente mas suportavel", "sol forte mas da pra aguentar"])
    if temp <= regional_avg - 3:
        return random.choice(["clima fresquinho", "tempo ameno"])
    return random.choice(_PLEASANT_LABELS)


def hot_weather_punch(temp: int, regional_avg: int) -> str:
    if temp >= regional_avg + 5:
        return random.choice(_HOT_PUNCH_SCORCHING)
    if temp >= regional_avg + 3:
        return random.choice(_HOT_PUNCH_WARM)
    if temp >= regional_avg + 1:
        return random.choice(_HOT_PUNCH_MILD)
    return random.choice(["ta esquentando", "sol aparecendo forte"])


def ariquemes_weather(cities: dict[str, dict[str, Any]]) -> dict[str, Any]:
    data = cities.get("Ariquemes", {})
    return data if data.get("ok") else {}


def is_ariguemes_scorching(cities: dict[str, dict[str, Any]]) -> bool:
    """True quando Ariquemes esta bem acima da media regional medida ao vivo."""
    ariquemes_data = ariquemes_weather(cities)
    stats = compute_regional_weather_stats(cities)
    if not ariquemes_data or not stats.get("ok"):
        return False

    ariquemes_temp = int(ariquemes_data["temp"])
    others_avg = float(stats["others_avg"])
    regional_avg = float(stats["regional_avg"])
    hottest_city = str(stats["hottest_city"])

    if ariquemes_temp < MIKU_HOT_BEER_MIN_TEMP:
        return False

    above_others = ariquemes_temp >= (others_avg + MIKU_HOT_ABOVE_AVG_DELTA)
    hottest_in_region = hottest_city == "Ariquemes" and ariquemes_temp > others_avg
    warm_region = regional_avg >= (MIKU_HOT_BEER_MIN_TEMP - 2)

    return warm_region and (above_others or hottest_in_region)


def build_hot_beer_funny_line(temp: int) -> str:
    template = random.choice(_HOT_BEER_FUNNY_LINES)
    return template.format(
        temp=format_temp_spoken_pt(temp),
        station=STATION_NAME,
    )


def build_weather_funny_commentary(primary: str, cities: dict[str, dict[str, Any]]) -> str:
    primary_data = cities.get(primary, {})
    if not primary_data.get("ok"):
        return ""

    valid = {name: data for name, data in cities.items() if data.get("ok")}
    if len(valid) < 2:
        return ""

    primary_temp = int(primary_data["temp"])
    primary_weather = str(primary_data["weather"])
    stats = compute_regional_weather_stats(valid)
    regional_avg = int(stats.get("regional_avg_int") or primary_temp)
    hottest_name = max(valid, key=lambda name: int(valid[name]["temp"]))
    coolest_name = min(valid, key=lambda name: int(valid[name]["temp"]))
    hottest = valid[hottest_name]
    coolest = valid[coolest_name]
    hottest_temp = int(hottest["temp"])
    coolest_temp = int(coolest["temp"])

    variants: list[str] = []

    ariquemes_data = ariquemes_weather(valid)
    if ariquemes_data and is_ariguemes_scorching(valid):
        ariquemes_temp = int(ariquemes_data["temp"])
        variants.extend(build_hot_beer_funny_line(ariquemes_temp) for _ in range(4))

    if primary != hottest_name and hottest_temp - primary_temp >= 3:
        variants.append(
            f"Em {primary} esta {pleasant_weather_label(primary_temp, primary_weather, regional_avg)} com "
            f"{format_temp_spoken_pt(primary_temp)} graus, enquanto isso em {hottest_name}, com "
            f"{format_temp_spoken_pt(hottest_temp)} graus, "
            f"{hot_weather_punch(hottest_temp, regional_avg)}!"
        )

    if primary == hottest_name and primary_temp >= regional_avg + 2:
        cool_data = valid.get(coolest_name, {})
        if coolest_name != primary and primary_temp - coolest_temp >= 3:
            variants.append(
                f"Em {primary} com {format_temp_spoken_pt(primary_temp)} graus "
                f"{hot_weather_punch(primary_temp, regional_avg)}! "
                f"Ja em {coolest_name}, so {format_temp_spoken_pt(coolest_temp)} graus, la ta "
                f"{pleasant_weather_label(coolest_temp, str(cool_data.get('weather', '')), regional_avg)}!"
            )

    rainy = [name for name, data in valid.items() if "chuva" in str(data.get("weather", ""))]
    sunny = [name for name, data in valid.items() if data.get("weather") == "ceu limpo"]
    if rainy and sunny:
        rain_city = random.choice(rainy)
        sun_city = random.choice(sunny)
        if rain_city != sun_city:
            rain_data = valid[rain_city]
            sun_data = valid[sun_city]
            variants.append(
                f"Em {sun_city} ta {sun_data['weather']} com {format_temp_spoken_pt(int(sun_data['temp']))} graus, "
                f"mas la em {rain_city} {random.choice(_RAIN_PUNCH)} com "
                f"{format_temp_spoken_pt(int(rain_data['temp']))} graus!"
            )

    if hottest_temp - coolest_temp >= 6:
        variants.append(
            f"De {coolest_name} com {format_temp_spoken_pt(coolest_temp)} graus ate {hottest_name} com "
            f"{format_temp_spoken_pt(hottest_temp)} graus — "
            f"{random.choice(_WEATHER_TWIST_PUNCH)}!"
        )

    if not variants:
        others = [name for name in valid if name != primary]
        if others:
            other_name = random.choice(others)
            other_data = valid[other_name]
            variants.append(
                f"Em {primary}: {format_temp_spoken_pt(primary_temp)} graus e {primary_weather}. "
                f"Em {other_name} sao {format_temp_spoken_pt(int(other_data['temp']))} graus — "
                f"{random.choice(_WEATHER_TWIST_PUNCH)}!"
            )

    return random.choice(variants) if variants else ""


def fetch_city_weather() -> dict[str, Any]:
    """Compatibilidade: retorna clima da cidade primaria (Ariquemes por padrao)."""
    bundle = fetch_rondonia_weather()
    if not bundle.get("ok"):
        return {"ok": False}
    return {
        "ok": True,
        "temp": bundle.get("temp"),
        "weather": bundle.get("weather"),
        "humidity": bundle.get("humidity"),
    }


def build_mid_info_narration_text(
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
        "temp": format_temp_spoken_pt(station_temp),
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
            context["temp"] = format_temp_spoken_pt(ariquemes_temp)
            context["weather"] = str(ariquemes_data.get("weather") or context["weather"])
            beer_line = build_hot_beer_funny_line(ariquemes_temp)
            if not context["weather_funny"] or random.random() < 0.65:
                context["weather_funny"] = beer_line
            pools.extend([_INFO_HOT_BEER_TEMPLATES] * MIKU_HOT_BEER_POOL_WEIGHT)

    template = random.choice(random.choice(pools))
    text = template.format(**context)
    return re.sub(r"\s+", " ", text).strip()


def build_narration_text(
    *,
    title: str,
    artist: str,
    album: str = "",
    genre: str = "",
    moment: str = "track_change",
) -> str:
    if moment == "mid_info":
        return build_mid_info_narration_text(
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

    daytime_pool = collect_daytime_templates(now, mid_track=(moment == "mid_track"))
    if (
        daytime_pool
        and random.random() < MIKU_DAYTIME_TEMPLATE_CHANCE
        and not str(moment).startswith("vote_")
    ):
        template = random.choice(daytime_pool)
    else:
        template = random.choice(base_pool)

    text = template.format(**context)
    return re.sub(r"\s+", " ", text).strip()


def wav_duration_ms(raw: bytes) -> int:
    with wave.open(io.BytesIO(raw), "rb") as handle:
        frames = handle.getnframes()
        rate = handle.getframerate() or 44100
        return max(int((frames / rate) * 1000), 500)


def _http_json(url: str, payload: dict[str, Any] | None = None, timeout: int = 20, method: str = "") -> Any:
    data = None
    headers: dict[str, str] = {}
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")

    http_method = method or ("POST" if payload is not None else "GET")
    request = Request(url, data=data, headers=headers, method=http_method)
    with urlopen(request, timeout=timeout) as response:
        body = response.read()
        if not body:
            return None
        content_type = response.headers.get("Content-Type", "")
        if "json" in content_type:
            return json.loads(body.decode("utf-8"))
        return body


def _voicevox_audio_query(text: str, speaker: int) -> dict[str, Any] | None:
    url = f"{VOICEVOX_URL}/audio_query?text={quote(text)}&speaker={speaker}"
    result = _http_json(url, timeout=25, method="POST")
    return result if isinstance(result, dict) else None


def voicevox_available() -> bool:
    try:
        with urlopen(f"{VOICEVOX_URL}/version", timeout=2) as response:
            return response.status == 200
    except (URLError, OSError, TimeoutError, ValueError):
        return False


def piper_available() -> bool:
    binary = PIPER_BIN or shutil.which("piper") or ""
    return bool(binary and PIPER_MODEL and Path_exists(PIPER_MODEL))


def Path_exists(path: str) -> bool:
    from pathlib import Path

    return Path(path).exists()


def edge_available() -> bool:
    try:
        import edge_tts  # noqa: F401

        return True
    except ImportError:
        return False


def resolve_tts_backend(preferred: str = "") -> str:
    mode = (preferred or TTS_MODE or "auto").lower()
    if mode not in {"", "auto"}:
        return mode

    if voicevox_available():
        return "voicevox"
    if VOICEVOX_REQUIRE:
        return "none"
    if piper_available():
        return "piper"
    if edge_available():
        return "edge"
    return "none"


def _voicevox_speaker_candidates() -> list[int]:
    if VOICEVOX_SPEAKER > 0:
        return [VOICEVOX_SPEAKER]
    return list(VOICEVOX_SPEAKER_FALLBACKS)


def _apply_voicevox_prosody(query: dict[str, Any], moment: str) -> dict[str, Any]:
    preset = VOICEVOX_PROSODY.get(moment, VOICEVOX_PROSODY["track_change"])
    mora_boost = float(preset.get("moraPitchBoost", 0.0))

    for key, value in preset.items():
        if key == "moraPitchBoost":
            continue
        query[key] = value

    accent_phrases = query.get("accent_phrases")
    if isinstance(accent_phrases, list) and mora_boost:
        for phrase in accent_phrases:
            if not isinstance(phrase, dict):
                continue
            moras = phrase.get("moras")
            if not isinstance(moras, list):
                continue
            for mora in moras:
                if not isinstance(mora, dict):
                    continue
                pitch = mora.get("pitch")
                if isinstance(pitch, (int, float)):
                    mora["pitch"] = float(pitch) + mora_boost

    return query


def _prepare_voicevox_text(text: str) -> str:
    if not MIKU_KATAKANA_PT:
        return text
    return portuguese_to_voicevox_katakana(text)


def synthesize_voicevox(text: str, moment: str = "track_change") -> tuple[bytes, str, int]:
    errors: list[str] = []
    safe_moment = moment if moment in VOICEVOX_PROSODY else "track_change"
    tts_text = _prepare_voicevox_text(text)

    for speaker in _voicevox_speaker_candidates():
        try:
            query = _voicevox_audio_query(tts_text, speaker)
            if not query:
                errors.append(f"speaker {speaker}: audio_query invalido")
                continue

            query = _apply_voicevox_prosody(query, safe_moment)
            raw = _http_json(
                f"{VOICEVOX_URL}/synthesis?speaker={speaker}",
                payload=query,
                timeout=60,
            )
            if isinstance(raw, (bytes, bytearray)) and raw:
                return bytes(raw), "audio/wav", speaker
            errors.append(f"speaker {speaker}: audio vazio")
        except Exception as error:
            errors.append(f"speaker {speaker}: {error}")

    hint = (
        "Instale VOICEVOX Engine e deixe aberto em http://127.0.0.1:50021. "
        "Rode .\\scripts\\install-voicevox-miku.ps1"
    )
    detail = errors[-1] if errors else "VOICEVOX indisponivel"
    raise RuntimeError(f"{detail}. {hint}")


def synthesize_piper(text: str) -> tuple[bytes, str]:
    binary = PIPER_BIN or shutil.which("piper") or ""
    if not binary or not PIPER_MODEL:
        raise RuntimeError("Piper nao configurado. Defina RADIOPOGGERS_PIPER_BIN e RADIOPOGGERS_PIPER_MODEL.")

    process = subprocess.run(
        [binary, "--model", PIPER_MODEL, "--output_file", "-"],
        input=text.encode("utf-8"),
        capture_output=True,
        timeout=60,
        check=False,
    )
    if process.returncode != 0 or not process.stdout:
        stderr = process.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(stderr or "Piper falhou ao sintetizar.")

    return process.stdout, "audio/wav"


def synthesize_edge(text: str) -> tuple[bytes, str]:
    try:
        import edge_tts
    except ImportError as error:
        raise RuntimeError("Instale edge-tts: python -m pip install edge-tts") from error

    async def _run() -> bytes:
        communicate = edge_tts.Communicate(text, EDGE_VOICE)
        chunks: list[bytes] = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                chunks.append(chunk["data"])
        if not chunks:
            raise RuntimeError("edge-tts nao gerou audio.")
        return b"".join(chunks)

    return asyncio.run(_run()), "audio/mpeg"


def synthesize_miku_speech(text: str, backend: str = "", moment: str = "track_change") -> tuple[bytes, str, str]:
    selected = resolve_tts_backend(backend)
    if selected == "none":
        if VOICEVOX_REQUIRE or (backend or TTS_MODE).lower() == "voicevox":
            raise RuntimeError(
                "VOICEVOX nao esta rodando. A voz estilo Miku com entonacao exige o engine local gratis. "
                "Rode .\\scripts\\install-voicevox-miku.ps1 e reinicie a API."
            )
        raise RuntimeError(
            "Nenhum TTS disponivel. Instale VOICEVOX (recomendado) ou edge-tts "
            "(python -m pip install edge-tts)."
        )

    used_speaker = VOICEVOX_SPEAKER
    if selected == "voicevox":
        raw, mime, used_speaker = synthesize_voicevox(text, moment=moment)
    elif selected == "piper":
        raw, mime = synthesize_piper(text)
    elif selected == "edge":
        raw, mime = synthesize_edge(text)
    else:
        raise RuntimeError(f"Backend TTS desconhecido: {selected}")

    backend_label = selected if selected != "voicevox" else f"voicevox:{used_speaker}"
    return raw, mime, backend_label


def miku_status() -> dict[str, Any]:
    backend = resolve_tts_backend()
    return {
        "enabled": os.environ.get("RADIOPOGGERS_MIKU_NARRATOR", "1").strip() not in {"0", "false", "no"},
        "station_name": STATION_NAME,
        "listener_id": MIKU_LISTENER_ID,
        "tts_mode": TTS_MODE,
        "resolved_backend": backend,
        "voicevox": {
            "url": VOICEVOX_URL,
            "speaker": VOICEVOX_SPEAKER,
            "speaker_auto_fallbacks": list(VOICEVOX_SPEAKER_FALLBACKS),
            "require_engine": VOICEVOX_REQUIRE,
            "available": voicevox_available(),
            "note": "Voz oficial Hatsune Miku (Vocaloid) nao e gratuita. VOICEVOX Song e o caminho gratis/legal mais proximo.",
        },
        "piper": {
            "binary": PIPER_BIN or shutil.which("piper") or "",
            "model": PIPER_MODEL,
            "available": piper_available(),
        },
        "edge": {
            "voice": EDGE_VOICE,
            "available": edge_available(),
        },
        "mid_track_chance": MIKU_MID_TRACK_CHANCE,
        "mid_info_chance": MIKU_MID_INFO_CHANCE,
        "mid_track_cooldown_sec": MIKU_MID_COOLDOWN_SEC,
        "city_name": MIKU_CITY_NAME,
        "weather_primary": MIKU_WEATHER_PRIMARY,
        "hot_above_avg_delta_c": MIKU_HOT_ABOVE_AVG_DELTA,
        "hot_beer_min_temp_c": MIKU_HOT_BEER_MIN_TEMP,
        "daytime_template_chance": MIKU_DAYTIME_TEMPLATE_CHANCE,
        "weather_cities": list(RONDONIA_WEATHER_CITIES.keys()),
        "timezone": MIKU_TIMEZONE,
        "katakana_portuguese": MIKU_KATAKANA_PT,
    }


def generate_miku_narration(
    *,
    title: str,
    artist: str,
    album: str = "",
    genre: str = "",
    backend: str = "",
    moment: str = "track_change",
) -> dict[str, Any]:
    safe_moment = moment if moment in MIKU_MOMENTS else "track_change"
    text = build_narration_text(
        title=title,
        artist=artist,
        album=album,
        genre=genre,
        moment=safe_moment,
    )
    raw, mime_type, used_backend = synthesize_miku_speech(text, backend=backend, moment=safe_moment)
    if mime_type.endswith("wav"):
        duration_ms = wav_duration_ms(raw)
        # Margem para o app nao cortar a frase no fim (ex.: "Linkin Park").
        duration_ms = int(duration_ms * 1.12) + 450
    else:
        duration_ms = max(2500, int((len(text.split()) / 2.5) * 1000))
    duration_ms = max(min(duration_ms, MIKU_MAX_SECONDS * 1000), 800)
    return {
        "text": text,
        "tts_text": _prepare_voicevox_text(text) if resolve_tts_backend(backend) == "voicevox" else text,
        "audio": raw,
        "mime_type": mime_type,
        "duration_ms": duration_ms,
        "backend": used_backend,
        "listener_id": MIKU_LISTENER_ID,
        "moment": safe_moment,
    }

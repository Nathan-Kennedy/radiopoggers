"""
PT-BR -> katakana para VOICEVOX/OpenJTalk.

OpenJTalk nao le bem alfabeto latino; katakana deixa o portugues mais nitido
mantendo a vibe de japones falando portugues.
"""

from __future__ import annotations

import re
import unicodedata

_WORD_RE = re.compile(r"[A-Za-zÀ-ÿ0-9]+(?:['-][A-Za-zÀ-ÿ0-9]+)*", re.UNICODE)
_DIGITS_RE = re.compile(r"\b\d+\b")

# Contagem em PT-BR (antes do katakana — evita leitura japonesa de algarismos).
_UNITS_PT = (
    "zero",
    "um",
    "dois",
    "tres",
    "quatro",
    "cinco",
    "seis",
    "sete",
    "oito",
    "nove",
)
_TEENS_PT = (
    "dez",
    "onze",
    "doze",
    "treze",
    "catorze",
    "quinze",
    "dezesseis",
    "dezessete",
    "dezoito",
    "dezenove",
)
_TENS_PT = (
    "",
    "",
    "vinte",
    "trinta",
    "quarenta",
    "cinquenta",
    "sessenta",
    "setenta",
    "oitenta",
    "noventa",
)

# Palavras fixas dos templates + funcao gramatical.
_LEXICON: dict[str, str] = {
    "a": "ア",
    "agora": "アゴラ",
    "ai": "アイ",
    "ainda": "アインダ",
    "alerta": "アレルタ",
    "aprova": "アプロヴァ",
    "area": "アレア",
    "ar": "アール",
    "artista": "アルチスタ",
    "atencao": "アテンサン",
    "baby": "ベイビ",
    "bora": "ボラ",
    "brazil": "ブラジウ",
    "canal": "カナウ",
    "com": "コン",
    "comigo": "コミゴ",
    "aqui": "アキ",
    "continua": "コンティヌア",
    "coracao": "コラサン",
    "curte": "クルチ",
    "da": "ダ",
    "de": "ジ",
    "desconhecido": "デスコニヘシド",
    "desconhecida": "デスコニヘシダ",
    "do": "ド",
    "ei": "エイ",
    "e": "イ",
    "em": "エン",
    "energia": "エネルジア",
    "esquece": "エスケセ",
    "essa": "エッサ",
    "estado": "エスタド",
    "esta": "エスタ",
    "faixa": "ファイシャ",
    "fone": "フォネ",
    "grale": "グラレ",
    "grita": "グリタ",
    "hihi": "ヒヒ",
    "iss": "イッ",
    "isso": "イッソ",
    "junto": "ジュント",
    "la": "ラ",
    "led": "レッジ",
    "eu": "エウ",
    "jogo": "ジョゴ",
    "lembra": "レンブラ",
    "lembrar": "レンブラール",
    "linha": "リーニャ",
    "locucao": "ロクサン",
    "mandando": "マンダンド",
    "melhor": "メリョール",
    "miku": "ミク",
    "na": "ナ",
    "no": "ノ",
    "ouve": "オウヴェ",
    "parou": "パロウ",
    "passando": "パサンド",
    "nao": "ナン",
    "o": "ウ",
    "ouvindo": "オヴィンド",
    "ouvinte": "オヴィンチ",
    "para": "パラ",
    "pra": "プラ",
    "prepara": "プレパラ",
    "pisca": "ピスカ",
    "quarto": "クアルト",
    "radio": "ラジオ",
    "rola": "ロラ",
    "rolando": "ロランド",
    "rondonia": "ホンドニア",
    "segura": "セグラ",
    "so": "ソウ",
    "som": "ソン",
    "state": "ステイト",
    "te": "チ",
    "toca": "トカ",
    "troca": "トロカ",
    "veia": "ヴェア",
    "vem": "ヴェン",
    "ver": "ヴェール",
    "voce": "ヴォセ",
    "voz": "ヴォズ",
    "volta": "ヴォルタ",
    "voto": "ヴォト",
    "votacao": "ヴォタサン",
    "aprovado": "アプロヴァド",
    "negado": "ネガド",
    "galera": "ガレラ",
    "pula": "プラ",
    "pulei": "プリ",
    "sorteio": "ソルテイオ",
    "roleta": "ロレタ",
    "empate": "エンパチ",
    "playlist": "プレイリスト",
    "fila": "フィラ",
    "estante": "エスタンチ",
    "pedido": "ペディド",
    "furar": "フラール",
    "democracia": "デモクラシア",
    "destino": "デスティノ",
    "comemora": "コメモラ",
    "maluco": "マルク",
    "proxima": "プロクシマ",
    "espera": "エスペラ",
    "musica": "ムジカ",
    "velha": "ヴェリャ",
    "tchau": "チャウ",
    "decidiu": "デシジウ",
    "front": "フロント",
    "paz": "パス",
    "pressa": "プレッサ",
    "rock": "ロック",
    # Anime / locutora
    "daisuki": "ダイスキ",
    "daisuke": "ダイスケ",
    "kawaii": "カワイイ",
    "sugoi": "スゴイ",
    "sugoii": "スゴイ",
    "yatta": "ヤッタ",
    "ne": "ネ",
    "ouw": "オウ",
    "amo": "アモ",
    "demais": "デマイス",
    "ouvintes": "オヴィンチス",
    "locutora": "ロクトゥラ",
    "transmissao": "トランスミサン",
    "programacao": "プログラマサン",
    "sintonizou": "シントニザウ",
    "sintonia": "シントニア",
    "sintonizado": "シントニザド",
    "sintonizar": "シントニザール",
    "transmitindo": "トランスミティンド",
    "boa": "ボア",
    "noite": "ノイチ",
    "antena": "アンテナ",
    "break": "ブレイク",
    "rapido": "ラピド",
    "pessoal": "ペソアウ",
    "ligados": "リガドス",
    "feliz": "フェリス",
    "carinho": "カリーニョ",
    "gente": "ジェンチ",
    "vibra": "ヴィブラ",
    "irada": "イラダ",
    "irado": "イラド",
    "fera": "フェラ",
    "insano": "インサノ",
    "explodindo": "エスプロジンド",
    "estourando": "エストウランド",
    "estoura": "エストウラ",
    "detona": "デトナ",
    "brabo": "ブラボ",
    "absurdo": "アブスルド",
    "verdade": "ヴェルダージ",
    "vermelho": "ヴェルメリョ",
    "volume": "ヴォリュメ",
    "maximo": "マクシモ",
    "onda": "オンダ",
    "raiz": "ハイジ",
    "pesado": "ペザド",
    "puro": "ピュロ",
    "chegou": "シェゴウ",
    "chegando": "シェガンド",
    "seguinte": "セグインチ",
    "comando": "コマンド",
    "vivo": "ヴィヴォ",
    "todo": "トド",
    "desliga": "デスリガ",
    "muito": "ムイト",
    "fica": "フィカ",
    "pediu": "ペディウ",
    "toma": "トマ",
    "grito": "グリト",
    "deixa": "デイシャ",
    # Clima / horario / informativo
    "clima": "クリマ",
    "horario": "オラリオ",
    "horas": "オラス",
    "hora": "オラ",
    "uma": "ウマ",
    "meia": "メイア",
    "minuto": "ミヌート",
    "minutos": "ミヌートス",
    "graus": "グラウス",
    "grau": "グラウ",
    "menos": "メノス",
    "catorze": "カトルゼ",
    "quinze": "キンゼ",
    "dezesseis": "デゼセイス",
    "dezessete": "デゼセテ",
    "dezoito": "デゾイト",
    "dezenove": "デゼノーヴェ",
    "vinte": "ヴィンチ",
    "trinta": "トリンタ",
    "quarenta": "クアレンタ",
    "cinquenta": "キンクエンタ",
    "sessenta": "セセンタ",
    "setenta": "セテンタ",
    "oitenta": "オイテンタ",
    "noventa": "ノヴェンタ",
    "cem": "セン",
    "previsao": "プレビサン",
    "meteorologa": "メテオロジガ",
    "servico": "セルヴィソ",
    "relogio": "レロジオ",
    "informacao": "インフォルマサン",
    "informa": "インフォルマ",
    "util": "ウティウ",
    "completo": "コンプレト",
    "recado": "レカド",
    "hidrate": "イドラチ",
    "hidrate-se": "イドラチセ",
    "variavel": "ヴァリアヴェウ",
    "instavel": "インスタヴェウ",
    "neblina": "ネブリナ",
    "garoa": "ガロア",
    "chuva": "チュヴァ",
    "tempestade": "テンペスタジ",
    "pancadas": "パンカダス",
    "limpo": "リンポ",
    "nublado": "ヌブラド",
    "porto": "ポルト",
    "velho": "ヴェリョ",
    "ariquemes": "アリケメス",
    "vilhena": "ヴィリェナ",
    "ji-parana": "ジパラナ",
    "parana": "パラナ",
    "comparativo": "コンパラティヴォ",
    "comparando": "コンパランド",
    "monitora": "モニトラ",
    "monitorando": "モニトランド",
    "regiao": "レジアン",
    "tambem": "タンベン",
    "faz": "ファズ",
    "marca": "マルカ",
    "segunda": "セグンダ",
    "engraçado": "エングラサド",
    "enquanto": "エンクアント",
    "agradavel": "アグラダヴェウ",
    "tranquilo": "トランキロ",
    "gostoso": "ゴストーゾ",
    "fresquinho": "フレスキーニョ",
    "ameno": "アメノ",
    "derretendo": "デルレテンド",
    "asfalto": "アスファルト",
    "forno": "フォルノ",
    "pizza": "ピザ",
    "piscina": "ピシナ",
    "piedade": "ピエダージ",
    "castigando": "カスチガンド",
    "pegando": "ペガンド",
    "fogo": "フォゴ",
    "bicho": "ビショ",
    "humor": "ユーモール",
    "piada": "ピアダ",
    "meteorologico": "メテオロロジコ",
    "plot": "プロット",
    "twist": "トゥイスト",
    "canto": "カント",
    "perdoa": "ペルドア",
    "sombra": "ソンブラ",
    "obrigatorio": "オブリガトーリオ",
    "guarda-chuva": "グアルダチュヴァ",
    "chove": "チョヴェ",
    "caprichoso": "カプリショーゾ",
    "suportavel": "スポルタヴェウ",
    "esquentando": "エスケンタンド",
    "aparecendo": "アパレセンド",
    "forte": "フォルチ",
    "terca": "テルサ",
    "cerveja": "セルヴェジャ",
    "cervejinha": "セルヴェジーニャ",
    "gelada": "ジェラダ",
    "churrasco": "シュラスコ",
    "calorao": "カロラン",
    "moderacao": "モデラサン",
    "combinacao": "コンビナサン",
    "vitoria": "ヴィトーリア",
    "bonito": "ボニト",
    "otimo": "オティモ",
    "ideal": "イデアウ",
    "tomar": "トマール",
    "pensa": "ペンサ",
    "pedindo": "ペジンド",
    "quarta": "クアルタ",
    "quinta": "キンタ",
    "sexta": "セクスタ",
    "sabado": "サバド",
    "domingo": "ドミンゴ",
    "feira": "フェイラ",
    "calor": "カロール",
    "publico": "プブリコ",
    "mantem": "マンテン",
    "informado": "インフォルマド",
    "pede": "ペジ",
    "media": "メディア",
    "sextou": "セクトウ",
    "amigos": "アミーゴス",
    "situacao": "シチュアサン",
    "sozinho": "ソジーニョ",
    "resenha": "レゼーニャ",
    "manha": "マーニャ",
    "madrugada": "マドゥルガダ",
    "tarde": "タルデ",
    "perfeita": "ペルフェイタ",
    "perfeito": "ペルフェイト",
    "companheira": "コンパニーア",
    "companhia": "コンパニーア",
    "animar": "アニマール",
    "animando": "アニマンド",
    "passe": "パッセ",
    "pesada": "ペザダ",
    "salva": "サルヴァ",
    "acorda": "アコルダ",
    "comeca": "コメサ",
    # Claridade extra (votacao / locucao)
    "chega": "シェガ",
    "irritada": "イリタダ",
    "furiosa": "フリオザ",
    "raiva": "ハイヴァ",
    "brava": "ブラヴァ",
    "adeus": "アデウス",
    "obedece": "オベデセ",
    "exagerando": "エザジェランド",
    "respeita": "レスペイタ",
    "controle": "コントロレ",
    "esquerda": "エスケルダ",
    "voou": "ヴォウ",
    "apresenta": "アプレゼンタ",
    "soa": "ソア",
    "abaixa": "アバイシャ",
    "aguenta": "アゲンタ",
    "aguentou": "アゲントウ",
    "manda": "マンダ",
    "banda": "バンダ",
    "entra": "エントラ",
    "entrou": "エントロウ",
    "segue": "セゲ",
    "programa": "プログラマ",
    "radio ao vivo": "ラジオ アオ ヴィヴォ",
    "momento": "モメント",
    "combo": "コンボ",
    "conversa": "コンヴェルサ",
    "chuvoso": "チュヴォーゾ",
    "comparacao do tempo": "コンパラサン ド テンポ",
    "comparacao": "コンパラサン",
    "voto da galera": "ヴォト ダ ガレラ",
    "util sim": "ウーティウ",
    "completo sim": "コンプレト",
    "muda": "ムーダ",
    "ok": "オーケー",
    "preciso": "プレシーゾ",
    "calma": "カルマ",
    "hmph": "フン",
    "skip": "スキップ",
    "controle remoto": "コントロレ",
}

_VOWELS = "aáàâãeéèêiíìoóòôõuúùy"
_NASAL_MARK = "~"

_ONSET_TABLE: dict[str, dict[str, str]] = {
    "b": {"a": "バ", "e": "ベ", "i": "ビ", "o": "ボ", "u": "ブ", "~a": "バン", "~e": "ベン", "~i": "ビン", "~o": "ボン", "~u": "ブン"},
    "c": {"a": "カ", "e": "セ", "i": "シ", "o": "コ", "u": "ク", "~a": "カン", "~e": "セン", "~i": "シン", "~o": "コン", "~u": "クン"},
    "d": {"a": "ダ", "e": "デ", "i": "ジ", "o": "ド", "u": "ド", "~a": "ダン", "~e": "デン", "~i": "ジン", "~o": "ドン", "~u": "ドン"},
    "f": {"a": "ファ", "e": "フェ", "i": "フィ", "o": "フォ", "u": "フ", "~a": "ファン", "~e": "フェン", "~i": "フィン", "~o": "フォン", "~u": "フン"},
    "g": {"a": "ガ", "e": "ジェ", "i": "ジ", "o": "ゴ", "u": "グ", "~a": "ガン", "~e": "ジェン", "~i": "ジン", "~o": "ゴン", "~u": "グン"},
    "j": {"a": "ジャ", "e": "ジェ", "i": "ジ", "o": "ジョ", "u": "ジュ", "~a": "ジャン", "~e": "ジェン", "~i": "ジン", "~o": "ジョン", "~u": "ジュン"},
    "k": {"a": "カ", "e": "ケ", "i": "キ", "o": "コ", "u": "ク", "~a": "カン", "~e": "ケン", "~i": "キン", "~o": "コン", "~u": "クン"},
    "l": {"a": "ラ", "e": "レ", "i": "リ", "o": "ロ", "u": "ル", "~a": "ラン", "~e": "レン", "~i": "リン", "~o": "ロン", "~u": "ルン"},
    "m": {"a": "マ", "e": "メ", "i": "ミ", "o": "モ", "u": "ム", "~a": "マン", "~e": "メン", "~i": "ミン", "~o": "モン", "~u": "ムン"},
    "n": {"a": "ナ", "e": "ネ", "i": "ニ", "o": "ノ", "u": "ヌ", "~a": "ナン", "~e": "ネン", "~i": "ニン", "~o": "ノン", "~u": "ヌン"},
    "p": {"a": "パ", "e": "ペ", "i": "ピ", "o": "ポ", "u": "プ", "~a": "パン", "~e": "ペン", "~i": "ピン", "~o": "ポン", "~u": "プン"},
    "r": {"a": "ラ", "e": "レ", "i": "リ", "o": "ロ", "u": "ル", "~a": "ラン", "~e": "レン", "~i": "リン", "~o": "ロン", "~u": "ルン"},
    "s": {"a": "サ", "e": "セ", "i": "シ", "o": "ソ", "u": "ス", "~a": "サン", "~e": "セン", "~i": "シン", "~o": "ソン", "~u": "スン"},
    "t": {"a": "タ", "e": "テ", "i": "チ", "o": "ト", "u": "ト", "~a": "タン", "~e": "テン", "~i": "チン", "~o": "トン", "~u": "トン"},
    "v": {"a": "ヴァ", "e": "ヴェ", "i": "ヴィ", "o": "ヴォ", "u": "ヴ", "~a": "ヴァン", "~e": "ヴェン", "~i": "ヴィン", "~o": "ヴォン", "~u": "ヴン"},
    "w": {"a": "ワ", "e": "ウェ", "i": "ウィ", "o": "ウォ", "u": "ウ", "~a": "ワン", "~e": "ウェン", "~i": "ウィン", "~o": "ウォン", "~u": "ウン"},
    "x": {"a": "クサ", "e": "クセ", "i": "クシ", "o": "クソ", "u": "クス", "~a": "クサン", "~e": "クセン", "~i": "クシン", "~o": "クソン", "~u": "クスン"},
    "z": {"a": "ザ", "e": "ゼ", "i": "ジ", "o": "ゾ", "u": "ズ", "~a": "ザン", "~e": "ゼン", "~i": "ジン", "~o": "ゾン", "~u": "ズン"},
}

_PURE_VOWEL = {
    "a": "ア", "e": "エ", "i": "イ", "o": "オ", "u": "ウ", "y": "イ",
    "~a": "アン", "~e": "エン", "~i": "イン", "~o": "オン", "~u": "ウン", "~y": "イン",
}

_LH_ONSET = {
    "a": "リャ", "e": "リェ", "i": "リ", "o": "リョ", "u": "リュ",
    "~a": "リャン", "~e": "リェン", "~i": "リン", "~o": "リョン", "~u": "リュン",
}

_NH_ONSET = {
    "a": "ニャ", "e": "ニェ", "i": "ニ", "o": "ニョ", "u": "ニュ",
    "~a": "ニャン", "~e": "ニェン", "~i": "ニン", "~o": "ニョン", "~u": "ニュン",
}

_SUFFIX_RULES: tuple[tuple[str, str], ...] = (
    ("acao", "サン"),
    ("icao", "サン"),
    ("sao", "サン"),
    ("dade", "ダージ"),
    ("mente", "メンチ"),
    ("inho", "イーニョ"),
    ("inha", "イーニャ"),
    ("oso", "オーゾ"),
    ("osa", "オーザ"),
)

_SPOKEN_SIMPLIFY_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\bartista desconhecido\b", "banda desconhecida"),
    (r"\bdesconhecido\b", "desconhecida"),
    (r"\bsintonizou\b", "entrou na radio"),
    (r"\bsintonizado\b", "na radio"),
    (r"\bsintonizar\b", "ouvir a radio"),
    (r"\btransmissao\b", "radio ao vivo"),
    (r"\btransmitindo\b", "no ar"),
    (r"\bprogramacao\b", "programa"),
    (r"\bmeteorologa\b", "do tempo"),
    (r"\bmeteorologico\b", "do tempo"),
    (r"\bcomparativo\b", "comparacao do tempo"),
    (r"\bcomparando\b", "comparacao do tempo"),
    (r"\bmonitorando\b", "vendo o tempo"),
    (r"\bsituacao\b", "momento"),
    (r"\bobrigatorio\b", "preciso"),
    (r"\bmoderacao\b", "calma"),
    (r"\bcombinacao\b", "combo"),
    (r"\bdemocracia\b", "voto da galera"),
    (r"\butil\b", "util sim"),
    (r"\bcompleto\b", "completo sim"),
    (r"\bvariavel\b", "muda"),
    (r"\binstavel\b", "muda"),
    (r"\bsuportavel\b", "ok"),
    (r"\bcaprichoso\b", "chuvoso"),
    (r"\bresenha\b", "conversa"),
    (r"\bcompanheira\b", "companhia"),
    (r"\bexagerando\b", "demais"),
    (r"\birritada\b", "brava"),
    (r"\bfuriosa\b", "brava"),
    (r"\braiva\b", "brava"),
    (r"\bcontrole remoto\b", "controle remoto"),
)


def integer_to_spoken_pt(value: int) -> str:
    """Ex.: 32 -> 'trinta e dois' (PT-BR) para TTS em katakana."""
    number = int(value)
    if number < 0:
        return f"menos {integer_to_spoken_pt(-number)}"
    if number < 10:
        return _UNITS_PT[number]
    if number < 20:
        return _TEENS_PT[number - 10]
    if number < 100:
        tens, ones = divmod(number, 10)
        if ones == 0:
            return _TENS_PT[tens]
        return f"{_TENS_PT[tens]} e {_UNITS_PT[ones]}"
    if number == 100:
        return "cem"
    return str(number)


def expand_numbers_for_speech(text: str) -> str:
    """Substitui algarismos isolados por palavras em portugues."""

    def _replace(match: re.Match[str]) -> str:
        return integer_to_spoken_pt(int(match.group(0)))

    return _DIGITS_RE.sub(_replace, str(text or ""))


def _ascii_key(word: str) -> str:
    lowered = word.lower()
    normalized = unicodedata.normalize("NFKD", lowered)
    stripped = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9'-]", "", stripped)


def _mark_nasal_vowels(text: str) -> str:
    chars: list[str] = []
    index = 0
    while index < len(text):
        ch = text[index]
        base = ch.lower()
        if base not in _VOWELS:
            chars.append(ch)
            index += 1
            continue

        next_ch = text[index + 1].lower() if index + 1 < len(text) else ""
        if base in ("ã", "õ") or (next_ch in "mn" and base in "aeiou"):
            normalized = {"ã": "a", "õ": "o"}.get(base, base)
            chars.append(_NASAL_MARK + normalized)
            index += 2 if next_ch in "mn" else 1
            continue

        chars.append(base)
        index += 1
    return "".join(chars)


def _consume_vowel(text: str, index: int) -> tuple[str, int] | None:
    if index >= len(text):
        return None
    ch = text[index]
    if ch == _NASAL_MARK and index + 1 < len(text):
        vowel = text[index + 1]
        if vowel in "aeiouy":
            return f"~{vowel}", index + 2
    if ch in "aeiouy":
        return ch, index + 1
    return None


def _lookup_onset(onset: str, vowel_key: str) -> str | None:
    table = _ONSET_TABLE.get(onset)
    if not table:
        return None
    return table.get(vowel_key)


def _transliterate_unknown(word: str) -> str:
    key = _ascii_key(word)
    if not key:
        return word
    if key.isdigit():
        spoken = integer_to_spoken_pt(int(key))
        pieces = [portuguese_word_to_katakana(part) for part in spoken.split() if part]
        return "".join(pieces)

    prepared = _mark_nasal_vowels(key)
    index = 0
    pieces: list[str] = []

    while index < len(prepared):
        chunk = prepared[index:]

        if chunk.startswith("lh"):
            vowel = _consume_vowel(prepared, index + 2)
            if vowel:
                pieces.append(_LH_ONSET.get(vowel[0], "リ"))
                index = vowel[1]
                continue
            pieces.append("リ")
            index += 2
            continue

        if chunk.startswith("nh"):
            vowel = _consume_vowel(prepared, index + 2)
            if vowel:
                pieces.append(_NH_ONSET.get(vowel[0], "ニ"))
                index = vowel[1]
                continue
            pieces.append("ニ")
            index += 2
            continue

        if chunk.startswith("ch"):
            vowel = _consume_vowel(prepared, index + 2)
            if vowel:
                ch_map = {
                    "a": "チャ", "e": "チェ", "i": "チ", "o": "チョ", "u": "チュ",
                    "~a": "チャン", "~e": "チェン", "~i": "チン", "~o": "チョン", "~u": "チュン",
                }
                pieces.append(ch_map.get(vowel[0], "チ"))
                index = vowel[1]
                continue

        if chunk.startswith("rr"):
            vowel = _consume_vowel(prepared, index + 2)
            if vowel:
                pieces.append(_lookup_onset("r", vowel[0]) or "ル")
                index = vowel[1]
                continue

        if chunk.startswith("qu"):
            vowel = _consume_vowel(prepared, index + 2)
            if vowel:
                if vowel[0] in {"e", "i", "~e", "~i"}:
                    pieces.append(_lookup_onset("k", vowel[0]) or "ケ")
                else:
                    pieces.append("ク" + _PURE_VOWEL.get(vowel[0], ""))
                index = vowel[1]
                continue

        if chunk.startswith("gu") and len(chunk) > 2 and chunk[2] in "ei":
            vowel = _consume_vowel(prepared, index + 2)
            if vowel:
                pieces.append(_lookup_onset("g", vowel[0]) or "グ")
                index = vowel[1]
                continue

        if chunk.startswith("ss"):
            vowel = _consume_vowel(prepared, index + 2)
            if vowel:
                pieces.append(_lookup_onset("s", vowel[0]) or "ス")
                index = vowel[1]
                continue

        vowel_only = _consume_vowel(prepared, index)
        if vowel_only and (index == 0 or prepared[index - 1] in " '-"):
            pieces.append(_PURE_VOWEL.get(vowel_only[0], "ア"))
            index = vowel_only[1]
            continue

        onset = prepared[index]
        if onset not in _ONSET_TABLE:
            index += 1
            continue

        vowel = _consume_vowel(prepared, index + 1)
        if not vowel:
            index += 1
            continue

        kana = _lookup_onset(onset, vowel[0])
        if not kana and onset == "c" and vowel[0] in {"a", "o", "u", "~a", "~o", "~u"}:
            kana = _lookup_onset("k", vowel[0])
        if kana:
            pieces.append(kana)
        index = vowel[1]

    return "".join(pieces) if pieces else word


def simplify_spoken_portuguese(text: str) -> str:
    value = str(text or "")
    for pattern, replacement in _SPOKEN_SIMPLIFY_PATTERNS:
        value = re.sub(pattern, replacement, value, flags=re.IGNORECASE)
    return value


def insert_clarity_pauses(text: str) -> str:
    value = str(text or "")
    value = re.sub(r"\s+—\s+", ", ", value)
    value = re.sub(r"\s+-\s+", ", ", value)
    value = re.sub(r":\s+", ", ", value)
    value = re.sub(r";\s+", ", ", value)
    return value.strip()


def prepare_proper_noun_for_speech(text: str) -> str:
    value = str(text or "").strip()
    if not value:
        return value

    value = re.sub(r"\b(feat\.?|ft\.?|featuring)\b", " com ", value, flags=re.IGNORECASE)
    value = re.sub(r"\s*&\s*", " e ", value)
    value = re.sub(r"\s*\+\s*", " e ", value)
    value = re.sub(r"[^\w\sà-úÀ-Ú'-]", " ", value, flags=re.UNICODE)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _katakana_suffix(stem: str, suffix: str, kana_suffix: str) -> str | None:
    if stem in _LEXICON:
        return _LEXICON[stem] + kana_suffix

    stem_kana = _transliterate_unknown(stem)
    if stem_kana and stem_kana != stem:
        return stem_kana + kana_suffix
    return None


def portuguese_word_to_katakana(word: str) -> str:
    key = _ascii_key(word)
    if not key:
        return word
    if key in _LEXICON:
        return _LEXICON[key]

    for suffix, kana_suffix in _SUFFIX_RULES:
        if len(key) > len(suffix) + 2 and key.endswith(suffix):
            stem = key[: -len(suffix)]
            composed = _katakana_suffix(stem, suffix, kana_suffix)
            if composed:
                return composed

    return _transliterate_unknown(word)


_PUNCT_MAP = {
    ",": "、",
    "!": "！",
    "?": "？",
    ".": "。",
    ":": "、",
    ";": "、",
    "—": "、",
    "-": "",
}


def _normalize_punctuation(chunk: str) -> str:
    return "".join(_PUNCT_MAP.get(ch, ch) for ch in chunk if not ch.isspace())


def portuguese_to_voicevox_katakana(text: str) -> str:
    text = expand_numbers_for_speech(text)
    text = simplify_spoken_portuguese(text)
    text = insert_clarity_pauses(text)
    parts: list[str] = []
    last = 0
    for match in _WORD_RE.finditer(text):
        gap = text[last:match.start()]
        if gap and not gap.isspace():
            parts.append(_normalize_punctuation(gap))
        parts.append(portuguese_word_to_katakana(match.group(0)))
        last = match.end()
    if last < len(text):
        tail = text[last:]
        if tail and not tail.isspace():
            parts.append(_normalize_punctuation(tail))
    return "".join(parts)

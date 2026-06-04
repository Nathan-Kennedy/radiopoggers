/// Efeitos de brincadeira na previa / envio da chamada do ouvinte.
class VoiceDropEffectsConfig {
  const VoiceDropEffectsConfig({
    this.noiseSuppressEnabled = false,
    this.echoEnabled = false,
    this.echoDelayMs = 240,
    this.echoFeedback = 0.38,
    this.autotuneEnabled = false,
    this.autotuneSemitones = 0,
    this.autotuneSnap = 0.65,
    this.robotEnabled = false,
    this.robotDepth = 0.45,
    this.megaphoneEnabled = false,
    this.chorusEnabled = false,
    this.chorusDepth = 0.35,
  });

  /// Redução de ruído (RNNoise) — liga/desliga como no Discord.
  final bool noiseSuppressEnabled;

  final bool echoEnabled;
  final double echoDelayMs;
  final double echoFeedback;

  final bool autotuneEnabled;
  /// -8 a +8 semitons (0 = tom original).
  final double autotuneSemitones;
  /// 0 = shift suave · 1 = “travado” estilo autotune.
  final double autotuneSnap;

  final bool robotEnabled;
  final double robotDepth;

  final bool megaphoneEnabled;

  final bool chorusEnabled;
  final double chorusDepth;

  static const defaults = VoiceDropEffectsConfig();

  bool get hasAny =>
      echoEnabled || autotuneEnabled || robotEnabled || megaphoneEnabled || chorusEnabled;

  VoiceDropEffectsConfig copyWith({
    bool? noiseSuppressEnabled,
    bool? echoEnabled,
    double? echoDelayMs,
    double? echoFeedback,
    bool? autotuneEnabled,
    double? autotuneSemitones,
    double? autotuneSnap,
    bool? robotEnabled,
    double? robotDepth,
    bool? megaphoneEnabled,
    bool? chorusEnabled,
    double? chorusDepth,
  }) {
    return VoiceDropEffectsConfig(
      noiseSuppressEnabled: noiseSuppressEnabled ?? this.noiseSuppressEnabled,
      echoEnabled: echoEnabled ?? this.echoEnabled,
      echoDelayMs: echoDelayMs ?? this.echoDelayMs,
      echoFeedback: echoFeedback ?? this.echoFeedback,
      autotuneEnabled: autotuneEnabled ?? this.autotuneEnabled,
      autotuneSemitones: autotuneSemitones ?? this.autotuneSemitones,
      autotuneSnap: autotuneSnap ?? this.autotuneSnap,
      robotEnabled: robotEnabled ?? this.robotEnabled,
      robotDepth: robotDepth ?? this.robotDepth,
      megaphoneEnabled: megaphoneEnabled ?? this.megaphoneEnabled,
      chorusEnabled: chorusEnabled ?? this.chorusEnabled,
      chorusDepth: chorusDepth ?? this.chorusDepth,
    );
  }

  Map<String, dynamic> toJson() => {
        'noiseSuppressEnabled': noiseSuppressEnabled,
        'echoEnabled': echoEnabled,
        'echoDelayMs': echoDelayMs,
        'echoFeedback': echoFeedback,
        'autotuneEnabled': autotuneEnabled,
        'autotuneSemitones': autotuneSemitones,
        'autotuneSnap': autotuneSnap,
        'robotEnabled': robotEnabled,
        'robotDepth': robotDepth,
        'megaphoneEnabled': megaphoneEnabled,
        'chorusEnabled': chorusEnabled,
        'chorusDepth': chorusDepth,
      };

  factory VoiceDropEffectsConfig.fromJson(Map<String, dynamic>? json) {
    if (json == null) return defaults;
    return VoiceDropEffectsConfig(
      noiseSuppressEnabled: json['noiseSuppressEnabled'] == true,
      echoEnabled: json['echoEnabled'] == true,
      echoDelayMs: _d(json['echoDelayMs'], 240, 60, 520),
      echoFeedback: _d(json['echoFeedback'], 0.38, 0.1, 0.72),
      autotuneEnabled: json['autotuneEnabled'] == true,
      autotuneSemitones: _d(json['autotuneSemitones'], 0, -8, 8),
      autotuneSnap: _d(json['autotuneSnap'], 0.65, 0, 1),
      robotEnabled: json['robotEnabled'] == true,
      robotDepth: _d(json['robotDepth'], 0.45, 0.15, 0.85),
      megaphoneEnabled: json['megaphoneEnabled'] == true,
      chorusEnabled: json['chorusEnabled'] == true,
      chorusDepth: _d(json['chorusDepth'], 0.35, 0.1, 0.7),
    );
  }

  static double _d(dynamic v, double fallback, double min, double max) {
    final n = (v is num) ? v.toDouble() : double.tryParse('$v');
    if (n == null || n.isNaN) return fallback;
    return n.clamp(min, max);
  }
}

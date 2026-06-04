import 'voice_drop_slot.dart';

/// Drops na chamada: início e fim independentes (seu áudio ou Mixkit).
class VoiceDropStingerConfig {
  const VoiceDropStingerConfig({
    this.enabled = false,
    this.volume = 0.4,
    this.intro = VoiceDropSlot.empty,
    this.outro = VoiceDropSlot.empty,
  });

  final bool enabled;
  final double volume;
  final VoiceDropSlot intro;
  final VoiceDropSlot outro;

  static const defaults = VoiceDropStingerConfig();

  bool get hasActiveSlot => intro.isActive || outro.isActive;

  bool get isActive => enabled && hasActiveSlot;

  bool get hasSameSlotConflict => intro.conflictsWith(outro);

  VoiceDropStingerConfig copyWith({
    bool? enabled,
    double? volume,
    VoiceDropSlot? intro,
    VoiceDropSlot? outro,
  }) {
    return VoiceDropStingerConfig(
      enabled: enabled ?? this.enabled,
      volume: volume ?? this.volume,
      intro: intro ?? this.intro,
      outro: outro ?? this.outro,
    );
  }

  Map<String, dynamic> toJson() => {
        'version': 2,
        'enabled': enabled,
        'volume': volume,
        'intro': intro.toJson(),
        'outro': outro.toJson(),
      };

  factory VoiceDropStingerConfig.fromJson(Map<String, dynamic>? json) {
    if (json == null) return defaults;
    if ((json['version'] as num?)?.toInt() == 2) {
      var cfg = VoiceDropStingerConfig(
        enabled: json['enabled'] == true,
        volume: _d(json['volume'], 0.4, 0.0, 1.0),
        intro: VoiceDropSlot.fromJson(json['intro'] as Map<String, dynamic>?),
        outro: VoiceDropSlot.fromJson(json['outro'] as Map<String, dynamic>?),
      );
      return _fixSameSlotConflict(cfg);
    }
    return _migrateV1(json);
  }

  static VoiceDropStingerConfig _migrateV1(Map<String, dynamic> json) {
    final enabled = json['enabled'] == true;
    final stingerId = json['stingerId']?.toString() ?? '';
    final placement = json['placement']?.toString() ?? 'beforeVoice';
    final volume = _d(json['volume'], 0.4, 0.0, 1.0);

    if (!enabled || stingerId.isEmpty) {
      return VoiceDropStingerConfig(enabled: false, volume: volume);
    }

    final slot = VoiceDropSlot(
      source: VoiceDropSlotSource.catalog,
      catalogId: stingerId,
    );
    VoiceDropSlot intro = VoiceDropSlot.empty;
    VoiceDropSlot outro = VoiceDropSlot.empty;
    switch (placement) {
      case 'afterVoice':
        outro = slot;
      case 'both':
        intro = slot;
      default:
        intro = slot;
    }
    return _fixSameSlotConflict(
      VoiceDropStingerConfig(enabled: true, volume: volume, intro: intro, outro: outro),
    );
  }

  static VoiceDropStingerConfig _fixSameSlotConflict(VoiceDropStingerConfig cfg) {
    if (!cfg.hasSameSlotConflict) return cfg;
    return cfg.copyWith(outro: VoiceDropSlot.empty);
  }

  static double _d(dynamic v, double fallback, double min, double max) {
    final n = (v is num) ? v.toDouble() : double.tryParse('$v');
    if (n == null || n.isNaN) return fallback;
    return n.clamp(min, max);
  }
}

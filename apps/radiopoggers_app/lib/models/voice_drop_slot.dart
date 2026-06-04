/// Origem do drop em um slot (início ou fim da chamada).
enum VoiceDropSlotSource {
  none,
  custom,
  catalog,
}

/// Um drop no início ou no fim — nunca repetir o mesmo som nos dois lados.
class VoiceDropSlot {
  const VoiceDropSlot({
    this.source = VoiceDropSlotSource.none,
    this.catalogId = '',
    this.customPath = '',
  });

  final VoiceDropSlotSource source;
  final String catalogId;
  final String customPath;

  static const empty = VoiceDropSlot();

  bool get isActive {
    switch (source) {
      case VoiceDropSlotSource.none:
        return false;
      case VoiceDropSlotSource.custom:
        return customPath.trim().isNotEmpty;
      case VoiceDropSlotSource.catalog:
        return catalogId.trim().isNotEmpty;
    }
  }

  bool get isCustom => source == VoiceDropSlotSource.custom && customPath.isNotEmpty;

  bool get isCatalog => source == VoiceDropSlotSource.catalog && catalogId.isNotEmpty;

  bool conflictsWith(VoiceDropSlot other) {
    if (!isActive || !other.isActive) return false;
    if (isCustom && other.isCustom) {
      return customPath.trim() == other.customPath.trim();
    }
    if (isCatalog && other.isCatalog) {
      return catalogId.trim() == other.catalogId.trim();
    }
    return false;
  }

  VoiceDropSlot copyWith({
    VoiceDropSlotSource? source,
    String? catalogId,
    String? customPath,
  }) {
    return VoiceDropSlot(
      source: source ?? this.source,
      catalogId: catalogId ?? this.catalogId,
      customPath: customPath ?? this.customPath,
    );
  }

  Map<String, dynamic> toJson() => {
        'source': source.name,
        'catalogId': catalogId,
        'customPath': customPath,
      };

  factory VoiceDropSlot.fromJson(Map<String, dynamic>? json) {
    if (json == null) return empty;
    final raw = json['source']?.toString() ?? 'none';
    return VoiceDropSlot(
      source: VoiceDropSlotSource.values.firstWhere(
        (s) => s.name == raw,
        orElse: () => VoiceDropSlotSource.none,
      ),
      catalogId: json['catalogId']?.toString() ?? '',
      customPath: json['customPath']?.toString() ?? '',
    );
  }
}

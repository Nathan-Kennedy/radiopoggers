import '../core/app_network_defaults.dart';

class AppSettings {
  const AppSettings({
    required this.apiBaseUrl,
    required this.azuracastBaseUrl,
    required this.streamUrl,
    required this.hlsUrl,
    required this.stationShortcode,
    required this.stationDisplayName,
    required this.pollIntervalMs,
    required this.selectedNarrator,
    required this.setupComplete,
  });

  final String apiBaseUrl;
  final String azuracastBaseUrl;
  final String streamUrl;
  final String hlsUrl;
  final String stationShortcode;
  final String stationDisplayName;
  final int pollIntervalMs;
  final String selectedNarrator;
  final bool setupComplete;

  static const localhost = AppSettings(
    apiBaseUrl: 'http://127.0.0.1:8765',
    azuracastBaseUrl: 'http://127.0.0.1',
    streamUrl: 'http://127.0.0.1/listen/radio-no-grale/radio.mp3',
    hlsUrl: 'http://127.0.0.1/hls/radio-no-grale/live.m3u8',
    stationShortcode: 'radio-no-grale',
    stationDisplayName: 'RADIO NO GRALE',
    pollIntervalMs: 3000,
    selectedNarrator: 'miku',
    setupComplete: false,
  );

  /// Preset Radmin: só preenchido se build com [AppNetworkDefaults.radminHost].
  static AppSettings get radminPreset => AppNetworkDefaults.compiledRadminSettings();

  /// Monta URLs a partir do IP/host informado pelo operador (não vai no GitHub).
  static AppSettings forRadminHost(String host, {bool setupComplete = false}) {
    final h = _normalizeHost(host);
    return AppSettings(
      apiBaseUrl: 'http://$h:8765',
      azuracastBaseUrl: 'http://$h',
      streamUrl: 'http://$h/listen/radio-no-grale/radio.mp3',
      hlsUrl: 'http://$h/hls/radio-no-grale/live.m3u8',
      stationShortcode: 'radio-no-grale',
      stationDisplayName: 'RADIO NO GRALE',
      pollIntervalMs: 3000,
      selectedNarrator: 'miku',
      setupComplete: setupComplete,
    );
  }

  static String normalizeHost(String raw) => _normalizeHost(raw);

  static String _normalizeHost(String raw) {
    var h = raw.trim();
    if (h.startsWith('http://')) h = h.substring(7);
    if (h.startsWith('https://')) h = h.substring(8);
    final slash = h.indexOf('/');
    if (slash > 0) h = h.substring(0, slash);
    final colon = h.indexOf(':');
    if (colon > 0) h = h.substring(0, colon);
    return h;
  }

  AppSettings copyWith({
    String? apiBaseUrl,
    String? azuracastBaseUrl,
    String? streamUrl,
    String? hlsUrl,
    String? stationShortcode,
    String? stationDisplayName,
    int? pollIntervalMs,
    String? selectedNarrator,
    bool? setupComplete,
  }) {
    return AppSettings(
      apiBaseUrl: apiBaseUrl ?? this.apiBaseUrl,
      azuracastBaseUrl: azuracastBaseUrl ?? this.azuracastBaseUrl,
      streamUrl: streamUrl ?? this.streamUrl,
      hlsUrl: hlsUrl ?? this.hlsUrl,
      stationShortcode: stationShortcode ?? this.stationShortcode,
      stationDisplayName: stationDisplayName ?? this.stationDisplayName,
      pollIntervalMs: pollIntervalMs ?? this.pollIntervalMs,
      selectedNarrator: selectedNarrator ?? this.selectedNarrator,
      setupComplete: setupComplete ?? this.setupComplete,
    );
  }

  String get mp3Stream => streamUrl;
  String get hlsStream => hlsUrl;
}

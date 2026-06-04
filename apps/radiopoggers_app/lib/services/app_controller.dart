import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math';
import 'dart:typed_data';
import 'package:flutter/foundation.dart';
import 'package:path_provider/path_provider.dart';
import 'package:flutter/services.dart';
import 'package:record/record.dart';

import '../ascii/ascii_animator.dart';
import '../models/app_settings.dart';
import '../models/system_banner_severity.dart';
import '../models/voice_drop_effects_config.dart';
import '../models/voice_drop_slot.dart';
import '../models/voice_drop_stinger_config.dart';
import 'custom_drop_audio.dart';
import 'custom_drop_storage.dart';
import 'overlay_audio_service.dart';
import 'package:file_picker/file_picker.dart';
import 'radio_stinger_catalog.dart';
import 'voice_drop_stinger_mix.dart';
import 'radiopoggers_api.dart';
import 'settings_store.dart';
import 'stream_duck_controller.dart';
import 'audio_reactive_meter.dart';
import 'stream_player_service.dart';
import 'voice_drop_processor.dart';

class AppController extends ChangeNotifier {
  AppController() {
    _init();
  }

  final SettingsStore settingsStore = SettingsStore();
  final AsciiRepository ascii = AsciiRepository();
  final StreamPlayerService stream = StreamPlayerService();
  final OverlayAudioService overlay = OverlayAudioService();
  final AudioReactiveMeter audioMeter = AudioReactiveMeter();
  final AudioRecorder _recorder = AudioRecorder();
  static const String _mikuListenerId = 'miku-narrator';
  static const String _hoshinoListenerId = 'hoshino-narrator';
  final Set<String> _playedVoiceDropIds = {};
  /// Evita duas chamadas simultâneas ao mesmo drop (poll + now playing).
  final Set<String> _voiceDropClaimedIds = {};
  bool _mikuNarratorEnabled = true;

  AppSettings settings = AppSettings.localhost;
  RadiopoggersApi? api;
  String listenerId = '';
  bool loading = true;
  bool apiOnline = false;
  bool maintenanceActive = false;
  String maintenanceMessage = '';
  String maintenanceLevel = 'maintenance';
  bool stationOnline = true;
  bool nowPlayingReachable = true;
  String? streamPlayError;
  String connectionLabel = 'Conectando';
  int audienceTotalOnSite = 0;
  int audienceEligible = 0;
  String asciiStageMode = 'idle';
  String? narratorCaption;
  String? narratorBadge;

  bool streamPlaying = false;
  double volume = 85;
  Map<String, dynamic>? nowPlaying;
  String trackTitle = 'Aguardando';
  String trackArtist = '—';
  String? coverUrl;
  int elapsedSec = 0;
  int durationSec = 0;

  List<Map<String, dynamic>> libraryTracks = [];
  List<String> libraryArtists = [];
  List<String> libraryAlbums = [];
  String librarySummary = 'Carregando estante...';
  String libraryQuery = '';
  String libraryArtist = '';
  String libraryAlbum = '';
  bool libraryLoading = false;

  String? shelfPreviewTrackId;
  String? shelfPreviewTitle;
  bool _shelfPreviewRadioWasPlaying = false;

  Map<String, dynamic>? activeVote;
  String voteUiMessage = '';
  bool showVoteOverlay = false;
  String? voteCastError;
  String? _voteOverlayDismissedId;
  String? _lastHandledClosedVoteId;
  Timer? _voteCountdownTimer;

  bool voiceRecording = false;
  bool voicePreviewReady = false;
  int voiceSecondsLeft = 15;
  int voiceRecordedMs = 0;
  String voiceStatus = 'Segure o mic para gravar (até 15s). Volume no ar: 100% = original.';
  double voiceDropGain = VoiceDropProcessor.defaultGain;
  VoiceDropEffectsConfig voiceEffects = VoiceDropEffectsConfig.defaults;
  VoiceDropStingerConfig voiceStinger = VoiceDropStingerConfig.defaults;
  String customDropMessage = '';
  bool voicePreviewPlaying = false;
  Timer? _voiceTimer;
  Timer? _voiceEffectsDebounce;
  Timer? _voiceStingerDebounce;

  List<Map<String, dynamic>> history = [];
  List<Map<String, dynamic>> spotifyManifestItems = [];
  List<Map<String, dynamic>> radioQueueItems = [];
  String spotifyPlaylistTitle = 'Playlist Spotify';
  String spotifyPlaylistSummary = 'Carregue um link do Spotify para ver a fila.';
  String spotifyStatus = '';
  String importUrl = '';
  bool spotifyImportBusy = false;
  String radioQueueSource = '';

  String? lastTrackKey;
  Timer? _pollTimer;
  Timer? _healthTimer;
  Timer? _heartbeatTimer;
  Timer? _votePollTimer;
  Timer? _voiceDropPollTimer;
  bool _overlayFinishHandled = false;
  bool _voicePreviewPlayback = false;
  String? _voiceBoostedPreviewPath;
  int _overlayDropDurationMs = 0;
  DateTime? _overlayPlayStartedAt;
  String? _overlayActiveMediaPath;
  bool _overlayActiveMediaIsUrl = false;
  Timer? _overlayMaxPlayTimer;
  int _overlayResumeAttempts = 0;
  static const int _overlayMaxResumeAttempts = 2;

  Map<String, dynamic>? narratorSamples;

  DateTime? _asciiHoldUntil;
  String? _lockedAsciiMode;
  Timer? _asciiHoldTimer;
  bool _overlayWasNarrator = false;

  static const int _narratorAsciiHoldMs = 700;
  static const int _narratorDuckTailMs = 0;
  /// Ignora evento "completed" fantasma do media_kit no início da Miku.
  static const int _narratorOverlayEarlyCompletedGuardMs = 450;
  static const int _listenerDuckTailMs = 650;

  bool get _asciiHoldActive =>
      _asciiHoldUntil != null && DateTime.now().isBefore(_asciiHoldUntil!);

  Future<void> _init() async {
    settings = await settingsStore.load();
    if (settings.selectedNarrator != 'miku') {
      settings = settings.copyWith(selectedNarrator: 'miku');
      await settingsStore.save(settings);
    }
    voiceDropGain = await settingsStore.getVoiceDropGain();
    voiceEffects = await settingsStore.getVoiceDropEffects();
    voiceStinger = await settingsStore.getVoiceDropStinger();
    await RadioStingerCatalog.ensureLoaded();
    voiceStinger = _normalizeVoiceStinger(voiceStinger);
    if (voiceStinger.intro.isCatalog) {
      unawaited(RadioStingerCatalog.preload(voiceStinger.intro.catalogId));
    }
    if (voiceStinger.outro.isCatalog &&
        voiceStinger.outro.catalogId != voiceStinger.intro.catalogId) {
      unawaited(RadioStingerCatalog.preload(voiceStinger.outro.catalogId));
    }
    listenerId = await settingsStore.getListenerId();
    api = RadiopoggersApi(settings);
    await ascii.loadAll();
    _loadNarratorSamples();
    _bindOverlayEvents();
    await _checkApi();
    loading = false;
    notifyListeners();
    if (settings.setupComplete) {
      _startTimers();
      unawaited(loadSpotifyData());
    }
  }

  void _bindOverlayEvents() {
    overlay.player.stream.completed.listen((done) {
      if (!done || _voicePreviewPlayback) return;
      unawaited(_handleOverlayPlaybackEnded(source: 'completed'));
    });
  }

  int get _overlayMinPlayMs {
    final d = _overlayDropDurationMs;
    if (d <= 0) return 1200;
    return max(1500, (d * 0.88).round());
  }

  Future<void> _handleOverlayPlaybackEnded({required String source}) async {
    if (_voicePreviewPlayback || _overlayFinishHandled || !overlay.busy) return;

    final started = _overlayPlayStartedAt;
    if (started != null) {
      final elapsed = DateTime.now().difference(started).inMilliseconds;
      // Miku: só ignora "completed" nos primeiros ms; não espera % da duração (evita silêncio no fim).
      if (_overlayWasNarrator) {
        if (elapsed < _narratorOverlayEarlyCompletedGuardMs) return;
      } else if (elapsed < _overlayMinPlayMs &&
          _overlayResumeAttempts < _overlayMaxResumeAttempts) {
        _overlayResumeAttempts++;
        await _resumeOverlayPlaybackIfCutShort();
        return;
      }
    }

    await _onOverlayFinished();
  }

  Future<void> _resumeOverlayPlaybackIfCutShort() async {
    final path = _overlayActiveMediaPath;
    if (path == null || path.isEmpty) return;
    try {
      if (_overlayActiveMediaIsUrl) {
        await overlay.playHttpUrl(path);
      } else {
        await overlay.playFilePath(path);
      }
      _overlayPlayStartedAt = DateTime.now();
    } catch (_) {}
  }

  void _scheduleOverlayMaxPlayTimer({bool narrator = false}) {
    _overlayMaxPlayTimer?.cancel();
    final ms = _overlayDropDurationMs;
    if (ms <= 0) return;
    final safetyMs = narrator ? 400 : 1200;
    _overlayMaxPlayTimer = Timer(Duration(milliseconds: ms + safetyMs), () {
      if (overlay.busy && !_overlayFinishHandled && !_voicePreviewPlayback) {
        unawaited(_onOverlayFinished());
      }
    });
  }

  void _clearOverlayPlaybackGuards() {
    _overlayMaxPlayTimer?.cancel();
    _overlayMaxPlayTimer = null;
    _overlayDropDurationMs = 0;
    _overlayPlayStartedAt = null;
    _overlayActiveMediaPath = null;
    _overlayActiveMediaIsUrl = false;
    _overlayResumeAttempts = 0;
  }

  Future<void> _onOverlayFinished() async {
    if (_voicePreviewPlayback) {
      _voicePreviewPlayback = false;
      voicePreviewPlaying = false;
      notifyListeners();
      return;
    }

    if (_overlayFinishHandled) return;
    _overlayFinishHandled = true;

    final wasShelf = shelfPreviewTrackId != null;
    _clearOverlayPlaybackGuards();
    await overlay.stop();

    if (wasShelf) {
      _overlayFinishHandled = false;
      await stopShelfPreview(resumeRadio: true);
      return;
    }

    if (_overlayWasNarrator) {
      _extendAsciiHold(_narratorAsciiHoldMs);
      if (_narratorDuckTailMs > 0) {
        await Future<void>.delayed(Duration(milliseconds: _narratorDuckTailMs));
      }
      await stream.restoreDuckImmediate();
      narratorCaption = null;
    } else {
      await Future<void>.delayed(Duration(milliseconds: _listenerDuckTailMs));
      await stream.restoreDuck(tail: const Duration(milliseconds: StreamDuckController.releaseMs));
    }
    _scheduleAsciiHoldRelease();
    _overlayFinishHandled = false;
    notifyListeners();
  }

  void _beginVoiceVisual({
    required String asciiMode,
    required int duckTailMs,
    required bool narrator,
    String? badge,
    String? caption,
    int? holdMs,
  }) {
    _overlayWasNarrator = narrator;
    _lockedAsciiMode = asciiMode;
    asciiStageMode = asciiMode;
    if (badge != null) narratorBadge = badge;
    if (caption != null && caption.isNotEmpty) narratorCaption = caption;
    final dropMs = _overlayDropDurationMs > 0 ? _overlayDropDurationMs : 6000;
    final asciiMs = holdMs ??
        (narrator ? dropMs + _narratorAsciiHoldMs : duckTailMs + 250);
    _extendAsciiHold(asciiMs);
    _scheduleAsciiHoldRelease();
    notifyListeners();
  }

  void _extendAsciiHold(int extraMs) {
    final until = DateTime.now().add(Duration(milliseconds: extraMs));
    if (_asciiHoldUntil == null || until.isAfter(_asciiHoldUntil!)) {
      _asciiHoldUntil = until;
    }
  }

  void _scheduleAsciiHoldRelease() {
    _asciiHoldTimer?.cancel();
    if (_asciiHoldUntil == null) return;
    final wait = _asciiHoldUntil!.difference(DateTime.now());
    if (wait.isNegative) {
      _releaseAsciiHold();
      return;
    }
    _asciiHoldTimer = Timer(wait, _releaseAsciiHold);
  }

  void _releaseAsciiHold() {
    _asciiHoldUntil = null;
    _lockedAsciiMode = null;
    if (streamPlaying) {
      asciiStageMode = 'play';
    } else if (apiOnline) {
      asciiStageMode = 'idle';
    } else {
      asciiStageMode = 'off';
    }
    notifyListeners();
  }

  void _applyDefaultAsciiStage() {
    if (_asciiHoldActive && _lockedAsciiMode != null) {
      asciiStageMode = _lockedAsciiMode!;
      return;
    }
    asciiStageMode = streamPlaying ? 'play' : (apiOnline ? 'idle' : 'off');
  }

  Future<void> _loadNarratorSamples() async {
    try {
      final raw = await rootBundle.loadString('assets/narrator_samples/manifest.json');
      narratorSamples = jsonDecode(raw) as Map<String, dynamic>;
    } catch (_) {
      narratorSamples = {'miku': [], 'hoshino': []};
    }
  }

  Future<void> applySettings(AppSettings next, {bool markSetup = true}) async {
    settings = markSetup ? next.copyWith(setupComplete: true) : next;
    await settingsStore.save(settings);
    api?.dispose();
    api = RadiopoggersApi(settings);
    await _checkApi();
    _startTimers();
    unawaited(loadSpotifyData());
    notifyListeners();
  }

  bool get maintenanceBlocksPlayback =>
      maintenanceActive && maintenanceLevel == 'maintenance';

  bool get radioPlayAllowed =>
      apiOnline &&
      nowPlayingReachable &&
      stationOnline &&
      !maintenanceBlocksPlayback;

  bool get connectionBadgeOnline =>
      apiOnline && nowPlayingReachable && stationOnline && !maintenanceBlocksPlayback;

  bool get audioReactiveLive =>
      (streamPlaying && connectionBadgeOnline) ||
      shelfPreviewTrackId != null ||
      (overlay.busy && overlay.isPlaying) ||
      voicePreviewPlaying ||
      voiceRecording;

  bool get headerPulseLive => audioReactiveLive;

  bool get canParticipateInVote => streamPlaying && connectionBadgeOnline;

  bool get voteOverlayVisible {
    final vote = activeVote;
    if (vote == null) return false;
    final phase = vote['phase']?.toString() ?? '';
    if (phase.isEmpty || phase == 'closed') return false;
    final id = vote['id']?.toString() ?? '';
    if (id.isNotEmpty && _voteOverlayDismissedId == id) return false;
    return showVoteOverlay;
  }

  bool get voteSessionActive {
    final phase = activeVote?['phase']?.toString() ?? '';
    return phase.isNotEmpty && phase != 'closed';
  }

  double get headerPulseIntensity {
    if (audioReactiveLive) {
      return (0.5 + audioMeter.smoothLevel * 0.5).clamp(0.45, 1.0);
    }
    return apiOnline ? 0.1 : 0.05;
  }

  String get listenerCountLabel {
    if (!apiOnline) return '--';
    return '$audienceTotalOnSite';
  }

  void _applyAudienceFromPayload(Map<String, dynamic> data) {
    final audience = data['audience'];
    if (audience is Map) {
      audienceTotalOnSite = (audience['total_on_site'] as num?)?.toInt() ?? audienceTotalOnSite;
      audienceEligible = (audience['eligible'] as num?)?.toInt() ?? audienceEligible;
    }
    final listeners = data['listeners'];
    if (listeners is Map) {
      final current = listeners['current'] ?? listeners['unique'];
      if (current is num) {
        audienceTotalOnSite = current.toInt();
      }
    }
  }

  String? get systemBannerMessage {
    if (maintenanceActive) {
      final custom = maintenanceMessage.trim();
      if (custom.isNotEmpty) return custom;
      return maintenanceLevel == 'warning'
          ? 'Aviso: o operador reportou instabilidade. Alguns recursos podem falhar.'
          : 'Rádio em manutenção. Tente novamente em instantes.';
    }
    if (!apiOnline) {
      return 'API local offline (${settings.apiBaseUrl}). O operador pode estar atualizando — confira em Mais ou aguarde.';
    }
    if (!nowPlayingReachable) {
      return 'Transmissão indisponível: não foi possível obter o now playing. API ou AzuraCast podem estar reiniciando.';
    }
    if (!stationOnline) {
      return 'Estação offline no AzuraCast. Nenhum stream ao vivo no momento.';
    }
    final err = streamPlayError?.trim();
    if (err != null && err.isNotEmpty) return err;
    return null;
  }

  SystemBannerSeverity get systemBannerSeverity {
    if (maintenanceActive) {
      return maintenanceLevel == 'warning' ? SystemBannerSeverity.warning : SystemBannerSeverity.error;
    }
    if (!apiOnline || !nowPlayingReachable || !stationOnline) {
      return SystemBannerSeverity.error;
    }
    if (streamPlayError != null && streamPlayError!.trim().isNotEmpty) {
      return SystemBannerSeverity.warning;
    }
    return SystemBannerSeverity.none;
  }

  void _applyMaintenanceFromHealth(Map<String, dynamic> health) {
    final block = health['maintenance'];
    if (block is! Map) {
      maintenanceActive = false;
      maintenanceMessage = '';
      maintenanceLevel = 'maintenance';
      return;
    }
    maintenanceActive = block['active'] == true;
    maintenanceMessage = block['message']?.toString() ?? '';
    maintenanceLevel = (block['level']?.toString() ?? 'maintenance').toLowerCase();
    if (maintenanceLevel != 'warning') maintenanceLevel = 'maintenance';
  }

  void _recomputeConnectionLabel() {
    if (maintenanceActive) {
      connectionLabel = maintenanceLevel == 'warning' ? 'Aviso' : 'Manutenção';
      return;
    }
    if (!apiOnline) {
      connectionLabel = 'API offline';
      return;
    }
    if (!nowPlayingReachable) {
      connectionLabel = 'Sem sinal';
      return;
    }
    if (!stationOnline) {
      connectionLabel = 'Fora do ar';
      return;
    }
    connectionLabel = streamPlaying ? 'Ao vivo' : 'Pausado';
  }

  Future<void> _checkApi({bool silent = false}) async {
    if (api == null) {
      apiOnline = false;
      nowPlayingReachable = false;
      _recomputeConnectionLabel();
      if (!silent) notifyListeners();
      return;
    }
    try {
      final health = await api!.health();
      apiOnline = true;
      _applyMaintenanceFromHealth(health);
      _mikuNarratorEnabled = health['miku_narrator'] != false;
      if (maintenanceBlocksPlayback && streamPlaying) {
        await stream.pause();
        streamPlaying = false;
        asciiStageMode = 'idle';
      }
    } catch (_) {
      apiOnline = false;
      maintenanceActive = false;
      maintenanceMessage = '';
      nowPlayingReachable = false;
    }
    _recomputeConnectionLabel();
    notifyListeners();
  }

  Timer? _audioMeterTimer;

  void _startTimers() {
    _pollTimer?.cancel();
    _healthTimer?.cancel();
    _heartbeatTimer?.cancel();
    _votePollTimer?.cancel();
    _voiceDropPollTimer?.cancel();
    _audioMeterTimer?.cancel();
    _audioMeterTimer = Timer.periodic(const Duration(milliseconds: 33), (_) {
      audioMeter.tick(
        live: audioReactiveLive,
        trackElapsedSec: streamPlaying && connectionBadgeOnline ? elapsedSec : null,
      );
    });
    _pollTimer = Timer.periodic(Duration(milliseconds: settings.pollIntervalMs), (_) => refreshNowPlaying());
    _healthTimer = Timer.periodic(const Duration(seconds: 20), (_) => _checkApi(silent: true));
    _heartbeatTimer = Timer.periodic(const Duration(seconds: 12), (_) => _sendHeartbeat());
    _votePollTimer = Timer.periodic(const Duration(seconds: 2), (_) => _pollVote());
    _voiceDropPollTimer = Timer.periodic(const Duration(seconds: 2), (_) => _pollActiveVoiceDrop());
    _pollAudienceCount();
    refreshNowPlaying();
    loadLibrary();
  }

  Future<void> refreshNowPlaying() async {
    if (api == null || !apiOnline) return;
    try {
      final data = await api!.nowPlaying();
      nowPlaying = data;
      _applyAudienceFromPayload(data);
      nowPlayingReachable = true;
      stationOnline = data['is_online'] != false;
      if (!stationOnline) {
        trackTitle = 'Transmissão desligada';
        trackArtist = 'Nenhum stream ativo no momento';
      } else {
        final np = data['now_playing'] as Map<String, dynamic>? ?? data;
        final song = np['song'] as Map<String, dynamic>? ?? np;
        trackTitle = song['title']?.toString() ?? trackTitle;
        trackArtist = song['artist']?.toString() ?? trackArtist;
        coverUrl = song['art']?.toString() ?? song['album_art']?.toString();
        elapsedSec = (np['elapsed'] as num?)?.toInt() ?? elapsedSec;
        durationSec = (np['duration'] as num?)?.toInt() ?? durationSec;
        final hist = data['song_history'] as List<dynamic>?;
        if (hist != null) {
          history = hist.whereType<Map<String, dynamic>>().take(12).toList();
        }
        final key = '$trackTitle|$trackArtist';
        if (key != lastTrackKey && lastTrackKey != null) {
          _onTrackChanged(song);
        }
        lastTrackKey = key;
        syncVoiceDropFromNowPlaying(data['voice_drop'] as Map<String, dynamic>?);
        _syncVoteFromNowPlaying(data['audience_vote']);
        unawaited(refreshRadioQueue(silent: true));
      }
      streamPlayError = null;
      _recomputeConnectionLabel();
      _applyDefaultAsciiStage();
      notifyListeners();
    } catch (_) {
      nowPlayingReachable = false;
      stationOnline = false;
      _recomputeConnectionLabel();
      notifyListeners();
    }
  }

  Future<void> _onTrackChanged(Map<String, dynamic> song) async {
    if (settings.selectedNarrator != 'hoshino' || api == null) return;
    try {
      final result = await api!.hoshinoNarrate(
        title: song['title']?.toString() ?? trackTitle,
        artist: song['artist']?.toString() ?? trackArtist,
        album: song['album']?.toString() ?? '',
        moment: 'track_change',
      );
      final drop = result['voice_drop'] as Map<String, dynamic>?;
      if (drop != null && drop['id'] != null) {
        await _playVoiceDrop(drop);
      }
    } catch (_) {}
  }

  bool _claimVoiceDropPlayback(String id) {
    if (id.isEmpty) return false;
    if (_playedVoiceDropIds.contains(id) || _voiceDropClaimedIds.contains(id)) {
      return false;
    }
    _voiceDropClaimedIds.add(id);
    return true;
  }

  void _releaseVoiceDropClaim(String id) {
    _voiceDropClaimedIds.remove(id);
  }

  void syncVoiceDropFromNowPlaying(Map<String, dynamic>? drop) {
    if (drop == null || drop['id'] == null || api == null || !apiOnline) return;
    if (voiceRecording || shelfPreviewTrackId != null) return;
    if (overlay.isPlaying || _voiceDropClaimedIds.isNotEmpty) return;

    final id = drop['id'].toString();
    if (!_claimVoiceDropPlayback(id)) return;

    final lid = drop['listener_id']?.toString() ?? '';
    if (lid == listenerId) {
      _releaseVoiceDropClaim(id);
      return;
    }
    if (lid == _mikuListenerId && settings.selectedNarrator == 'hoshino') {
      _releaseVoiceDropClaim(id);
      return;
    }
    if (lid == _mikuListenerId && !_mikuNarratorEnabled) {
      _releaseVoiceDropClaim(id);
      return;
    }
    if (lid == _mikuListenerId && !streamPlaying) {
      _releaseVoiceDropClaim(id);
      return;
    }

    unawaited(_playVoiceDrop(drop));
  }

  Future<void> _pollActiveVoiceDrop() async {
    if (api == null || !apiOnline || voiceRecording) return;
    final drop = await api!.fetchActiveVoiceDrop();
    syncVoiceDropFromNowPlaying(drop);
  }

  Future<void> _playVoiceDrop(
    Map<String, dynamic> drop, {
    bool allowOwnListener = false,
    String? localFilePath,
  }) async {
    final id = drop['id']?.toString() ?? '';
    if (id.isEmpty || api == null) return;

    final lid = drop['listener_id']?.toString() ?? '';
    if (!allowOwnListener && lid == listenerId) {
      _releaseVoiceDropClaim(id);
      return;
    }
    if (!allowOwnListener) {
      if (_playedVoiceDropIds.contains(id)) {
        _releaseVoiceDropClaim(id);
        return;
      }
      if (!_voiceDropClaimedIds.contains(id) && !_claimVoiceDropPlayback(id)) {
        return;
      }
    }

    final isNarrator = lid == _mikuListenerId || lid == _hoshinoListenerId;

    try {
      _overlayFinishHandled = false;
      _clearOverlayPlaybackGuards();
      _overlayResumeAttempts = 0;
      await overlay.stop();
      await stream.duckForVoiceOverlay();

      final caption = drop['caption']?.toString() ?? drop['text']?.toString() ?? '';
      final asciiMode = lid == _hoshinoListenerId
          ? 'hoshino'
          : (lid == _mikuListenerId ? 'miku' : 'play');
      final badge = isNarrator
          ? (lid == _hoshinoListenerId ? 'HOSHINO · NO AR' : 'MIKU · NO AR')
          : 'OUVINTE · NO AR';

      final durationMs = (drop['duration_ms'] as num?)?.toInt() ?? 0;
      _overlayDropDurationMs = durationMs > 0 ? durationMs : 6000;
      _overlayPlayStartedAt = DateTime.now();

      _beginVoiceVisual(
        asciiMode: asciiMode,
        duckTailMs: isNarrator ? _narratorDuckTailMs : _listenerDuckTailMs,
        narrator: isNarrator,
        badge: badge,
        caption: caption,
      );

      if (localFilePath != null && File(localFilePath).existsSync()) {
        _overlayActiveMediaPath = localFilePath;
        _overlayActiveMediaIsUrl = false;
        await overlay.playFilePath(localFilePath);
      } else {
        final url = api!.voiceDropFileUrl(id);
        _overlayActiveMediaPath = url;
        _overlayActiveMediaIsUrl = true;
        await overlay.playHttpUrl(url);
      }
      _scheduleOverlayMaxPlayTimer(narrator: isNarrator);

      _playedVoiceDropIds.add(id);
      while (_playedVoiceDropIds.length > 96) {
        _playedVoiceDropIds.remove(_playedVoiceDropIds.first);
      }
    } catch (e) {
      if (!allowOwnListener) _playedVoiceDropIds.remove(id);
      await stream.restoreDuckImmediate();
      _releaseAsciiHold();
      connectionLabel = 'Voz: $e';
    } finally {
      _releaseVoiceDropClaim(id);
    }
    notifyListeners();
  }

  Future<void> togglePlay() async {
    await stream.ensureInitialized();
    if (streamPlaying) {
      await stream.pause();
      streamPlaying = false;
      asciiStageMode = 'idle';
      streamPlayError = null;
    } else {
      if (!radioPlayAllowed) {
        _recomputeConnectionLabel();
        notifyListeners();
        return;
      }
      try {
        await stream.playStream(settings);
        await stream.setVolume(volume);
        streamPlaying = true;
        asciiStageMode = 'play';
        streamPlayError = null;
      } catch (e) {
        streamPlaying = false;
        asciiStageMode = 'idle';
        streamPlayError = 'Não foi possível abrir o stream. Verifique a URL em Mais ou aguarde a estação voltar.';
      }
    }
    _recomputeConnectionLabel();
    notifyListeners();
    _sendHeartbeat();
  }

  Future<void> setVolumeLevel(double v) async {
    volume = v;
    await stream.setVolume(volume);
    notifyListeners();
  }

  Future<void> loadLibrary({bool refresh = false}) async {
    if (api == null || !apiOnline) {
      librarySummary = 'API offline — configure em Mais.';
      notifyListeners();
      return;
    }
    libraryLoading = true;
    notifyListeners();
    try {
      final data = await api!.library(
        q: libraryQuery,
        artist: libraryArtist,
        album: libraryAlbum,
        refresh: refresh,
      );
      final tracks = data['tracks'] as List<dynamic>? ?? [];
      libraryTracks = tracks.whereType<Map<String, dynamic>>().toList();
      final summary = data['summary'] as Map<String, dynamic>?;
      final total = data['total'] ?? libraryTracks.length;
      librarySummary = '${libraryTracks.length} faixa(s) na estante · ${summary?['tracks'] ?? total} no catálogo.';
      final filtersPayload = await api!.libraryFilters(refresh: refresh);
      final filters = filtersPayload['filters'] as Map<String, dynamic>? ?? filtersPayload;
      libraryArtists = (filters['artists'] as List<dynamic>? ?? []).map((e) => e.toString()).toList();
      libraryAlbums = (filters['albums'] as List<dynamic>? ?? []).map((e) => e.toString()).toList();
    } catch (e) {
      librarySummary = 'Estante indisponível: $e';
    }
    libraryLoading = false;
    notifyListeners();
  }

  String resolveLibraryPreviewId(Map<String, dynamic> track) {
    final id = track['id']?.toString().trim() ?? '';
    if (id.isNotEmpty) return id;
    return track['spotify_id']?.toString().trim() ?? '';
  }

  Future<void> playShelfPreview(Map<String, dynamic> track) async {
    final trackId = resolveLibraryPreviewId(track);
    final title = track['title']?.toString() ?? 'Faixa';
    if (trackId.isEmpty) {
      librarySummary = 'Previa indisponivel: faixa sem ID no catalogo.';
      notifyListeners();
      return;
    }
    if (!apiOnline || api == null) {
      librarySummary = 'Previa precisa da API em ${settings.apiBaseUrl}';
      notifyListeners();
      return;
    }

    if (shelfPreviewTrackId == trackId) {
      await stopShelfPreview(resumeRadio: true);
      librarySummary = 'Previa parada.';
      notifyListeners();
      return;
    }

    try {
      await stopShelfPreview(resumeRadio: false);
      shelfPreviewTrackId = trackId;
      shelfPreviewTitle = title;
      librarySummary = 'Carregando previa de $title...';
      notifyListeners();

      _shelfPreviewRadioWasPlaying = streamPlaying;
      if (_shelfPreviewRadioWasPlaying) {
        await stream.pause();
      }

      await overlay.stop();
      final url = api!.libraryPreviewUrl(trackId);
      await overlay.playHttpUrl(url, volume: OverlayAudioService.shelfPreviewVolume);
      librarySummary = 'Ouvindo $title — previa local (so neste aparelho).';
    } catch (e) {
      shelfPreviewTrackId = null;
      shelfPreviewTitle = null;
      await overlay.stop();
      if (_shelfPreviewRadioWasPlaying) {
        await stream.resume();
        streamPlaying = true;
      }
      _shelfPreviewRadioWasPlaying = false;
      librarySummary = 'Previa falhou: $e. Confira API e arquivo local da faixa.';
    }
    notifyListeners();
  }

  Future<void> stopShelfPreview({bool resumeRadio = true}) async {
    await overlay.stop();
    shelfPreviewTrackId = null;
    shelfPreviewTitle = null;
    if (resumeRadio && _shelfPreviewRadioWasPlaying) {
      await stream.resume();
      streamPlaying = true;
    }
    _shelfPreviewRadioWasPlaying = false;
    notifyListeners();
  }

  Future<void> requestTrack(Map<String, dynamic> track) async {
    final trackId = resolveLibraryPreviewId(track);
    if (trackId.isEmpty) {
      librarySummary = 'Pedido falhou: faixa sem ID.';
      notifyListeners();
      return;
    }
    await api!.libraryRequest(trackId);
    librarySummary = 'Pedido enviado para a fila.';
    notifyListeners();
  }

  Future<void> _sendHeartbeat() async {
    if (api == null || !apiOnline) return;
    try {
      final data = await api!.audienceHeartbeat(listenerId: listenerId, playing: streamPlaying);
      audienceTotalOnSite = (data['total_on_site'] as num?)?.toInt() ?? audienceTotalOnSite;
      audienceEligible = (data['eligible'] as num?)?.toInt() ?? audienceEligible;
      notifyListeners();
    } catch (_) {}
  }

  Future<void> _pollAudienceCount() async {
    if (api == null || !apiOnline) return;
    try {
      final data = await api!.audienceCount();
      audienceTotalOnSite = (data['total_on_site'] as num?)?.toInt() ?? audienceTotalOnSite;
      audienceEligible = (data['eligible'] as num?)?.toInt() ?? audienceEligible;
      notifyListeners();
    } catch (_) {}
  }

  Future<void> _pollVote() async {
    if (api == null || !apiOnline) return;
    try {
      final data = await api!.voteActive();
      _applyVoteUpdate(_asVoteMap(data['vote']));
    } catch (_) {}
  }

  void _syncVoteFromNowPlaying(dynamic raw) {
    if (raw is! Map) return;
    final vote = _asVoteMap(raw);
    if (vote == null) return;
    final phase = vote['phase']?.toString() ?? '';
    if (phase.isNotEmpty && phase != 'closed') {
      _applyVoteUpdate(vote);
    }
  }

  Map<String, dynamic>? _asVoteMap(dynamic raw) {
    if (raw is Map<String, dynamic>) return Map<String, dynamic>.from(raw);
    if (raw is Map) return raw.cast<String, dynamic>();
    return null;
  }

  void _applyVoteUpdate(Map<String, dynamic>? vote) {
    if (vote == null) {
      _stopVoteCountdown();
      activeVote = null;
      showVoteOverlay = false;
      notifyListeners();
      return;
    }

    final phase = vote['phase']?.toString() ?? '';
    if (phase == 'closed') {
      _handleVoteClosed(vote);
      return;
    }

    final id = vote['id']?.toString() ?? '';
    final prevId = activeVote?['id']?.toString();
    if (id.isNotEmpty && id != prevId) {
      _voteOverlayDismissedId = null;
    }

    activeVote = Map<String, dynamic>.from(vote);
    showVoteOverlay = true;
    voteCastError = null;
    _startVoteCountdownIfOpen();
    notifyListeners();
  }

  void _handleVoteClosed(Map<String, dynamic> vote) {
    final id = vote['id']?.toString() ?? '';
    if (id.isNotEmpty && _lastHandledClosedVoteId == id) return;
    _lastHandledClosedVoteId = id;
    _stopVoteCountdown();
    activeVote = Map<String, dynamic>.from(vote);
    showVoteOverlay = true;
    notifyListeners();

    final delayMs = vote['solo'] == true ? 900 : 2600;
    Future<void>.delayed(Duration(milliseconds: delayMs), () {
      if (activeVote?['id']?.toString() != id) return;
      activeVote = null;
      showVoteOverlay = false;
      _voteOverlayDismissedId = null;
      notifyListeners();
    });
  }

  void _startVoteCountdownIfOpen() {
    _voteCountdownTimer?.cancel();
    final vote = activeVote;
    if (vote == null || vote['phase']?.toString() != 'open') return;

    _voteCountdownTimer = Timer.periodic(const Duration(seconds: 1), (_) {
      final current = activeVote;
      if (current == null || current['phase']?.toString() != 'open') {
        _stopVoteCountdown();
        return;
      }
      final remaining = (current['remaining_sec'] as num?)?.toDouble() ?? 0;
      current['remaining_sec'] = remaining > 0 ? remaining - 1 : 0;
      notifyListeners();
    });
  }

  void _stopVoteCountdown() {
    _voteCountdownTimer?.cancel();
    _voteCountdownTimer = null;
  }

  Future<void> startSkipVote() async {
    if (api == null || !apiOnline) return;
    try {
      final data = await api!.voteStart(type: 'skip_track', proposerId: listenerId);
      _applyVoteUpdate(_asVoteMap(data['vote']));
      voteUiMessage = 'Votação para pular faixa';
    } catch (e) {
      voteUiMessage = e.toString();
      notifyListeners();
    }
  }

  Future<void> castVote(String choice) async {
    final vote = activeVote;
    if (vote == null || api == null) return;
    if (vote['phase']?.toString() != 'open') return;
    final id = vote['id']?.toString() ?? '';
    if (id.isEmpty) return;
    try {
      voteCastError = null;
      await api!.voteCast(voteId: id, listenerId: listenerId, choice: choice);
      final data = await api!.voteActive();
      _applyVoteUpdate(_asVoteMap(data['vote']));
    } catch (e) {
      voteCastError = 'Não foi possível registrar o voto. Tente de novo.';
      notifyListeners();
    }
  }

  void closeVoteOverlay() {
    final id = activeVote?['id']?.toString();
    if (id != null && id.isNotEmpty) _voteOverlayDismissedId = id;
    showVoteOverlay = false;
    notifyListeners();
  }

  String? _voiceRecordingPath;
  String? _voicePreviewPath;
  DateTime? _voiceRecordingStartedAt;

  Future<void> startVoiceRecording() async {
    if (voicePreviewReady) await discardVoicePreview();
    if (!await _recorder.hasPermission()) {
      voiceStatus = 'Permissão de microfone negada.';
      notifyListeners();
      return;
    }
    final dir = await getTemporaryDirectory();
    _voiceRecordingPath = '${dir.path}/voice-drop-${DateTime.now().millisecondsSinceEpoch}.wav';
    _voiceRecordingStartedAt = DateTime.now();
    voiceRecording = true;
    voicePreviewReady = false;
    voiceSecondsLeft = 15;
    voiceRecordedMs = 0;
    voiceStatus = 'Gravando… deslize para cancelar';
    await _recorder.start(const RecordConfig(encoder: AudioEncoder.wav), path: _voiceRecordingPath!);
    _voiceTimer?.cancel();
    _voiceTimer = Timer.periodic(const Duration(seconds: 1), (t) async {
      voiceSecondsLeft = max(0, 15 - t.tick);
      voiceRecordedMs = min(15000, t.tick * 1000);
      notifyListeners();
      if (voiceSecondsLeft <= 0) {
        await finishVoiceRecording();
      }
    });
    notifyListeners();
  }

  Future<void> setVoiceDropGain(double gain) async {
    voiceDropGain = gain.clamp(VoiceDropProcessor.minGain, VoiceDropProcessor.maxGain);
    await _refreshRadioPreviewAudio(restartPlayback: voicePreviewPlaying);
    notifyListeners();
  }

  Future<void> persistVoiceDropGain() async {
    await settingsStore.setVoiceDropGain(voiceDropGain);
  }

  Future<void> updateVoiceEffects(VoiceDropEffectsConfig next, {bool persist = true}) async {
    voiceEffects = next;
    if (persist) await settingsStore.saveVoiceDropEffects(voiceEffects);
    _scheduleVoiceEffectsPreviewRefresh();
    notifyListeners();
  }

  Future<void> commitVoiceEffects() async {
    await settingsStore.saveVoiceDropEffects(voiceEffects);
    await _refreshRadioPreviewAudio(restartPlayback: voicePreviewPlaying);
    notifyListeners();
  }

  VoiceDropStingerConfig _normalizeVoiceStinger(VoiceDropStingerConfig cfg) {
    var next = cfg;
    if (next.intro.isCatalog && RadioStingerCatalog.find(next.intro.catalogId) == null) {
      next = next.copyWith(
        intro: next.intro.copyWith(catalogId: RadioStingerCatalog.defaultId),
      );
    }
    if (next.outro.isCatalog && RadioStingerCatalog.find(next.outro.catalogId) == null) {
      next = next.copyWith(
        outro: next.outro.copyWith(catalogId: RadioStingerCatalog.defaultId),
      );
    }
    if (next.hasSameSlotConflict) {
      next = next.copyWith(outro: VoiceDropSlot.empty);
    }
    return next;
  }

  Future<void> updateVoiceStinger(VoiceDropStingerConfig next, {bool persist = true}) async {
    final normalized = _normalizeVoiceStinger(next);
    if (normalized.hasSameSlotConflict) {
      customDropMessage = 'Escolha sons diferentes no início e no fim.';
      notifyListeners();
      return;
    }
    voiceStinger = normalized;
    customDropMessage = '';
    if (persist) await settingsStore.saveVoiceDropStinger(voiceStinger);
    _scheduleVoiceStingerPreviewRefresh();
    notifyListeners();
  }

  Future<void> setIntroDropCatalog(String catalogId) async {
    final intro = VoiceDropSlot(source: VoiceDropSlotSource.catalog, catalogId: catalogId);
    final draft = voiceStinger.copyWith(
      enabled: true,
      intro: intro,
    );
    if (draft.hasSameSlotConflict) {
      customDropMessage = 'Esse som já está no fim — escolha outro.';
      notifyListeners();
      return;
    }
    await updateVoiceStinger(draft);
  }

  Future<void> setOutroDropCatalog(String catalogId) async {
    final outro = VoiceDropSlot(source: VoiceDropSlotSource.catalog, catalogId: catalogId);
    final draft = voiceStinger.copyWith(
      enabled: true,
      outro: outro,
    );
    if (draft.hasSameSlotConflict) {
      customDropMessage = 'Esse som já está no início — escolha outro.';
      notifyListeners();
      return;
    }
    await updateVoiceStinger(draft);
  }

  Future<void> clearIntroDrop() async {
    final old = voiceStinger.intro.customPath;
    await updateVoiceStinger(voiceStinger.copyWith(intro: VoiceDropSlot.empty));
    if (old.isNotEmpty) await CustomDropStorage.deleteStored(old);
  }

  Future<void> clearOutroDrop() async {
    final old = voiceStinger.outro.customPath;
    await updateVoiceStinger(voiceStinger.copyWith(outro: VoiceDropSlot.empty));
    if (old.isNotEmpty) await CustomDropStorage.deleteStored(old);
  }

  /// Abre o seletor e devolve WAV completo (sem salvar). UI abre o editor se > 5 s.
  Future<Uint8List?> pickCustomDropSourceFile() async {
    if (voiceRecording) return null;
    try {
      final picked = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: CustomDropAudio.pickerExtensions,
        allowMultiple: false,
      );
      if (picked == null || picked.files.isEmpty) return null;
      final path = picked.files.single.path;
      if (path == null || path.isEmpty) return null;
      return CustomDropAudio.decodeFileToWav(path);
    } catch (e) {
      customDropMessage = 'Importar: $e';
      notifyListeners();
      return null;
    }
  }

  Future<void> applyCustomDropWav({
    required Uint8List wav,
    required bool forOutro,
  }) async {
    try {
      final stored = await CustomDropStorage.saveWavBytes(
        wav,
        slotLabel: forOutro ? 'outro' : 'intro',
      );

      final other = forOutro ? voiceStinger.intro : voiceStinger.outro;
      if (other.isCustom && other.customPath == stored) {
        customDropMessage = 'Não pode ser o mesmo áudio do outro lado.';
        await CustomDropStorage.deleteStored(stored);
        notifyListeners();
        return;
      }

      final slot = VoiceDropSlot(source: VoiceDropSlotSource.custom, customPath: stored);
      if (forOutro) {
        final old = voiceStinger.outro.customPath;
        await updateVoiceStinger(voiceStinger.copyWith(enabled: true, outro: slot));
        if (old.isNotEmpty && old != stored) await CustomDropStorage.deleteStored(old);
      } else {
        final old = voiceStinger.intro.customPath;
        await updateVoiceStinger(voiceStinger.copyWith(enabled: true, intro: slot));
        if (old.isNotEmpty && old != stored) await CustomDropStorage.deleteStored(old);
      }
      customDropMessage = 'Drop pronto (WAV · 5 s).';
      notifyListeners();
    } catch (e) {
      customDropMessage = 'Salvar drop: $e';
      notifyListeners();
    }
  }

  Future<void> previewDropSlot({required bool outro}) async {
    final slot = outro ? voiceStinger.outro : voiceStinger.intro;
    if (!slot.isActive) {
      customDropMessage = 'Nada configurado nesse lado.';
      notifyListeners();
      return;
    }
    try {
      await stopVoicePreview();
      final dir = await getTemporaryDirectory();
      final path = '${dir.path}/drop-preview-${DateTime.now().millisecondsSinceEpoch}.wav';
      final Uint8List bytes;
      if (slot.isCustom) {
        bytes = VoiceDropStingerMix.scaleStinger(
          await CustomDropAudio.loadPrepared(slot.customPath),
          voiceStinger.volume,
          custom: true,
        );
      } else {
        await RadioStingerCatalog.ensureLoaded();
        bytes = VoiceDropStingerMix.scaleStinger(
          await RadioStingerCatalog.loadBytes(slot.catalogId),
          voiceStinger.volume,
        );
      }
      await File(path).writeAsBytes(bytes, flush: true);
      _voicePreviewPlayback = true;
      voicePreviewPlaying = true;
      await overlay.playFilePath(path, volume: 100);
      customDropMessage = 'Prévia do drop ${outro ? 'final' : 'inicial'}.';
    } catch (e) {
      customDropMessage = 'Prévia: $e';
    }
    notifyListeners();
  }

  Future<void> commitVoiceStinger() async {
    await settingsStore.saveVoiceDropStinger(voiceStinger);
    await _refreshRadioPreviewAudio(restartPlayback: voicePreviewPlaying);
    notifyListeners();
  }

  void _scheduleVoiceStingerPreviewRefresh() {
    _voiceStingerDebounce?.cancel();
    if (!voicePreviewReady) return;
    _voiceStingerDebounce = Timer(const Duration(milliseconds: 380), () {
      unawaited(_refreshRadioPreviewAudio(restartPlayback: voicePreviewPlaying));
    });
  }

  Future<void> previewStingerOnly() async => previewDropSlot(outro: false);

  void _scheduleVoiceEffectsPreviewRefresh() {
    _voiceEffectsDebounce?.cancel();
    if (!voicePreviewReady) return;
    _voiceEffectsDebounce = Timer(const Duration(milliseconds: 380), () {
      unawaited(_refreshRadioPreviewAudio(restartPlayback: voicePreviewPlaying));
    });
  }

  Future<Uint8List> _processVoiceBytesForRadio(String path) async {
    var bytes = await VoiceDropProcessor.processForRadio(
      path,
      voiceDropGain,
      effects: voiceEffects,
    );
    if (voiceStinger.isActive) {
      bytes = await VoiceDropStingerMix.mix(voiceWav: bytes, stinger: voiceStinger);
    }
    return bytes;
  }

  static int wavDurationMs(Uint8List wav) {
    if (wav.length < 48) return 500;
    final view = ByteData.sublistView(wav);
    final rate = view.getUint32(24, Endian.little);
    if (rate <= 0) return 500;
    var headerEnd = 44;
    for (var i = 12; i + 8 < wav.length; i++) {
      if (wav[i] == 0x64 && wav[i + 1] == 0x61 && wav[i + 2] == 0x74 && wav[i + 3] == 0x61) {
        headerEnd = i + 8;
        break;
      }
    }
    final samples = (wav.length - headerEnd) ~/ 2;
    return max(500, (samples * 1000 / rate).round());
  }

  Future<void> applyVoiceEffectsPreset(String preset) async {
    VoiceDropEffectsConfig next;
    switch (preset) {
      case 'autotune':
        next = voiceEffects.copyWith(
          autotuneEnabled: true,
          autotuneSemitones: 2,
          autotuneSnap: 0.85,
          echoEnabled: false,
        );
      case 'echo':
        next = voiceEffects.copyWith(
          echoEnabled: true,
          echoDelayMs: 280,
          echoFeedback: 0.42,
        );
      case 'robot':
        next = voiceEffects.copyWith(robotEnabled: true, robotDepth: 0.55);
      case 'megaphone':
        next = voiceEffects.copyWith(megaphoneEnabled: true);
      case 'chorus':
        next = voiceEffects.copyWith(chorusEnabled: true, chorusDepth: 0.4);
      case 'clear':
        next = VoiceDropEffectsConfig.defaults;
      default:
        return;
    }
    await updateVoiceEffects(next);
  }

  int get voiceDropGainPercent => VoiceDropProcessor.gainToPercent(voiceDropGain);

  Future<void> _refreshRadioPreviewAudio({required bool restartPlayback}) async {
    final source = _voicePreviewPath;
    if (source == null || !File(source).existsSync()) return;

    try {
      await _deleteVoiceFile(_voiceBoostedPreviewPath);
      final processed = await _processVoiceBytesForRadio(source);
      final out = '$source.radio-preview.wav';
      await File(out).writeAsBytes(processed, flush: true);
      _voiceBoostedPreviewPath = out;
      final pct = voiceDropGainPercent;
      final fx = voiceEffects.hasAny ? ' · efeitos' : '';
      final st = voiceStinger.isActive ? ' · drops na chamada' : '';
      voiceStatus = pct == 100
          ? 'Prévia = rádio (100% · original$fx$st).'
          : 'Prévia = rádio ($pct%$fx$st). Mova sliders ao ouvir.';

      if (restartPlayback) {
        await overlay.stop();
        _voicePreviewPlayback = true;
        voicePreviewPlaying = true;
        await overlay.playFilePath(_voiceBoostedPreviewPath!, volume: 100);
      }
    } catch (e) {
      voiceStatus = 'Prévia: $e';
    }
  }

  Future<void> playVoicePreview() async {
    final path = _voicePreviewPath;
    if (path == null || !File(path).existsSync()) return;
    try {
      await stopVoicePreview();
      _voicePreviewPlayback = true;
      voicePreviewPlaying = true;
      await _refreshRadioPreviewAudio(restartPlayback: true);
    } catch (e) {
      voiceStatus = 'Prévia: $e';
      voicePreviewPlaying = false;
      _voicePreviewPlayback = false;
    }
    notifyListeners();
  }

  Future<void> stopVoicePreview() async {
    if (!voicePreviewPlaying && !overlay.isPlaying) return;
    _voicePreviewPlayback = false;
    voicePreviewPlaying = false;
    await overlay.stop();
    notifyListeners();
  }

  Future<void> toggleVoicePreview() async {
    if (voicePreviewPlaying) {
      await stopVoicePreview();
    } else {
      await playVoicePreview();
    }
  }

  Future<void> cancelVoiceRecording() async {
    _voiceTimer?.cancel();
    await stopVoicePreview();
    if (voiceRecording) {
      try {
        await _recorder.stop();
      } catch (_) {}
    }
    voiceRecording = false;
    voicePreviewReady = false;
    voiceSecondsLeft = 15;
    voiceRecordedMs = 0;
    await _deleteVoiceFile(_voiceRecordingPath);
    await _deleteVoiceFile(_voicePreviewPath);
    await _deleteVoiceFile(_voiceBoostedPreviewPath);
    _voiceRecordingPath = null;
    _voicePreviewPath = null;
    _voiceBoostedPreviewPath = null;
    _voiceRecordingStartedAt = null;
    voiceStatus = 'Gravação cancelada. Toque no mic para tentar de novo.';
    notifyListeners();
  }

  Future<void> finishVoiceRecording() async {
    _voiceTimer?.cancel();
    if (!voiceRecording) return;
    voiceRecording = false;
    try {
      final path = await _recorder.stop() ?? _voiceRecordingPath;
      if (path == null || !File(path).existsSync()) {
        throw Exception('Gravação vazia');
      }
      final started = _voiceRecordingStartedAt;
      if (started != null) {
        voiceRecordedMs = max(500, DateTime.now().difference(started).inMilliseconds);
      }
      _voicePreviewPath = path;
      voicePreviewReady = true;
      voiceStatus = voiceDropGainPercent == 100
          ? 'Ouça a prévia (100% = original na rádio).'
          : 'Ouça a prévia (${voiceDropGainPercent}% do original na rádio).';
      unawaited(playVoicePreview());
    } catch (e) {
      voiceStatus = 'Falha na gravação: $e';
      voicePreviewReady = false;
      await _deleteVoiceFile(_voiceRecordingPath);
      _voicePreviewPath = null;
    }
    notifyListeners();
  }

  Future<void> discardVoicePreview() async {
    await stopVoicePreview();
    voicePreviewReady = false;
    voiceRecordedMs = 0;
    voiceSecondsLeft = 15;
    await _deleteVoiceFile(_voicePreviewPath);
    await _deleteVoiceFile(_voiceRecordingPath);
    await _deleteVoiceFile(_voiceBoostedPreviewPath);
    _voicePreviewPath = null;
    _voiceRecordingPath = null;
    _voiceBoostedPreviewPath = null;
    _voiceRecordingStartedAt = null;
    voiceStatus = 'Áudio descartado. Toque no mic para gravar de novo.';
    notifyListeners();
  }

  Future<void> submitVoicePreview() async {
    final path = _voicePreviewPath;
    if (path == null || !File(path).existsSync() || api == null) {
      voiceStatus = 'Nada para enviar.';
      notifyListeners();
      return;
    }
    await stopVoicePreview();
    voicePreviewReady = false;
    voiceStatus = 'Enviando…';
    notifyListeners();
    try {
      final fileBytes = await _processVoiceBytesForRadio(path);
      final durationMs = max(500, wavDurationMs(fileBytes));
      final mixedOnAirPath = '${path}.onair-mix.wav';
      await File(mixedOnAirPath).writeAsBytes(fileBytes, flush: true);
      final result = await api!.voiceDropUpload(
        bytes: fileBytes,
        mimeType: 'audio/wav',
        durationMs: durationMs,
        listenerId: listenerId,
      );
      final drop = result['voice_drop'];
      if (drop is Map) {
        final dropMap = drop.cast<String, dynamic>();
        voiceStatus = 'Sua chamada entrou no ar.';
        final onAirPath = mixedOnAirPath;
        await _playVoiceDrop(
          dropMap,
          allowOwnListener: true,
          localFilePath: onAirPath,
        );
      } else {
        voiceStatus = result['message']?.toString() ?? 'Enviado.';
      }
      await _deleteVoiceFile(_voiceRecordingPath);
      await _deleteVoiceFile(_voiceBoostedPreviewPath);
      _voicePreviewPath = null;
      _voiceRecordingPath = null;
      _voiceBoostedPreviewPath = null;
      _voiceRecordingStartedAt = null;
      voiceRecordedMs = 0;
      voiceSecondsLeft = 15;
    } catch (e) {
      voiceStatus = 'Falha: $e';
      voicePreviewReady = true;
      _voicePreviewPath = path;
    }
    notifyListeners();
  }

  Future<void> _deleteVoiceFile(String? path) async {
    if (path == null) return;
    try {
      final file = File(path);
      if (await file.exists()) await file.delete();
    } catch (_) {}
  }

  static bool isValidSpotifyUrl(String url) {
    final trimmed = url.trim();
    if (trimmed.isEmpty) return false;
    final uri = Uri.tryParse(trimmed);
    if (uri == null || uri.host.toLowerCase() != 'open.spotify.com') return false;
    return RegExp(r'/(playlist|track)/[A-Za-z0-9]+').hasMatch(uri.path);
  }

  Future<void> loadSpotifyData() async {
    if (api == null || !apiOnline) return;
    try {
      final manifest = await api!.manifest();
      _applySpotifyManifest(manifest);
      await refreshRadioQueue(silent: true);
    } catch (_) {}
    notifyListeners();
  }

  void _applySpotifyManifest(Map<String, dynamic> manifest) {
    final source = manifest['source'] as Map<String, dynamic>? ?? {};
    final summary = manifest['summary'] as Map<String, dynamic>? ?? {};
    final items = manifest['items'] as List<dynamic>? ?? [];
    spotifyManifestItems = items.whereType<Map<String, dynamic>>().toList();
    spotifyPlaylistTitle = source['title']?.toString() ?? 'Playlist Spotify';
    final ready = summary['ready'] as int? ??
        spotifyManifestItems.where((i) => i['status'] == 'ready').length;
    final pending = summary['pending_local_audio'] as int? ??
        spotifyManifestItems.where((i) => i['status'] != 'ready').length;
    spotifyPlaylistSummary =
        '${spotifyManifestItems.length} faixas · $ready prontas · $pending pendentes';
  }

  Future<void> refreshRadioQueue({bool silent = false}) async {
    if (api == null || !apiOnline) return;
    try {
      final data = await api!.stationQueue();
      radioQueueSource = data['source']?.toString() ?? '';
      final title = data['playlist_title']?.toString();
      if (title != null && title.isNotEmpty) {
        spotifyPlaylistTitle = title;
      }
      final items = data['items'] as List<dynamic>? ?? [];
      radioQueueItems = items.whereType<Map<String, dynamic>>().toList();
    } catch (e) {
      if (!silent) {
        spotifyStatus = 'Fila da rádio: $e';
      }
    }
    notifyListeners();
  }

  Future<void> importSpotify() async {
    final url = importUrl.trim();
    if (url.isEmpty) {
      spotifyStatus = 'Cole um link do Spotify antes de tocar.';
      notifyListeners();
      return;
    }
    if (!isValidSpotifyUrl(url)) {
      spotifyStatus = 'Link inválido. Use playlist ou faixa do open.spotify.com.';
      notifyListeners();
      return;
    }
    if (api == null || !apiOnline) {
      spotifyStatus = 'API offline.';
      notifyListeners();
      return;
    }
    if (spotifyImportBusy) {
      spotifyStatus = 'Aguarde a importação anterior terminar.';
      notifyListeners();
      return;
    }

    spotifyImportBusy = true;
    spotifyStatus = 'Conectando…';
    notifyListeners();
    try {
      final inspect = await api!.inspectSpotify(url);
      final cached = inspect['manifest'];
      if (inspect['already_imported'] == true && cached is Map) {
        _applySpotifyManifest(cached.cast<String, dynamic>());
        spotifyStatus = 'Playlist já importada. Atualizando fila…';
        await refreshRadioQueue();
        spotifyImportBusy = false;
        notifyListeners();
        return;
      }

      final started = await api!.importSpotify(url);
      _spotifyJobId = started['job_id']?.toString();
      spotifyStatus = started['message']?.toString() ?? 'Importação iniciada.';
      await _pollImportStatus();
    } catch (e) {
      spotifyStatus = e.toString();
      spotifyImportBusy = false;
    }
    notifyListeners();
  }

  Future<void> selectNarrator(String narrator) async {
    if (narrator != 'miku') return;
    settings = settings.copyWith(selectedNarrator: 'miku');
    await settingsStore.save(settings);
    narratorBadge = 'MIKU · NO AR';
    asciiStageMode = 'miku';
    notifyListeners();
  }

  Future<void> playNarratorSample(String narrator) async {
    if (narrator != 'miku') return;
    final pool = narratorSamples?['miku'] as List<dynamic>? ?? [];
    if (pool.isEmpty) {
      narratorCaption = 'Amostras nao encontradas. Rode sync-app-assets.ps1';
      notifyListeners();
      return;
    }
    final pick = pool[Random().nextInt(pool.length)] as Map<String, dynamic>;
    final file = pick['file']?.toString() ?? '';
    final caption = pick['caption']?.toString() ?? '';
    if (file.isEmpty) return;

    try {
      _overlayFinishHandled = false;
      await stopShelfPreview(resumeRadio: streamPlaying);
      await overlay.stop();
      await stream.duckForNarratorOverlay();
      _overlayDropDurationMs = 8000;
      _overlayPlayStartedAt = DateTime.now();
      _beginVoiceVisual(
        asciiMode: 'miku',
        duckTailMs: _narratorDuckTailMs,
        narrator: true,
        badge: 'MIKU · AMOSTRA',
        caption: caption,
      );
      _scheduleOverlayMaxPlayTimer(narrator: true);
      await overlay.playAssetRelative(file, volume: OverlayAudioService.narratorSampleVolume);
    } catch (e) {
      await stream.restoreDuckImmediate();
      _releaseAsciiHold();
      narratorCaption = 'Falha na amostra: $e';
      notifyListeners();
    }
  }

  String? _spotifyJobId;

  Future<void> _pollImportStatus() async {
    for (var i = 0; i < 90; i++) {
      await Future<void>.delayed(const Duration(seconds: 2));
      try {
        final st = await api!.importSpotifyStatus(jobId: _spotifyJobId ?? '');
        spotifyStatus = st['message']?.toString() ?? st['status']?.toString() ?? '...';
        final status = st['status']?.toString() ?? '';
        if (status == 'done' || status == 'completed' || st['done'] == true) {
          final manifest = await api!.manifest();
          _applySpotifyManifest(manifest);
          await refreshRadioQueue();
          break;
        }
        if (status == 'failed' || status == 'error') break;
        notifyListeners();
      } catch (_) {}
    }
    spotifyImportBusy = false;
    notifyListeners();
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    _healthTimer?.cancel();
    _heartbeatTimer?.cancel();
    _votePollTimer?.cancel();
    _voteCountdownTimer?.cancel();
    _voiceDropPollTimer?.cancel();
    _audioMeterTimer?.cancel();
    _overlayMaxPlayTimer?.cancel();
    _voiceEffectsDebounce?.cancel();
    _voiceTimer?.cancel();
    _asciiHoldTimer?.cancel();
    api?.dispose();
    stream.dispose();
    overlay.dispose();
    _recorder.dispose();
    super.dispose();
  }
}

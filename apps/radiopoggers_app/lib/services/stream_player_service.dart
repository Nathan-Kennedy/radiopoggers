import 'package:media_kit/media_kit.dart';

import '../models/app_settings.dart';
import 'radio_audio_bridge.dart';
import 'stream_duck_controller.dart';
import 'stream_loudness.dart';

class StreamPlayerService {
  StreamPlayerService({Player? sharedPlayer})
      : player = sharedPlayer ?? Player() {
    duck.onMultiplierChanged = (_) => _applyEffectiveVolume();
  }

  final Player player;
  final StreamDuckController duck = StreamDuckController();
  bool _initialized = false;
  double _userVolume = 85;

  Future<void> ensureInitialized() async {
    if (_initialized) return;
    MediaKit.ensureInitialized();
    _initialized = true;
  }

  bool get isPlaying => player.state.playing;

  Stream<bool> get playingStream => player.stream.playing;

  Future<void> playStream(AppSettings settings, {bool preferHls = true}) async {
    await ensureInitialized();
    final urls = <String>[];
    if (preferHls && settings.hlsUrl.isNotEmpty) urls.add(settings.hlsUrl);
    if (settings.streamUrl.isNotEmpty) urls.add(settings.streamUrl);
    Object? lastError;
    for (final url in urls) {
      try {
        await player.open(Media(url), play: true);
        await StreamLoudness.applyTo(player);
        return;
      } catch (e) {
        lastError = e;
      }
    }
    throw Exception('Falha ao abrir stream: $lastError');
  }

  Future<void> pause() => player.pause();
  Future<void> resume() => player.play();
  Future<void> stop() => player.stop();
  Future<void> setVolume(double volume) async {
    _userVolume = volume.clamp(0, 100);
    await _applyEffectiveVolume();
  }

  Future<void> _applyEffectiveVolume() async {
    final effective = _userVolume * duck.multiplier;
    await player.setVolume(effective.clamp(0, 100));
  }

  Future<void> duckForVoiceOverlay() async {
    duck.duckForVoiceOverlay();
    await _applyEffectiveVolume();
  }

  Future<void> duckForNarratorOverlay() => duckForVoiceOverlay();

  Future<void> duckForListenerOverlay() => duckForVoiceOverlay();

  Future<void> restoreDuck({Duration tail = const Duration(milliseconds: StreamDuckController.releaseMs)}) async {
    duck.restore(tail: tail);
    await _applyEffectiveVolume();
  }

  Future<void> restoreDuckImmediate() async {
    duck.restoreImmediate();
    await _applyEffectiveVolume();
  }

  void dispose() {
    duck.dispose();
    if (RadioAudioBridge.handler == null) {
      player.dispose();
    }
  }
}

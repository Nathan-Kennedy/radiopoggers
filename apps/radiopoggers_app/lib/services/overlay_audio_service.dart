import 'dart:io';

import 'package:flutter/services.dart';
import 'package:media_kit/media_kit.dart';

/// Voz sobre a radio (previa estante, amostra narradora, voice drops no ar).
class OverlayAudioService {
  OverlayAudioService() {
    MediaKit.ensureInitialized();
  }

  /// Ouvinte no app: volume maximo (arquivo ja vem amplificado da API).
  static const double voiceDropVolume = 100;
  static const double narratorSampleVolume = 100;
  static const double shelfPreviewVolume = 92;

  final Player player = Player();
  bool _busy = false;

  bool get isPlaying => player.state.playing;
  bool get busy => _busy;

  Future<void> playHttpUrl(String url, {double volume = voiceDropVolume}) async {
    _busy = true;
    await player.setVolume(volume.clamp(0, 100));
    await player.open(Media(url), play: true);
  }

  Future<void> playFilePath(String path, {double volume = voiceDropVolume}) async {
    _busy = true;
    await player.setVolume(volume.clamp(0, 100));
    await player.open(Media(path), play: true);
  }

  Future<void> playAssetRelative(String relativeAssetPath, {double volume = narratorSampleVolume}) async {
    _busy = true;
    final assetKey = relativeAssetPath.startsWith('assets/')
        ? relativeAssetPath
        : 'assets/narrator_samples/$relativeAssetPath';
    final bytes = await rootBundle.load(assetKey);
    final dir = await Directory.systemTemp.createTemp('rp_overlay_');
    final file = File('${dir.path}/sample.mp3');
    await file.writeAsBytes(bytes.buffer.asUint8List(bytes.offsetInBytes, bytes.lengthInBytes));
    await player.setVolume(volume.clamp(0, 100));
    await player.open(Media(file.path), play: true);
  }

  Future<void> setVolume(double volume) async {
    await player.setVolume(volume.clamp(0, 100));
  }

  Future<void> stop() async {
    _busy = false;
    await player.stop();
  }

  void dispose() {
    player.dispose();
  }
}

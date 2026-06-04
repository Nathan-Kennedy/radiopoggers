import 'dart:async';

import 'package:audio_service/audio_service.dart';
import 'package:media_kit/media_kit.dart';

import 'radio_playback_callbacks.dart';

/// Sessão de mídia do sistema (notificação / tela bloqueada) para o stream da rádio.
class RadioAudioHandler extends BaseAudioHandler with SeekHandler {
  RadioAudioHandler() {
    _bindPlayerStreams();
  }

  final Player player = Player();
  RadioPlaybackCallbacks? _callbacks;
  StreamSubscription<bool>? _playingSub;

  void attach(RadioPlaybackCallbacks callbacks) {
    _callbacks = callbacks;
    _publishMetadata();
    _publishPlaybackState(callbacks.isPlaying());
  }

  void detach() {
    _callbacks = null;
  }

  void _bindPlayerStreams() {
    _playingSub = player.stream.playing.listen((playing) {
      _publishPlaybackState(playing);
    });
  }

  void syncFromApp({required bool playing}) {
    _publishPlaybackState(playing);
    _publishMetadata();
  }

  void updateMetadata(RadioNowPlayingMetadata meta) {
    mediaItem.add(
      MediaItem(
        id: 'radio-live-stream',
        title: meta.title,
        artist: meta.artist,
        album: 'RADIO NO GRALE',
        artUri: meta.artUrl != null && meta.artUrl!.isNotEmpty ? Uri.tryParse(meta.artUrl!) : null,
        extras: const {'live': true},
      ),
    );
  }

  void _publishMetadata() {
    final cb = _callbacks;
    if (cb == null) return;
    updateMetadata(cb.getMetadata());
  }

  void _publishPlaybackState(bool playing) {
    playbackState.add(
      PlaybackState(
        controls: [
          if (playing) MediaControl.pause else MediaControl.play,
          MediaControl.stop,
        ],
        systemActions: const {
          MediaAction.play,
          MediaAction.pause,
          MediaAction.stop,
        },
        androidCompactActionIndices: const [0, 1],
        processingState: AudioProcessingState.ready,
        playing: playing,
        updatePosition: Duration.zero,
        speed: 1,
      ),
    );
  }

  @override
  Future<void> play() async {
    await _callbacks?.requestPlay();
  }

  @override
  Future<void> pause() async {
    await _callbacks?.requestPause();
  }

  @override
  Future<void> stop() async {
    await _callbacks?.requestStop();
    await super.stop();
  }

  @override
  Future<void> seek(Duration position) async {
    // Stream ao vivo — sem seek.
  }

  Future<void> disposeHandler() async {
    await _playingSub?.cancel();
    await player.dispose();
  }
}

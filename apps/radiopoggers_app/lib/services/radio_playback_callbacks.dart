import '../models/app_settings.dart';

/// Liga o [RadioAudioHandler] ao [AppController] (play/pause da notificação).
class RadioPlaybackCallbacks {
  const RadioPlaybackCallbacks({
    required this.getSettings,
    required this.requestPlay,
    required this.requestPause,
    required this.requestStop,
    required this.getMetadata,
    required this.isPlaying,
  });

  final AppSettings Function() getSettings;
  final Future<void> Function() requestPlay;
  final Future<void> Function() requestPause;
  final Future<void> Function() requestStop;
  final RadioNowPlayingMetadata Function() getMetadata;
  final bool Function() isPlaying;
}

class RadioNowPlayingMetadata {
  const RadioNowPlayingMetadata({
    required this.title,
    required this.artist,
    this.artUrl,
  });

  final String title;
  final String artist;
  final String? artUrl;
}

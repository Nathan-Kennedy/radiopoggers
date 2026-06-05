import 'dart:io';

import 'package:audio_service/audio_service.dart';
import 'package:flutter/foundation.dart';

import 'radio_audio_handler.dart';

/// Handler de áudio em segundo plano (Android/iOS), inicializado em [main].
abstract final class RadioAudioBridge {
  static RadioAudioHandler? handler;

  static Future<RadioAudioHandler?> initIfNeeded() async {
    if (handler != null) return handler;
    if (kIsWeb || !(Platform.isAndroid || Platform.isIOS)) return null;
    try {
      handler = await AudioService.init(
        builder: () => RadioAudioHandler(),
        config: AudioServiceConfig(
          androidNotificationChannelId: 'com.radiopoggers.radiopoggers_app.playback',
          androidNotificationChannelName: 'RADIO NO GRALE',
          androidNotificationChannelDescription: 'Reprodução da rádio ao vivo',
          androidNotificationOngoing: true,
          androidNotificationIcon: 'drawable/ic_notification',
          androidShowNotificationBadge: true,
          androidStopForegroundOnPause: false,
        ),
      );
      return handler;
    } catch (e, st) {
      handler = null;
      debugPrint('AudioService init falhou: $e');
      if (kDebugMode) debugPrint('$st');
      return null;
    }
  }
}

import 'dart:io';

import 'package:audio_service/audio_service.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:media_kit/media_kit.dart';

import 'app.dart';
import 'services/radio_audio_bridge.dart';
import 'services/radio_audio_handler.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  MediaKit.ensureInitialized();

  if (!kIsWeb && (Platform.isAndroid || Platform.isIOS)) {
    RadioAudioBridge.handler = await AudioService.init(
      builder: () => RadioAudioHandler(),
      config: AudioServiceConfig(
        androidNotificationChannelId: 'com.radiopoggers.radiopoggers_app.playback',
        androidNotificationChannelName: 'RADIO NO GRALE',
        androidNotificationChannelDescription: 'Reprodução da rádio ao vivo',
        androidNotificationOngoing: true,
        androidNotificationIcon: 'mipmap/ic_launcher',
        androidShowNotificationBadge: true,
        androidStopForegroundOnPause: false,
      ),
    );
  }

  runApp(const RadioPoggersApp());
}

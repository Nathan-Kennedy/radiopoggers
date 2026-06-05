import 'package:flutter/material.dart';
import 'package:media_kit/media_kit.dart';

import 'app.dart';
import 'services/radio_audio_bridge.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  MediaKit.ensureInitialized();
  await RadioAudioBridge.initIfNeeded();
  runApp(const RadioPoggersApp());
}

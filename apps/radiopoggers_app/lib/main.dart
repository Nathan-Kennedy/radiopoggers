import 'package:flutter/material.dart';
import 'package:media_kit/media_kit.dart';

import 'app.dart';
import 'services/radio_audio_bridge.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  MediaKit.ensureInitialized();
  // Inicializa servico de audio em segundo plano (notificacao/lockscreen).
  // Falha silenciosa em desktop/web — so Android/iOS ativam.
  await RadioAudioBridge.initIfNeeded();
  runApp(const RadioPoggersApp());
}
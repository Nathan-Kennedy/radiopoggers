import 'radio_audio_handler.dart';

/// Handler de áudio em segundo plano (Android/iOS), inicializado em [main].
abstract final class RadioAudioBridge {
  static RadioAudioHandler? handler;
}

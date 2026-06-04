import 'package:media_kit/media_kit.dart';

/// Compressao leve no stream (parecido com o site: nivelar volume entre faixas).
class StreamLoudness {
  static const String mpvFilterChain =
      'acompressor=threshold=-20dB:ratio=2.2:attack=280:release=950:makeup=4,'
      'alimiter=limit=0.96';

  static Future<void> applyTo(Player player) async {
    final platform = player.platform;
    if (platform == null) return;
    try {
      await (platform as dynamic).setProperty(
        'af',
        mpvFilterChain,
        waitForInitialization: false,
      );
    } catch (_) {
      // Backend sem suporte a af (ex.: web).
    }
  }
}

import 'dart:io';
import 'dart:math';
import 'dart:typed_data';

import '../models/voice_drop_effects_config.dart';
import 'voice_drop_effects.dart';
import 'voice_drop_noise_suppress.dart';

/// 100% = volume original da gravação · 200% = 2× · 0% = mudo.
/// Prévia e envio usam o mesmo processamento.
class VoiceDropProcessor {
  static const double minGain = 0.0;
  static const double maxGain = 2.0;
  static const double defaultGain = 1.0;

  static const int minPercent = 0;
  static const int maxPercent = 200;
  static const int defaultPercent = 100;

  static Future<Uint8List> processForRadio(
    String path,
    double gain, {
    VoiceDropEffectsConfig effects = VoiceDropEffectsConfig.defaults,
  }) async {
    final bytes = await File(path).readAsBytes();
    return await processForRadioBytes(bytes, gain, effects: effects);
  }

  static Future<Uint8List> processForRadioBytes(
    Uint8List input,
    double gain, {
    VoiceDropEffectsConfig effects = VoiceDropEffectsConfig.defaults,
  }) async {
    final userGain = gain.clamp(minGain, maxGain);
    if (userGain <= 0) return _silencePcm(input);
    var out = amplifyWavWithPeakNormalize(input, userGain);
    if (effects.noiseSuppressEnabled) {
      out = await VoiceDropNoiseSuppress.apply(out);
    }
    if (effects.hasAny) {
      out = VoiceDropEffects.apply(out, effects);
    }
    return out;
  }

  static Future<String> writeRadioPreviewCopy(
    String sourcePath,
    double gain, {
    VoiceDropEffectsConfig effects = VoiceDropEffectsConfig.defaults,
  }) async {
    final processed = await processForRadio(sourcePath, gain, effects: effects);
    final out = '$sourcePath.radio-preview.wav';
    await File(out).writeAsBytes(processed, flush: true);
    return out;
  }

  static Uint8List amplifyWavWithPeakNormalize(Uint8List input, double multiplier) {
    if (input.length < 48 || multiplier <= 0) return input;

    final headerEnd = _findPcmDataOffset(input);
    if (headerEnd <= 0 || headerEnd >= input.length) return input;

    final view = ByteData.sublistView(input);
    final bits = view.getUint16(34, Endian.little);
    if (bits != 16) return input;

    final out = Uint8List.fromList(input);
    final outView = ByteData.sublistView(out);

    var peak = 1;
    for (var i = headerEnd; i + 1 < out.length; i += 2) {
      final boosted = (view.getInt16(i, Endian.little) * multiplier).round();
      final clamped = boosted.clamp(-32768, 32767);
      outView.setInt16(i, clamped, Endian.little);
      peak = max(peak, clamped.abs());
    }

    // Só limita quando passa de 200% do “original” (evita estourar no 200%).
    const targetPeak = 30000;
    if (multiplier > 1.85 && peak > targetPeak) {
      final scale = targetPeak / peak;
      for (var i = headerEnd; i + 1 < out.length; i += 2) {
        final scaled = (outView.getInt16(i, Endian.little) * scale).round().clamp(-32768, 32767);
        outView.setInt16(i, scaled, Endian.little);
      }
    }

    return out;
  }

  static Uint8List _silencePcm(Uint8List input) {
    final out = Uint8List.fromList(input);
    final headerEnd = _findPcmDataOffset(out);
    if (headerEnd <= 0) return out;
    for (var i = headerEnd; i < out.length; i++) {
      out[i] = 0;
    }
    return out;
  }

  static int _findPcmDataOffset(Uint8List bytes) {
    for (var i = 12; i + 8 < bytes.length; i++) {
      if (bytes[i] == 0x64 &&
          bytes[i + 1] == 0x61 &&
          bytes[i + 2] == 0x74 &&
          bytes[i + 3] == 0x61) {
        return i + 8;
      }
    }
    return 44;
  }

  static int gainToPercent(double gain) =>
      (gain * 100).round().clamp(minPercent, maxPercent);

  static double percentToGain(int percent) =>
      (percent / 100.0).clamp(minGain, maxGain);
}

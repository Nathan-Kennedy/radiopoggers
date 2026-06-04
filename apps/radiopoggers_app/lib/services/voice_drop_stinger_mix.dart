import 'dart:math';
import 'dart:typed_data';

import '../models/voice_drop_slot.dart';
import '../models/voice_drop_stinger_config.dart';
import 'custom_drop_audio.dart';
import 'radio_stinger_catalog.dart';

class VoiceDropStingerMix {
  static const double mixkitHeadroom = 0.5;
  static const double customHeadroom = 0.72;

  /// Voz entra sobre o final do drop de início.
  static const int introVoiceOverlapMs = 1150;

  /// Drop de fim entra antes da voz acabar.
  static const int voiceOutroOverlapMs = 950;

  static Uint8List scaleStinger(Uint8List wav, double volume, {bool custom = false}) =>
      _scaleWav(wav, _gain(volume, custom: custom));

  static double _gain(double volume, {bool custom = false}) =>
      volume.clamp(0.0, 1.0) * (custom ? customHeadroom : mixkitHeadroom);

  static Future<Uint8List> mix({
    required Uint8List voiceWav,
    required VoiceDropStingerConfig stinger,
  }) async {
    if (!stinger.isActive || stinger.volume < 0.005 || stinger.hasSameSlotConflict) {
      return voiceWav;
    }

    final rate = _sampleRate(voiceWav);
    if (rate <= 0) return voiceWav;

    final voice = _decodeMono(voiceWav);
    final introBytes = await _resolveSlot(stinger.intro, stinger.volume);
    final outroBytes = await _resolveSlot(stinger.outro, stinger.volume);

    if (introBytes == null && outroBytes == null) return voiceWav;

    final intro = introBytes != null
        ? _trimIntroTail(_resampleToRate(_decodeMono(introBytes), _sampleRate(introBytes), rate), rate)
        : null;
    final outro = outroBytes != null
        ? _trimOutroHead(_resampleToRate(_decodeMono(outroBytes), _sampleRate(outroBytes), rate), rate)
        : null;

    return _mixImmersive(voice: voice, intro: intro, outro: outro, sampleRate: rate);
  }

  static Future<Uint8List?> _resolveSlot(VoiceDropSlot slot, double volume) async {
    if (!slot.isActive || volume < 0.005) return null;
    switch (slot.source) {
      case VoiceDropSlotSource.none:
        return null;
      case VoiceDropSlotSource.custom:
        final raw = await CustomDropAudio.loadPrepared(slot.customPath);
        return _scaleWav(raw, _gain(volume, custom: true));
      case VoiceDropSlotSource.catalog:
        final raw = await RadioStingerCatalog.loadBytes(slot.catalogId);
        return _scaleWav(raw, _gain(volume, custom: false));
    }
  }

  static Uint8List _mixImmersive({
    required List<double> voice,
    required List<double>? intro,
    required List<double>? outro,
    required int sampleRate,
  }) {
    final introLen = intro?.length ?? 0;
    final outroLen = outro?.length ?? 0;
    final voiceLen = voice.length;

    final introOv = max(1, (sampleRate * introVoiceOverlapMs / 1000).round());
    final outroOv = max(1, (sampleRate * voiceOutroOverlapMs / 1000).round());

    final voiceStart = introLen > 0 ? max(0, introLen - introOv) : 0;
    final voiceEnd = voiceStart + voiceLen;
    final outroStart = outroLen > 0 ? max(voiceStart, voiceEnd - outroOv) : voiceEnd;
    final totalLen = max(max(introLen, voiceEnd), outroLen > 0 ? outroStart + outroLen : 0);

    final buf = List<double>.filled(totalLen, 0.0);

    if (intro != null) {
      for (var i = 0; i < intro.length; i++) {
        final g = i < voiceStart
            ? 1.0
            : (i >= introLen ? 0.0 : _introFadeOut((i - voiceStart) / introOv));
        buf[i] += intro[i] * g;
      }
    }

    for (var vi = 0; vi < voiceLen; vi++) {
      final idx = voiceStart + vi;
      if (idx >= totalLen) break;
      var g = 1.0;
      if (introLen > 0 && idx < voiceStart + introOv) {
        g *= _voiceFadeIn((idx - voiceStart) / introOv);
      }
      if (outroLen > 0 && idx >= outroStart) {
        g *= _voiceFadeOut((idx - outroStart) / outroOv);
      }
      buf[idx] += voice[vi] * g;
    }

    if (outro != null) {
      for (var i = 0; i < outro.length; i++) {
        final idx = outroStart + i;
        if (idx >= totalLen) break;
        final g = _outroFadeIn((idx - outroStart) / outroOv);
        buf[idx] += outro[i] * g;
      }
    }

    for (var i = 0; i < buf.length; i++) {
      buf[i] = buf[i].clamp(-0.98, 0.98);
    }
    return _encodeMono(buf, sampleRate);
  }

  /// Intro some rápido para abrir espaço à voz.
  static double _introFadeOut(double t) => pow(1.0 - _smoothstep(t), 1.35).toDouble();

  /// Voz entra audível cedo (sem “buraco” antes de falar).
  static double _voiceFadeIn(double t) => 0.42 + 0.58 * _smoothstep(t);

  static double _voiceFadeOut(double t) => 1.0 - _smoothstep(t);

  static double _outroFadeIn(double t) => _smoothstep(t);

  static double _smoothstep(double t) {
    final x = t.clamp(0.0, 1.0);
    return x * x * (3 - 2 * x);
  }

  /// Remove silêncio no final do drop de início (evita pausa antes da voz).
  static List<double> _trimIntroTail(List<double> s, int rate) =>
      _trimTail(s, rate, maxTrimMs: 420);

  /// Remove silêncio no começo do drop de fim.
  static List<double> _trimOutroHead(List<double> s, int rate) =>
      _trimHead(s, rate, maxTrimMs: 320);

  static List<double> _trimTail(List<double> s, int rate, {required int maxTrimMs}) {
    if (s.isEmpty) return s;
    final maxTrim = max(1, rate * maxTrimMs ~/ 1000);
    const thresh = 0.012;
    var end = s.length;
    var trimmed = 0;
    while (end > 0 && trimmed < maxTrim && s[end - 1].abs() < thresh) {
      end--;
      trimmed++;
    }
    if (end < rate ~/ 15) return s;
    return s.sublist(0, end);
  }

  static List<double> _trimHead(List<double> s, int rate, {required int maxTrimMs}) {
    if (s.isEmpty) return s;
    final maxTrim = max(1, rate * maxTrimMs ~/ 1000);
    const thresh = 0.012;
    var start = 0;
    var trimmed = 0;
    while (start < s.length && trimmed < maxTrim && s[start].abs() < thresh) {
      start++;
      trimmed++;
    }
    if (s.length - start < rate ~/ 15) return s;
    return s.sublist(start);
  }

  static List<double> _resampleToRate(List<double> pcm, int fromRate, int toRate) {
    if (pcm.isEmpty || fromRate <= 0 || toRate <= 0 || fromRate == toRate) return pcm;
    final outLen = max(1, (pcm.length * toRate / fromRate).round());
    final out = List<double>.filled(outLen, 0);
    for (var i = 0; i < outLen; i++) {
      final src = i * fromRate / toRate;
      final i0 = src.floor().clamp(0, pcm.length - 1);
      final i1 = min(pcm.length - 1, i0 + 1);
      final t = src - i0;
      out[i] = pcm[i0] * (1 - t) + pcm[i1] * t;
    }
    return out;
  }

  static int _sampleRate(Uint8List bytes) {
    if (bytes.length < 28) return 0;
    return ByteData.sublistView(bytes).getUint32(24, Endian.little);
  }

  static Uint8List _scaleWav(Uint8List wav, double gain) {
    final headerEnd = _dataOffset(wav);
    if (headerEnd <= 0 || headerEnd >= wav.length) return wav;

    final out = Uint8List.fromList(wav);
    final view = ByteData.sublistView(out);
    final g = gain.clamp(0.0, 1.0);

    for (var i = headerEnd; i + 1 < out.length; i += 2) {
      final v = (view.getInt16(i, Endian.little) * g).round().clamp(-32768, 32767);
      view.setInt16(i, v, Endian.little);
    }
    return out;
  }

  static List<double> _decodeMono(Uint8List bytes) {
    final headerEnd = _dataOffset(bytes);
    final view = ByteData.sublistView(bytes);
    final channels = max(1, view.getUint16(22, Endian.little));
    final out = <double>[];
    for (var i = headerEnd; i + 1 < bytes.length; i += 2 * channels) {
      out.add(view.getInt16(i, Endian.little) / 32768.0);
    }
    return out;
  }

  static Uint8List _encodeMono(List<double> samples, int sampleRate) {
    final dataBytes = samples.length * 2;
    final fileBytes = 44 + dataBytes;
    final out = Uint8List(fileBytes);
    final view = ByteData.sublistView(out);
    out.setAll(0, 'RIFF'.codeUnits);
    view.setUint32(4, fileBytes - 8, Endian.little);
    out.setAll(8, 'WAVE'.codeUnits);
    out.setAll(12, 'fmt '.codeUnits);
    view.setUint32(16, 16, Endian.little);
    view.setUint16(20, 1, Endian.little);
    view.setUint16(22, 1, Endian.little);
    view.setUint32(24, sampleRate, Endian.little);
    view.setUint32(28, sampleRate * 2, Endian.little);
    view.setUint16(32, 2, Endian.little);
    view.setUint16(34, 16, Endian.little);
    out.setAll(36, 'data'.codeUnits);
    view.setUint32(40, dataBytes, Endian.little);
    for (var i = 0; i < samples.length; i++) {
      view.setInt16(44 + i * 2, (samples[i].clamp(-1.0, 1.0) * 32767).round(), Endian.little);
    }
    return out;
  }

  static int _dataOffset(Uint8List bytes) {
    for (var i = 12; i + 8 < bytes.length; i++) {
      if (bytes[i] == 0x64 && bytes[i + 1] == 0x61 && bytes[i + 2] == 0x74 && bytes[i + 3] == 0x61) {
        return i + 8;
      }
    }
    return 44;
  }
}

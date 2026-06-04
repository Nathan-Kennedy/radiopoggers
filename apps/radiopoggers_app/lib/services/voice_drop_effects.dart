import 'dart:math';
import 'dart:typed_data';

import '../models/voice_drop_effects_config.dart';

class _WavPcm {
  _WavPcm({required this.sampleRate, required this.samples});

  final int sampleRate;
  final List<double> samples;
}

/// Processa efeitos em WAV PCM 16-bit (mono ou stereo → mono).
class VoiceDropEffects {
  static Uint8List apply(Uint8List wavBytes, VoiceDropEffectsConfig fx) {
    if (!fx.hasAny) return wavBytes;
    final pcm = _decodeWav(wavBytes);
    if (pcm == null) return wavBytes;

    var s = pcm.samples;
    if (fx.autotuneEnabled) {
      s = _autotune(s, pcm.sampleRate, fx.autotuneSemitones, fx.autotuneSnap);
    }
    if (fx.robotEnabled) {
      s = _robot(s, pcm.sampleRate, fx.robotDepth);
    }
    if (fx.megaphoneEnabled) {
      s = _megaphone(s, pcm.sampleRate);
    }
    if (fx.echoEnabled) {
      s = _echo(s, pcm.sampleRate, fx.echoDelayMs, fx.echoFeedback);
    }
    if (fx.chorusEnabled) {
      s = _chorus(s, pcm.sampleRate, fx.chorusDepth);
    }
    return _encodeWavMono(s, pcm.sampleRate);
  }

  static _WavPcm? _decodeWav(Uint8List bytes) {
    if (bytes.length < 48) return null;
    final view = ByteData.sublistView(bytes);
    final channels = view.getUint16(22, Endian.little);
    final sampleRate = view.getUint16(24, Endian.little);
    final bits = view.getUint16(34, Endian.little);
    if (bits != 16 || sampleRate <= 0) return null;

    final dataOffset = _dataOffset(bytes);
    if (dataOffset <= 0) return null;

    final samples = <double>[];
    for (var i = dataOffset; i + 1 < bytes.length; i += 2 * channels) {
      var sum = 0.0;
      for (var ch = 0; ch < channels; ch++) {
        final idx = i + ch * 2;
        if (idx + 1 >= bytes.length) break;
        sum += view.getInt16(idx, Endian.little) / 32768.0;
      }
      samples.add(sum / channels);
    }
    return _WavPcm(sampleRate: sampleRate, samples: samples);
  }

  static int _dataOffset(Uint8List bytes) {
    for (var i = 12; i + 8 < bytes.length; i++) {
      if (bytes[i] == 0x64 && bytes[i + 1] == 0x61 && bytes[i + 2] == 0x74 && bytes[i + 3] == 0x61) {
        return i + 8;
      }
    }
    return 44;
  }

  static Uint8List _encodeWavMono(List<double> samples, int sampleRate) {
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
      final clamped = samples[i].clamp(-1.0, 1.0);
      final v = (clamped * 32767).round().clamp(-32768, 32767);
      view.setInt16(44 + i * 2, v, Endian.little);
    }
    return out;
  }

  static List<double> _echo(List<double> s, int rate, double delayMs, double feedback) {
    final delay = max(1, (delayMs * rate / 1000).round());
    final fb = feedback.clamp(0.08, 0.75);
    final out = List<double>.filled(s.length, 0);
    for (var i = 0; i < s.length; i++) {
      final wet = i >= delay ? out[i - delay] * fb : 0.0;
      out[i] = (s[i] + wet).clamp(-1.0, 1.0);
    }
    return _normalize(out, 0.96);
  }

  static List<double> _autotune(List<double> s, int rate, double semitones, double snap) {
    final shift = semitones.clamp(-8.0, 8.0);
    final snapAmt = snap.clamp(0.0, 1.0);
    if (shift.abs() < 0.01 && snapAmt < 0.05) return s;

    final baseRatio = pow(2, shift / 12).toDouble();
    if (snapAmt < 0.12) return _resample(s, baseRatio);

    final window = max(512, (rate * 0.045).round());
    final out = <double>[];
    for (var start = 0; start < s.length; start += window) {
      final end = min(start + window, s.length);
      final chunk = s.sublist(start, end);
      final localRatio = _windowSnapRatio(chunk, rate, baseRatio, snapAmt);
      out.addAll(_resample(chunk, localRatio));
    }
    return _normalize(out, 0.95);
  }

  static double _windowSnapRatio(List<double> chunk, int rate, double baseRatio, double snapAmt) {
    if (chunk.length < 64) return baseRatio;
    var crossings = 0;
    for (var i = 1; i < chunk.length; i++) {
      if ((chunk[i] >= 0) != (chunk[i - 1] >= 0)) crossings++;
    }
    final freq = crossings * rate / (2 * chunk.length);
    if (freq < 60 || freq > 900) return baseRatio;
    final midi = 69 + 12 * (log(freq / 440) / ln2);
    final snapped = midi.roundToDouble();
    final targetFreq = 440 * pow(2, (snapped - 69) / 12);
    final ratio = (targetFreq / freq) * baseRatio;
    return 1.0 + (ratio - 1.0) * snapAmt;
  }

  static const double ln2 = 0.6931471805599453;

  static List<double> _resample(List<double> s, double ratio) {
    if (ratio <= 0.05 || ratio.isNaN) return s;
    final outLen = max(1, (s.length / ratio).round());
    final out = List<double>.filled(outLen, 0);
    for (var i = 0; i < outLen; i++) {
      final src = i * ratio;
      final i0 = src.floor().clamp(0, s.length - 1);
      final i1 = min(i0 + 1, s.length - 1);
      final t = src - i0;
      out[i] = s[i0] * (1 - t) + s[i1] * t;
    }
    return out;
  }

  static List<double> _robot(List<double> s, int rate, double depth) {
    final d = depth.clamp(0.1, 0.9);
    final out = List<double>.filled(s.length, 0);
    for (var i = 0; i < s.length; i++) {
      final mod = 0.5 + 0.5 * sin(2 * pi * 38 * i / rate);
      out[i] = (s[i] * ((1 - d) + d * mod)).clamp(-1.0, 1.0);
    }
    return out;
  }

  static List<double> _megaphone(List<double> s, int rate) {
    var hp = 0.0;
    final rc = 1.0 / (2 * pi * 280);
    final dt = 1.0 / rate;
    final alpha = rc / (rc + dt);
    final out = List<double>.filled(s.length, 0);
    for (var i = 0; i < s.length; i++) {
      final x = s[i];
      hp = alpha * (hp + x - (i > 0 ? s[i - 1] : x));
      final driven = _tanh(hp * 2.8);
      out[i] = driven.clamp(-1.0, 1.0);
    }
    return _normalize(out, 0.92);
  }

  static List<double> _chorus(List<double> s, int rate, double depth) {
    final d = depth.clamp(0.08, 0.75);
    final detuned = _resample(s, 1.018);
    final delay = max(1, (rate * 0.022).round());
    final out = List<double>.from(s);
    for (var i = 0; i < out.length; i++) {
      final wet = i < detuned.length ? detuned[i] : 0.0;
      final echo = i >= delay ? out[i - delay] * 0.25 : 0.0;
      out[i] = (out[i] * (1 - d) + wet * d * 0.7 + echo * d * 0.2).clamp(-1.0, 1.0);
    }
    return _normalize(out, 0.95);
  }

  static double _tanh(double x) {
    if (x > 6) return 1;
    if (x < -6) return -1;
    final e2x = exp(2 * x);
    return (e2x - 1) / (e2x + 1);
  }

  static List<double> _normalize(List<double> s, double targetPeak) {
    var peak = 0.0;
    for (final v in s) {
      peak = max(peak, v.abs());
    }
    if (peak < 0.001) return s;
    final scale = targetPeak / peak;
    return [for (final v in s) (v * scale).clamp(-1.0, 1.0)];
  }
}

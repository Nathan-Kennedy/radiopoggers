import 'dart:math';
import 'dart:typed_data';

/// Redução de ruído por ganho Wiener suave (preserva timbre da voz).
class VoiceDropSpectralDenoise {
  static Uint8List apply(Uint8List wav) {
    if (wav.length < 128) return wav;

    final rate = _sampleRate(wav);
    if (rate < 8000) return wav;

    final samples = _decodeMono(wav);
    if (samples.length < rate ~/ 20) return wav;

    final cleaned = _wienerDenoise(samples, rate);
    return _encodeMono(cleaned, rate);
  }

  static List<double> _wienerDenoise(List<double> x, int rate) {
    final frame = max(320, (rate * 0.02).round());
    final hop = max(80, frame ~/ 4);
    final window = List<double>.generate(frame, (i) {
      final t = i / max(1, frame - 1);
      return 0.5 - 0.5 * cos(2 * pi * t);
    });

    final out = List<double>.filled(x.length, 0.0);
    final norm = List<double>.filled(x.length, 0.0);
    var noiseFloor = 0.002;
    var calibrated = false;

    for (var start = 0; start < x.length; start += hop) {
      var energy = 0.0;
      for (var i = 0; i < frame; i++) {
        final idx = start + i;
        if (idx >= x.length) break;
        final s = x[idx] * window[i];
        energy += s * s;
      }
      energy = sqrt(energy / frame);

      if (!calibrated) {
        noiseFloor = min(noiseFloor, energy + 1e-6);
        if (start > rate ~/ 5) calibrated = true;
      } else if (energy < noiseFloor * 2.2) {
        noiseFloor = noiseFloor * 0.94 + energy * 0.06;
      } else {
        noiseFloor = noiseFloor * 0.9985 + energy * 0.0015;
      }

      final snr = max(0.0, energy / max(1e-6, noiseFloor) - 1.0);
      final gain = (snr / (snr + 2.8)).clamp(0.18, 1.0);

      for (var i = 0; i < frame; i++) {
        final idx = start + i;
        if (idx >= x.length) break;
        final w = window[i];
        out[idx] += x[idx] * gain * w;
        norm[idx] += w;
      }
    }

    for (var i = 0; i < out.length; i++) {
      if (norm[i] > 1e-6) out[i] /= norm[i];
    }

    var peak = 1e-9;
    for (final v in out) {
      peak = max(peak, v.abs());
    }
    final scale = min(1.0, 0.97 / peak);
    return out.map((v) => (v * scale).clamp(-1.0, 1.0)).toList();
  }

  static int _sampleRate(Uint8List bytes) {
    if (bytes.length < 28) return 0;
    return ByteData.sublistView(bytes).getUint32(24, Endian.little);
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

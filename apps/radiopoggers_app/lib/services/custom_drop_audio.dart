import 'dart:io';
import 'dart:math';
import 'dart:typed_data';

import 'package:audio_decoder/audio_decoder.dart';
import 'package:path_provider/path_provider.dart';

import 'custom_drop_storage.dart';

/// Decodifica MP3/M4A/etc. para WAV mono 44.1 kHz (mix e envio usam só WAV).
class CustomDropAudio {
  static const maxDurationMs = CustomDropStorage.maxDurationMs;
  static const int targetSampleRate = 44100;

  static final List<String> pickerExtensions = AudioDecoder.supportedExtensions
      .map((e) => e.startsWith('.') ? e.substring(1) : e)
      .toList();

  static Future<Uint8List> loadPrepared(String storedName) async {
    final path = await CustomDropStorage.resolvePath(storedName);
    if (path.isEmpty || !File(path).existsSync()) {
      throw StateError('Arquivo do drop não encontrado.');
    }
    return decodeFileToWav(path);
  }

  /// Converte qualquer formato suportado para WAV pronto para mix.
  static Future<Uint8List> decodeFileToWav(String path) async {
    final ext = _extension(path);
    if (ext == 'wav') {
      return normalizeToMonoWav(await File(path).readAsBytes());
    }

    try {
      final wavPath = await _convertWithNativeDecoder(path);
      final bytes = await File(wavPath).readAsBytes();
      try {
        await File(wavPath).delete();
      } catch (_) {}
      return normalizeToMonoWav(bytes);
    } on AudioConversionException catch (e) {
      final fallback = await _decodeFullViaFfmpeg(path);
      if (fallback != null) return normalizeToMonoWav(fallback);
      throw StateError(
        'Não foi possível abrir este áudio (${ext.isEmpty ? 'formato' : ext}). '
        '${e.message}',
      );
    } catch (_) {
      final fallback = await _decodeFullViaFfmpeg(path);
      if (fallback != null) return normalizeToMonoWav(fallback);
      rethrow;
    }
  }

  static Future<String> _convertWithNativeDecoder(String inputPath) async {
    final dir = await getTemporaryDirectory();
    final out = '${dir.path}/drop-decode-${DateTime.now().millisecondsSinceEpoch}.wav';
    await AudioDecoder.convertToWav(
      inputPath,
      out,
      sampleRate: targetSampleRate,
      channels: 1,
      bitDepth: 16,
    );
    return out;
  }

  static int durationMs(Uint8List wav) {
    final rate = _sampleRate(wav);
    if (rate <= 0) return 0;
    return (_pcmSampleCount(wav) * 1000 / rate).round();
  }

  /// Duração do arquivo original (antes do corte de 5 s).
  static Future<int> fileDurationMs(String path) async {
    try {
      final info = await AudioDecoder.getAudioInfo(path);
      return (info.duration.inMilliseconds).round();
    } catch (_) {
      final wav = await decodeFileToWav(path);
      return durationMs(wav);
    }
  }

  static Uint8List extractSegment(
    Uint8List wav, {
    required int startMs,
    int lengthMs = maxDurationMs,
  }) {
    final rate = _sampleRate(wav);
    if (rate <= 0) return wav;

    final pcm = _decodeMono(wav);
    final startSample = (rate * startMs / 1000).round().clamp(0, pcm.length);
    final lenSamples = max(1, (rate * lengthMs / 1000).round());
    final end = min(pcm.length, startSample + lenSamples);
    if (startSample >= pcm.length) return _encodeMono(const [], rate);
    return _encodeMono(pcm.sublist(startSample, end), rate);
  }

  static Uint8List trimFromStart(Uint8List input, {required int maxMs}) =>
      extractSegment(input, startMs: 0, lengthMs: maxMs);

  static Uint8List normalizeToMonoWav(Uint8List input) {
    if (input.length < 48) return input;
    final rate = _sampleRate(input);
    if (rate <= 0) return input;
    final pcm = _decodeMono(input);
    if (rate == targetSampleRate) {
      return _encodeMono(pcm, rate);
    }
    final resampled = _resample(pcm, rate, targetSampleRate);
    return _encodeMono(resampled, targetSampleRate);
  }

  static List<double> _resample(List<double> pcm, int fromRate, int toRate) {
    if (fromRate <= 0 || toRate <= 0 || pcm.isEmpty) return pcm;
    if (fromRate == toRate) return pcm;
    final outLen = max(1, (pcm.length * toRate / fromRate).round());
    final out = List<double>.filled(outLen, 0);
    for (var i = 0; i < outLen; i++) {
      final srcPos = i * fromRate / toRate;
      final i0 = srcPos.floor().clamp(0, pcm.length - 1);
      final i1 = min(pcm.length - 1, i0 + 1);
      final t = srcPos - i0;
      out[i] = pcm[i0] * (1 - t) + pcm[i1] * t;
    }
    return out;
  }

  static Future<Uint8List?> _decodeFullViaFfmpeg(String inputPath) async {
    try {
      final result = await Process.run('ffmpeg', [
        '-y',
        '-i',
        inputPath,
        '-ac',
        '1',
        '-ar',
        '$targetSampleRate',
        '-f',
        'wav',
        'pipe:1',
      ]);
      if (result.exitCode != 0) return null;
      final out = result.stdout;
      if (out is List<int> && out.length > 48) {
        return Uint8List.fromList(out);
      }
      if (out is Uint8List && out.length > 48) return out;
    } catch (_) {}
    return null;
  }

  static String _extension(String path) {
    final dot = path.lastIndexOf('.');
    if (dot < 0) return '';
    return path.substring(dot + 1).toLowerCase();
  }

  static int _sampleRate(Uint8List bytes) {
    if (bytes.length < 28) return 0;
    return ByteData.sublistView(bytes).getUint32(24, Endian.little);
  }

  static int _pcmSampleCount(Uint8List bytes) {
    final headerEnd = _dataOffset(bytes);
    final channels = max(1, ByteData.sublistView(bytes).getUint16(22, Endian.little));
    return max(0, (bytes.length - headerEnd) ~/ (2 * channels));
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

  static int _dataOffset(Uint8List bytes) {
    for (var i = 12; i + 8 < bytes.length; i++) {
      if (bytes[i] == 0x64 && bytes[i + 1] == 0x61 && bytes[i + 2] == 0x74 && bytes[i + 3] == 0x61) {
        return i + 8;
      }
    }
    return 44;
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
}

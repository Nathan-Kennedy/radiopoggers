import 'dart:io';
import 'dart:typed_data';

import 'package:path_provider/path_provider.dart';

import 'voice_drop_spectral_denoise.dart';

/// Redução de ruído estilo Discord: RNNoise via FFmpeg quando disponível;
/// fallback espectral Wiener (sem gate agressivo que estraga a voz).
class VoiceDropNoiseSuppress {
  static Future<Uint8List> apply(Uint8List wav) async {
    if (wav.length < 128) return wav;

    final ff = await _tryFfmpegRnnoise(wav);
    if (ff != null && ff.length > 48) return ff;

    return VoiceDropSpectralDenoise.apply(wav);
  }

  static Future<Uint8List?> _tryFfmpegRnnoise(Uint8List wav) async {
    const chains = [
      'highpass=f=90,lowpass=f=12000,arnndn=m=0.55',
      'highpass=f=90,lowpass=f=12000,arnndn=m=0.45',
      'highpass=f=90,afftdn=nr=16:nf=-28:tn=1',
    ];
    final dir = await getTemporaryDirectory();
    final id = DateTime.now().microsecondsSinceEpoch;
    final inPath = '${dir.path}/rp-ff-in-$id.wav';
    final outPath = '${dir.path}/rp-ff-out-$id.wav';
    try {
      await File(inPath).writeAsBytes(wav, flush: true);
      for (final af in chains) {
        try {
          final result = await Process.run('ffmpeg', [
            '-hide_banner',
            '-loglevel',
            'error',
            '-y',
            '-i',
            inPath,
            '-af',
            af,
            outPath,
          ]);
          if (result.exitCode != 0) continue;
          if (!File(outPath).existsSync()) continue;
          final out = await File(outPath).readAsBytes();
          if (out.length > 48) return out;
        } catch (_) {}
      }
    } catch (_) {}
    finally {
      await _deleteQuiet(inPath, outPath);
    }
    return null;
  }

  static Future<void> _deleteQuiet(String a, String b) async {
    for (final p in [a, b]) {
      try {
        final f = File(p);
        if (f.existsSync()) await f.delete();
      } catch (_) {}
    }
  }
}

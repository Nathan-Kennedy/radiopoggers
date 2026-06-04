import 'dart:math' as math;

import 'package:flutter/foundation.dart';

/// Energia espectral suavizada para visualizadores (barras + ondas).
/// Com áudio ao vivo usa simulação orgânica; parado fica quase estático.
class AudioReactiveMeter extends ChangeNotifier {
  static const int binCount = 128;

  final List<double> bins = List<double>.filled(binCount, 0.04);

  double smoothLevel = 0;
  double hotLevel = 0;
  double phase = 0;

  void tick({required bool live, double dt = 1 / 30, int? trackElapsedSec}) {
    phase += live ? dt : dt * 0.12;

    if (!live) {
      smoothLevel += (0 - smoothLevel) * 0.14;
      hotLevel *= 0.82;
      for (var i = 0; i < binCount; i++) {
        final breath = 0.035 + math.sin(phase * 0.35 + i * 0.18) * 0.015;
        bins[i] += (breath - bins[i]) * 0.16;
      }
      notifyListeners();
      return;
    }

    final trackBeat = trackElapsedSec != null && trackElapsedSec > 0
        ? math.sin((trackElapsedSec % 2) * math.pi) * 0.22 + 0.78
        : 1.0;
    final beat = (math.sin(phase * 2.1) * 0.5 + 0.5) * trackBeat;
    var bassSum = 0.0;
    var midSum = 0.0;
    const bassEnd = 14;
    const midEnd = 48;

    for (var i = 0; i < binCount; i++) {
      final t = i / binCount;
      final w1 = math.sin(phase * (3.2 + t * 11) + i * 0.41) * 0.5 + 0.5;
      final w2 = math.sin(phase * 1.7 + i * 0.23) * 0.5 + 0.5;
      final w3 = math.sin(phase * 0.9 + i * 0.08) * 0.5 + 0.5;
      final energy = w1 * w2 * (0.32 + beat * 0.48) * (0.55 + w3 * 0.45);
      final target = (0.06 + energy * 0.94).clamp(0.0, 1.0);
      bins[i] += (target - bins[i]) * 0.32;
      if (i < bassEnd) {
        bassSum += bins[i];
      } else if (i < midEnd) {
        midSum += bins[i];
      }
    }

    final bass = bassSum / bassEnd;
    final mid = midSum / (midEnd - bassEnd);
    final raw = math.min(1.0, bass * 0.78 + mid * 0.22);
    smoothLevel += (raw - smoothLevel) * 0.34;
    hotLevel *= 0.82;
    if (raw > smoothLevel + 0.12) {
      hotLevel = math.min(1.0, hotLevel + ((raw - smoothLevel) * 1.6));
    }
    notifyListeners();
  }

  double binForBar(int index, int barCount) {
    final bin = ((index / barCount) * math.min(72, binCount)).floor();
    return bins[bin.clamp(0, binCount - 1)];
  }

  double sampleAlongWidth(double t) {
    final bin = math.min(binCount - 1, (t * 28).floor());
    return bins[bin];
  }
}

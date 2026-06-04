import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../core/theme/app_colors.dart';
import '../services/audio_reactive_meter.dart';

/// Barras estilo NCS / site `.visualizer`.
class NcsVisualizer extends StatelessWidget {
  const NcsVisualizer({
    super.key,
    required this.active,
    required this.meter,
    this.barCount = 5,
    this.height = 48,
  });

  final bool active;
  final AudioReactiveMeter meter;
  final int barCount;
  final double height;

  @override
  Widget build(BuildContext context) {
    return RepaintBoundary(
      child: ListenableBuilder(
        listenable: meter,
        builder: (context, _) {
          // Altura fixa = extensão máxima das barras; animação só cresce pra cima.
          return SizedBox(
            height: height,
            width: double.infinity,
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.end,
              children: List.generate(barCount, (i) {
                final bin = meter.binForBar(i, barCount);
                final wave = active ? (0.28 + bin * 0.72) : (0.1 + math.sin(meter.phase * 0.35 + i * 0.2) * 0.04);
                final barH = height * wave.clamp(0.1, 1.0);
                return Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 3),
                  child: Container(
                    width: 6,
                    height: barH,
                    decoration: BoxDecoration(
                      gradient: const LinearGradient(
                        begin: Alignment.bottomCenter,
                        end: Alignment.topCenter,
                        colors: [AppColors.accent, AppColors.accentHot],
                      ),
                      borderRadius: BorderRadius.circular(2),
                      boxShadow: active && bin > 0.35
                          ? [BoxShadow(color: AppColors.accentHot.withValues(alpha: 0.45), blurRadius: 8)]
                          : null,
                    ),
                  ),
                );
              }),
            ),
          );
        },
      ),
    );
  }
}

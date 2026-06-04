import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../core/theme/app_colors.dart';
import '../services/audio_reactive_meter.dart';

/// Visual do `audioPulseCanvas` do site — canto superior direito, fade à esquerda.
class HeaderPulseBackdrop extends StatefulWidget {
  const HeaderPulseBackdrop({
    super.key,
    required this.meter,
    this.active = true,
    this.intensity = 1,
    this.width,
    this.height = 96,
    this.bleedBottom = 32,
  });

  final AudioReactiveMeter meter;
  final bool active;
  final double intensity;
  final double? width;
  final double height;
  /// Quanto a animação “invade” a interface abaixo do cabeçalho.
  final double bleedBottom;

  @override
  State<HeaderPulseBackdrop> createState() => _HeaderPulseBackdropState();
}

class _HeaderPulseBackdropState extends State<HeaderPulseBackdrop> {
  final List<double> _barSmooth = List.filled(42, 0.06);

  @override
  Widget build(BuildContext context) {
    final screenW = MediaQuery.sizeOf(context).width;
    final w = widget.width ?? math.min(screenW * 0.52, 400.0);
    final h = widget.height + widget.bleedBottom;

    return SizedBox(
      width: w,
      height: h,
      child: ListenableBuilder(
        listenable: widget.meter,
        builder: (context, _) {
          return HeaderPulseMask(
            child: CustomPaint(
              size: Size(w, h),
              painter: _HeaderPulsePainter(
                meter: widget.meter,
                active: widget.active,
                intensity: widget.intensity.clamp(0, 1),
                barSmooth: _barSmooth,
                bleedBottom: widget.bleedBottom,
              ),
            ),
          );
        },
      ),
    );
  }
}

/// Máscara igual ao site: transparente à esquerda, opaco à direita.
class HeaderPulseMask extends StatelessWidget {
  const HeaderPulseMask({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return ShaderMask(
      blendMode: BlendMode.dstIn,
      shaderCallback: (bounds) {
        return LinearGradient(
          begin: Alignment.centerLeft,
          end: Alignment.centerRight,
          colors: [
            Colors.transparent,
            Colors.white.withValues(alpha: 0.35),
            Colors.white,
          ],
          stops: const [0.08, 0.38, 0.72],
        ).createShader(bounds);
      },
      child: child,
    );
  }
}

class _HeaderPulsePainter extends CustomPainter {
  _HeaderPulsePainter({
    required this.meter,
    required this.active,
    required this.intensity,
    required this.barSmooth,
    required this.bleedBottom,
  });

  final AudioReactiveMeter meter;
  final bool active;
  final double intensity;
  final List<double> barSmooth;
  final double bleedBottom;

  static const int _barCount = 42;

  @override
  void paint(Canvas canvas, Size size) {
    final width = size.width;
    final height = size.height;
    if (width <= 0 || height <= 0) return;

    final time = meter.phase;
    final motion = active ? 1.0 : 0.08;
    final level = active
        ? (0.34 + intensity * 0.5 + meter.smoothLevel * 0.22)
        : (0.03 + intensity * 0.05);
    final hot = active ? (intensity * 0.25 + meter.hotLevel * 0.35) : 0.0;
    final coreH = math.max(1.0, height - bleedBottom);

    final barWidth = width / _barCount;
    for (var index = 0; index < _barCount; index++) {
      final target = active ? meter.binForBar(index, _barCount) : (0.04 + math.sin(time * 0.4 + index * 0.15) * 0.02);
      barSmooth[index] += (target - barSmooth[index]) * (active ? 0.32 : 0.12);
      final value = barSmooth[index];
      final barHeight = value * coreH * 0.52 * (0.4 + level * 0.6);
      final x = width - (index + 1) * barWidth;

      final grad = Paint()
        ..shader = LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [
            Color.lerp(const Color(0xFFFF4152), const Color(0xFFFF3344), value)!
                .withValues(alpha: 0.2 + value * 0.32 + hot * 0.12),
            Color.lerp(const Color(0xFFB41624), const Color(0xFF501018), value)!
                .withValues(alpha: 0.12 + value * 0.22 + hot * 0.08),
            const Color(0xFF500810).withValues(alpha: 0.04 + value * 0.1),
          ],
        ).createShader(Rect.fromLTWH(x, 0, barWidth, barHeight.clamp(1, coreH)));

      canvas.drawRRect(
        RRect.fromRectAndRadius(
          Rect.fromLTWH(x + 1, 0, math.max(1, barWidth - 2), barHeight.clamp(1, coreH)),
          const Radius.circular(1),
        ),
        grad,
      );
    }

    const waveLayers = [
      _WaveLayer(amp: 0.13, speed: 1.15, freq: 5.8, opacity: 0.1, width: 1.4, yFromTop: 0.66),
      _WaveLayer(amp: 0.1, speed: 0.82, freq: 4.2, opacity: 0.08, width: 1.8, yFromTop: 0.54),
      _WaveLayer(amp: 0.085, speed: 1.4, freq: 7.6, opacity: 0.07, width: 1.1, yFromTop: 0.44),
      _WaveLayer(amp: 0.065, speed: 0.58, freq: 3, opacity: 0.06, width: 2.2, yFromTop: 0.76),
    ];

    for (var layerIndex = 0; layerIndex < waveLayers.length; layerIndex++) {
      final layer = waveLayers[layerIndex];
      final path = Path();
      final amplitude = layer.amp * coreH * (0.6 + level * 0.55) * motion;
      final yBase = coreH * layer.yFromTop;

      for (var x = 0.0; x <= width; x += 2) {
        final t = x / width;
        final mod = active ? (0.5 + meter.sampleAlongWidth(t) * 0.55) : 0.52;
        final wave = math.sin((t * layer.freq * math.pi) + (time * layer.speed * motion) + (layerIndex * 1.3)) *
            math.sin((t * 2.1) + (time * 0.45 * motion) + layerIndex) *
            amplitude *
            mod;
        final y = yBase + wave;
        if (x == 0) {
          path.moveTo(x, y);
        } else {
          path.lineTo(x, y);
        }
      }

      canvas.drawPath(
        path,
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = layer.width
          ..strokeCap = StrokeCap.round
          ..color = AppColors.accentHot.withValues(alpha: layer.opacity + (level * 0.14) + (hot * 0.07)),
      );
    }

    final ripplePath = Path();
    final rippleBase = 6 + (level * 14);
    for (var x = 0.0; x <= width; x += 3) {
      final t = x / width;
      final bassMod = active ? meter.sampleAlongWidth(t) : 0.04;
      final ripple = math.sin((t * 14) + (time * 2.4 * motion)) *
          (2 + (level * 10) + (hot * 8) + (bassMod * 6)) *
          motion;
      if (x == 0) {
        ripplePath.moveTo(x, rippleBase + ripple);
      } else {
        ripplePath.lineTo(x, rippleBase + ripple);
      }
    }
    canvas.drawPath(
      ripplePath,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.2
        ..color = AppColors.accentHot.withValues(alpha: 0.14 + (level * 0.28) + (hot * 0.1)),
    );

    if (bleedBottom > 0) {
      final bleedFade = Paint()
        ..shader = LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [
            Colors.transparent,
            AppColors.bg.withValues(alpha: 0.35),
            Colors.transparent,
          ],
          stops: const [0.0, 0.55, 1.0],
        ).createShader(Rect.fromLTWH(0, coreH - 8, width, bleedBottom + 12));
      canvas.drawRect(Rect.fromLTWH(0, coreH - 8, width, bleedBottom + 12), bleedFade);
    }
  }

  @override
  bool shouldRepaint(covariant _HeaderPulsePainter oldDelegate) {
    return oldDelegate.meter.phase != meter.phase ||
        oldDelegate.active != active ||
        oldDelegate.intensity != intensity ||
        oldDelegate.meter.smoothLevel != meter.smoothLevel ||
        oldDelegate.bleedBottom != bleedBottom;
  }
}

class _WaveLayer {
  const _WaveLayer({
    required this.amp,
    required this.speed,
    required this.freq,
    required this.opacity,
    required this.width,
    required this.yFromTop,
  });

  final double amp;
  final double speed;
  final double freq;
  final double opacity;
  final double width;
  final double yFromTop;
}

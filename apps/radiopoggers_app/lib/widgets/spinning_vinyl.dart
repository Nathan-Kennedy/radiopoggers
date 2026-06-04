import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../core/theme/app_colors.dart';
import '../core/theme/app_motion.dart';

/// Disco girando quando `spinning` — capa no label, sulcos no vinil.
class SpinningVinyl extends StatefulWidget {
  const SpinningVinyl({
    super.key,
    required this.spinning,
    this.coverUrl,
    this.size = 200,
    this.fallbackLabel = 'RG',
  });

  final bool spinning;
  final String? coverUrl;
  final double size;
  final String fallbackLabel;

  @override
  State<SpinningVinyl> createState() => _SpinningVinylState();
}

class _SpinningVinylState extends State<SpinningVinyl> with SingleTickerProviderStateMixin {
  late final AnimationController _spin;

  @override
  void initState() {
    super.initState();
    _spin = AnimationController(vsync: this, duration: AppMotion.vinylSpin);
    _syncSpin();
  }

  @override
  void didUpdateWidget(SpinningVinyl oldWidget) {
    super.didUpdateWidget(oldWidget);
    _syncSpin();
  }

  void _syncSpin() {
    if (widget.spinning) {
      _spin.repeat();
    } else {
      _spin.stop();
    }
  }

  @override
  void dispose() {
    _spin.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final s = widget.size;
    return SizedBox(
      width: s,
      height: s,
      child: Stack(
        alignment: Alignment.center,
        children: [
          Container(
            width: s + 24,
            height: s + 24,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              boxShadow: [
                BoxShadow(
                  color: widget.spinning ? AppColors.broadcastGlow : Colors.black54,
                  blurRadius: widget.spinning ? 36 : 16,
                  spreadRadius: widget.spinning ? 2 : 0,
                ),
              ],
            ),
          ),
          RotationTransition(
            turns: _spin,
            child: SizedBox(
              width: s,
              height: s,
              child: Stack(
                alignment: Alignment.center,
                children: [
                  CustomPaint(size: Size(s, s), painter: _VinylGroovesPainter()),
                  _cover(s * 0.72),
                ],
              ),
            ),
          ),
          Container(
            width: s * 0.14,
            height: s * 0.14,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: AppColors.bg,
              border: Border.all(color: AppColors.lineStrong, width: 2),
              boxShadow: const [BoxShadow(color: Colors.black87, blurRadius: 6)],
            ),
          ),
        ],
      ),
    );
  }

  Widget _cover(double diameter) {
    final url = widget.coverUrl?.trim();
    if (url != null && url.isNotEmpty) {
      return Center(
        child: SizedBox(
          width: diameter,
          height: diameter,
          child: ClipOval(
            child: Image.network(url, fit: BoxFit.cover, errorBuilder: (_, __, ___) => _fallback(diameter)),
          ),
        ),
      );
    }
    return _fallback(diameter);
  }

  Widget _fallback(double diameter) {
    return Container(
      width: diameter,
      height: diameter,
      alignment: Alignment.center,
      color: AppColors.vinylGroove,
      child: Text(
        widget.fallbackLabel,
        style: GoogleFonts.bebasNeue(fontSize: diameter * 0.28, color: AppColors.accent),
      ),
    );
  }
}

class _VinylGroovesPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final maxR = size.width / 2;
    final bg = Paint()..color = Colors.black;
    canvas.drawCircle(center, maxR, bg);

    for (var i = 0; i < 28; i++) {
      final t = i / 28;
      final r = maxR * (0.35 + t * 0.62);
      final paint = Paint()
        ..color = Color.lerp(AppColors.vinylGroove, const Color(0xFF2E2E2E), (i % 3) / 3)!
        ..style = PaintingStyle.stroke
        ..strokeWidth = 0.6 + (i % 2) * 0.4;
      canvas.drawCircle(center, r, paint);
    }

    final shine = Paint()
      ..shader = SweepGradient(
        colors: [
          Colors.transparent,
          Colors.white.withValues(alpha: 0.06),
          Colors.transparent,
        ],
        transform: GradientRotation(math.pi / 5),
      ).createShader(Rect.fromCircle(center: center, radius: maxR));
    canvas.drawCircle(center, maxR, shine);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

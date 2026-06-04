import 'dart:async';

import 'package:flutter/material.dart';

import '../ascii/ascii_animator.dart';

class AsciiStage extends StatefulWidget {
  const AsciiStage({
    super.key,
    required this.animator,
    this.caption,
    this.badge = 'MIKU · NO AR',
  });

  final AsciiAnimator? animator;
  final String? caption;
  final String badge;

  @override
  State<AsciiStage> createState() => _AsciiStageState();
}

class _AsciiStageState extends State<AsciiStage> {
  int _tick = 0;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _timer = Timer.periodic(const Duration(milliseconds: AsciiAnimator.frameMs), (_) {
      if (mounted) setState(() => _tick++);
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final animator = widget.animator;
    final size = animator?.size ?? const Size(120, 80);
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 16),
      decoration: BoxDecoration(
        color: Colors.black.withValues(alpha: 0.45),
        border: Border.all(color: Colors.white24),
      ),
      child: Column(
        children: [
          if (animator != null)
            CustomPaint(
              size: size,
              painter: _AsciiPainter(animator, _tick),
            ),
          if (widget.caption != null && widget.caption!.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(
              widget.caption!,
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(height: 1.35),
            ),
          ],
          const SizedBox(height: 6),
          Text(
            widget.badge,
            style: Theme.of(context).textTheme.labelSmall,
          ),
        ],
      ),
    );
  }
}

class _AsciiPainter extends CustomPainter {
  _AsciiPainter(this.animator, this.tick);
  final AsciiAnimator animator;
  final int tick;

  @override
  void paint(Canvas canvas, Size size) {
    animator.paint(canvas, tick);
  }

  @override
  bool shouldRepaint(covariant _AsciiPainter old) => old.tick != tick;
}

/// Frame fixo no picker (sem timer = bem mais leve).
class AsciiFrameStill extends StatelessWidget {
  const AsciiFrameStill({super.key, required this.animator, this.frame = 0});
  final AsciiAnimator? animator;
  final int frame;

  @override
  Widget build(BuildContext context) {
    final a = animator;
    if (a == null) return const SizedBox(height: 80);
    return RepaintBoundary(
      child: CustomPaint(size: a.size, painter: _AsciiPainter(a, frame)),
    );
  }
}

class AsciiMini extends StatefulWidget {
  const AsciiMini({super.key, required this.animator, this.animate = true});
  final AsciiAnimator? animator;
  final bool animate;

  @override
  State<AsciiMini> createState() => _AsciiMiniState();
}

class _AsciiMiniState extends State<AsciiMini> {
  int _tick = 0;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    if (widget.animate) {
      _timer = Timer.periodic(const Duration(milliseconds: AsciiAnimator.frameMs * 2), (_) {
        if (mounted) setState(() => _tick++);
      });
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (!widget.animate) {
      return AsciiFrameStill(animator: widget.animator);
    }
    final a = widget.animator;
    if (a == null) return const SizedBox(height: 80);
    return RepaintBoundary(
      child: CustomPaint(size: a.size, painter: _AsciiPainter(a, _tick)),
    );
  }
}

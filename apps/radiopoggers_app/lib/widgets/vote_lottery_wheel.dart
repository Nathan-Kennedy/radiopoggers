import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../core/theme/app_colors.dart';

/// Roleta do empate — animação inspirada no `#voteLottery` do site.
class VoteLotteryWheel extends StatefulWidget {
  const VoteLotteryWheel({super.key, this.winner});

  /// `yes` ou `no` quando o servidor já definiu o sorteio.
  final String? winner;

  @override
  State<VoteLotteryWheel> createState() => _VoteLotteryWheelState();
}

class _VoteLotteryWheelState extends State<VoteLotteryWheel> with SingleTickerProviderStateMixin {
  static const _spinLabels = ['ROCK', 'PULA!', 'NÃO!', 'METAL', 'FOGO', 'SORTE', 'GRALE', 'POW!'];

  late final AnimationController _wheelCtrl;
  Timer? _labelTimer;
  Timer? _finishTimer;
  int _labelIndex = 0;
  bool _spinning = true;
  bool? _yesWon;
  String _resultText = 'Roleta do rock no vermelho...';

  @override
  void initState() {
    super.initState();
    _wheelCtrl = AnimationController(vsync: this, duration: const Duration(milliseconds: 340))..repeat();
    _labelTimer = Timer.periodic(const Duration(milliseconds: 85), (_) {
      if (!_spinning || !mounted) return;
      setState(() => _labelIndex += 1);
    });
    _scheduleFinish(widget.winner);
  }

  @override
  void didUpdateWidget(covariant VoteLotteryWheel oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.winner != null && widget.winner != oldWidget.winner && _spinning) {
      _finishTimer?.cancel();
      _scheduleFinish(widget.winner);
    }
  }

  void _scheduleFinish(String? winner) {
    _finishTimer?.cancel();
    _finishTimer = Timer(const Duration(milliseconds: 2800), () => _finish(winner));
  }

  void _finish(String? winner) {
    if (!mounted) return;
    final yes = (winner ?? '').toLowerCase() == 'yes';
    _wheelCtrl.stop();
    _labelTimer?.cancel();
    setState(() {
      _spinning = false;
      _yesWon = yes;
      _resultText = yes ? 'A roleta EXPLODIU: VAI PULAR!' : 'A roleta segurou: DEIXA ROLAR!';
    });
  }

  @override
  void dispose() {
    _labelTimer?.cancel();
    _finishTimer?.cancel();
    _wheelCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final faceLabel = _spinning
        ? _spinLabels[_labelIndex % _spinLabels.length]
        : (_yesWon == true ? 'PULA!' : 'NÃO!');
    final stopAngle = (_yesWon == true ? 0.31 : -0.42) * math.pi * 2;

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        AnimatedContainer(
          duration: const Duration(milliseconds: 280),
          padding: const EdgeInsets.symmetric(vertical: 8),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(12),
            boxShadow: _spinning
                ? [
                    BoxShadow(
                      color: AppColors.accentHot.withValues(alpha: 0.35),
                      blurRadius: 28,
                      spreadRadius: 2,
                    ),
                  ]
                : null,
          ),
          child: SizedBox(
            height: 148,
            width: 148,
            child: Stack(
              alignment: Alignment.center,
              children: [
                if (_spinning)
                  ...List.generate(6, (i) {
                    final a = (i / 6) * math.pi * 2 + _labelIndex * 0.4;
                    return Positioned(
                      left: 74 + math.cos(a) * 52,
                      top: 74 + math.sin(a) * 52,
                      child: Icon(Icons.star, size: 8, color: AppColors.accentHot.withValues(alpha: 0.7)),
                    );
                  }),
                const Positioned(
                  top: 4,
                  child: Icon(Icons.arrow_drop_down, size: 32, color: AppColors.accentHot),
                ),
                _spinning
                    ? RotationTransition(turns: _wheelCtrl, child: _WheelDisc(faceLabel))
                    : Transform.rotate(angle: stopAngle, child: _WheelDisc(faceLabel)),
              ],
            ),
          ),
        ),
        const SizedBox(height: 10),
        Text(
          _resultText,
          textAlign: TextAlign.center,
          style: GoogleFonts.ibmPlexMono(
            fontSize: 11,
            fontWeight: FontWeight.w700,
            color: _yesWon == null ? AppColors.muted : (_yesWon! ? AppColors.accentHot : AppColors.text),
            height: 1.35,
          ),
        ),
      ],
    );
  }
}

class _WheelDisc extends StatelessWidget {
  const _WheelDisc(this.faceLabel);
  final String faceLabel;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 120,
      height: 120,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        gradient: const SweepGradient(
          colors: [
            AppColors.accentHot,
            Color(0xFF501018),
            AppColors.accent,
            AppColors.accentHot,
          ],
        ),
        border: Border.all(color: AppColors.lineStrong, width: 3),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.5),
            blurRadius: 12,
            offset: Offset(0, 6),
          ),
        ],
      ),
      child: Center(
        child: Text(
          faceLabel,
          style: GoogleFonts.bebasNeue(fontSize: 22, color: Colors.white, letterSpacing: 1),
        ),
      ),
    );
  }
}

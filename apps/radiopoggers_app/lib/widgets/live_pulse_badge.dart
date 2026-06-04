import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../core/theme/app_colors.dart';
import '../core/theme/app_motion.dart';

class LivePulseBadge extends StatefulWidget {
  const LivePulseBadge({super.key, required this.label, this.online = true});

  final String label;
  final bool online;

  @override
  State<LivePulseBadge> createState() => _LivePulseBadgeState();
}

class _LivePulseBadgeState extends State<LivePulseBadge> with SingleTickerProviderStateMixin {
  late final AnimationController _pulse;

  @override
  void initState() {
    super.initState();
    _pulse = AnimationController(vsync: this, duration: AppMotion.livePulse)..repeat(reverse: true);
  }

  @override
  void dispose() {
    _pulse.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _pulse,
      builder: (context, child) {
        final glow = widget.online ? 0.4 + _pulse.value * 0.6 : 0.2;
        return Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
          decoration: BoxDecoration(
            color: widget.online ? AppColors.accentDim : AppColors.bgElevated,
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: AppColors.lineStrong),
            boxShadow: widget.online
                ? [BoxShadow(color: AppColors.accent.withValues(alpha: glow * 0.5), blurRadius: 12)]
                : null,
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 8,
                height: 8,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: widget.online ? AppColors.accentHot : AppColors.muted,
                  boxShadow: widget.online
                      ? [BoxShadow(color: AppColors.accentHot.withValues(alpha: glow), blurRadius: 6)]
                      : null,
                ),
              ),
              const SizedBox(width: 6),
              Text(
                widget.label,
                style: GoogleFonts.ibmPlexMono(fontSize: 10, fontWeight: FontWeight.w700, letterSpacing: 1),
              ),
            ],
          ),
        );
      },
    );
  }
}

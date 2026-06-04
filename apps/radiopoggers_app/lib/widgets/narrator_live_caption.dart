import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../ascii/ascii_animator.dart';
import '../core/theme/app_colors.dart';
import '../core/theme/app_decorations.dart';
import 'ascii_stage.dart';

/// Legenda da narradora no player (ASCII falando + texto), como no site.
class NarratorLiveCaption extends StatelessWidget {
  const NarratorLiveCaption({
    super.key,
    required this.animator,
    required this.badge,
    this.caption,
  });

  final AsciiAnimator? animator;
  final String badge;
  final String? caption;

  bool get _visible => animator != null || (caption != null && caption!.trim().isNotEmpty);

  @override
  Widget build(BuildContext context) {
    if (!_visible) return const SizedBox.shrink();

    return Container(
      margin: const EdgeInsets.only(bottom: 14),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: AppDecorations.glassPanel(radius: BorderRadius.circular(10)).copyWith(
        border: Border.all(color: AppColors.accentHot.withValues(alpha: 0.45)),
        boxShadow: [
          BoxShadow(
            color: AppColors.accent.withValues(alpha: 0.12),
            blurRadius: 20,
            offset: const Offset(0, 6),
          ),
        ],
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (animator != null)
            Padding(
              padding: const EdgeInsets.only(right: 10, top: 2),
              child: AsciiMini(animator: animator, animate: true),
            ),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Container(
                      width: 7,
                      height: 7,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: AppColors.accentHot,
                        boxShadow: [
                          BoxShadow(
                            color: AppColors.accentHot.withValues(alpha: 0.55),
                            blurRadius: 8,
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      badge,
                      style: GoogleFonts.ibmPlexMono(
                        fontSize: 10,
                        fontWeight: FontWeight.w800,
                        letterSpacing: 1.8,
                        color: AppColors.accentHot,
                      ),
                    ),
                  ],
                ),
                if (caption != null && caption!.trim().isNotEmpty) ...[
                  const SizedBox(height: 8),
                  Text(
                    caption!.trim(),
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                          height: 1.4,
                          fontWeight: FontWeight.w500,
                        ),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

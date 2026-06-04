import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../core/theme/app_colors.dart';

class ListenerCountBadge extends StatelessWidget {
  const ListenerCountBadge({
    super.key,
    required this.count,
    this.compact = false,
  });

  final String count;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final display = count.trim().isEmpty ? '--' : count;
    return Container(
      padding: EdgeInsets.symmetric(horizontal: compact ? 8 : 10, vertical: compact ? 4 : 6),
      decoration: BoxDecoration(
        color: AppColors.bgElevated.withValues(alpha: 0.75),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppColors.lineStrong.withValues(alpha: 0.45)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.headphones_rounded, size: compact ? 14 : 16, color: AppColors.accentHot),
          const SizedBox(width: 6),
          Text(
            display,
            style: GoogleFonts.ibmPlexMono(
              fontSize: compact ? 10 : 11,
              fontWeight: FontWeight.w800,
              letterSpacing: 0.5,
            ),
          ),
          if (!compact) ...[
            const SizedBox(width: 4),
            Text(
              'ouvintes',
              style: TextStyle(fontSize: 10, color: AppColors.muted.withValues(alpha: 0.9)),
            ),
          ],
        ],
      ),
    );
  }
}

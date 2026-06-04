import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../core/theme/app_colors.dart';
import '../models/system_banner_severity.dart';

class SystemStatusBanner extends StatelessWidget {
  const SystemStatusBanner({
    super.key,
    required this.message,
    required this.severity,
  });

  final String message;
  final SystemBannerSeverity severity;

  @override
  Widget build(BuildContext context) {
    if (severity == SystemBannerSeverity.none || message.trim().isEmpty) {
      return const SizedBox.shrink();
    }

    final (Color bg, Color border, IconData icon) = switch (severity) {
      SystemBannerSeverity.warning => (const Color(0xFF3D2E10), AppColors.accentHot, Icons.warning_amber_rounded),
      SystemBannerSeverity.info => (AppColors.bgElevated, AppColors.lineStrong, Icons.info_outline_rounded),
      _ => (const Color(0xFF3A1218), AppColors.accentHot, Icons.error_outline_rounded),
    };

    return Material(
      color: Colors.transparent,
      child: Container(
        width: double.infinity,
        margin: const EdgeInsets.fromLTRB(12, 8, 12, 0),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        decoration: BoxDecoration(
          color: bg,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: border.withValues(alpha: 0.65)),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, size: 22, color: AppColors.accentHot),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                message,
                style: GoogleFonts.ibmPlexSans(
                  fontSize: 13,
                  height: 1.35,
                  fontWeight: FontWeight.w600,
                  color: Colors.white.withValues(alpha: 0.95),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../core/theme/app_colors.dart';

String? resolveTrackCoverUrl(Map<String, dynamic> track) {
  for (final key in ['cover_url', 'art', 'album_art', 'cover']) {
    final value = track[key]?.toString().trim() ?? '';
    if (value.isNotEmpty) return value;
  }
  return null;
}

class TrackCoverThumb extends StatelessWidget {
  const TrackCoverThumb({super.key, required this.url, this.size = 52});

  final String? url;
  final double size;

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(6),
      child: SizedBox(
        width: size,
        height: size,
        child: url != null && url!.isNotEmpty
            ? Image.network(
                url!,
                fit: BoxFit.cover,
                errorBuilder: (_, __, ___) => const _CoverFallback(),
                loadingBuilder: (context, child, progress) {
                  if (progress == null) return child;
                  return const ColoredBox(
                    color: Colors.black26,
                    child: Center(child: SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))),
                  );
                },
              )
            : const _CoverFallback(),
      ),
    );
  }
}

class _CoverFallback extends StatelessWidget {
  const _CoverFallback();

  @override
  Widget build(BuildContext context) {
    return ColoredBox(
      color: Colors.black,
      child: Center(
        child: Text('RG', style: GoogleFonts.bebasNeue(fontSize: 22, color: AppColors.accent)),
      ),
    );
  }
}

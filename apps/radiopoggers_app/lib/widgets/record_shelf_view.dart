import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../core/theme/app_colors.dart';
import '../core/theme/app_decorations.dart';
import '../services/app_controller.dart';
import 'track_cover_thumb.dart';

/// Catálogo em grade — capas grandes, prévia e pedido na rádio.
class RecordShelfView extends StatelessWidget {
  const RecordShelfView({
    super.key,
    required this.controller,
    required this.searchField,
  });

  final AppController controller;
  final Widget searchField;

  @override
  Widget build(BuildContext context) {
    final c = controller;
    final width = MediaQuery.sizeOf(context).width;
    final crossCount = width >= 900 ? 4 : (width >= 600 ? 3 : 2);

    if (c.libraryLoading) {
      return const Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            CircularProgressIndicator(color: AppColors.accent),
            SizedBox(height: 16),
            Text('Carregando discos...', style: TextStyle(color: AppColors.muted)),
          ],
        ),
      );
    }

    if (c.libraryTracks.isEmpty) {
      return CustomScrollView(
        slivers: [
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(12, 4, 12, 16),
              child: searchField,
            ),
          ),
          SliverFillRemaining(
            hasScrollBody: false,
            child: Center(
              child: Padding(
                padding: const EdgeInsets.all(32),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.album_outlined, size: 64, color: AppColors.muted.withValues(alpha: 0.4)),
                    const SizedBox(height: 16),
                    Text('Nenhum disco encontrado', style: GoogleFonts.bebasNeue(fontSize: 24, color: AppColors.muted)),
                    const SizedBox(height: 8),
                    Text(
                      c.librarySummary,
                      textAlign: TextAlign.center,
                      style: const TextStyle(color: AppColors.muted, fontSize: 13),
                    ),
                    const SizedBox(height: 16),
                    OutlinedButton.icon(
                      onPressed: c.apiOnline ? () => c.loadLibrary(refresh: true) : null,
                      icon: const Icon(Icons.refresh),
                      label: const Text('ATUALIZAR ESTANTE'),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      );
    }

    return CustomScrollView(
      slivers: [
        SliverToBoxAdapter(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(12, 4, 12, 12),
            child: searchField,
          ),
        ),
        SliverPadding(
          padding: const EdgeInsets.fromLTRB(12, 0, 12, 28),
          sliver: SliverGrid(
            gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: crossCount,
              mainAxisSpacing: 14,
              crossAxisSpacing: 12,
              childAspectRatio: 0.62,
            ),
            delegate: SliverChildBuilderDelegate(
              (context, index) => _RecordCard(track: c.libraryTracks[index], controller: c),
              childCount: c.libraryTracks.length,
            ),
          ),
        ),
      ],
    );
  }
}

class _RecordCard extends StatelessWidget {
  const _RecordCard({required this.track, required this.controller});

  final Map<String, dynamic> track;
  final AppController controller;

  @override
  Widget build(BuildContext context) {
    final c = controller;
    final previewId = c.resolveLibraryPreviewId(track);
    final title = track['title']?.toString() ?? 'Faixa';
    final artists = (track['artists'] as List<dynamic>?)?.join(', ') ?? track['artist']?.toString() ?? '';
    final previewing = previewId.isNotEmpty && c.shelfPreviewTrackId == previewId;

    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: previewId.isEmpty ? null : () => c.playShelfPreview(track),
        borderRadius: BorderRadius.circular(10),
        child: Ink(
          decoration: AppDecorations.recordSleeve(active: previewing),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Expanded(
                child: ClipRRect(
                  borderRadius: const BorderRadius.vertical(top: Radius.circular(5)),
                  child: Stack(
                    fit: StackFit.expand,
                    children: [
                      TrackCoverThumb(url: resolveTrackCoverUrl(track)),
                      if (previewing)
                        Container(
                          color: Colors.black54,
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              const Icon(Icons.equalizer, color: AppColors.accentHot, size: 36),
                              const SizedBox(height: 4),
                              Text(
                                'PRÉVIA',
                                style: GoogleFonts.ibmPlexMono(
                                  fontSize: 9,
                                  letterSpacing: 2,
                                  fontWeight: FontWeight.w800,
                                  color: AppColors.accentHot,
                                ),
                              ),
                            ],
                          ),
                        ),
                    ],
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(8, 8, 8, 6),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: GoogleFonts.ibmPlexMono(
                        fontSize: 10,
                        fontWeight: FontWeight.w800,
                        height: 1.1,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      artists,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontSize: 9, color: AppColors.muted),
                    ),
                  ],
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(4, 0, 4, 6),
                child: Row(
                  children: [
                    Expanded(
                      child: _CardAction(
                        icon: previewing ? Icons.stop_rounded : Icons.headphones_rounded,
                        label: previewing ? 'Parar' : 'Ouvir',
                        hot: previewing,
                        onPressed: previewId.isEmpty ? null : () => c.playShelfPreview(track),
                      ),
                    ),
                    Expanded(
                      child: _CardAction(
                        icon: Icons.radio_rounded,
                        label: 'Pedir',
                        onPressed: previewId.isEmpty ? null : () => c.requestTrack(track),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _CardAction extends StatelessWidget {
  const _CardAction({
    required this.icon,
    required this.label,
    this.hot = false,
    this.onPressed,
  });

  final IconData icon;
  final String label;
  final bool hot;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    return TextButton.icon(
      style: TextButton.styleFrom(
        padding: const EdgeInsets.symmetric(vertical: 4),
        minimumSize: Size.zero,
        tapTargetSize: MaterialTapTargetSize.shrinkWrap,
        foregroundColor: hot ? AppColors.accentHot : AppColors.text,
      ),
      onPressed: onPressed,
      icon: Icon(icon, size: 15),
      label: Text(label, style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w700)),
    );
  }
}

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../../core/theme/app_colors.dart';
import '../../core/theme/app_decorations.dart';
import '../../services/app_controller.dart';
import '../../widgets/record_shelf_view.dart';
import '../../widgets/screen_glow_header.dart' show ScreenCleanHeaderBar, kHeaderPulseBleed;

class LibraryScreen extends StatefulWidget {
  const LibraryScreen({super.key, required this.controller});
  final AppController controller;

  @override
  State<LibraryScreen> createState() => _LibraryScreenState();
}

class _LibraryScreenState extends State<LibraryScreen> {
  final _search = TextEditingController();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final c = widget.controller;
      if (c.apiOnline && !c.libraryLoading && c.libraryTracks.isEmpty) {
        c.loadLibrary();
      }
    });
  }

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final c = widget.controller;
    final wide = MediaQuery.sizeOf(context).width >= 720;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        ScreenCleanHeaderBar(
          meter: c.audioMeter,
          title: 'ESTANTE DE DISCOS',
          pulseActive: c.audioReactiveLive,
          pulseIntensity: c.headerPulseIntensity,
        ),
        if (c.shelfPreviewTrackId != null) _PreviewNowPlayingBar(controller: c),
        Padding(
          padding: EdgeInsets.fromLTRB(wide ? 20 : 14, 8 + kHeaderPulseBleed * 0.45, wide ? 20 : 14, 4),
          child: Row(
            children: [
              Icon(Icons.library_music_outlined, size: 16, color: AppColors.muted.withValues(alpha: 0.8)),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  c.librarySummary,
                  style: GoogleFonts.ibmPlexMono(fontSize: 11, color: AppColors.muted, height: 1.3),
                ),
              ),
            ],
          ),
        ),
        Expanded(
          child: RecordShelfView(
            controller: c,
            searchField: _DigCrateSearch(controller: c, searchController: _search, wide: wide),
          ),
        ),
      ],
    );
  }
}

class _PreviewNowPlayingBar extends StatelessWidget {
  const _PreviewNowPlayingBar({required this.controller});
  final AppController controller;

  @override
  Widget build(BuildContext context) {
    final c = controller;
    return Container(
      margin: const EdgeInsets.fromLTRB(12, 8, 12, 0),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [AppColors.accent.withValues(alpha: 0.35), AppColors.accentDim],
        ),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.accentHot.withValues(alpha: 0.5)),
      ),
      child: ListTile(
        leading: Container(
          padding: const EdgeInsets.all(8),
          decoration: const BoxDecoration(shape: BoxShape.circle, color: Colors.black26),
          child: const Icon(Icons.headphones, color: Colors.white),
        ),
        title: Text(
          c.shelfPreviewTitle ?? 'Prévia',
          style: const TextStyle(fontWeight: FontWeight.w800),
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
        subtitle: const Text('Ouvindo prévia local — rádio pausada'),
        trailing: FilledButton(
          style: FilledButton.styleFrom(
            backgroundColor: Colors.black87,
            foregroundColor: AppColors.accentHot,
            padding: const EdgeInsets.symmetric(horizontal: 16),
          ),
          onPressed: c.stopShelfPreview,
          child: const Text('PARAR'),
        ),
      ),
    );
  }
}

class _DigCrateSearch extends StatelessWidget {
  const _DigCrateSearch({
    required this.controller,
    required this.searchController,
    required this.wide,
  });

  final AppController controller;
  final TextEditingController searchController;
  final bool wide;

  void _runSearch(AppController c) {
    c.libraryQuery = searchController.text.trim();
    c.loadLibrary();
  }

  @override
  Widget build(BuildContext context) {
    final c = controller;

    final searchBox = TextField(
      controller: searchController,
      style: const TextStyle(fontWeight: FontWeight.w600),
      decoration: InputDecoration(
        hintText: 'Procurar disco, artista, álbum...',
        hintStyle: TextStyle(color: AppColors.muted.withValues(alpha: 0.7)),
        prefixIcon: const Icon(Icons.search_rounded, color: AppColors.accentHot),
        filled: true,
        fillColor: AppColors.bgElevated,
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: BorderSide.none),
        suffixIcon: IconButton(
          icon: const Icon(Icons.arrow_forward_rounded, color: AppColors.accent),
          onPressed: () => _runSearch(c),
        ),
      ),
      onSubmitted: (_) => _runSearch(c),
    );

    final artistFilter = _FilterDropdown(
      label: 'Artista',
      value: c.libraryArtist.isEmpty ? null : c.libraryArtist,
      options: c.libraryArtists,
      onChanged: (v) {
        c.libraryArtist = v ?? '';
        c.loadLibrary();
      },
    );

    final albumFilter = _FilterDropdown(
      label: 'Álbum',
      value: c.libraryAlbum.isEmpty ? null : c.libraryAlbum,
      options: c.libraryAlbums,
      onChanged: (v) {
        c.libraryAlbum = v ?? '';
        c.loadLibrary();
      },
    );

    return Container(
      decoration: AppDecorations.glassPanel(radius: BorderRadius.circular(12)),
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            'CAIXA DE BUSCA',
            style: GoogleFonts.ibmPlexMono(fontSize: 9, letterSpacing: 2.5, color: AppColors.muted, fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 10),
          if (wide)
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(flex: 3, child: searchBox),
                const SizedBox(width: 12),
                Expanded(child: artistFilter),
                const SizedBox(width: 12),
                Expanded(child: albumFilter),
              ],
            )
          else ...[
            searchBox,
            const SizedBox(height: 10),
            artistFilter,
            const SizedBox(height: 10),
            albumFilter,
          ],
        ],
      ),
    );
  }
}

class _FilterDropdown extends StatelessWidget {
  const _FilterDropdown({
    required this.label,
    required this.value,
    required this.options,
    required this.onChanged,
  });

  final String label;
  final String? value;
  final List<String> options;
  final ValueChanged<String?> onChanged;

  @override
  Widget build(BuildContext context) {
    return DropdownButtonFormField<String>(
      isExpanded: true,
      value: value,
      decoration: InputDecoration(
        labelText: label,
        labelStyle: GoogleFonts.ibmPlexMono(fontSize: 10, letterSpacing: 1, color: AppColors.muted),
        filled: true,
        fillColor: AppColors.bg,
      ),
      menuMaxHeight: 320,
      items: [
        const DropdownMenuItem<String>(
          value: null,
          child: Text('Todos', maxLines: 1, overflow: TextOverflow.ellipsis),
        ),
        ...options.map(
          (name) => DropdownMenuItem<String>(
            value: name,
            child: Text(name, maxLines: 1, overflow: TextOverflow.ellipsis),
          ),
        ),
      ],
      onChanged: onChanged,
    );
  }
}

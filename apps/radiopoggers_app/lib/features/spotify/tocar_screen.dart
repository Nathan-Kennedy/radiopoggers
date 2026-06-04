import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../../core/theme/app_colors.dart';
import '../../core/theme/app_decorations.dart';
import '../../services/app_controller.dart';
import '../../widgets/screen_glow_header.dart' show ScreenCleanHeaderBar, kHeaderPulseBleed;
import '../../widgets/track_cover_thumb.dart';

/// Importar playlist/link e colocar faixas na fila da rádio.
class TocarScreen extends StatefulWidget {
  const TocarScreen({super.key, required this.controller});
  final AppController controller;

  @override
  State<TocarScreen> createState() => _TocarScreenState();
}

class _TocarScreenState extends State<TocarScreen> {
  late final TextEditingController _urlCtrl;

  @override
  void initState() {
    super.initState();
    _urlCtrl = TextEditingController(text: widget.controller.importUrl);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      widget.controller.loadSpotifyData();
    });
  }

  @override
  void dispose() {
    _urlCtrl.dispose();
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
          title: 'TOCAR',
          pulseActive: c.audioReactiveLive,
          pulseIntensity: c.headerPulseIntensity,
          actions: [
            IconButton(
              tooltip: 'Atualizar fila',
              onPressed: c.apiOnline ? () => c.refreshRadioQueue() : null,
              icon: const Icon(Icons.refresh_rounded),
            ),
            const SizedBox(width: 4),
          ],
        ),
        Expanded(
          child: CustomScrollView(
            slivers: [
              SliverPadding(
                padding: EdgeInsets.fromLTRB(wide ? 24 : 14, 8 + kHeaderPulseBleed * 0.45, wide ? 24 : 14, 100),
                sliver: SliverList(
                  delegate: SliverChildListDelegate([
                    _ImportPanel(controller: c, urlCtrl: _urlCtrl),
                    const SizedBox(height: 24),
                    _SectionTitle('FILA DA RÁDIO', subtitle: c.radioQueueSource.isEmpty
                        ? 'Próximas faixas na estação'
                        : 'Fonte: ${c.radioQueueSource}'),
                    const SizedBox(height: 10),
                    if (c.radioQueueItems.isEmpty)
                      _EmptyHint(
                        icon: Icons.queue_music_outlined,
                        text: 'Nenhuma faixa na fila. Cole um link e toque em Tocar.',
                      )
                    else
                      ...c.radioQueueItems.map((item) => _QueueTile(item: item)),
                    const SizedBox(height: 28),
                    _SectionTitle('MANIFESTO', subtitle: c.spotifyPlaylistSummary),
                    const SizedBox(height: 6),
                    Text(c.spotifyPlaylistTitle, style: GoogleFonts.bebasNeue(fontSize: 26)),
                    const SizedBox(height: 12),
                    if (c.spotifyManifestItems.isEmpty)
                      const _EmptyHint(
                        icon: Icons.link,
                        text: 'Manifesto vazio. Cole um link do Spotify e toque em Tocar.',
                      )
                    else
                      ...c.spotifyManifestItems.take(48).map((item) => _ManifestTile(item: item)),
                  ]),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _ImportPanel extends StatelessWidget {
  const _ImportPanel({required this.controller, required this.urlCtrl});
  final AppController controller;
  final TextEditingController urlCtrl;

  @override
  Widget build(BuildContext context) {
    final c = controller;
    final busy = c.spotifyImportBusy;
    final canPlay = c.apiOnline && !busy;

    return Container(
      decoration: AppDecorations.broadcastHero(),
      padding: const EdgeInsets.all(18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            'Playlist ou faixa do Spotify · cole o link',
            style: TextStyle(fontSize: 12, color: AppColors.muted.withValues(alpha: 0.95)),
          ),
          const SizedBox(height: 14),
          Text(
            'COLE O LINK',
            style: GoogleFonts.ibmPlexMono(fontSize: 9, letterSpacing: 2.5, color: AppColors.muted, fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 10),
          TextField(
            controller: urlCtrl,
            keyboardType: TextInputType.url,
            style: const TextStyle(fontWeight: FontWeight.w600),
            decoration: InputDecoration(
              hintText: 'https://open.spotify.com/playlist/...',
              filled: true,
              fillColor: AppColors.bg,
              prefixIcon: const Icon(Icons.link_rounded, color: AppColors.accentHot),
              border: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: BorderSide.none),
            ),
            onChanged: (v) => c.importUrl = v,
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(
                flex: 2,
                child: FilledButton.icon(
                  onPressed: canPlay ? c.importSpotify : null,
                  icon: busy
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                        )
                      : const Icon(Icons.play_arrow_rounded),
                  label: Text(busy ? 'IMPORTANDO…' : 'TOCAR NA RÁDIO'),
                  style: FilledButton.styleFrom(
                    padding: const EdgeInsets.symmetric(vertical: 16),
                    backgroundColor: AppColors.accent,
                  ),
                ),
              ),
              const SizedBox(width: 10),
              IconButton.filledTonal(
                onPressed: c.apiOnline ? () => c.refreshRadioQueue() : null,
                icon: const Icon(Icons.refresh_rounded),
                tooltip: 'Atualizar fila',
              ),
            ],
          ),
          if (c.spotifyStatus.isNotEmpty) ...[
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: AppColors.bg.withValues(alpha: 0.6),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: AppColors.lineStrong.withValues(alpha: 0.35)),
              ),
              child: Text(c.spotifyStatus, style: const TextStyle(fontSize: 12, color: AppColors.muted, height: 1.35)),
            ),
          ],
        ],
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle(this.title, {required this.subtitle});
  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: GoogleFonts.ibmPlexMono(fontSize: 10, letterSpacing: 2.5, color: AppColors.muted, fontWeight: FontWeight.w800)),
        const SizedBox(height: 4),
        Text(subtitle, style: const TextStyle(fontSize: 12, color: AppColors.muted)),
      ],
    );
  }
}

class _EmptyHint extends StatelessWidget {
  const _EmptyHint({required this.icon, required this.text});
  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: AppDecorations.glassPanel(radius: BorderRadius.circular(10)),
      child: Row(
        children: [
          Icon(icon, color: AppColors.muted.withValues(alpha: 0.5), size: 32),
          const SizedBox(width: 14),
          Expanded(child: Text(text, style: const TextStyle(color: AppColors.muted, fontSize: 13))),
        ],
      ),
    );
  }
}

class _QueueTile extends StatelessWidget {
  const _QueueTile({required this.item});
  final Map<String, dynamic> item;

  @override
  Widget build(BuildContext context) {
    final state = item['state']?.toString() ?? 'queued';
    final rank = item['rank']?.toString() ?? '';
    final title = item['title']?.toString() ?? '—';
    final artist = item['artist']?.toString() ?? '';
    final art = item['art']?.toString();

    Color accent = AppColors.muted;
    String badge = 'NA FILA';
    if (state == 'playing') {
      accent = AppColors.accentHot;
      badge = 'AGORA';
    } else if (state == 'upcoming') {
      accent = AppColors.good;
      badge = 'PRÓXIMA';
    } else if (state == 'played') {
      badge = 'JÁ TOCOU';
    }

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      decoration: AppDecorations.glassPanel(radius: BorderRadius.circular(10)),
      child: ListTile(
        contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
        leading: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            SizedBox(width: 24, child: Text(rank, style: const TextStyle(fontFamily: 'monospace', color: AppColors.muted, fontSize: 11))),
            TrackCoverThumb(url: art, size: 48),
          ],
        ),
        title: Text(title, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w700)),
        subtitle: Text(artist, maxLines: 1, overflow: TextOverflow.ellipsis),
        trailing: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          decoration: BoxDecoration(
            color: accent.withValues(alpha: 0.12),
            border: Border.all(color: accent.withValues(alpha: 0.5)),
            borderRadius: BorderRadius.circular(6),
          ),
          child: Text(badge, style: TextStyle(fontSize: 9, color: accent, fontWeight: FontWeight.w800, letterSpacing: 0.5)),
        ),
      ),
    );
  }
}

class _ManifestTile extends StatelessWidget {
  const _ManifestTile({required this.item});
  final Map<String, dynamic> item;

  @override
  Widget build(BuildContext context) {
    final rank = item['playlist_position']?.toString() ?? item['track_number']?.toString() ?? '';
    final title = item['title']?.toString() ?? '—';
    final artists = item['artists'] as List<dynamic>? ?? [];
    final artist = artists.map((a) => a.toString()).where((a) => a.isNotEmpty).join(', ');
    final ready = item['status']?.toString() == 'ready';
    final art = item['cover_url']?.toString() ?? item['art']?.toString();

    return Container(
      margin: const EdgeInsets.only(bottom: 6),
      child: ListTile(
        dense: true,
        contentPadding: const EdgeInsets.symmetric(horizontal: 8),
        leading: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            SizedBox(width: 22, child: Text(rank, style: const TextStyle(fontFamily: 'monospace', color: AppColors.muted, fontSize: 10))),
            TrackCoverThumb(url: art, size: 40),
          ],
        ),
        title: Text(title, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 13)),
        subtitle: Text(
          '$artist · ${ready ? 'Pronta' : 'Pendente'}',
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: TextStyle(color: ready ? AppColors.good : AppColors.warn, fontSize: 11),
        ),
      ),
    );
  }
}

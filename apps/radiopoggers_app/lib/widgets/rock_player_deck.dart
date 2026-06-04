import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../core/theme/app_colors.dart';
import '../core/theme/app_decorations.dart';
import '../services/app_controller.dart';
import 'listener_count_badge.dart';
import 'ncs_visualizer.dart';
import 'spinning_vinyl.dart';

/// Console de transmissão — vinil hero, VU e controles de play/volume/voto.
class RockPlayerDeck extends StatelessWidget {
  const RockPlayerDeck({super.key, required this.controller});

  final AppController controller;

  String _formatTime(int sec) {
    final m = sec ~/ 60;
    final s = sec % 60;
    return '$m:${s.toString().padLeft(2, '0')}';
  }

  @override
  Widget build(BuildContext context) {
    final c = controller;
    final progress = c.durationSec > 0 ? (c.elapsedSec / c.durationSec).clamp(0.0, 1.0) : 0.0;
    final live = c.streamPlaying && c.connectionBadgeOnline;
    final wide = MediaQuery.sizeOf(context).width >= 520;

    return Container(
      decoration: AppDecorations.broadcastHero(),
      padding: EdgeInsets.fromLTRB(wide ? 28 : 16, wide ? 28 : 20, wide ? 28 : 16, 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              if (live)
                Container(
                  margin: const EdgeInsets.only(bottom: 12, right: 8),
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                  decoration: BoxDecoration(
                    color: AppColors.accent.withValues(alpha: 0.2),
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(color: AppColors.accentHot.withValues(alpha: 0.6)),
                  ),
                  child: Text(
                    '● ON AIR',
                    style: GoogleFonts.ibmPlexMono(fontSize: 10, fontWeight: FontWeight.w800, letterSpacing: 2),
                  ),
                ),
              Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: ListenerCountBadge(count: c.listenerCountLabel),
              ),
            ],
          ),
          Center(
            child: SpinningVinyl(
              spinning: live,
              coverUrl: c.coverUrl,
              size: wide ? 220 : 180,
            ),
          ),
          const SizedBox(height: 20),
          Text(
            'AGORA NO AR',
            textAlign: TextAlign.center,
            style: GoogleFonts.ibmPlexMono(
              fontSize: 10,
              letterSpacing: 3,
              color: AppColors.muted,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            c.trackTitle,
            textAlign: TextAlign.center,
            style: GoogleFonts.bebasNeue(fontSize: wide ? 42 : 34, height: 0.9, color: AppColors.text),
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
          ),
          Text(
            c.trackArtist,
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w600,
              color: AppColors.muted.withValues(alpha: 0.95),
            ),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
          const SizedBox(height: 16),
          NcsVisualizer(
            active: live,
            meter: c.audioMeter,
            height: wide ? 48 : 40,
            barCount: wide ? 28 : 22,
          ),
          const SizedBox(height: 14),
          _ProgressRail(progress: progress, elapsed: _formatTime(c.elapsedSec), total: _formatTime(c.durationSec)),
          const SizedBox(height: 22),
          _ControlConsole(
            streamPlaying: c.streamPlaying,
            radioPlayAllowed: c.radioPlayAllowed,
            volume: c.volume,
            onPlay: () => c.togglePlay(),
            onSkip: c.radioPlayAllowed ? c.startSkipVote : null,
            onVolume: c.setVolumeLevel,
          ),
        ],
      ),
    );
  }
}

class _ProgressRail extends StatelessWidget {
  const _ProgressRail({required this.progress, required this.elapsed, required this.total});

  final double progress;
  final String elapsed;
  final String total;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(elapsed, style: _mono),
            Text(total, style: _mono.copyWith(color: AppColors.muted)),
          ],
        ),
        const SizedBox(height: 8),
        LayoutBuilder(
          builder: (context, constraints) {
            final w = constraints.maxWidth * (progress > 0 ? progress : 0.02);
            return Stack(
              children: [
                Container(
                  height: 6,
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.08),
                    borderRadius: BorderRadius.circular(3),
                  ),
                ),
                AnimatedContainer(
                  duration: const Duration(milliseconds: 400),
                  width: w,
                  height: 6,
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(3),
                    gradient: AppDecorations.accentGradient,
                    boxShadow: [
                      BoxShadow(color: AppColors.accent.withValues(alpha: 0.5), blurRadius: 8),
                    ],
                  ),
                ),
              ],
            );
          },
        ),
      ],
    );
  }

  static final _mono = GoogleFonts.ibmPlexMono(fontSize: 11, fontWeight: FontWeight.w600);
}

class _ControlConsole extends StatelessWidget {
  const _ControlConsole({
    required this.streamPlaying,
    required this.radioPlayAllowed,
    required this.volume,
    required this.onPlay,
    required this.onSkip,
    required this.onVolume,
  });

  final bool streamPlaying;
  final bool radioPlayAllowed;
  final double volume;
  final VoidCallback onPlay;
  final VoidCallback? onSkip;
  final ValueChanged<double> onVolume;

  @override
  Widget build(BuildContext context) {
    final playEnabled = streamPlaying || radioPlayAllowed;

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: AppDecorations.glassPanel(radius: BorderRadius.circular(12)),
      child: Row(
        children: [
          _PlayOrb(
            playing: streamPlaying,
            enabled: playEnabled,
            onTap: playEnabled ? onPlay : null,
          ),
          const SizedBox(width: 12),
          _ConsoleIconButton(
            icon: Icons.skip_next_rounded,
            label: 'VOTO',
            onPressed: onSkip,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('VOLUME', style: GoogleFonts.ibmPlexMono(fontSize: 8, letterSpacing: 2, color: AppColors.muted)),
                SliderTheme(
                  data: SliderTheme.of(context).copyWith(
                    trackHeight: 4,
                    thumbShape: const RoundSliderThumbShape(enabledThumbRadius: 7),
                    overlayShape: SliderComponentShape.noOverlay,
                    activeTrackColor: AppColors.accent,
                    inactiveTrackColor: Colors.white12,
                    thumbColor: AppColors.accentHot,
                  ),
                  child: Slider(value: volume, max: 100, onChanged: onVolume),
                ),
              ],
            ),
          ),
          Icon(Icons.volume_up_rounded, size: 22, color: AppColors.muted.withValues(alpha: 0.85)),
        ],
      ),
    );
  }
}

class _PlayOrb extends StatelessWidget {
  const _PlayOrb({required this.playing, required this.enabled, required this.onTap});

  final bool playing;
  final bool enabled;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        customBorder: const CircleBorder(),
        child: Container(
          width: 64,
          height: 64,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            gradient: enabled ? AppDecorations.accentGradient : null,
            color: enabled ? null : AppColors.bgElevated.withValues(alpha: 0.8),
            border: Border.all(
              color: enabled ? AppColors.accentHot : AppColors.lineStrong,
              width: 2,
            ),
            boxShadow: enabled
                ? [BoxShadow(color: AppColors.accent.withValues(alpha: 0.45), blurRadius: 16, spreadRadius: -2)]
                : null,
          ),
          child: Icon(
            playing ? Icons.pause_rounded : Icons.play_arrow_rounded,
            size: 36,
            color: Colors.white,
          ),
        ),
      ),
    );
  }
}

class _ConsoleIconButton extends StatelessWidget {
  const _ConsoleIconButton({required this.icon, required this.label, this.onPressed});

  final IconData icon;
  final String label;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    final enabled = onPressed != null;
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        IconButton.filled(
          style: IconButton.styleFrom(
            backgroundColor: enabled ? AppColors.bgElevated : AppColors.bgElevated.withValues(alpha: 0.5),
            foregroundColor: enabled ? AppColors.text : AppColors.muted,
            side: BorderSide(color: AppColors.lineStrong.withValues(alpha: enabled ? 0.8 : 0.3)),
          ),
          onPressed: onPressed,
          icon: Icon(icon),
        ),
        const SizedBox(height: 2),
        Text(label, style: GoogleFonts.ibmPlexMono(fontSize: 8, letterSpacing: 1, color: AppColors.muted)),
      ],
    );
  }
}

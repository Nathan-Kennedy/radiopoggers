import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../../ascii/ascii_animator.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_decorations.dart';
import '../../services/app_controller.dart';
import '../../widgets/ascii_stage.dart';
import '../../widgets/dj_mixer_sheet.dart';
import '../../widgets/listener_count_badge.dart';
import '../../widgets/live_pulse_badge.dart';
import '../../widgets/rock_player_deck.dart';
import '../../widgets/screen_glow_header.dart' show ScreenCleanHeaderBar, kHeaderPulseBleed;
import '../narrator/narrator_picker_sheet.dart';

class OnAirScreen extends StatelessWidget {
  const OnAirScreen({super.key, required this.controller});
  final AppController controller;

  @override
  Widget build(BuildContext context) {
    final c = controller;
    final animator = c.ascii.forStage(c.asciiStageMode);
    final wide = MediaQuery.sizeOf(context).width >= 900;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        ScreenCleanHeaderBar(
          meter: c.audioMeter,
          title: c.settings.stationDisplayName,
          pulseActive: c.audioReactiveLive,
          pulseIntensity: c.headerPulseIntensity,
          actions: [
            ListenerCountBadge(count: c.listenerCountLabel, compact: true),
            const SizedBox(width: 8),
            LivePulseBadge(label: c.connectionLabel, online: c.connectionBadgeOnline),
            const SizedBox(width: 12),
          ],
        ),
        Expanded(
          child: CustomScrollView(
            slivers: [
              SliverPadding(
                padding: EdgeInsets.fromLTRB(wide ? 24 : 12, 8 + kHeaderPulseBleed * 0.45, wide ? 24 : 12, 0),
                sliver: SliverToBoxAdapter(
                  child: wide ? _WideBroadcastLayout(c: c, animator: animator) : _NarrowBroadcastLayout(c: c, animator: animator),
                ),
              ),
              SliverPadding(
                padding: EdgeInsets.fromLTRB(wide ? 24 : 12, 16, wide ? 24 : 12, 100),
                sliver: SliverToBoxAdapter(child: _QuickActionsRow(controller: c)),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _WideBroadcastLayout extends StatelessWidget {
  const _WideBroadcastLayout({required this.c, required this.animator});

  final AppController c;
  final AsciiAnimator? animator;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(
          flex: 11,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _SectionLabel('MONITOR · PALCO ASCII'),
              const SizedBox(height: 8),
              _AsciiMonitor(animator: animator, c: c),
              const SizedBox(height: 16),
              DjMixerLaunchBar(controller: c),
            ],
          ),
        ),
        const SizedBox(width: 20),
        Expanded(flex: 13, child: RockPlayerDeck(controller: c)),
      ],
    );
  }
}

class _NarrowBroadcastLayout extends StatelessWidget {
  const _NarrowBroadcastLayout({required this.c, required this.animator});

  final AppController c;
  final AsciiAnimator? animator;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        RockPlayerDeck(controller: c),
        const SizedBox(height: 16),
        _SectionLabel('MONITOR · PALCO'),
        const SizedBox(height: 8),
        _AsciiMonitor(animator: animator, c: c),
        const SizedBox(height: 14),
        DjMixerLaunchBar(controller: c),
      ],
    );
  }
}

class _AsciiMonitor extends StatelessWidget {
  const _AsciiMonitor({required this.animator, required this.c});

  final AsciiAnimator? animator;
  final AppController c;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: const Color(0xFF0A0A0A),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.lineStrong.withValues(alpha: 0.5)),
        boxShadow: [
          BoxShadow(color: AppColors.accent.withValues(alpha: 0.08), blurRadius: 24, offset: const Offset(0, 8)),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              color: AppColors.bgElevated,
              borderRadius: const BorderRadius.vertical(top: Radius.circular(11)),
              border: Border(bottom: BorderSide(color: AppColors.lineStrong.withValues(alpha: 0.35))),
            ),
            child: Row(
              children: [
                _MonitorLed(active: c.connectionBadgeOnline),
                const SizedBox(width: 8),
                Text(
                  'CRT-01',
                  style: GoogleFonts.ibmPlexMono(fontSize: 9, letterSpacing: 2, color: AppColors.muted),
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(10),
            child: AsciiStage(
              animator: animator,
              caption: c.narratorCaption,
              badge: c.narratorBadge ?? 'MIKU · NO AR',
            ),
          ),
        ],
      ),
    );
  }
}

class _MonitorLed extends StatelessWidget {
  const _MonitorLed({required this.active});
  final bool active;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 8,
      height: 8,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: active ? AppColors.good : AppColors.danger,
        boxShadow: active ? [BoxShadow(color: AppColors.good.withValues(alpha: 0.6), blurRadius: 6)] : null,
      ),
    );
  }
}

class _SectionLabel extends StatelessWidget {
  const _SectionLabel(this.text);
  final String text;

  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      style: GoogleFonts.ibmPlexMono(fontSize: 9, letterSpacing: 2.5, color: AppColors.muted, fontWeight: FontWeight.w700),
    );
  }
}

class _QuickActionsRow extends StatelessWidget {
  const _QuickActionsRow({required this.controller});
  final AppController controller;

  @override
  Widget build(BuildContext context) {
    final c = controller;
    const narrator = 'MIKU';

    return Row(
      children: [
        Expanded(
          child: _ActionTile(
            icon: Icons.record_voice_over_rounded,
            title: 'NARRADORA',
            subtitle: narrator,
            accent: AppColors.chibiAccent,
            onTap: () => showNarratorPickerSheet(context, c),
          ),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: _StatusTile(
            subtitle: c.connectionLabel,
            online: c.connectionBadgeOnline,
          ),
        ),
      ],
    );
  }
}

class _StatusTile extends StatelessWidget {
  const _StatusTile({required this.subtitle, required this.online});

  final String subtitle;
  final bool online;

  @override
  Widget build(BuildContext context) {
    final accent = online ? AppColors.good : AppColors.warn;
    return Container(
      decoration: AppDecorations.glassPanel(radius: BorderRadius.circular(10)),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: accent.withValues(alpha: 0.15),
              border: Border.all(color: accent.withValues(alpha: 0.5)),
            ),
            child: Icon(Icons.sensors, color: accent, size: 22),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('STATUS', style: GoogleFonts.ibmPlexMono(fontSize: 9, letterSpacing: 2, color: AppColors.muted)),
                Text(subtitle, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w700)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _ActionTile extends StatelessWidget {
  const _ActionTile({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.accent,
    required this.onTap,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final Color accent;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(10),
        child: Ink(
          decoration: AppDecorations.glassPanel(radius: BorderRadius.circular(10)),
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: accent.withValues(alpha: 0.15),
                  border: Border.all(color: accent.withValues(alpha: 0.5)),
                ),
                child: Icon(icon, color: accent, size: 22),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title, style: GoogleFonts.ibmPlexMono(fontSize: 9, letterSpacing: 2, color: AppColors.muted)),
                    Text(subtitle, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w700)),
                  ],
                ),
              ),
              Icon(Icons.chevron_right, color: AppColors.muted.withValues(alpha: 0.6), size: 20),
            ],
          ),
        ),
      ),
    );
  }
}

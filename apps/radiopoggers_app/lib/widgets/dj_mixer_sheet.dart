import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../core/theme/app_colors.dart';
import '../core/theme/app_decorations.dart';
import '../services/app_controller.dart';
import 'ncs_visualizer.dart';
import 'voice_recorder_bar.dart';

Future<void> showDjMixerSheet(BuildContext context, AppController controller) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    useSafeArea: true,
    backgroundColor: Colors.transparent,
    builder: (ctx) => DraggableScrollableSheet(
      initialChildSize: 0.92,
      minChildSize: 0.55,
      maxChildSize: 0.98,
      expand: false,
      builder: (_, scroll) => _DjMixerBody(controller: controller, scrollController: scroll),
    ),
  );
}

class _DjMixerBody extends StatelessWidget {
  const _DjMixerBody({required this.controller, required this.scrollController});

  final AppController controller;
  final ScrollController scrollController;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.bgElevated,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(16)),
        border: Border.all(color: AppColors.lineStrong),
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [
            const Color(0xFF1A1012),
            AppColors.bg,
          ],
        ),
      ),
      child: Column(
        children: [
          const SizedBox(height: 8),
          Container(
            width: 40,
            height: 4,
            decoration: BoxDecoration(
              color: AppColors.lineStrong,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 8, 0),
            child: Row(
              children: [
                Text('MESA DE CHAMADA', style: GoogleFonts.bebasNeue(fontSize: 28, color: AppColors.accentHot)),
                const Spacer(),
                IconButton(onPressed: () => Navigator.pop(context), icon: const Icon(Icons.keyboard_arrow_down)),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Row(
              children: [
                Expanded(child: _FakeFader(label: 'MIC', value: 0.78)),
                const SizedBox(width: 8),
                Expanded(child: _FakeFader(label: 'FX', value: 0.45)),
                const SizedBox(width: 8),
                Expanded(child: _FakeFader(label: 'DROP', value: controller.voiceStinger.isActive ? 0.6 : 0.2)),
                const SizedBox(width: 12),
                NcsVisualizer(
                  active: controller.voiceRecording || controller.voicePreviewPlaying,
                  meter: controller.audioMeter,
                  height: 56,
                ),
              ],
            ),
          ),
          const SizedBox(height: 8),
          Expanded(
            child: SingleChildScrollView(
              controller: scrollController,
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
              child: Container(
                decoration: AppDecorations.brutalCard(),
                padding: const EdgeInsets.all(4),
                child: VoiceRecorderBar(controller: controller),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _FakeFader extends StatelessWidget {
  const _FakeFader({required this.label, required this.value});

  final String label;
  final double value;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(label, style: GoogleFonts.ibmPlexMono(fontSize: 9, letterSpacing: 1.5, color: AppColors.muted)),
        const SizedBox(height: 6),
        Container(
          height: 72,
          decoration: BoxDecoration(
            color: Colors.black,
            borderRadius: BorderRadius.circular(4),
            border: Border.all(color: AppColors.lineStrong),
          ),
          alignment: Alignment.bottomCenter,
          padding: const EdgeInsets.all(6),
          child: FractionallySizedBox(
            heightFactor: value.clamp(0.1, 1.0),
            widthFactor: 0.45,
            child: Container(
              decoration: BoxDecoration(
                gradient: AppDecorations.accentGradient,
                borderRadius: BorderRadius.circular(2),
                boxShadow: [BoxShadow(color: AppColors.accent.withValues(alpha: 0.4), blurRadius: 8)],
              ),
            ),
          ),
        ),
      ],
    );
  }
}

/// Barra compacta na tela Rádio para abrir a mesa.
class DjMixerLaunchBar extends StatelessWidget {
  const DjMixerLaunchBar({super.key, required this.controller});

  final AppController controller;

  @override
  Widget build(BuildContext context) {
    final c = controller;
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: () => showDjMixerSheet(context, c),
        borderRadius: BorderRadius.circular(12),
        child: Ink(
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(12),
            gradient: LinearGradient(
              colors: [AppColors.accent.withValues(alpha: 0.18), AppColors.panel],
            ),
            border: Border.all(color: AppColors.accent.withValues(alpha: 0.45)),
            boxShadow: [BoxShadow(color: AppColors.accent.withValues(alpha: 0.12), blurRadius: 16, offset: const Offset(0, 6))],
          ),
          padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 16),
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: AppDecorations.accentGradient,
                  boxShadow: [BoxShadow(color: AppColors.accent.withValues(alpha: 0.4), blurRadius: 12)],
                ),
                child: const Icon(Icons.mic_external_on_rounded, color: Colors.white, size: 26),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'MESA DE CHAMADA',
                      style: GoogleFonts.bebasNeue(fontSize: 22, color: AppColors.accentHot, height: 1),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      c.voicePreviewReady ? 'Prévia pronta — toque para abrir o mixer' : c.voiceStatus,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontSize: 12, color: AppColors.muted),
                    ),
                  ],
                ),
              ),
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  border: Border.all(color: AppColors.lineStrong),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Icon(Icons.open_in_full_rounded, color: AppColors.accentHot, size: 22),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

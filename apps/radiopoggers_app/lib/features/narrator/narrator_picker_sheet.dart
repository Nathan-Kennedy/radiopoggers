import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../../core/theme/app_colors.dart';
import '../../ascii/ascii_animator.dart';
import '../../services/app_controller.dart';
import '../../widgets/ascii_stage.dart';

Future<void> showNarratorPickerSheet(BuildContext context, AppController controller) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    backgroundColor: AppColors.bgElevated,
    builder: (ctx) => NarratorPickerSheet(controller: controller),
  );
}

class NarratorPickerSheet extends StatelessWidget {
  const NarratorPickerSheet({super.key, required this.controller});
  final AppController controller;

  @override
  Widget build(BuildContext context) {
    final selected = controller.settings.selectedNarrator == 'miku';
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.paddingOf(context).bottom + 16, left: 16, right: 16, top: 20),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text('NARRADORA', style: GoogleFonts.bebasNeue(fontSize: 28)),
          const SizedBox(height: 6),
          const Text(
            'Acompanha só no seu app — a rádio global continua com a Miku.',
            textAlign: TextAlign.center,
            style: TextStyle(color: AppColors.muted, fontSize: 13),
          ),
          const SizedBox(height: 20),
          _MikuCard(
            controller: controller,
            animator: controller.ascii.pickerMiku,
            selected: selected,
          ),
          const SizedBox(height: 16),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: AppColors.bg,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: AppColors.lineStrong.withValues(alpha: 0.4)),
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(Icons.hourglass_top_rounded, color: AppColors.warn.withValues(alpha: 0.9), size: 22),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'NOVOS NARRADORES EM BREVE',
                        style: GoogleFonts.ibmPlexMono(fontSize: 10, letterSpacing: 1.5, fontWeight: FontWeight.w800),
                      ),
                      const SizedBox(height: 6),
                      Text(
                        'Estamos criando novas vozes para acompanhar você no ar. Aguarde as próximas atualizações!',
                        style: TextStyle(fontSize: 12, color: AppColors.muted.withValues(alpha: 0.95), height: 1.35),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Fechar')),
        ],
      ),
    );
  }
}

class _MikuCard extends StatelessWidget {
  const _MikuCard({
    required this.controller,
    required this.animator,
    required this.selected,
  });

  final AppController controller;
  final AsciiAnimator? animator;
  final bool selected;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: () async {
          await controller.selectNarrator('miku');
          if (context.mounted) Navigator.pop(context);
        },
        borderRadius: BorderRadius.circular(12),
        child: Ink(
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(12),
            gradient: selected
                ? LinearGradient(
                    colors: [AppColors.chibiAccent.withValues(alpha: 0.2), AppColors.accentDim],
                  )
                : null,
            color: selected ? null : AppColors.bg,
            border: Border.all(color: selected ? AppColors.chibiAccent : AppColors.lineStrong, width: selected ? 2 : 1),
          ),
          padding: const EdgeInsets.all(16),
          child: Column(
            children: [
              Center(child: AsciiFrameStill(animator: animator)),
              const SizedBox(height: 12),
              Text('MIKU', style: GoogleFonts.bebasNeue(fontSize: 32, color: AppColors.chibiAccent)),
              if (selected)
                Padding(
                  padding: const EdgeInsets.only(top: 6),
                  child: Text(
                    'ATIVA NO SEU APP',
                    style: GoogleFonts.ibmPlexMono(fontSize: 9, letterSpacing: 2, color: AppColors.good),
                  ),
                ),
              const SizedBox(height: 12),
              OutlinedButton.icon(
                onPressed: () => controller.playNarratorSample('miku'),
                icon: const Icon(Icons.play_circle_outline, size: 18),
                label: const Text('Ouvir amostra'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

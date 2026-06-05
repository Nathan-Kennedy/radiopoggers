import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../../core/theme/app_colors.dart';
import '../../core/theme/app_decorations.dart';
import '../../core/theme/app_motion.dart';
import '../../services/app_controller.dart';

/// Modal “Tocar já / Na fila” quando só um ouvinte está no ar (igual ao site).
class VoteDirectModal extends StatefulWidget {
  const VoteDirectModal({super.key, required this.controller});
  final AppController controller;

  @override
  State<VoteDirectModal> createState() => _VoteDirectModalState();
}

class _VoteDirectModalState extends State<VoteDirectModal> with SingleTickerProviderStateMixin {
  late final AnimationController _enter;
  late final Animation<Offset> _slide;

  @override
  void initState() {
    super.initState();
    _enter = AnimationController(vsync: this, duration: AppMotion.modal);
    _slide = Tween<Offset>(begin: const Offset(0, 0.08), end: Offset.zero).animate(
      CurvedAnimation(parent: _enter, curve: AppMotion.slideCurve),
    );
    _enter.forward();
  }

  @override
  void dispose() {
    _enter.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final c = widget.controller;
    final type = c.votePendingDirectType ?? 'library_request';
    final payload = c.votePendingDirectPayload ?? const {};
    final copy = AppController.voteDirectCopyFor(type);
    final title = c.voteDirectModalTitle(type: type, payload: payload, fallbackTitle: copy.title);
    final yesLabel = copy.yes;
    final noLabel = copy.no;
    final busy = c.voteDirectBusy;

    return Material(
      color: Colors.black.withValues(alpha: 0.88),
      child: SlideTransition(
        position: _slide,
        child: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 400),
                child: Container(
                  decoration: AppDecorations.glassPanel(radius: BorderRadius.circular(14)),
                  padding: const EdgeInsets.fromLTRB(20, 20, 20, 16),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Text(
                        'SÓ VOCÊ NO AR',
                        style: GoogleFonts.ibmPlexMono(
                          fontSize: 9,
                          letterSpacing: 2.2,
                          fontWeight: FontWeight.w800,
                          color: AppColors.accentHot,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        title,
                        textAlign: TextAlign.center,
                        style: GoogleFonts.bebasNeue(fontSize: 28, height: 0.95),
                      ),
                      const SizedBox(height: 20),
                      Row(
                        children: [
                          Expanded(
                            child: FilledButton(
                              onPressed: busy ? null : () => c.executeDirectVote('yes'),
                              style: FilledButton.styleFrom(
                                padding: const EdgeInsets.symmetric(vertical: 16),
                                backgroundColor: AppColors.accent,
                              ),
                              child: Text(yesLabel, style: GoogleFonts.bebasNeue(fontSize: 20)),
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: OutlinedButton(
                              onPressed: busy ? null : () => c.executeDirectVote('no'),
                              style: OutlinedButton.styleFrom(
                                padding: const EdgeInsets.symmetric(vertical: 16),
                                side: const BorderSide(color: AppColors.lineStrong, width: 1.5),
                              ),
                              child: Text(noLabel, style: GoogleFonts.bebasNeue(fontSize: 20)),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      TextButton(
                        onPressed: busy ? null : c.hideVoteDirectModal,
                        child: const Text('Cancelar'),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

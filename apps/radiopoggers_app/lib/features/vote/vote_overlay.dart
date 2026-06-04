import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../../core/theme/app_colors.dart';
import '../../core/theme/app_decorations.dart';
import '../../core/theme/app_motion.dart';
import '../../services/app_controller.dart';
import '../../widgets/vote_lottery_wheel.dart';
import 'vote_ui.dart';

class VoteOverlay extends StatefulWidget {
  const VoteOverlay({super.key, required this.controller});
  final AppController controller;

  @override
  State<VoteOverlay> createState() => _VoteOverlayState();
}

class _VoteOverlayState extends State<VoteOverlay> with SingleTickerProviderStateMixin {
  late final AnimationController _enter;
  late final Animation<Offset> _slide;

  @override
  void initState() {
    super.initState();
    _enter = AnimationController(vsync: this, duration: AppMotion.modal);
    _slide = Tween<Offset>(begin: const Offset(0, 0.06), end: Offset.zero).animate(
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
    final vote = c.activeVote;
    if (vote == null) return const SizedBox.shrink();

    final phase = vote['phase']?.toString() ?? '';
    final isOpen = phase == 'open';
    final isLottery = phase == 'lottery';
    final canVote = isOpen && c.canParticipateInVote;
    final yesVotes = (vote['yes_votes'] as num?)?.toInt() ?? 0;
    final noVotes = (vote['no_votes'] as num?)?.toInt() ?? 0;
    final abstain = (vote['abstain'] as num?)?.toInt() ?? 0;
    final noTotal = noVotes + abstain;
    final total = (yesVotes + noTotal).clamp(1, 99999);
    final yesPct = yesVotes / total;
    final noPct = noTotal / total;
    final yesLabel = vote['yes_label']?.toString() ?? 'SIM';
    final noLabel = vote['no_label']?.toString() ?? 'NÃO';
    final lotteryRock = isLottery;

    return Material(
      color: Colors.black.withValues(alpha: lotteryRock ? 0.92 : 0.88),
      child: SlideTransition(
        position: _slide,
        child: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 440),
                child: Container(
                  decoration: AppDecorations.glassPanel(radius: BorderRadius.circular(14)).copyWith(
                    border: Border.all(
                      color: lotteryRock
                          ? AppColors.accentHot.withValues(alpha: 0.65)
                          : AppColors.lineStrong,
                      width: lotteryRock ? 2 : 1,
                    ),
                    boxShadow: lotteryRock
                        ? [
                            BoxShadow(
                              color: AppColors.accentHot.withValues(alpha: 0.25),
                              blurRadius: 32,
                              spreadRadius: 2,
                            ),
                          ]
                        : null,
                  ),
                  padding: const EdgeInsets.fromLTRB(20, 18, 20, 20),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Expanded(
                            child: Text(
                              VoteUi.eyebrow(vote),
                              style: GoogleFonts.ibmPlexMono(
                                fontSize: 9,
                                letterSpacing: 2.2,
                                fontWeight: FontWeight.w800,
                                color: AppColors.accentHot,
                              ),
                            ),
                          ),
                          if (isOpen)
                            IconButton(
                              visualDensity: VisualDensity.compact,
                              onPressed: c.closeVoteOverlay,
                              icon: const Icon(Icons.close, size: 22),
                            ),
                        ],
                      ),
                      Text(
                        vote['title']?.toString() ?? 'Votação ao vivo',
                        style: GoogleFonts.bebasNeue(fontSize: 30, height: 0.95),
                      ),
                      const SizedBox(height: 6),
                      Text(
                        VoteUi.meta(vote),
                        style: TextStyle(fontSize: 12, color: AppColors.muted.withValues(alpha: 0.95)),
                      ),
                      const SizedBox(height: 14),
                      Text(
                        VoteUi.formatTimer(vote['remaining_sec']),
                        textAlign: TextAlign.center,
                        style: GoogleFonts.bebasNeue(
                          fontSize: 42,
                          color: AppColors.accentHot,
                          letterSpacing: 2,
                        ),
                      ),
                      const SizedBox(height: 16),
                      if (!isLottery) ...[
                        _VoteBar(label: yesLabel, fill: yesPct, count: yesVotes, yes: true),
                        const SizedBox(height: 10),
                        _VoteBar(label: noLabel, fill: noPct, count: noTotal, yes: false),
                        const SizedBox(height: 18),
                      ],
                      if (isLottery)
                        VoteLotteryWheel(winner: vote['lottery_winner']?.toString())
                      else if (isOpen) ...[
                        if (!c.canParticipateInVote)
                          Padding(
                            padding: const EdgeInsets.only(bottom: 12),
                            child: Text(
                              'Toque play na rádio para participar da votação.',
                              textAlign: TextAlign.center,
                              style: TextStyle(fontSize: 12, color: AppColors.muted.withValues(alpha: 0.95)),
                            ),
                          ),
                        Row(
                          children: [
                            Expanded(
                              child: FilledButton(
                                onPressed: canVote ? () => c.castVote('yes') : null,
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
                                onPressed: canVote ? () => c.castVote('no') : null,
                                style: OutlinedButton.styleFrom(
                                  padding: const EdgeInsets.symmetric(vertical: 16),
                                  side: const BorderSide(color: AppColors.lineStrong, width: 1.5),
                                ),
                                child: Text(noLabel, style: GoogleFonts.bebasNeue(fontSize: 20)),
                              ),
                            ),
                          ],
                        ),
                      ],
                      const SizedBox(height: 14),
                      Text(
                        VoteUi.statusForPhase(vote),
                        textAlign: TextAlign.center,
                        style: GoogleFonts.ibmPlexMono(
                          fontSize: 10,
                          height: 1.4,
                          color: AppColors.muted.withValues(alpha: 0.9),
                        ),
                      ),
                      if (c.voteCastError != null) ...[
                        const SizedBox(height: 10),
                        Text(
                          c.voteCastError!,
                          textAlign: TextAlign.center,
                          style: const TextStyle(color: AppColors.accentHot, fontSize: 12),
                        ),
                      ],
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

class _VoteBar extends StatelessWidget {
  const _VoteBar({
    required this.label,
    required this.fill,
    required this.count,
    required this.yes,
  });

  final String label;
  final double fill;
  final int count;
  final bool yes;

  @override
  Widget build(BuildContext context) {
    final color = yes ? AppColors.accent : AppColors.muted;
    return Row(
      children: [
        SizedBox(
          width: 72,
          child: Text(
            label,
            style: GoogleFonts.ibmPlexMono(fontSize: 10, fontWeight: FontWeight.w800, color: color),
          ),
        ),
        Expanded(
          child: ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: fill.clamp(0.0, 1.0),
              minHeight: 10,
              backgroundColor: AppColors.bg,
              color: yes ? AppColors.accentHot : AppColors.lineStrong,
            ),
          ),
        ),
        const SizedBox(width: 10),
        SizedBox(
          width: 28,
          child: Text(
            '$count',
            textAlign: TextAlign.right,
            style: GoogleFonts.bebasNeue(fontSize: 22, color: color),
          ),
        ),
      ],
    );
  }
}

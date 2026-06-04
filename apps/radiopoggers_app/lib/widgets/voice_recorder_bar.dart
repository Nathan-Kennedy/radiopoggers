import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../core/theme/app_colors.dart';
import '../services/app_controller.dart';
import '../services/voice_drop_processor.dart';
import 'voice_drop_effects_panel.dart';
import 'voice_drop_stinger_panel.dart';

/// Gravação estilo WhatsApp: gravar, cancelar, ouvir e ajustar volume antes de enviar.
class VoiceRecorderBar extends StatelessWidget {
  const VoiceRecorderBar({super.key, required this.controller});

  final AppController controller;

  @override
  Widget build(BuildContext context) {
    final c = controller;
    final recording = c.voiceRecording;
    final preview = c.voicePreviewReady;

    if (preview) {
      return _PreviewBar(controller: c);
    }

    if (recording) {
      return _RecordingBar(controller: c);
    }

    return _IdleBar(controller: c);
  }
}

class _IdleBar extends StatelessWidget {
  const _IdleBar({required this.controller});
  final AppController controller;

  @override
  Widget build(BuildContext context) {
    final c = controller;
    return Card(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('CHAMADA NO AR', style: Theme.of(context).textTheme.labelSmall),
                      const SizedBox(height: 4),
                      Text(
                        c.voiceStatus,
                        style: const TextStyle(fontSize: 12, color: AppColors.muted),
                      ),
                      Text(
                        'Volume no ar: ${c.voiceDropGainPercent}%',
                        style: const TextStyle(fontSize: 11, color: AppColors.muted),
                      ),
                    ],
                  ),
                ),
                _MicButton(
                  icon: Icons.mic,
                  label: 'GRAVAR',
                  onTap: c.apiOnline ? c.startVoiceRecording : null,
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _RecordingBar extends StatelessWidget {
  const _RecordingBar({required this.controller});
  final AppController controller;

  @override
  Widget build(BuildContext context) {
    final c = controller;
    final progress = (15 - c.voiceSecondsLeft) / 15;
    return Card(
      color: AppColors.accentDim,
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                Container(
                  width: 10,
                  height: 10,
                  decoration: const BoxDecoration(color: AppColors.danger, shape: BoxShape.circle),
                ),
                const SizedBox(width: 8),
                Text(
                  '0:${c.voiceSecondsLeft.toString().padLeft(2, '0')}',
                  style: GoogleFonts.ibmPlexMono(fontSize: 22, fontWeight: FontWeight.w600),
                ),
                const Spacer(),
                TextButton.icon(
                  onPressed: c.cancelVoiceRecording,
                  icon: const Icon(Icons.delete_outline, size: 18),
                  label: const Text('CANCELAR'),
                  style: TextButton.styleFrom(foregroundColor: AppColors.danger),
                ),
              ],
            ),
            const SizedBox(height: 10),
            ClipRRect(
              borderRadius: BorderRadius.circular(2),
              child: LinearProgressIndicator(
                value: progress.clamp(0.05, 1.0),
                minHeight: 4,
                backgroundColor: Colors.white12,
                color: AppColors.accentHot,
              ),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: Text(
                    c.voiceStatus,
                    style: const TextStyle(fontSize: 12, color: AppColors.muted),
                  ),
                ),
                FilledButton(
                  onPressed: c.finishVoiceRecording,
                  child: const Text('PARAR'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _PreviewBar extends StatelessWidget {
  const _PreviewBar({required this.controller});
  final AppController controller;

  @override
  Widget build(BuildContext context) {
    final c = controller;
    final sec = (c.voiceRecordedMs / 1000).ceil();
    const minPct = VoiceDropProcessor.minPercent;
    const maxPct = VoiceDropProcessor.maxPercent;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                const Icon(Icons.graphic_eq, color: AppColors.good),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'Áudio gravado · ${sec}s',
                    style: GoogleFonts.ibmPlexMono(fontWeight: FontWeight.w600),
                  ),
                ),
                IconButton.filled(
                  tooltip: c.voicePreviewPlaying ? 'Parar prévia' : 'Ouvir como vai no ar',
                  onPressed: c.toggleVoicePreview,
                  icon: Icon(c.voicePreviewPlaying ? Icons.stop_circle_outlined : Icons.volume_up),
                ),
              ],
            ),
            const SizedBox(height: 6),
            Text(
              c.voiceStatus,
              style: const TextStyle(fontSize: 12, color: AppColors.muted),
            ),
            const SizedBox(height: 14),
            Row(
              children: [
                Text('VOLUME NO AR', style: Theme.of(context).textTheme.labelSmall),
                const Spacer(),
                Text(
                  '${c.voiceDropGainPercent}%',
                  style: GoogleFonts.ibmPlexMono(
                    fontWeight: FontWeight.w700,
                    color: AppColors.accentHot,
                  ),
                ),
              ],
            ),
            Slider(
              value: c.voiceDropGainPercent.toDouble(),
              min: minPct.toDouble(),
              max: maxPct.toDouble(),
              divisions: 20,
              label: '${c.voiceDropGainPercent}%',
              onChanged: (v) => c.setVoiceDropGain(VoiceDropProcessor.percentToGain(v.round())),
              onChangeEnd: (_) => c.persistVoiceDropGain(),
            ),
            const Text(
              '100% = original na rádio. Efeitos e imaging abaixo entram na prévia e no envio.',
              style: TextStyle(fontSize: 11, color: AppColors.muted),
            ),
            const SizedBox(height: 12),
            VoiceDropStingerPanel(controller: c),
            const SizedBox(height: 12),
            VoiceDropEffectsPanel(controller: c),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: c.discardVoicePreview,
                    icon: const Icon(Icons.refresh),
                    label: const Text('GRAVAR OUTRA'),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: FilledButton.icon(
                    onPressed: c.submitVoicePreview,
                    icon: const Icon(Icons.send_rounded),
                    label: const Text('ENVIAR'),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _MicButton extends StatelessWidget {
  const _MicButton({
    required this.icon,
    required this.label,
    required this.onTap,
  });

  final IconData icon;
  final String label;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: onTap == null ? AppColors.bgElevated : AppColors.accent,
      shape: const CircleBorder(),
      child: InkWell(
        customBorder: const CircleBorder(),
        onTap: onTap,
        child: SizedBox(
          width: 56,
          height: 56,
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(icon, color: Colors.white, size: 26),
              Text(label, style: const TextStyle(fontSize: 9, color: Colors.white, fontWeight: FontWeight.w700)),
            ],
          ),
        ),
      ),
    );
  }
}

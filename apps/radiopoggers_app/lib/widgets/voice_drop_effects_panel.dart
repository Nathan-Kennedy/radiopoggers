import 'package:flutter/material.dart';

import '../core/theme/app_colors.dart';
import '../services/app_controller.dart';

class VoiceDropEffectsPanel extends StatelessWidget {
  const VoiceDropEffectsPanel({super.key, required this.controller});

  final AppController controller;

  @override
  Widget build(BuildContext context) {
    final c = controller;
    final fx = c.voiceEffects;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text('EFEITOS DE VOZ', style: Theme.of(context).textTheme.labelSmall),
        const SizedBox(height: 6),
        Wrap(
          spacing: 6,
          runSpacing: 6,
          children: [
            _presetChip(c, 'Autotune', 'autotune'),
            _presetChip(c, 'Eco', 'echo'),
            _presetChip(c, 'Robô', 'robot'),
            _presetChip(c, 'Megafone', 'megaphone'),
            _presetChip(c, 'Coro', 'chorus'),
            ActionChip(
              label: const Text('Limpar'),
              onPressed: () => c.applyVoiceEffectsPreset('clear'),
            ),
          ],
        ),
        const SizedBox(height: 10),
        _effectSwitch(
          label: 'Redução de ruído',
          subtitle: 'Remove teclado, ventilador e barulho de fundo (estilo Discord)',
          value: fx.noiseSuppressEnabled,
          onChanged: (v) => c.updateVoiceEffects(fx.copyWith(noiseSuppressEnabled: v)),
        ),
        _effectSwitch(
          label: 'Eco',
          subtitle: 'Delay com repetição',
          value: fx.echoEnabled,
          onChanged: (v) => c.updateVoiceEffects(fx.copyWith(echoEnabled: v)),
          children: fx.echoEnabled
              ? [
                  _slider(
                    label: 'Tempo do eco',
                    value: fx.echoDelayMs,
                    min: 80,
                    max: 480,
                    divisions: 20,
                    display: '${fx.echoDelayMs.round()} ms',
                    onChanged: (v) => c.updateVoiceEffects(fx.copyWith(echoDelayMs: v), persist: false),
                    onChangeEnd: (_) => c.commitVoiceEffects(),
                  ),
                  _slider(
                    label: 'Intensidade',
                    value: fx.echoFeedback,
                    min: 0.12,
                    max: 0.68,
                    divisions: 14,
                    display: '${(fx.echoFeedback * 100).round()}%',
                    onChanged: (v) => c.updateVoiceEffects(fx.copyWith(echoFeedback: v), persist: false),
                    onChangeEnd: (_) => c.commitVoiceEffects(),
                  ),
                ]
              : null,
        ),
        _effectSwitch(
          label: 'Autotune',
          subtitle: 'Tom travado / pitch shift',
          value: fx.autotuneEnabled,
          onChanged: (v) => c.updateVoiceEffects(fx.copyWith(autotuneEnabled: v)),
          children: fx.autotuneEnabled
              ? [
                  _slider(
                    label: 'Semitons',
                    value: fx.autotuneSemitones,
                    min: -8,
                    max: 8,
                    divisions: 16,
                    display: fx.autotuneSemitones >= 0
                        ? '+${fx.autotuneSemitones.round()}'
                        : '${fx.autotuneSemitones.round()}',
                    onChanged: (v) => c.updateVoiceEffects(fx.copyWith(autotuneSemitones: v), persist: false),
                    onChangeEnd: (_) => c.commitVoiceEffects(),
                  ),
                  _slider(
                    label: 'Trava (estilo TPain)',
                    value: fx.autotuneSnap,
                    min: 0,
                    max: 1,
                    divisions: 10,
                    display: '${(fx.autotuneSnap * 100).round()}%',
                    onChanged: (v) => c.updateVoiceEffects(fx.copyWith(autotuneSnap: v), persist: false),
                    onChangeEnd: (_) => c.commitVoiceEffects(),
                  ),
                ]
              : null,
        ),
        _effectSwitch(
          label: 'Voz robô',
          subtitle: 'Modulação metálica',
          value: fx.robotEnabled,
          onChanged: (v) => c.updateVoiceEffects(fx.copyWith(robotEnabled: v)),
          children: fx.robotEnabled
              ? [
                  _slider(
                    label: 'Profundidade',
                    value: fx.robotDepth,
                    min: 0.15,
                    max: 0.85,
                    divisions: 14,
                    display: '${(fx.robotDepth * 100).round()}%',
                    onChanged: (v) => c.updateVoiceEffects(fx.copyWith(robotDepth: v), persist: false),
                    onChangeEnd: (_) => c.commitVoiceEffects(),
                  ),
                ]
              : null,
        ),
        _effectSwitch(
          label: 'Megafone',
          subtitle: 'Filtro de rua / alto-falante',
          value: fx.megaphoneEnabled,
          onChanged: (v) => c.updateVoiceEffects(fx.copyWith(megaphoneEnabled: v)),
        ),
        _effectSwitch(
          label: 'Coro',
          subtitle: 'Camada dupla desafinada',
          value: fx.chorusEnabled,
          onChanged: (v) => c.updateVoiceEffects(fx.copyWith(chorusEnabled: v)),
          children: fx.chorusEnabled
              ? [
                  _slider(
                    label: 'Mix',
                    value: fx.chorusDepth,
                    min: 0.1,
                    max: 0.7,
                    divisions: 12,
                    display: '${(fx.chorusDepth * 100).round()}%',
                    onChanged: (v) => c.updateVoiceEffects(fx.copyWith(chorusDepth: v), persist: false),
                    onChangeEnd: (_) => c.commitVoiceEffects(),
                  ),
                ]
              : null,
        ),
      ],
    );
  }

  Widget _presetChip(AppController c, String label, String preset) {
    return ActionChip(
      label: Text(label),
      onPressed: () => c.applyVoiceEffectsPreset(preset),
    );
  }

  Widget _effectSwitch({
    required String label,
    required String subtitle,
    required bool value,
    required ValueChanged<bool> onChanged,
    List<Widget>? children,
  }) {
    return Column(
      children: [
        SwitchListTile(
          contentPadding: EdgeInsets.zero,
          dense: true,
          title: Text(label, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13)),
          subtitle: Text(subtitle, style: const TextStyle(fontSize: 11, color: AppColors.muted)),
          value: value,
          onChanged: onChanged,
        ),
        if (children != null) ...children,
        const Divider(height: 8),
      ],
    );
  }

  Widget _slider({
    required String label,
    required double value,
    required double min,
    required double max,
    required int divisions,
    required String display,
    required ValueChanged<double> onChanged,
    required ValueChanged<double> onChangeEnd,
  }) {
    return Padding(
      padding: const EdgeInsets.only(left: 4, bottom: 6),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Text(label, style: const TextStyle(fontSize: 11, color: AppColors.muted)),
              const Spacer(),
              Text(display, style: const TextStyle(fontSize: 11, fontFamily: 'monospace')),
            ],
          ),
          Slider(
            value: value.clamp(min, max),
            min: min,
            max: max,
            divisions: divisions,
            onChanged: onChanged,
            onChangeEnd: onChangeEnd,
          ),
        ],
      ),
    );
  }
}

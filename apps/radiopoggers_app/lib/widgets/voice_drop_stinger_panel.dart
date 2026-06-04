import 'dart:typed_data';

import 'package:flutter/material.dart';

import '../core/theme/app_colors.dart';
import '../models/voice_drop_slot.dart';
import '../services/app_controller.dart';
import '../services/custom_drop_audio.dart';
import '../services/radio_stinger_catalog.dart';
import 'custom_drop_trim_page.dart';

class VoiceDropStingerPanel extends StatelessWidget {
  const VoiceDropStingerPanel({super.key, required this.controller});

  final AppController controller;

  Future<void> _importCustomDrop(BuildContext context, {required bool forOutro}) async {
    final bytes = await controller.pickCustomDropSourceFile();
    if (bytes == null || !context.mounted) return;

    Uint8List finalWav = bytes;
    final dur = CustomDropAudio.durationMs(bytes);
    if (dur > CustomDropAudio.maxDurationMs + 80) {
      final trimmed = await Navigator.of(context).push<Uint8List>(
        MaterialPageRoute(
          fullscreenDialog: true,
          builder: (_) => CustomDropTrimPage(
            wavBytes: bytes,
            durationMs: dur,
            title: forOutro ? 'Recortar drop do fim' : 'Recortar drop do início',
          ),
        ),
      );
      if (trimmed == null || !context.mounted) return;
      finalWav = trimmed;
    } else {
      finalWav = CustomDropAudio.trimFromStart(bytes, maxMs: CustomDropAudio.maxDurationMs);
    }

    await controller.applyCustomDropWav(wav: finalWav, forOutro: forOutro);
  }

  @override
  Widget build(BuildContext context) {
    final c = controller;
    final st = c.voiceStinger;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          children: [
            Expanded(
              child: Text('DROPS NA CHAMADA', style: Theme.of(context).textTheme.labelSmall),
            ),
            Switch(
              value: st.enabled,
              onChanged: (v) => c.updateVoiceStinger(st.copyWith(enabled: v)),
            ),
          ],
        ),
        const Text(
          'Até 5 s por lado · envie meme/áudio ou Mixkit · início e fim sempre diferentes.',
          style: TextStyle(fontSize: 11, color: AppColors.muted),
        ),
        if (c.customDropMessage.isNotEmpty) ...[
          const SizedBox(height: 6),
          Text(
            c.customDropMessage,
            style: const TextStyle(fontSize: 11, color: AppColors.accentHot),
          ),
        ],
        if (st.hasSameSlotConflict) ...[
          const SizedBox(height: 4),
          const Text(
            'Mesmo som no início e no fim — ajuste um dos lados.',
            style: TextStyle(fontSize: 11, color: AppColors.danger),
          ),
        ],
        if (st.enabled) ...[
          const SizedBox(height: 10),
          _DropSlotSection(
            title: 'DROP NO INÍCIO',
            isOutro: false,
            slot: st.intro,
            controller: c,
            blockedCatalogIds: st.outro.isCatalog ? {st.outro.catalogId} : {},
            onSetCatalog: c.setIntroDropCatalog,
            onPickFile: () => _importCustomDrop(context, forOutro: false),
            onClear: c.clearIntroDrop,
            onPreview: () => c.previewDropSlot(outro: false),
            onDisable: () => c.updateVoiceStinger(st.copyWith(intro: VoiceDropSlot.empty)),
          ),
          const SizedBox(height: 12),
          _DropSlotSection(
            title: 'DROP NO FIM',
            isOutro: true,
            slot: st.outro,
            controller: c,
            blockedCatalogIds: st.intro.isCatalog ? {st.intro.catalogId} : {},
            onSetCatalog: c.setOutroDropCatalog,
            onPickFile: () => _importCustomDrop(context, forOutro: true),
            onClear: c.clearOutroDrop,
            onPreview: () => c.previewDropSlot(outro: true),
            onDisable: () => c.updateVoiceStinger(st.copyWith(outro: VoiceDropSlot.empty)),
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              const Text('Volume dos drops', style: TextStyle(fontSize: 12)),
              const Spacer(),
              Text('${(st.volume * 100).round()}%'),
            ],
          ),
          Slider(
            value: st.volume.clamp(0.0, 1.0),
            min: 0,
            max: 1.0,
            divisions: 40,
            label: st.volume < 0.01 ? 'Mudo' : '${(st.volume * 100).round()}%',
            onChanged: (v) => c.updateVoiceStinger(st.copyWith(volume: v), persist: false),
            onChangeEnd: (_) => c.commitVoiceStinger(),
          ),
        ],
      ],
    );
  }
}

class _DropSlotSection extends StatelessWidget {
  const _DropSlotSection({
    required this.title,
    required this.isOutro,
    required this.slot,
    required this.controller,
    required this.blockedCatalogIds,
    required this.onSetCatalog,
    required this.onPickFile,
    required this.onClear,
    required this.onPreview,
    required this.onDisable,
  });

  final String title;
  final bool isOutro;
  final VoiceDropSlot slot;
  final AppController controller;
  final Set<String> blockedCatalogIds;
  final Future<void> Function(String catalogId) onSetCatalog;
  final VoidCallback onPickFile;
  final VoidCallback onClear;
  final VoidCallback onPreview;
  final VoidCallback onDisable;

  @override
  Widget build(BuildContext context) {
    final active = slot.isActive;
    final catalogItem = slot.isCatalog ? RadioStingerCatalog.find(slot.catalogId) : null;

    return DecoratedBox(
      decoration: BoxDecoration(
        border: Border.all(color: AppColors.line),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Padding(
        padding: const EdgeInsets.all(10),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                Text(title, style: Theme.of(context).textTheme.labelSmall),
                const Spacer(),
                if (active)
                  IconButton(
                    tooltip: 'Remover drop deste lado',
                    icon: const Icon(Icons.close, size: 18),
                    onPressed: onDisable,
                  ),
              ],
            ),
            SegmentedButton<VoiceDropSlotSource>(
              segments: const [
                ButtonSegment(
                  value: VoiceDropSlotSource.none,
                  label: Text('Off', style: TextStyle(fontSize: 11)),
                ),
                ButtonSegment(
                  value: VoiceDropSlotSource.custom,
                  label: Text('Meu áudio', style: TextStyle(fontSize: 11)),
                ),
                ButtonSegment(
                  value: VoiceDropSlotSource.catalog,
                  label: Text('Mixkit', style: TextStyle(fontSize: 11)),
                ),
              ],
              selected: {slot.source},
              onSelectionChanged: (s) {
                if (s.isEmpty) return;
                final src = s.first;
                if (src == VoiceDropSlotSource.none) {
                  onDisable();
                  return;
                }
                if (src == VoiceDropSlotSource.catalog) {
                  final id = RadioStingerCatalog.defaultId;
                  if (!blockedCatalogIds.contains(id)) {
                    onSetCatalog(id);
                  }
                  return;
                }
                final custom = VoiceDropSlot(
                  source: VoiceDropSlotSource.custom,
                  customPath: slot.customPath,
                );
                controller.updateVoiceStinger(
                  controller.voiceStinger.copyWith(
                    enabled: true,
                    intro: isOutro ? controller.voiceStinger.intro : custom,
                    outro: isOutro ? custom : controller.voiceStinger.outro,
                  ),
                );
              },
            ),
            if (slot.source == VoiceDropSlotSource.custom) ...[
              const SizedBox(height: 8),
              SizedBox(
                width: double.infinity,
                child: FilledButton.icon(
                  onPressed: controller.voiceRecording ? null : onPickFile,
                  icon: const Icon(Icons.upload_file),
                  label: const Text('ENVIAR ARQUIVO'),
                ),
              ),
              const SizedBox(height: 4),
              Text(
                slot.isCustom
                    ? 'Salvo: ${slot.customPath}'
                    : 'MP3, M4A, AAC, OGG, FLAC, WAV… (converte para WAV ao enviar). > 5 s abre o editor de corte.',
                style: const TextStyle(fontSize: 10, color: AppColors.muted),
                maxLines: 3,
                overflow: TextOverflow.ellipsis,
              ),
              if (slot.isCustom) ...[
                const SizedBox(height: 6),
                Row(
                  children: [
                    TextButton.icon(
                      onPressed: onPreview,
                      icon: const Icon(Icons.play_arrow, size: 18),
                      label: const Text('Ouvir no ar'),
                    ),
                    TextButton.icon(
                      onPressed: onClear,
                      icon: const Icon(Icons.delete_outline, size: 18),
                      label: const Text('Apagar'),
                    ),
                  ],
                ),
              ],
            ],
            if (slot.source == VoiceDropSlotSource.catalog) ...[
              const SizedBox(height: 8),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: [
                  for (final item in RadioStingerCatalog.items)
                    FilterChip(
                      label: Text(item.label),
                      selected: slot.catalogId == item.id,
                      onSelected: blockedCatalogIds.contains(item.id)
                          ? null
                          : (_) => onSetCatalog(item.id),
                    ),
                ],
              ),
              if (catalogItem != null)
                Text(
                  catalogItem.description,
                  style: const TextStyle(fontSize: 11, color: AppColors.muted),
                ),
              if (blockedCatalogIds.isNotEmpty)
                const Text(
                  'Chips bloqueados = já usados no outro lado.',
                  style: TextStyle(fontSize: 10, color: AppColors.muted),
                ),
              Align(
                alignment: Alignment.centerLeft,
                child: TextButton.icon(
                  onPressed: slot.isCatalog ? onPreview : null,
                  icon: const Icon(Icons.play_arrow, size: 18),
                  label: const Text('Ouvir este drop'),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

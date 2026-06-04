import 'dart:async';
import 'dart:io';
import 'dart:math';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:media_kit/media_kit.dart';
import 'package:path_provider/path_provider.dart';

import '../core/theme/app_colors.dart';
import '../services/custom_drop_audio.dart';

/// Editor local: escolhe 5 s em qualquer ponto do áudio (só prévia; o corte vai pro drop salvo).
class CustomDropTrimPage extends StatefulWidget {
  const CustomDropTrimPage({
    super.key,
    required this.wavBytes,
    required this.durationMs,
    this.title = 'Recortar drop (5 s)',
  });

  final Uint8List wavBytes;
  final int durationMs;
  final String title;

  @override
  State<CustomDropTrimPage> createState() => _CustomDropTrimPageState();
}

class _CustomDropTrimPageState extends State<CustomDropTrimPage> {
  static const int windowMs = CustomDropAudio.maxDurationMs;

  late final int _maxStartMs;
  late double _startMs;
  final Player _player = Player();
  bool _playing = false;
  String? _previewPath;
  StreamSubscription<bool>? _playingSub;

  @override
  void initState() {
    super.initState();
    _maxStartMs = max(0, widget.durationMs - windowMs);
    _startMs = 0;
    _playingSub = _player.stream.playing.listen((playing) {
      if (mounted) setState(() => _playing = playing);
    });
  }

  @override
  void dispose() {
    _playingSub?.cancel();
    _player.dispose();
    _deletePreviewFile();
    super.dispose();
  }

  Uint8List get _segmentWav => CustomDropAudio.extractSegment(
        widget.wavBytes,
        startMs: _startMs.round(),
        lengthMs: windowMs,
      );

  String _formatMs(int ms) {
    final s = ms / 1000;
    return '${s.toStringAsFixed(2)} s';
  }

  Future<void> _deletePreviewFile() async {
    final path = _previewPath;
    if (path != null && File(path).existsSync()) {
      try {
        await File(path).delete();
      } catch (_) {}
    }
    _previewPath = null;
  }

  Future<void> _playSegmentPreview() async {
    try {
      await _player.stop();
      await _deletePreviewFile();
      final dir = await getTemporaryDirectory();
      final path = '${dir.path}/trim-preview-${DateTime.now().millisecondsSinceEpoch}.wav';
      await File(path).writeAsBytes(_segmentWav, flush: true);
      _previewPath = path;
      await _player.open(Media(path), play: true);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Prévia: $e')),
        );
      }
    }
  }

  void _updateStartFromRatio(double ratio) {
    setState(() => _startMs = _maxStartMs * ratio.clamp(0.0, 1.0));
  }

  void _onDragEnd() {
    unawaited(_playSegmentPreview());
  }

  @override
  Widget build(BuildContext context) {
    final endMs = min(widget.durationMs, _startMs.round() + windowMs);
    final ratio = _maxStartMs > 0 ? (_startMs / _maxStartMs) : 0.0;

    return Scaffold(
      backgroundColor: AppColors.bg,
      appBar: AppBar(
        title: Text(widget.title),
        backgroundColor: AppColors.bgElevated,
      ),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              'Áudio: ${_formatMs(widget.durationMs)} · janela fixa de 5 s',
              style: const TextStyle(color: AppColors.muted, fontSize: 13),
            ),
            const SizedBox(height: 8),
            Text(
              'Trecho: ${_formatMs(_startMs.round())} → ${_formatMs(endMs)}',
              style: GoogleFonts.ibmPlexMono(
                fontWeight: FontWeight.w600,
                color: AppColors.accentHot,
              ),
            ),
            const SizedBox(height: 20),
            Text('Arraste a faixa vermelha', style: Theme.of(context).textTheme.labelSmall),
            const SizedBox(height: 10),
            LayoutBuilder(
              builder: (context, constraints) {
                final trackW = constraints.maxWidth;
                final windowW = widget.durationMs > windowMs
                    ? trackW * (windowMs / widget.durationMs)
                    : trackW;
                final maxLeft = max(0.0, trackW - windowW);
                final left = _maxStartMs > 0 ? ratio * maxLeft : 0.0;

                return Column(
                  children: [
                    SizedBox(
                      height: 48,
                      child: Stack(
                        children: [
                          Positioned.fill(
                            child: DecoratedBox(
                              decoration: BoxDecoration(
                                color: AppColors.bgElevated,
                                borderRadius: BorderRadius.circular(8),
                                border: Border.all(color: AppColors.line),
                              ),
                            ),
                          ),
                          Positioned(
                            left: left,
                            width: windowW,
                            top: 4,
                            bottom: 4,
                            child: GestureDetector(
                              onHorizontalDragUpdate: (d) {
                                final nextLeft = (left + d.delta.dx).clamp(0.0, maxLeft);
                                _updateStartFromRatio(maxLeft > 0 ? nextLeft / maxLeft : 0);
                              },
                              onHorizontalDragEnd: (_) => _onDragEnd(),
                              child: DecoratedBox(
                                decoration: BoxDecoration(
                                  color: AppColors.accent.withValues(alpha: 0.85),
                                  borderRadius: BorderRadius.circular(6),
                                  border: Border.all(color: AppColors.accentHot, width: 2),
                                ),
                                child: const Center(
                                  child: Icon(Icons.drag_indicator, color: Colors.white, size: 20),
                                ),
                              ),
                            ),
                          ),
                          Positioned.fill(
                            child: GestureDetector(
                              behavior: HitTestBehavior.translucent,
                              onTapDown: (d) {
                                final w = max(1.0, windowW);
                                final tapLeft = (d.localPosition.dx - w / 2)
                                    .clamp(0.0, max(0.0, trackW - w));
                                _updateStartFromRatio(maxLeft > 0 ? tapLeft / maxLeft : 0);
                                _onDragEnd();
                              },
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 8),
                    Slider(
                      value: ratio,
                      onChanged: (v) => setState(() => _updateStartFromRatio(v)),
                      onChangeEnd: (_) => _onDragEnd(),
                    ),
                  ],
                );
              },
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _playSegmentPreview,
                    icon: Icon(_playing ? Icons.stop : Icons.play_arrow),
                    label: Text(_playing ? 'Parar prévia' : 'Ouvir 5 s recortados'),
                  ),
                ),
              ],
            ),
            const Spacer(),
            const Text(
              'Só a prévia roda aqui. Na rádio entra apenas este trecho de 5 s.',
              style: TextStyle(fontSize: 11, color: AppColors.muted),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: () => Navigator.pop(context),
                    child: const Text('Cancelar'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  flex: 2,
                  child: FilledButton(
                    onPressed: () => Navigator.pop(context, _segmentWav),
                    child: const Text('USAR ESTE TRECHO'),
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

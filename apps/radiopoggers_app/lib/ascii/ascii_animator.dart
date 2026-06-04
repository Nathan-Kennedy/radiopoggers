import 'dart:convert';
import 'dart:math' as math;

import 'package:flutter/foundation.dart' show TargetPlatform, defaultTargetPlatform, kIsWeb;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../core/theme/app_colors.dart';

/// Port de [frontend/ascii-guitarist.js].
class AsciiAnimator {
  AsciiAnimator._(this.frames, this.width, this.height, this.cellSize, this.colorMode);

  final List<List<List<String>>> frames;
  final int width;
  final int height;
  final double cellSize;
  final String colorMode;

  static const frameMs = 100;
  static const defaultCell = 6.0;
  static const mikuCell = 3.0;
  static const pickerCell = 4.0;

  /// Celular: menos quadros e intervalo maior (aba Rádio).
  static const int mobileMaxStageFrames = 14;
  static const int mobileStageFrameMs = 160;

  static bool get isMobilePlatform =>
      !kIsWeb &&
      (defaultTargetPlatform == TargetPlatform.android ||
          defaultTargetPlatform == TargetPlatform.iOS);

  static int get animationIntervalMs => isMobilePlatform ? mobileStageFrameMs : frameMs;

  static List<dynamic> decimateFramesForMobile(List<dynamic> raw, {int maxFrames = mobileMaxStageFrames}) {
    if (!isMobilePlatform || raw.length <= maxFrames) return raw;
    final step = (raw.length / maxFrames).ceil().clamp(1, raw.length);
    final out = <dynamic>[];
    for (var i = 0; i < raw.length && out.length < maxFrames; i += step) {
      out.add(raw[i]);
    }
    if (out.isEmpty) return raw.sublist(0, 1);
    return out;
  }

  static const _lum = <String, double>{
    ' ': 0,
    '.': 0.12,
    ':': 0.22,
    '-': 0.34,
    '=': 0.44,
    '+': 0.48,
    '*': 0.62,
    '#': 0.82,
    '%': 0.88,
    '@': 0.96,
  };

  static Map<String, dynamic> _computeCropBox(List<dynamic> rawFrames) {
    var top = 999999;
    var bottom = -1;
    var left = 999999;
    var right = -1;
    for (final frame in rawFrames) {
      final lines = frame as List<dynamic>;
      for (var y = 0; y < lines.length; y++) {
        final line = lines[y] as String;
        for (var x = 0; x < line.length; x++) {
          if (line[x] != ' ') {
            top = math.min(top, y);
            bottom = math.max(bottom, y);
            left = math.min(left, x);
            right = math.max(right, x);
          }
        }
      }
    }
    if (top == 999999) {
      return {'left': 0, 'top': 0, 'right': 0, 'bottom': 0};
    }
    return {'left': left, 'top': top, 'right': right, 'bottom': bottom};
  }

  static List<List<String>> _cropFrame(List<dynamic> frame, Map<String, dynamic> box) {
    final cropped = <List<String>>[];
    final top = box['top'] as int;
    final bottom = box['bottom'] as int;
    final left = box['left'] as int;
    final right = box['right'] as int;
    for (var y = top; y <= bottom; y++) {
      final line = (frame[y] as String?) ?? '';
      cropped.add(line.substring(left, math.min(right + 1, line.length)).split(''));
    }
    return cropped;
  }

  static AsciiAnimator fromRaw(List<dynamic> raw, {double cellSize = defaultCell, String colorMode = 'mono'}) {
    final box = _computeCropBox(raw);
    final cropped = raw.map((f) => _cropFrame(f as List<dynamic>, box)).toList();
    final height = cropped[0].length;
    final width = cropped[0].fold<int>(0, (m, row) => math.max(m, row.length));
    final frames = cropped.map((grid) {
      return grid.map((row) {
        if (row.length < width) {
          return [...row, ...List.filled(width - row.length, ' ')];
        }
        return row;
      }).toList();
    }).toList();
    return AsciiAnimator._(frames, width, height, cellSize, colorMode);
  }

  static Future<AsciiAnimator> loadAsset(
    String assetPath, {
    double cellSize = defaultCell,
    bool stageAnimation = false,
  }) async {
    final raw = await rootBundle.loadString(assetPath);
    var data = jsonDecode(raw) as List<dynamic>;
    if (stageAnimation) {
      data = decimateFramesForMobile(data);
    }
    return fromRaw(data, cellSize: cellSize);
  }

  Color? _colorForChar(String ch, int tick) {
    final lum = _lum[ch];
    if (lum == null || lum < 0.05) return null;
    if (colorMode == 'mono') {
      final pulse = math.sin(tick * 0.06) * 2;
      final light = (18 + lum * 72 + pulse).clamp(0, 100).toDouble();
      final hue = 312 + lum * 8;
      return HSLColor.fromAHSL(1, hue, 0.28 + lum * 0.22, light / 100).toColor();
    }
    if (lum >= 0.84 || lum >= 0.72) return AppColors.chibiOutline;
    if (lum >= 0.58) return AppColors.chibiAccent;
    if (lum >= 0.44) return AppColors.chibiSoft;
    if (lum >= 0.28) return AppColors.chibiFill;
    return AppColors.chibiHighlight;
  }

  void paint(Canvas canvas, int tick) {
    if (frames.isEmpty) return;
    final grid = frames[tick % frames.length];
    final textStyle = TextStyle(
      fontFamily: 'monospace',
      fontSize: cellSize,
      height: 1,
    );
    for (var y = 0; y < height; y++) {
      for (var x = 0; x < width; x++) {
        final ch = grid[y][x];
        final color = _colorForChar(ch, tick);
        if (color == null) continue;
        final tp = TextPainter(
          text: TextSpan(text: ch, style: textStyle.copyWith(color: color)),
          textDirection: TextDirection.ltr,
        )..layout();
        tp.paint(canvas, Offset(x * cellSize, y * cellSize));
      }
    }
  }

  Size get size => Size(width * cellSize, height * cellSize);
}

class AsciiRepository {
  AsciiRepository();

  AsciiAnimator? play;
  AsciiAnimator? idle;
  AsciiAnimator? off;
  AsciiAnimator? mikuCaption;
  AsciiAnimator? hoshinoCaption;
  AsciiAnimator? pickerMiku;
  AsciiAnimator? pickerHoshino;

  Future<void> loadAll() async {
    if (play != null) return;
    play = await AsciiAnimator.loadAsset('assets/ascii/ascii-frames.json', stageAnimation: true);
    idle = await AsciiAnimator.loadAsset('assets/ascii/ascii-frames sentado.json', stageAnimation: true);
    off = await AsciiAnimator.loadAsset('assets/ascii/ascii-frames off.json', stageAnimation: true);
    mikuCaption = await AsciiAnimator.loadAsset(
      'assets/ascii/ascii-frames falando.json',
      cellSize: AsciiAnimator.mikuCell,
      stageAnimation: true,
    );
    hoshinoCaption = await AsciiAnimator.loadAsset(
      'assets/ascii/ascii-frames hoshino falando.json',
      cellSize: AsciiAnimator.mikuCell,
      stageAnimation: true,
    );
    pickerMiku = await AsciiAnimator.loadAsset('assets/ascii/ascii-frames miku.json', cellSize: AsciiAnimator.pickerCell);
    pickerHoshino = await AsciiAnimator.loadAsset('assets/ascii/ascii-frames hoshino.json', cellSize: AsciiAnimator.pickerCell);
  }

  AsciiAnimator? forStage(String mode) {
    switch (mode) {
      case 'play':
        return play;
      case 'idle':
        return idle;
      case 'off':
        return off;
      case 'miku':
        return mikuCaption;
      case 'hoshino':
        return hoshinoCaption;
      default:
        return idle;
    }
  }
}

import 'dart:convert';
import 'dart:math' as math;

import 'package:flutter/foundation.dart' show TargetPlatform, defaultTargetPlatform, kIsWeb;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../core/theme/app_colors.dart';

/// Perfil de animação no celular: menos quadros + intervalo maior (evita loop rápido demais).
enum AsciiMobileProfile {
  /// Sem redução (desktop / web).
  desktop,
  /// Palco na aba Rádio (play / idle / off).
  stage,
  /// Miku / Hoshino falando (deck + legenda).
  caption,
  /// Picker de narrador (frame fixo, mas reduz memória ao carregar).
  picker,
}

/// Port de [frontend/ascii-guitarist.js].
class AsciiAnimator {
  AsciiAnimator._(
    this.frames,
    this.width,
    this.height,
    this.cellSize,
    this.colorMode,
    this.frameIntervalMs,
  );

  final List<List<List<String>>> frames;
  final int width;
  final int height;
  final double cellSize;
  final String colorMode;

  /// Intervalo entre quadros desta animação (ms).
  final int frameIntervalMs;

  static const frameMs = 100;
  static const defaultCell = 6.0;
  static const mikuCell = 3.0;
  static const pickerCell = 4.0;

  /// Palco: menos quadros; intervalo compensa para não acelerar o loop.
  static const int mobileMaxStageFrames = 10;
  static const int mobileStageFrameMs = 200;

  static const int mobileMaxCaptionFrames = 8;
  static const int mobileCaptionFrameMs = 195;

  static const int mobileMaxPickerFrames = 8;
  static const int mobilePickerFrameMs = 200;

  static bool get isMobilePlatform =>
      !kIsWeb &&
      (defaultTargetPlatform == TargetPlatform.android ||
          defaultTargetPlatform == TargetPlatform.iOS);

  /// Legado: palco na aba Rádio.
  static int get animationIntervalMs => mobileStageFrameMs;

  static int _maxFramesFor(AsciiMobileProfile profile) {
    switch (profile) {
      case AsciiMobileProfile.desktop:
        return 999999;
      case AsciiMobileProfile.stage:
        return mobileMaxStageFrames;
      case AsciiMobileProfile.caption:
        return mobileMaxCaptionFrames;
      case AsciiMobileProfile.picker:
        return mobileMaxPickerFrames;
    }
  }

  static int _intervalMsFor(AsciiMobileProfile profile) {
    if (!isMobilePlatform || profile == AsciiMobileProfile.desktop) return frameMs;
    switch (profile) {
      case AsciiMobileProfile.stage:
        return mobileStageFrameMs;
      case AsciiMobileProfile.caption:
        return mobileCaptionFrameMs;
      case AsciiMobileProfile.picker:
        return mobilePickerFrameMs;
      case AsciiMobileProfile.desktop:
        return frameMs;
    }
  }

  /// Amostra quadros uniformemente (início e fim preservados).
  static List<dynamic> decimateFramesForMobile(List<dynamic> raw, {int maxFrames = mobileMaxStageFrames}) {
    if (!isMobilePlatform || raw.length <= maxFrames) return raw;
    if (maxFrames <= 1) return [raw.first];
    final out = <dynamic>[];
    for (var i = 0; i < maxFrames; i++) {
      final idx = (i * (raw.length - 1) / (maxFrames - 1)).round().clamp(0, raw.length - 1);
      final frame = raw[idx];
      if (out.isEmpty || !identical(frame, out.last)) {
        out.add(frame);
      }
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

  static AsciiAnimator fromRaw(
    List<dynamic> raw, {
    double cellSize = defaultCell,
    String colorMode = 'mono',
    int frameIntervalMs = frameMs,
  }) {
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
    return AsciiAnimator._(frames, width, height, cellSize, colorMode, frameIntervalMs);
  }

  static Future<AsciiAnimator> loadAsset(
    String assetPath, {
    double cellSize = defaultCell,
    AsciiMobileProfile mobileProfile = AsciiMobileProfile.desktop,
    @Deprecated('Use mobileProfile: AsciiMobileProfile.stage')
    bool stageAnimation = false,
  }) async {
    final profile = stageAnimation ? AsciiMobileProfile.stage : mobileProfile;
    final raw = await rootBundle.loadString(assetPath);
    var data = jsonDecode(raw) as List<dynamic>;
    if (profile != AsciiMobileProfile.desktop) {
      data = decimateFramesForMobile(data, maxFrames: _maxFramesFor(profile));
    }
    final interval = _intervalMsFor(profile);
    return fromRaw(data, cellSize: cellSize, frameIntervalMs: interval);
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
    play = await AsciiAnimator.loadAsset(
      'assets/ascii/ascii-frames.json',
      mobileProfile: AsciiMobileProfile.stage,
    );
    idle = await AsciiAnimator.loadAsset(
      'assets/ascii/ascii-frames sentado.json',
      mobileProfile: AsciiMobileProfile.stage,
    );
    off = await AsciiAnimator.loadAsset(
      'assets/ascii/ascii-frames off.json',
      mobileProfile: AsciiMobileProfile.stage,
    );
    mikuCaption = await AsciiAnimator.loadAsset(
      'assets/ascii/ascii-frames falando.json',
      cellSize: AsciiAnimator.mikuCell,
      mobileProfile: AsciiMobileProfile.caption,
    );
    hoshinoCaption = await AsciiAnimator.loadAsset(
      'assets/ascii/ascii-frames hoshino falando.json',
      cellSize: AsciiAnimator.mikuCell,
      mobileProfile: AsciiMobileProfile.caption,
    );
    pickerMiku = await AsciiAnimator.loadAsset(
      'assets/ascii/ascii-frames miku.json',
      cellSize: AsciiAnimator.pickerCell,
      mobileProfile: AsciiMobileProfile.picker,
    );
    pickerHoshino = await AsciiAnimator.loadAsset(
      'assets/ascii/ascii-frames hoshino.json',
      cellSize: AsciiAnimator.pickerCell,
      mobileProfile: AsciiMobileProfile.picker,
    );
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

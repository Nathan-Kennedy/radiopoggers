import 'package:flutter/animation.dart';
import 'package:flutter/material.dart';

/// Curvas e durações alinhadas ao site (visualizer, flash de faixa).
abstract final class AppMotion {
  static const Duration visualizerBar = Duration(milliseconds: 800);
  static const Duration trackFlash = Duration(milliseconds: 600);
  static const Duration modal = Duration(milliseconds: 320);
  static const Duration livePulse = Duration(milliseconds: 1400);
  static const Duration ambient = Duration(seconds: 12);
  static const Duration vinylSpin = Duration(seconds: 14);

  static const Curve visualizerCurve = Curves.easeInOut;
  static const Curve modalCurve = Curves.easeOutCubic;
  static const Curve slideCurve = Curves.easeOutBack;
}

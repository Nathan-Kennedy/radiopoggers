import 'dart:async';

/// Ducking da radio — mesmo perfil da Miku: musica continua audivel.
class StreamDuckController {
  /// Piso com voz no ar (~42% da musica — parecido com sidechain medio do site).
  static const double voiceDuckFloor = 0.42;

  /// Primeiro passo mais suave (evita a musica “sumir” de uma vez).
  static const double voiceDuckPreDip = 0.62;

  static const int tickMs = 40;
  static const int releaseMs = 520;
  static const int preDipHoldMs = 90;

  double _multiplier = 1.0;
  double _target = 1.0;
  Timer? _timer;
  Timer? _preDipTimer;
  void Function(double effectiveMultiplier)? onMultiplierChanged;

  double get multiplier => _multiplier;

  void dispose() {
    _timer?.cancel();
    _preDipTimer?.cancel();
  }

  /// Narradora e ouvinte: mesmo ducking.
  void duckForVoiceOverlay() {
    _preDipTimer?.cancel();
    _animateTo(voiceDuckPreDip);
    _preDipTimer = Timer(const Duration(milliseconds: preDipHoldMs), () {
      _animateTo(voiceDuckFloor);
    });
  }

  void duckForNarrator() => duckForVoiceOverlay();

  void duckForListener() => duckForVoiceOverlay();

  void restore({Duration tail = const Duration(milliseconds: releaseMs)}) {
    _preDipTimer?.cancel();
    _timer?.cancel();
    _timer = Timer(tail, () => _animateTo(1.0));
  }

  void restoreImmediate() {
    _preDipTimer?.cancel();
    _timer?.cancel();
    _animateTo(1.0);
  }

  void _animateTo(double target) {
    _target = target.clamp(voiceDuckFloor, 1.0);
    _timer?.cancel();
    _timer = Timer.periodic(const Duration(milliseconds: tickMs), (t) {
      final diff = _target - _multiplier;
      if (diff.abs() < 0.02) {
        _multiplier = _target;
        onMultiplierChanged?.call(_multiplier);
        t.cancel();
        _timer = null;
        return;
      }
      // Sobe mais rapido; desce devagar (release suave).
      final follow = diff > 0 ? 0.38 : 0.14;
      _multiplier += diff * follow;
      onMultiplierChanged?.call(_multiplier);
    });
  }
}

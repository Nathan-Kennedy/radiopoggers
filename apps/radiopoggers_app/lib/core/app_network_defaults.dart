import '../models/app_settings.dart';

/// Host da VPN — nunca commitar IP real no código publicado.
///
/// Build privado (só na sua máquina):
/// `flutter build windows --dart-define=RADIOPOGGERS_RADMIN_HOST=SEU.IP.AQUI`
abstract final class AppNetworkDefaults {
  static const String radminHost = String.fromEnvironment('RADIOPOGGERS_RADMIN_HOST');

  static bool get hasCompiledRadminHost => radminHost.trim().isNotEmpty;

  static AppSettings compiledRadminSettings({bool setupComplete = false}) {
    if (hasCompiledRadminHost) {
      return AppSettings.forRadminHost(radminHost, setupComplete: setupComplete);
    }
    return AppSettings.localhost.copyWith(setupComplete: setupComplete);
  }
}

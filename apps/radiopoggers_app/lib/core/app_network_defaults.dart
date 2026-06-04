import '../models/app_settings.dart';

/// Host da VPN — nunca commitar IP real no código publicado.
///
/// Build privado (só na sua máquina):
/// `flutter build windows --dart-define=RADIOPOGGERS_VPN_HOST=SEU.IP.AQUI`
/// (aceita também `RADIOPOGGERS_RADMIN_HOST` por compatibilidade)
abstract final class AppNetworkDefaults {
  static const String _vpnFromEnv = String.fromEnvironment('RADIOPOGGERS_VPN_HOST');
  static const String _legacyRadmin = String.fromEnvironment('RADIOPOGGERS_RADMIN_HOST');

  static String get vpnHost {
    final v = _vpnFromEnv.trim();
    if (v.isNotEmpty) return v;
    return _legacyRadmin.trim();
  }

  static bool get hasCompiledVpnHost => vpnHost.isNotEmpty;

  @Deprecated('Use hasCompiledVpnHost')
  static bool get hasCompiledRadminHost => hasCompiledVpnHost;

  static AppSettings compiledVpnSettings({bool setupComplete = false}) {
    if (hasCompiledVpnHost) {
      return AppSettings.forVpnHost(vpnHost, setupComplete: setupComplete);
    }
    return AppSettings.localhost.copyWith(setupComplete: setupComplete);
  }

  @Deprecated('Use compiledVpnSettings')
  static AppSettings compiledRadminSettings({bool setupComplete = false}) =>
      compiledVpnSettings(setupComplete: setupComplete);
}

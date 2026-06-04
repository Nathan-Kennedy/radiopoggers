import 'package:flutter/material.dart';

import '../core/app_network_defaults.dart';
import '../models/app_settings.dart';
import '../services/app_controller.dart';
import '../widgets/vpn_host_dialog.dart';

/// Aplica preset VPN: IP compilado (build privado) ou pergunta ao usuário.
Future<bool> applyVpnPreset(BuildContext context, AppController controller) async {
  if (AppNetworkDefaults.hasCompiledVpnHost) {
    await controller.applySettings(
      AppSettings.forVpnHost(AppNetworkDefaults.vpnHost, setupComplete: true),
    );
    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Rede privada (VPN) aplicada.')),
      );
    }
    return true;
  }

  final host = await showVpnHostDialog(context);
  if (host == null || host.isEmpty) return false;

  await controller.applySettings(AppSettings.forVpnHost(host, setupComplete: true));
  if (context.mounted) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('VPN configurada para $host')),
    );
  }
  return true;
}

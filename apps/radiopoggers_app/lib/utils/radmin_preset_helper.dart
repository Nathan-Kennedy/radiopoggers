import 'package:flutter/material.dart';

import '../core/app_network_defaults.dart';
import '../models/app_settings.dart';
import '../services/app_controller.dart';
import '../widgets/radmin_host_dialog.dart';

/// Aplica preset Radmin: IP compilado (build privado) ou pergunta ao usuário.
Future<bool> applyRadminPreset(BuildContext context, AppController controller) async {
  if (AppNetworkDefaults.hasCompiledRadminHost) {
    await controller.applySettings(
      AppSettings.forRadminHost(AppNetworkDefaults.radminHost, setupComplete: true),
    );
    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Preset Radmin aplicado.')),
      );
    }
    return true;
  }

  final host = await showRadminHostDialog(context);
  if (host == null || host.isEmpty) return false;

  await controller.applySettings(AppSettings.forRadminHost(host, setupComplete: true));
  if (context.mounted) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('Radmin configurado para $host')),
    );
  }
  return true;
}

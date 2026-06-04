import 'package:flutter/material.dart';

import '../models/app_settings.dart';

/// Pede o IP/host do PC do operador na VPN (ZeroTier, Tailscale, etc.).
Future<String?> showVpnHostDialog(BuildContext context) async {
  final ctrl = TextEditingController();
  final result = await showDialog<String>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: const Text('IP na rede privada (VPN)'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Text(
            'O operador da rádio informa o IP do PC dele na VPN '
            '(ZeroTier, Tailscale ou similar). Esse valor não vem embutido no app público.',
          ),
          const SizedBox(height: 12),
          TextField(
            controller: ctrl,
            decoration: const InputDecoration(
              labelText: 'Host / IP',
              hintText: 'ex.: 10.147.20.12',
            ),
            autofocus: true,
            keyboardType: TextInputType.url,
            onSubmitted: (v) {
              final h = AppSettings.normalizeHost(v);
              if (h.isNotEmpty) Navigator.pop(ctx, h);
            },
          ),
        ],
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancelar')),
        FilledButton(
          onPressed: () {
            final host = AppSettings.normalizeHost(ctrl.text);
            if (host.isEmpty) return;
            Navigator.pop(ctx, host);
          },
          child: const Text('Aplicar'),
        ),
      ],
    ),
  );
  ctrl.dispose();
  return result;
}

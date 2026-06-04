import 'package:flutter/material.dart';

import '../models/app_settings.dart';

/// Pede o IP/host Radmin quando o app publicado não traz IP embutido.
Future<String?> showRadminHostDialog(BuildContext context) async {
  final ctrl = TextEditingController();
  final result = await showDialog<String>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: const Text('IP da rede Radmin'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Text(
            'O operador da rádio deve informar o IP dele na VPN. '
            'Esse valor não vem embutido no app baixado da internet.',
          ),
          const SizedBox(height: 12),
          TextField(
            controller: ctrl,
            decoration: const InputDecoration(
              labelText: 'Host / IP',
              hintText: 'ex.: 192.168.0.10',
            ),
            autofocus: true,
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

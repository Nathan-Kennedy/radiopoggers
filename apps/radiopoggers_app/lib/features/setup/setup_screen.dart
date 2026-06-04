import 'package:flutter/material.dart';

import '../../core/theme/app_colors.dart';
import '../../core/theme/app_decorations.dart';
import '../../core/app_network_defaults.dart';
import '../../models/app_settings.dart';
import '../../services/app_controller.dart';
import '../../utils/vpn_preset_helper.dart';

class SetupScreen extends StatefulWidget {
  const SetupScreen({super.key, required this.controller});
  final AppController controller;

  @override
  State<SetupScreen> createState() => _SetupScreenState();
}

class _SetupScreenState extends State<SetupScreen> {
  late final TextEditingController _api;
  late final TextEditingController _azura;
  late final TextEditingController _stream;
  late final TextEditingController _hls;

  @override
  void initState() {
    super.initState();
    final preset = widget.controller.settings.setupComplete
        ? widget.controller.settings
        : AppNetworkDefaults.compiledVpnSettings();
    _api = TextEditingController(text: preset.apiBaseUrl);
    _azura = TextEditingController(text: preset.azuracastBaseUrl);
    _stream = TextEditingController(text: preset.streamUrl);
    _hls = TextEditingController(text: preset.hlsUrl);
  }

  @override
  void dispose() {
    _api.dispose();
    _azura.dispose();
    _stream.dispose();
    _hls.dispose();
    super.dispose();
  }

  void _applyPreset(AppSettings preset) {
    _api.text = preset.apiBaseUrl;
    _azura.text = preset.azuracastBaseUrl;
    _stream.text = preset.streamUrl;
    _hls.text = preset.hlsUrl;
    setState(() {});
  }

  Future<void> _save() async {
    final next = AppSettings(
      apiBaseUrl: _api.text.trim(),
      azuracastBaseUrl: _azura.text.trim(),
      streamUrl: _stream.text.trim(),
      hlsUrl: _hls.text.trim(),
      stationShortcode: 'radio-no-grale',
      stationDisplayName: 'RADIO NO GRALE',
      pollIntervalMs: 3000,
      selectedNarrator: widget.controller.settings.selectedNarrator,
      setupComplete: true,
    );
    await widget.controller.applySettings(next);
    if (mounted && Navigator.canPop(context)) {
      Navigator.pop(context);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('CONFIGURAR RADIO'),
        flexibleSpace: Container(decoration: const BoxDecoration(gradient: AppDecorations.panelGlow)),
      ),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          Text(
            'RADIO NO GRALE',
            style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                  fontSize: 42,
                  letterSpacing: 2,
                  color: AppColors.accentHot,
                ),
          ),
          const SizedBox(height: 8),
          const Text(
            'Rede privada (ZeroTier, Tailscale…): informe o IP do PC do operador na VPN.',
            style: TextStyle(color: AppColors.muted),
          ),
          const SizedBox(height: 20),
          Wrap(
            spacing: 10,
            children: [
              FilledButton(
                onPressed: () => applyVpnPreset(context, widget.controller).then((ok) {
                  if (ok && mounted) {
                    final s = widget.controller.settings;
                    _applyPreset(s);
                  }
                }),
                child: const Text('Rede privada (VPN)'),
              ),
              OutlinedButton(onPressed: () => _applyPreset(AppSettings.localhost), child: const Text('Localhost')),
            ],
          ),
          const SizedBox(height: 24),
          TextField(controller: _api, decoration: const InputDecoration(labelText: 'API local (8765)')),
          const SizedBox(height: 12),
          TextField(controller: _azura, decoration: const InputDecoration(labelText: 'AzuraCast')),
          const SizedBox(height: 12),
          TextField(controller: _stream, decoration: const InputDecoration(labelText: 'Stream MP3')),
          const SizedBox(height: 12),
          TextField(controller: _hls, decoration: const InputDecoration(labelText: 'Stream HLS')),
          const SizedBox(height: 28),
          FilledButton(onPressed: _save, child: const Text('ENTRAR NA ALTA CUPULA')),
        ],
      ),
    );
  }
}

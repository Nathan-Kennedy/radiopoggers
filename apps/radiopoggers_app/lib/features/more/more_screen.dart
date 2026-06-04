import 'package:flutter/material.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/app_release_config.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_decorations.dart';
import '../../models/app_settings.dart';
import '../../services/app_controller.dart';
import '../../services/app_update_service.dart';
import '../../utils/radmin_preset_helper.dart';
import '../../widgets/screen_glow_header.dart';
import '../setup/setup_screen.dart';

class MoreScreen extends StatefulWidget {
  const MoreScreen({super.key, required this.controller});
  final AppController controller;

  @override
  State<MoreScreen> createState() => _MoreScreenState();
}

class _MoreScreenState extends State<MoreScreen> {
  String _versionLabel = '…';
  bool _checkingUpdate = false;

  @override
  void initState() {
    super.initState();
    _loadVersion();
  }

  Future<void> _loadVersion() async {
    final info = await PackageInfo.fromPlatform();
    if (mounted) setState(() => _versionLabel = '${info.version}+${info.buildNumber}');
  }

  Future<void> _checkUpdate() async {
    setState(() => _checkingUpdate = true);
    try {
      final info = await AppUpdateService.checkForUpdate();
      if (!mounted) return;
      if (info == null) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Você já está na versão mais recente.')));
        return;
      }
      await showDialog<void>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('Atualização encontrada'),
          content: Text('Versão ${info.version} disponível.'),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancelar')),
            FilledButton(
              onPressed: () async {
                Navigator.pop(ctx);
                await AppUpdateService.installUpdate(context, info);
              },
              child: const Text('Instalar'),
            ),
          ],
        ),
      );
    } finally {
      if (mounted) setState(() => _checkingUpdate = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final c = widget.controller;
    return Scaffold(
      appBar: ScreenGlowAppBar(
        meter: c.audioMeter,
        title: 'MAIS',
        pulseActive: c.audioReactiveLive,
        pulseIntensity: c.headerPulseIntensity,
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Container(
            decoration: AppDecorations.glassPanel(),
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('SOBRE', style: Theme.of(context).textTheme.labelSmall),
                const SizedBox(height: 8),
                Text('RADIO NO GRALE', style: Theme.of(context).textTheme.titleLarge),
                Text('Versão $_versionLabel', style: const TextStyle(color: AppColors.muted, fontSize: 12)),
                const SizedBox(height: 8),
                Text(
                  'Updates: github.com/${AppReleaseConfig.githubRepo}',
                  style: const TextStyle(fontSize: 11, color: AppColors.muted),
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),
          ListTile(
            leading: _checkingUpdate
                ? const SizedBox(width: 24, height: 24, child: CircularProgressIndicator(strokeWidth: 2))
                : const Icon(Icons.system_update_alt),
            title: const Text('Verificar atualizações'),
            subtitle: const Text('Baixa da última release no GitHub'),
            onTap: _checkingUpdate ? null : _checkUpdate,
          ),
          const Divider(),
          Text('HISTÓRICO', style: Theme.of(context).textTheme.labelSmall),
          const SizedBox(height: 8),
          ...c.history.take(8).map((h) {
            final song = h['song'] as Map<String, dynamic>? ?? h;
            return ListTile(
              dense: true,
              title: Text(song['title']?.toString() ?? '—'),
              subtitle: Text(song['artist']?.toString() ?? ''),
            );
          }),
          const Divider(),
          ListTile(
            title: const Text('Usar preset Radmin (amigos na VPN)'),
            subtitle: const Text('Informe o IP do operador · API :8765'),
            onTap: () => applyRadminPreset(context, c),
          ),
          ListTile(
            title: const Text('Configuração de rede'),
            subtitle: Text(c.settings.apiBaseUrl),
            trailing: const Icon(Icons.chevron_right),
            onTap: () async {
              await Navigator.push<void>(
                context,
                MaterialPageRoute<void>(builder: (_) => SetupScreen(controller: c)),
              );
              await c.applySettings(c.settings.copyWith(setupComplete: true));
            },
          ),
          ListTile(
            title: const Text('Painel AzuraCast'),
            onTap: () => launchUrl(Uri.parse(c.settings.azuracastBaseUrl), mode: LaunchMode.externalApplication),
          ),
          ListTile(
            title: const Text('Áudio e uso legal'),
            onTap: () => launchUrl(
              Uri.parse('https://github.com/${AppReleaseConfig.githubRepo}/blob/main/docs/LEGAL_AUDIO.md'),
              mode: LaunchMode.externalApplication,
            ),
          ),
          ListTile(
            title: const Text('Preset Localhost'),
            onTap: () => c.applySettings(AppSettings.localhost.copyWith(setupComplete: true)),
          ),
          ListTile(
            title: const Text('Preset Radmin'),
            onTap: () => applyRadminPreset(context, c),
          ),
        ],
      ),
    );
  }
}

import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../core/theme/app_colors.dart';
import '../services/app_update_service.dart';

/// Bloqueia o app no Android (release) até instalar a APK da última release no GitHub.
class MandatoryUpdateGate extends StatefulWidget {
  const MandatoryUpdateGate({
    super.key,
    required this.child,
    this.enabled = true,
  });

  final Widget child;

  /// Quando false, repassa direto para [child] (ex.: debug ou desktop).
  final bool enabled;

  @override
  State<MandatoryUpdateGate> createState() => _MandatoryUpdateGateState();
}

class _MandatoryUpdateGateState extends State<MandatoryUpdateGate> {
  _GatePhase _phase = _GatePhase.checking;
  AppUpdateInfo? _info;
  double _progress = 0;
  String? _error;

  @override
  void initState() {
    super.initState();
    if (!widget.enabled) {
      _phase = _GatePhase.ready;
      return;
    }
    _runCheck();
  }

  Future<void> _runCheck() async {
    setState(() {
      _phase = _GatePhase.checking;
      _error = null;
      _progress = 0;
    });
    final info = await AppUpdateService.checkForUpdate();
    if (!mounted) return;
    if (info == null) {
      setState(() => _phase = _GatePhase.ready);
      return;
    }
    setState(() {
      _info = info;
      _phase = _GatePhase.updateRequired;
    });
  }

  Future<void> _downloadAndInstall() async {
    final info = _info;
    if (info == null) return;
    final url = info.androidDownloadUrl;
    if (url == null) {
      setState(() => _error = 'APK não encontrado na release do GitHub.');
      return;
    }

    setState(() {
      _phase = _GatePhase.downloading;
      _error = null;
      _progress = 0;
    });

    try {
      final path = await AppUpdateService.downloadAndroidApk(
        url,
        onProgress: (p) {
          if (mounted) setState(() => _progress = p);
        },
      );
      if (!mounted) return;
      setState(() => _phase = _GatePhase.installing);
      final err = await AppUpdateService.installAndroidApk(path);
      if (!mounted) return;
      if (err != null) {
        setState(() {
          _phase = _GatePhase.updateRequired;
          _error = err;
        });
      }
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _phase = _GatePhase.updateRequired;
        _error = e.toString();
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_phase == _GatePhase.ready) return widget.child;

    return PopScope(
      canPop: false,
      child: Scaffold(
        backgroundColor: AppColors.bg,
        body: SafeArea(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 32),
            child: _buildBody(context),
          ),
        ),
      ),
    );
  }

  Widget _buildBody(BuildContext context) {
    switch (_phase) {
      case _GatePhase.checking:
        return const _CenteredStatus(
          icon: Icons.system_update_alt,
          title: 'Verificando atualização…',
          subtitle: 'Aguarde um instante.',
        );
      case _GatePhase.downloading:
        return _UpdatePanel(
          title: 'Baixando atualização',
          subtitle: _info != null ? 'Versão ${_info!.version}' : null,
          progress: _progress,
          showProgress: true,
        );
      case _GatePhase.installing:
        return const _UpdatePanel(
          title: 'Abrindo instalador',
          subtitle:
              'Na tela do Android, toque em Instalar. Se pedir, permita instalar apps desta fonte e confirme a substituição do app.',
          showProgress: true,
          progress: 1,
        );
      case _GatePhase.updateRequired:
        final info = _info!;
        final hasApk = info.androidDownloadUrl != null;
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Icon(Icons.new_releases_outlined, size: 56, color: AppColors.accent),
            const SizedBox(height: 20),
            Text(
              'Atualização obrigatória',
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                    color: AppColors.text,
                    fontWeight: FontWeight.w700,
                  ),
            ),
            const SizedBox(height: 12),
            Text(
              'Para continuar usando a rádio, instale a versão ${info.version}. '
              'O download é feito aqui no app; depois o Android pede as permissões normais de instalação.',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: AppColors.muted),
            ),
            if (_error != null) ...[
              const SizedBox(height: 16),
              Text(_error!, style: const TextStyle(color: AppColors.danger)),
            ],
            const Spacer(),
            if (hasApk)
              FilledButton(
                onPressed: _downloadAndInstall,
                style: FilledButton.styleFrom(
                  backgroundColor: AppColors.accent,
                  minimumSize: const Size.fromHeight(52),
                ),
                child: const Text('Baixar e instalar'),
              )
            else
              FilledButton(
                onPressed: () => launchUrl(Uri.parse(info.releasePageUrl), mode: LaunchMode.externalApplication),
                style: FilledButton.styleFrom(
                  backgroundColor: AppColors.accent,
                  minimumSize: const Size.fromHeight(52),
                ),
                child: const Text('Abrir página da release'),
              ),
            const SizedBox(height: 12),
            TextButton(
              onPressed: _runCheck,
              child: const Text('Tentar de novo'),
            ),
          ],
        );
      case _GatePhase.ready:
        return widget.child;
    }
  }
}

enum _GatePhase { checking, updateRequired, downloading, installing, ready }

class _CenteredStatus extends StatelessWidget {
  const _CenteredStatus({
    required this.icon,
    required this.title,
    this.subtitle,
  });

  final IconData icon;
  final String title;
  final String? subtitle;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, size: 48, color: AppColors.accent),
          const SizedBox(height: 24),
          Text(title, style: Theme.of(context).textTheme.titleLarge?.copyWith(color: AppColors.text)),
          if (subtitle != null) ...[
            const SizedBox(height: 8),
            Text(subtitle!, style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: AppColors.muted)),
          ],
          const SizedBox(height: 32),
          const CircularProgressIndicator(color: AppColors.accent),
        ],
      ),
    );
  }
}

class _UpdatePanel extends StatelessWidget {
  const _UpdatePanel({
    required this.title,
    this.subtitle,
    this.progress = 0,
    this.showProgress = false,
  });

  final String title;
  final String? subtitle;
  final double progress;
  final bool showProgress;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const Spacer(),
        Text(
          title,
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                color: AppColors.text,
                fontWeight: FontWeight.w700,
              ),
        ),
        if (subtitle != null) ...[
          const SizedBox(height: 12),
          Text(
            subtitle!,
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: AppColors.muted),
          ),
        ],
        if (showProgress) ...[
          const SizedBox(height: 32),
          LinearProgressIndicator(
            value: progress > 0 && progress < 1 ? progress : null,
            color: AppColors.accent,
            backgroundColor: AppColors.line,
            minHeight: 6,
            borderRadius: BorderRadius.circular(3),
          ),
          if (progress > 0 && progress < 1)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Text(
                '${(progress * 100).round()}%',
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(color: AppColors.muted),
              ),
            ),
        ],
        const Spacer(flex: 2),
      ],
    );
  }
}

/// Ativa bloqueio de update obrigatório no Android em builds release.
bool mandatoryUpdateGateEnabled() {
  return !kIsWeb && Platform.isAndroid && kReleaseMode;
}

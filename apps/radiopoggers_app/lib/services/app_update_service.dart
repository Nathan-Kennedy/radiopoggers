import 'dart:convert';
import 'dart:io';

import 'package:archive/archive.dart';
import 'package:crypto/crypto.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:open_filex/open_filex.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:url_launcher/url_launcher.dart';

import '../core/app_release_config.dart';

class AppUpdateInfo {
  const AppUpdateInfo({
    required this.version,
    required this.tagName,
    required this.releasePageUrl,
    required this.windowsDownloadUrl,
    required this.androidDownloadUrl,
    this.windowsSha256,
  });

  final String version;
  final String tagName;
  final String releasePageUrl;
  final String? windowsDownloadUrl;
  final String? androidDownloadUrl;
  final String? windowsSha256;
}

class AppUpdateService {
  static bool _allowedHost(Uri uri) {
    final h = uri.host.toLowerCase();
    return h == 'github.com' || h.endsWith('.githubusercontent.com') || h == 'api.github.com';
  }

  static Future<AppUpdateInfo?> checkForUpdate() async {
    try {
      final pkg = await PackageInfo.fromPlatform();
      final current = pkg.version;
      final uri = Uri.parse('https://api.github.com/repos/${AppReleaseConfig.githubRepo}/releases/latest');
      final res = await http.get(uri, headers: {'Accept': 'application/vnd.github+json'}).timeout(const Duration(seconds: 12));
      if (res.statusCode != 200) return null;

      final json = jsonDecode(res.body) as Map<String, dynamic>;
      final tag = json['tag_name']?.toString() ?? '';
      final version = tag.startsWith('v') ? tag.substring(1) : tag;
      if (version.isEmpty || !_isNewer(version, current)) return null;

      String? winUrl;
      String? apkUrl;
      final assets = json['assets'] as List<dynamic>? ?? [];
      for (final a in assets) {
        if (a is! Map<String, dynamic>) continue;
        final name = a['name']?.toString() ?? '';
        final url = a['browser_download_url']?.toString();
        if (url == null || !_allowedHost(Uri.parse(url))) continue;
        if (name == AppReleaseConfig.windowsAssetName) winUrl = url;
        if (name == AppReleaseConfig.androidAssetName) apkUrl = url;
      }

      final sha = await _fetchWindowsSha256(json['html_url']?.toString() ?? '', assets);

      return AppUpdateInfo(
        version: version,
        tagName: tag,
        releasePageUrl: json['html_url']?.toString() ?? 'https://github.com/${AppReleaseConfig.githubRepo}/releases',
        windowsDownloadUrl: winUrl,
        androidDownloadUrl: apkUrl,
        windowsSha256: sha,
      );
    } catch (e) {
      if (kDebugMode) debugPrint('Update check: $e');
      return null;
    }
  }

  static Future<String?> _fetchWindowsSha256(String releasePage, List<dynamic> assets) async {
    try {
      String? sumsUrl;
      for (final a in assets) {
        if (a is Map && a['name'] == AppReleaseConfig.checksumsAssetName) {
          sumsUrl = a['browser_download_url']?.toString();
          break;
        }
      }
      if (sumsUrl == null) return null;
      final res = await http.get(Uri.parse(sumsUrl)).timeout(const Duration(seconds: 10));
      if (res.statusCode != 200) return null;
      for (final line in res.body.split('\n')) {
        if (line.contains(AppReleaseConfig.windowsAssetName)) {
          final parts = line.trim().split(RegExp(r'\s+'));
          if (parts.length >= 2) return parts.first.toLowerCase();
        }
      }
    } catch (_) {}
    return null;
  }

  static bool _isNewer(String remote, String current) {
    List<int> parse(String v) {
      return v.split('.').map((e) => int.tryParse(e.replaceAll(RegExp(r'[^0-9]'), '')) ?? 0).toList();
    }

    final a = parse(remote);
    final b = parse(current);
    for (var i = 0; i < 3; i++) {
      final av = i < a.length ? a[i] : 0;
      final bv = i < b.length ? b[i] : 0;
      if (av > bv) return true;
      if (av < bv) return false;
    }
    return false;
  }

  static Future<void> promptIfUpdateAvailable(BuildContext context) async {
    final info = await checkForUpdate();
    if (info == null || !context.mounted) return;
    await showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Nova versão disponível'),
        content: Text('Versão ${info.version} está no ar. Deseja instalar agora?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Depois')),
          FilledButton(
            onPressed: () async {
              Navigator.pop(ctx);
              await installUpdate(context, info);
            },
            child: const Text('Instalar'),
          ),
        ],
      ),
    );
  }

  static Future<void> installUpdate(BuildContext context, AppUpdateInfo info) async {
    if (Platform.isAndroid) {
      await _installAndroid(context, info);
    } else if (Platform.isWindows) {
      await _installWindows(context, info);
    } else {
      await launchUrl(Uri.parse(info.releasePageUrl), mode: LaunchMode.externalApplication);
    }
  }

  static Future<void> _installAndroid(BuildContext context, AppUpdateInfo info) async {
    final url = info.androidDownloadUrl;
    if (url == null) {
      _snack(context, 'APK não encontrado na release.');
      return;
    }
    _snack(context, 'Baixando atualização…');
    try {
      final dir = await getTemporaryDirectory();
      final path = p.join(dir.path, AppReleaseConfig.androidAssetName);
      await _download(url, path);
      final result = await OpenFilex.open(path);
      if (result.type != ResultType.done && context.mounted) {
        _snack(context, 'Abra o APK manualmente: $path');
      }
    } catch (e) {
      if (context.mounted) _snack(context, 'Falha no download: $e');
    }
  }

  static Future<void> _installWindows(BuildContext context, AppUpdateInfo info) async {
    final url = info.windowsDownloadUrl;
    if (url == null) {
      await launchUrl(Uri.parse(info.releasePageUrl), mode: LaunchMode.externalApplication);
      return;
    }
    _snack(context, 'Baixando atualização…');
    try {
      final dir = await getTemporaryDirectory();
      final zipPath = p.join(dir.path, AppReleaseConfig.windowsAssetName);
      await _download(url, zipPath);

      if (info.windowsSha256 != null) {
        final bytes = await File(zipPath).readAsBytes();
        final hash = sha256.convert(bytes).toString();
        if (hash != info.windowsSha256) {
          if (context.mounted) _snack(context, 'Checksum inválido. Abortado.');
          return;
        }
      }

      final extractDir = p.join(dir.path, 'rp-update-extract');
      if (Directory(extractDir).existsSync()) {
        await Directory(extractDir).delete(recursive: true);
      }
      await Directory(extractDir).create(recursive: true);
      final archive = ZipDecoder().decodeBytes(await File(zipPath).readAsBytes());
      for (final file in archive) {
        final outPath = p.join(extractDir, file.name);
        if (file.isFile) {
          await File(outPath).create(recursive: true);
          await File(outPath).writeAsBytes(file.content as List<int>);
        } else {
          await Directory(outPath).create(recursive: true);
        }
      }

      final exe = File(Platform.resolvedExecutable);
      final installDir = exe.parent.path;
      final batPath = p.join(dir.path, 'rp-apply-update.bat');
      final bat = '''
@echo off
timeout /t 2 /nobreak >nul
xcopy /E /Y /I "${extractDir.replaceAll('/', '\\')}\\*" "${installDir.replaceAll('/', '\\')}"
start "" "${p.join(installDir, 'radiopoggers_app.exe').replaceAll('/', '\\')}"
''';
      await File(batPath).writeAsString(bat);
      await Process.start('cmd', ['/c', batPath], mode: ProcessStartMode.detached);
      if (context.mounted) {
        _snack(context, 'Reiniciando app com a nova versão…');
      }
      exit(0);
    } catch (e) {
      if (context.mounted) {
        _snack(context, 'Update: $e — abrindo página da release.');
        await launchUrl(Uri.parse(info.releasePageUrl), mode: LaunchMode.externalApplication);
      }
    }
  }

  static Future<void> _download(String url, String dest) async {
    final uri = Uri.parse(url);
    if (!_allowedHost(uri)) throw StateError('URL não permitida');
    final client = http.Client();
    try {
      final res = await client.get(uri).timeout(const Duration(minutes: 5));
      if (res.statusCode != 200) throw StateError('HTTP ${res.statusCode}');
      await File(dest).writeAsBytes(res.bodyBytes);
    } finally {
      client.close();
    }
  }

  static void _snack(BuildContext context, String msg) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
  }

  static Future<PackageInfo> packageInfo() => PackageInfo.fromPlatform();
}

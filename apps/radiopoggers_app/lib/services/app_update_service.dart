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
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';

import '../core/app_release_config.dart';

enum AppUpdateStatus { upToDate, available, checkFailed }

class AppUpdateCheckResult {
  const AppUpdateCheckResult({
    required this.status,
    this.info,
    this.message,
  });

  final AppUpdateStatus status;
  final AppUpdateInfo? info;
  final String? message;
}

class AppUpdateInfo {
  const AppUpdateInfo({
    required this.version,
    required this.tagName,
    required this.releasePageUrl,
    required this.windowsDownloadUrl,
    required this.androidDownloadUrl,
    this.windowsSha256,
    this.trustedApiBaseUrl,
    this.expectedApkSha256,
  });

  final String version;
  final String tagName;
  final String releasePageUrl;
  final String? windowsDownloadUrl;
  final String? androidDownloadUrl;
  final String? windowsSha256;

  /// Quando o APK vem da API do operador, downloads só desse host.
  final String? trustedApiBaseUrl;

  /// SHA256 do APK na API (detecta APK novo com mesmo número de versão).
  final String? expectedApkSha256;
}

class _ApiReleaseSnapshot {
  const _ApiReleaseSnapshot({
    required this.baseUrl,
    required this.json,
    required this.remoteLabel,
    required this.versionSource,
    required this.apkAvailable,
    this.apkSha256,
  });

  final String baseUrl;
  final Map<String, dynamic> json;
  final String remoteLabel;
  final String versionSource;
  final bool apkAvailable;
  final String? apkSha256;
}

class AppUpdateService {
  static const _installedApkShaKey = 'installed_apk_sha256';

  static bool _allowedGithubHost(Uri uri) {
    final h = uri.host.toLowerCase();
    return h == 'github.com' || h.endsWith('.githubusercontent.com') || h == 'api.github.com';
  }

  static bool _allowedDownloadUri(Uri uri, {String? trustedApiBaseUrl}) {
    if (_allowedGithubHost(uri)) return true;
    if (trustedApiBaseUrl == null || trustedApiBaseUrl.isEmpty) return false;
    final base = Uri.tryParse(trustedApiBaseUrl);
    if (base == null || base.host.isEmpty) return false;
    return uri.host.toLowerCase() == base.host.toLowerCase() && uri.port == base.port;
  }

  static String resolveDownloadUrl(String url, {String? apiBaseUrl}) {
    final trimmed = url.trim();
    final uri = Uri.tryParse(trimmed);
    if (uri != null && uri.hasScheme) return trimmed;
    if (apiBaseUrl == null || apiBaseUrl.isEmpty) return trimmed;
    return Uri.parse(apiBaseUrl).resolve(trimmed.startsWith('/') ? trimmed : '/$trimmed').toString();
  }

  /// `v1.2.3+4` → semver `1.2.3`, build `4`.
  static ({String semver, int build}) parseReleaseLabel(String label) {
    var t = label.trim();
    if (t.startsWith('v') || t.startsWith('V')) t = t.substring(1);
    final plus = t.indexOf('+');
    if (plus >= 0) {
      return (
        semver: t.substring(0, plus),
        build: int.tryParse(t.substring(plus + 1)) ?? 0,
      );
    }
    return (semver: t, build: 0);
  }

  static int _compareSemver(String a, String b) {
    List<int> parse(String v) {
      return v.split('.').map((e) => int.tryParse(e.replaceAll(RegExp(r'[^0-9]'), '')) ?? 0).toList();
    }

    final pa = parse(a);
    final pb = parse(b);
    for (var i = 0; i < 3; i++) {
      final av = i < pa.length ? pa[i] : 0;
      final bv = i < pb.length ? pb[i] : 0;
      if (av > bv) return 1;
      if (av < bv) return -1;
    }
    return 0;
  }

  static bool isUpdateRequired(String remoteTag, PackageInfo local) {
    final remote = parseReleaseLabel(remoteTag);
    final localBuild = int.tryParse(local.buildNumber) ?? 0;
    final cmp = _compareSemver(remote.semver, local.version);
    if (cmp > 0) return true;
    if (cmp < 0) return false;
    return remote.build > localBuild;
  }

  static String _remoteLabelFromApi(Map<String, dynamic> json) {
    final tag = json['tag_name']?.toString().trim() ?? '';
    if (tag.isNotEmpty) return tag.toLowerCase().startsWith('v') ? tag : 'v$tag';
    final ver = json['version']?.toString().trim() ?? '';
    if (ver.isEmpty) return '?';
    return ver.toLowerCase().startsWith('v') ? ver : 'v$ver';
  }

  static Future<bool> _apkOnServerDiffersFromInstalled(String? remoteSha) async {
    if (remoteSha == null || remoteSha.isEmpty) return false;
    final prefs = await SharedPreferences.getInstance();
    final saved = prefs.getString(_installedApkShaKey);
    if (saved == null || saved.isEmpty) return false;
    return saved.toLowerCase() != remoteSha.toLowerCase();
  }

  static Future<void> rememberInstalledApkSha(String sha) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_installedApkShaKey, sha.toLowerCase());
  }

  static Future<bool> _shouldOfferApiUpdate(String remoteLabel, PackageInfo pkg, String? remoteSha) async {
    if (remoteLabel.isEmpty || remoteLabel == '?') return false;
    if (isUpdateRequired(remoteLabel, pkg)) return true;
    return _apkOnServerDiffersFromInstalled(remoteSha);
  }

  static Future<AppUpdateCheckResult> checkForUpdate({String? apiBaseUrl}) async {
    final pkg = await PackageInfo.fromPlatform();
    final localLabel = '${pkg.version}+${pkg.buildNumber}';

    AppUpdateInfo? githubInfo;
    String? githubError;

    try {
      githubInfo = await _fetchGithubUpdate(pkg);
    } catch (e) {
      githubError = e.toString();
      if (kDebugMode) debugPrint('Update GitHub: $e');
    }

    if (githubInfo != null) {
      return AppUpdateCheckResult(status: AppUpdateStatus.available, info: githubInfo);
    }

    final api = apiBaseUrl?.trim();
    if (api != null && api.isNotEmpty) {
      try {
        final snapshot = await _fetchApiReleaseSnapshot(api);
        if (snapshot == null) {
          return AppUpdateCheckResult(
            status: AppUpdateStatus.checkFailed,
            message:
                'Update: API sem release ($api). No PC da rádio rode package-app-release.ps1 e reinicie a API.',
          );
        }
        final apiInfo = await _apiInfoFromSnapshot(snapshot, pkg);
        if (apiInfo != null) {
          return AppUpdateCheckResult(status: AppUpdateStatus.available, info: apiInfo);
        }
        final remote = snapshot.remoteLabel;
        final src = snapshot.versionSource;
        final apk = snapshot.apkAvailable ? 'APK no servidor' : 'sem APK no servidor';
        return AppUpdateCheckResult(
          status: AppUpdateStatus.upToDate,
          message:
              'App instalado: $localLabel. API ($src): $remote ($apk). '
              'Se você gerou APK novo e ainda não aparece aqui, atualize dist/app-release/ no PC da rádio '
              'e reinicie a API.',
        );
      } catch (e) {
        if (kDebugMode) debugPrint('Update API: $e');
        return AppUpdateCheckResult(
          status: AppUpdateStatus.checkFailed,
          message:
              'Não foi possível verificar atualização na API ($api). Confira se o servidor está no ar.',
        );
      }
    }

    if (githubError != null) {
      return AppUpdateCheckResult(
        status: AppUpdateStatus.checkFailed,
        message:
            'Release no GitHub (${AppReleaseConfig.githubRepo}) não encontrada. '
            'Publique a release ou configure a API com data/app-release.json e o APK em dist/app-release/.',
      );
    }

    return AppUpdateCheckResult(status: AppUpdateStatus.upToDate);
  }

  /// Compat: null = sem update ou falha silenciosa (evitar em UI nova).
  static Future<AppUpdateInfo?> checkForUpdateLegacy({String? apiBaseUrl}) async {
    final r = await checkForUpdate(apiBaseUrl: apiBaseUrl);
    if (r.status == AppUpdateStatus.available) return r.info;
    return null;
  }

  static Future<AppUpdateInfo?> _fetchGithubUpdate(PackageInfo pkg) async {
    final uri = Uri.parse('https://api.github.com/repos/${AppReleaseConfig.githubRepo}/releases/latest');
    final res = await http.get(uri, headers: {'Accept': 'application/vnd.github+json'}).timeout(const Duration(seconds: 12));
    if (res.statusCode == 404) return null;
    if (res.statusCode != 200) {
      throw StateError('GitHub HTTP ${res.statusCode}');
    }

    final json = jsonDecode(res.body) as Map<String, dynamic>;
    final tag = json['tag_name']?.toString() ?? '';
    if (tag.isEmpty || !isUpdateRequired(tag, pkg)) return null;

    final version = tag.startsWith('v') ? tag.substring(1) : tag;

    String? winUrl;
    String? apkUrl;
    final assets = json['assets'] as List<dynamic>? ?? [];
    for (final a in assets) {
      if (a is! Map<String, dynamic>) continue;
      final name = a['name']?.toString() ?? '';
      final url = a['browser_download_url']?.toString();
      if (url == null || !_allowedGithubHost(Uri.parse(url))) continue;
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
  }

  static Future<_ApiReleaseSnapshot?> _fetchApiReleaseSnapshot(String apiBaseUrl) async {
    final base = apiBaseUrl.replaceAll(RegExp(r'/+$'), '');
    final uri = Uri.parse('$base/api/app/release');
    final res = await http.get(uri).timeout(const Duration(seconds: 12));
    if (res.statusCode == 404) return null;
    if (res.statusCode != 200) {
      throw StateError('API HTTP ${res.statusCode}');
    }

    final json = jsonDecode(res.body) as Map<String, dynamic>;
    if (json['ok'] != true) return null;

    return _ApiReleaseSnapshot(
      baseUrl: base,
      json: json,
      remoteLabel: _remoteLabelFromApi(json),
      versionSource: json['version_source']?.toString() ?? 'app-release.json',
      apkAvailable: json['apk_available'] == true,
      apkSha256: json['apk_sha256']?.toString(),
    );
  }

  static Future<AppUpdateInfo?> _apiInfoFromSnapshot(_ApiReleaseSnapshot snapshot, PackageInfo pkg) async {
    final tag = snapshot.remoteLabel;
    final remoteSha = snapshot.apkSha256;
    if (!await _shouldOfferApiUpdate(tag, pkg, remoteSha)) return null;

    final json = snapshot.json;
    final version = (json['version']?.toString() ?? tag).trim();
    final displayVersion = version.startsWith('v') ? version.substring(1) : version;
    final apkRaw = json['android_download_url']?.toString();
    final apkUrl = apkRaw != null && apkRaw.isNotEmpty
        ? resolveDownloadUrl(apkRaw, apiBaseUrl: snapshot.baseUrl)
        : null;

    if (apkUrl == null) return null;

    return AppUpdateInfo(
      version: displayVersion,
      tagName: tag,
      releasePageUrl: json['release_page_url']?.toString() ?? '${snapshot.baseUrl}/api/app/release',
      windowsDownloadUrl: null,
      androidDownloadUrl: apkUrl,
      trustedApiBaseUrl: snapshot.baseUrl,
      expectedApkSha256: remoteSha,
    );
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

  static Future<void> promptIfUpdateAvailable(BuildContext context, {String? apiBaseUrl}) async {
    final result = await checkForUpdate(apiBaseUrl: apiBaseUrl);
    if (!context.mounted) return;
    if (result.status != AppUpdateStatus.available || result.info == null) return;
    final info = result.info!;
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
      await _installAndroidWithUi(context, info);
    } else if (Platform.isWindows) {
      await _installWindows(context, info);
    } else {
      await launchUrl(Uri.parse(info.releasePageUrl), mode: LaunchMode.externalApplication);
    }
  }

  static Future<String> downloadAndroidApk(
    String url, {
    void Function(double progress)? onProgress,
    String? trustedApiBaseUrl,
  }) async {
    final dir = await getTemporaryDirectory();
    final path = p.join(dir.path, AppReleaseConfig.androidAssetName);
    await _download(url, path, onProgress: onProgress, trustedApiBaseUrl: trustedApiBaseUrl);
    return path;
  }

  static Future<String?> installAndroidApk(String path) async {
    if (!File(path).existsSync()) return 'Arquivo APK não encontrado.';
    try {
      final result = await OpenFilex.open(path);
      if (result.type != ResultType.done) {
        return result.message.isNotEmpty ? result.message : 'Não foi possível abrir o instalador.';
      }
      return null;
    } catch (e) {
      return e.toString();
    }
  }

  static Future<void> _installAndroidWithUi(BuildContext context, AppUpdateInfo info) async {
    final url = info.androidDownloadUrl;
    if (url == null) {
      _snack(context, 'APK não encontrado na release.');
      return;
    }
    _snack(context, 'Baixando atualização…');
    try {
      final path = await downloadAndroidApk(url, trustedApiBaseUrl: info.trustedApiBaseUrl);
      final err = await installAndroidApk(path);
      if (err != null && context.mounted) {
        _snack(context, err);
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

  static Future<void> _download(
    String url,
    String dest, {
    void Function(double progress)? onProgress,
    String? trustedApiBaseUrl,
  }) async {
    final uri = Uri.parse(url);
    if (!_allowedDownloadUri(uri, trustedApiBaseUrl: trustedApiBaseUrl)) {
      throw StateError('URL de download não permitida');
    }
    final client = http.Client();
    try {
      final request = http.Request('GET', uri);
      final streamed = await client.send(request).timeout(const Duration(minutes: 8));
      if (streamed.statusCode != 200) throw StateError('HTTP ${streamed.statusCode}');
      final total = streamed.contentLength ?? 0;
      var received = 0;
      final file = File(dest);
      final sink = file.openWrite();
      await for (final chunk in streamed.stream) {
        sink.add(chunk);
        received += chunk.length;
        if (total > 0 && onProgress != null) {
          onProgress(received / total);
        }
      }
      await sink.flush();
      await sink.close();
      onProgress?.call(1);
      final hash = sha256.convert(await File(dest).readAsBytes()).toString();
      await rememberInstalledApkSha(hash);
    } finally {
      client.close();
    }
  }

  static void _snack(BuildContext context, String msg) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
  }

  static Future<PackageInfo> packageInfo() => PackageInfo.fromPlatform();
}

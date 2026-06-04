import 'dart:io';
import 'dart:typed_data';

import 'package:path_provider/path_provider.dart';

/// Armazena memes / drops do usuário no disco do app.
class CustomDropStorage {
  static const maxDurationMs = 5000;

  static Future<Directory> dropsDir() async {
    final base = await getApplicationDocumentsDirectory();
    final dir = Directory('${base.path}/custom_drops');
    if (!await dir.exists()) {
      await dir.create(recursive: true);
    }
    return dir;
  }

  static Future<String> resolvePath(String storedName) async {
    if (storedName.isEmpty) return '';
    final dir = await dropsDir();
    return '${dir.path}/$storedName';
  }

  static Future<File> fileFor(String storedName) async {
    final path = await resolvePath(storedName);
    return File(path);
  }

  static Future<bool> exists(String storedName) async {
    if (storedName.isEmpty) return false;
    return fileFor(storedName).then((f) => f.existsSync());
  }

  static Future<String> saveWavBytes(
    Uint8List wav, {
    required String slotLabel,
  }) async {
    final dir = await dropsDir();
    final name = '$slotLabel-${DateTime.now().millisecondsSinceEpoch}.wav';
    await File('${dir.path}/$name').writeAsBytes(wav, flush: true);
    return name;
  }

  static Future<String> importFile({
    required File source,
    required String slotLabel,
  }) async {
    final dir = await dropsDir();
    final ext = _extension(source.path);
    final name = '$slotLabel-${DateTime.now().millisecondsSinceEpoch}$ext';
    final dest = File('${dir.path}/$name');
    await source.copy(dest.path);
    return name;
  }

  static Future<void> deleteStored(String storedName) async {
    if (storedName.isEmpty) return;
    final f = await fileFor(storedName);
    if (await f.exists()) {
      await f.delete();
    }
  }

  static String _extension(String path) {
    final dot = path.lastIndexOf('.');
    if (dot < 0) return '.wav';
    final ext = path.substring(dot).toLowerCase();
    if (ext.length > 8) return '.wav';
    return ext;
  }
}

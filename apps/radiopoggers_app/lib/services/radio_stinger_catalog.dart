import 'dart:convert';

import 'package:flutter/services.dart';

/// Drops / imaging (Mixkit + manifest em assets).
class RadioStingerItem {
  const RadioStingerItem({
    required this.id,
    required this.label,
    required this.description,
    required this.category,
    required this.assetFile,
  });

  final String id;
  final String label;
  final String description;
  final String category;
  final String assetFile;
}

class RadioStingerCatalog {
  static const _manifestAsset = 'assets/radio_imaging/manifest.json';
  static const _assetPrefix = 'assets/radio_imaging/';

  static List<RadioStingerItem> _items = const [];
  static final Map<String, Uint8List> _cache = {};
  static bool _loaded = false;

  static List<RadioStingerItem> get items => List.unmodifiable(_items);

  static Future<void> ensureLoaded() async {
    if (_loaded) return;
    final raw = await rootBundle.loadString(_manifestAsset);
    final data = jsonDecode(raw) as Map<String, dynamic>;
    final list = data['items'] as List<dynamic>? ?? [];
    _items = [
      for (final entry in list)
        if (entry is Map<String, dynamic>)
          RadioStingerItem(
            id: entry['id']?.toString() ?? '',
            label: entry['label']?.toString() ?? entry['id']?.toString() ?? '',
            description: entry['description']?.toString() ?? '',
            category: entry['category']?.toString() ?? 'fx',
            assetFile: entry['file']?.toString() ?? '',
          ),
    ].where((e) => e.id.isNotEmpty && e.assetFile.isNotEmpty).toList();
    _loaded = true;
  }

  static RadioStingerItem? find(String id) {
    for (final item in _items) {
      if (item.id == id) return item;
    }
    return null;
  }

  static String get defaultId => _items.isNotEmpty ? _items.first.id : 'sweep_express';

  static Future<void> preload(String id) async {
    await ensureLoaded();
    if (id.isNotEmpty) await loadBytes(id);
  }

  static Future<Uint8List> loadBytes(String id) async {
    await ensureLoaded();
    final cached = _cache[id];
    if (cached != null) return cached;

    final item = find(id);
    if (item == null) {
      throw StateError('Stinger desconhecido: $id');
    }
    final data = await rootBundle.load('$_assetPrefix${item.assetFile}');
    final bytes = data.buffer.asUint8List();
    _cache[id] = bytes;
    return bytes;
  }
}

import 'package:shared_preferences/shared_preferences.dart';

import 'dart:convert';

import '../core/app_network_defaults.dart';
import '../models/app_settings.dart';
import '../models/voice_drop_effects_config.dart';
import '../models/voice_drop_stinger_config.dart';
import 'voice_drop_processor.dart';

class SettingsStore {
  static const _keyApi = 'api_base_url';
  static const _keyAzura = 'azuracast_base_url';
  static const _keyStream = 'stream_url';
  static const _keyHls = 'hls_url';
  static const _keyShortcode = 'station_shortcode';
  static const _keyStationName = 'station_display_name';
  static const _keyPoll = 'poll_interval_ms';
  static const _keyNarrator = 'selected_narrator';
  static const _keySetup = 'setup_complete';
  static const _keyListener = 'listener_id';
  static const _keyPresetVersion = 'settings_preset_version';
  static const _keyVoiceDropGain = 'voice_drop_gain';
  static const _keyVoiceDropEffects = 'voice_drop_effects_json';
  static const _keyVoiceDropStinger = 'voice_drop_stinger_json';
  static const _presetVersion = 2;

  Future<AppSettings> load() async {
    final prefs = await SharedPreferences.getInstance();
    final storedPresetVersion = prefs.getInt(_keyPresetVersion) ?? 0;
    if (storedPresetVersion < _presetVersion) {
      await prefs.setInt(_keyPresetVersion, _presetVersion);
    }
    if (!prefs.containsKey(_keyApi)) {
      return AppNetworkDefaults.compiledVpnSettings(setupComplete: false);
    }
    final fallback = AppSettings.localhost;
    return AppSettings(
      apiBaseUrl: prefs.getString(_keyApi) ?? fallback.apiBaseUrl,
      azuracastBaseUrl: prefs.getString(_keyAzura) ?? fallback.azuracastBaseUrl,
      streamUrl: prefs.getString(_keyStream) ?? fallback.streamUrl,
      hlsUrl: prefs.getString(_keyHls) ?? fallback.hlsUrl,
      stationShortcode: prefs.getString(_keyShortcode) ?? 'radio-no-grale',
      stationDisplayName: prefs.getString(_keyStationName) ?? 'RADIO NO GRALE',
      pollIntervalMs: prefs.getInt(_keyPoll) ?? 3000,
      selectedNarrator: prefs.getString(_keyNarrator) ?? 'miku',
      setupComplete: prefs.getBool(_keySetup) ?? false,
    );
  }

  Future<void> save(AppSettings settings) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_keyApi, settings.apiBaseUrl.trim().replaceAll(RegExp(r'/+$'), ''));
    await prefs.setString(_keyAzura, settings.azuracastBaseUrl.trim().replaceAll(RegExp(r'/+$'), ''));
    await prefs.setString(_keyStream, settings.streamUrl.trim());
    await prefs.setString(_keyHls, settings.hlsUrl.trim());
    await prefs.setString(_keyShortcode, settings.stationShortcode);
    await prefs.setString(_keyStationName, settings.stationDisplayName);
    await prefs.setInt(_keyPoll, settings.pollIntervalMs);
    await prefs.setString(_keyNarrator, settings.selectedNarrator);
    await prefs.setBool(_keySetup, settings.setupComplete);
  }

  Future<double> getVoiceDropGain() async {
    final prefs = await SharedPreferences.getInstance();
    final stored = prefs.getDouble(_keyVoiceDropGain) ?? VoiceDropProcessor.defaultGain;
    // Migra valores antigos (ex.: 3.2 = “320%” no sistema anterior).
    if (stored > VoiceDropProcessor.maxGain) {
      return VoiceDropProcessor.defaultGain;
    }
    return stored.clamp(VoiceDropProcessor.minGain, VoiceDropProcessor.maxGain);
  }

  Future<VoiceDropEffectsConfig> getVoiceDropEffects() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_keyVoiceDropEffects);
    if (raw == null || raw.isEmpty) return VoiceDropEffectsConfig.defaults;
    try {
      return VoiceDropEffectsConfig.fromJson(jsonDecode(raw) as Map<String, dynamic>);
    } catch (_) {
      return VoiceDropEffectsConfig.defaults;
    }
  }

  Future<void> saveVoiceDropEffects(VoiceDropEffectsConfig config) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_keyVoiceDropEffects, jsonEncode(config.toJson()));
  }

  Future<VoiceDropStingerConfig> getVoiceDropStinger() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_keyVoiceDropStinger);
    if (raw == null || raw.isEmpty) return VoiceDropStingerConfig.defaults;
    try {
      return VoiceDropStingerConfig.fromJson(jsonDecode(raw) as Map<String, dynamic>);
    } catch (_) {
      return VoiceDropStingerConfig.defaults;
    }
  }

  Future<void> saveVoiceDropStinger(VoiceDropStingerConfig config) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_keyVoiceDropStinger, jsonEncode(config.toJson()));
  }

  Future<void> setVoiceDropGain(double gain) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setDouble(
      _keyVoiceDropGain,
      gain.clamp(VoiceDropProcessor.minGain, VoiceDropProcessor.maxGain),
    );
  }

  Future<String> getListenerId() async {
    final prefs = await SharedPreferences.getInstance();
    var id = prefs.getString(_keyListener);
    if (id == null || id.isEmpty) {
      id = 'app-${DateTime.now().millisecondsSinceEpoch}';
      await prefs.setString(_keyListener, id);
    }
    return id;
  }
}

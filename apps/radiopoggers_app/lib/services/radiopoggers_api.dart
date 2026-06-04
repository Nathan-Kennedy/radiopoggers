import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/app_settings.dart';

class RadiopoggersApi {
  RadiopoggersApi(this.settings);

  AppSettings settings;
  final http.Client _client = http.Client();

  Uri _uri(String path, [Map<String, String>? query]) {
    final base = settings.apiBaseUrl.replaceAll(RegExp(r'/+$'), '');
    return Uri.parse('$base$path').replace(queryParameters: query);
  }

  Future<Map<String, dynamic>> health() async {
    final r = await _client.get(_uri('/api/health')).timeout(const Duration(seconds: 8));
    return _decode(r);
  }

  Future<Map<String, dynamic>> nowPlaying() async {
    final r = await _client
        .get(_uri('/api/nowplaying', {'_': '${DateTime.now().millisecondsSinceEpoch}'}))
        .timeout(const Duration(seconds: 12));
    return _decode(r);
  }

  Future<Map<String, dynamic>> library({
    String q = '',
    String artist = '',
    String album = '',
    int limit = 100,
    int offset = 0,
    bool refresh = false,
  }) async {
    final query = <String, String>{
      'limit': '$limit',
      'offset': '$offset',
      if (q.isNotEmpty) 'q': q,
      if (artist.isNotEmpty) 'artist': artist,
      if (album.isNotEmpty) 'album': album,
      if (refresh) 'refresh': '1',
    };
    final r = await _client.get(_uri('/api/library', query)).timeout(const Duration(seconds: 30));
    return _decode(r);
  }

  Future<Map<String, dynamic>> libraryFilters({bool refresh = false}) async {
    final r = await _client
        .get(_uri('/api/library/filters', refresh ? {'refresh': '1'} : null))
        .timeout(const Duration(seconds: 20));
    return _decode(r);
  }

  String libraryPreviewUrl(String trackId) {
    final id = Uri.encodeComponent(trackId);
    return '${settings.apiBaseUrl.replaceAll(RegExp(r'/+$'), '')}/api/library/preview/$id';
  }

  Future<Map<String, dynamic>> libraryRequest(String trackId) async {
    final r = await _client
        .post(
          _uri('/api/library/request'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'track_id': trackId}),
        )
        .timeout(const Duration(seconds: 60));
    return _decode(r);
  }

  Future<Map<String, dynamic>> audienceCount() async {
    final r = await _client.get(_uri('/api/audience/count')).timeout(const Duration(seconds: 8));
    return _decode(r);
  }

  Future<Map<String, dynamic>> audienceHeartbeat({
    required String listenerId,
    required bool playing,
  }) async {
    final r = await _client
        .post(
          _uri('/api/audience/heartbeat'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'listener_id': listenerId, 'playing': playing}),
        )
        .timeout(const Duration(seconds: 8));
    return _decode(r);
  }

  Future<Map<String, dynamic>?> fetchActiveVoiceDrop() async {
    try {
      final r = await _client.get(_uri('/api/voice-drop/active')).timeout(const Duration(seconds: 8));
      final data = _decode(r);
      final drop = data['voice_drop'];
      if (drop is Map<String, dynamic>) return drop;
      if (drop is Map) return drop.cast<String, dynamic>();
      return null;
    } catch (_) {
      return null;
    }
  }

  Future<Map<String, dynamic>> voteActive() async {
    final r = await _client.get(_uri('/api/vote/active')).timeout(const Duration(seconds: 8));
    return _decode(r);
  }

  Future<Map<String, dynamic>> voteStart({
    required String type,
    required String proposerId,
    Map<String, dynamic>? payload,
  }) async {
    final r = await _client
        .post(
          _uri('/api/vote/start'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'type': type, 'proposer_id': proposerId, 'payload': payload ?? {}}),
        )
        .timeout(const Duration(seconds: 12));
    return _decode(r);
  }

  Future<Map<String, dynamic>> voteCast({
    required String voteId,
    required String listenerId,
    required String choice,
  }) async {
    final r = await _client
        .post(
          _uri('/api/vote/cast'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'vote_id': voteId, 'listener_id': listenerId, 'choice': choice}),
        )
        .timeout(const Duration(seconds: 12));
    return _decode(r);
  }

  Future<Map<String, dynamic>> voteExecuteDirect({
    required String type,
    required String proposerId,
    required String choice,
    Map<String, dynamic>? payload,
  }) async {
    final r = await _client
        .post(
          _uri('/api/vote/execute-direct'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'type': type,
            'proposer_id': proposerId,
            'choice': choice,
            'payload': payload ?? {},
          }),
        )
        .timeout(const Duration(seconds: 12));
    return _decode(r);
  }

  Future<Map<String, dynamic>> voiceDropUpload({
    required List<int> bytes,
    required String mimeType,
    required int durationMs,
    required String listenerId,
  }) async {
    final r = await _client
        .post(
          _uri('/api/voice-drop'),
          headers: {
            'Content-Type': mimeType,
            'X-Duration-Ms': '$durationMs',
            'X-Listener-Id': listenerId,
            'X-Client-Radio-Processed': '1',
          },
          body: bytes,
        )
        .timeout(const Duration(seconds: 120));
    return _decode(r);
  }

  Future<Map<String, dynamic>> hoshinoNarrate({
    required String title,
    required String artist,
    String album = '',
    String genre = '',
    String moment = 'track_change',
  }) async {
    final r = await _client
        .post(
          _uri('/api/hoshino/narrate'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'title': title,
            'artist': artist,
            'album': album,
            'genre': genre,
            'moment': moment,
          }),
        )
        .timeout(const Duration(seconds: 90));
    return _decode(r);
  }

  Future<Map<String, dynamic>> inspectSpotify(String spotifyUrl) async {
    final r = await _client
        .get(_uri('/api/import-spotify/inspect', {'spotifyUrl': spotifyUrl}))
        .timeout(const Duration(seconds: 20));
    return _decode(r);
  }

  Future<Map<String, dynamic>> stationQueue({int limit = 48}) async {
    final r = await _client.get(_uri('/api/station-queue', {'limit': '$limit'})).timeout(const Duration(seconds: 15));
    return _decode(r);
  }

  Future<Map<String, dynamic>> importSpotify(String spotifyUrl) async {
    final r = await _client
        .post(
          _uri('/api/import-spotify'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'spotifyUrl': spotifyUrl}),
        )
        .timeout(const Duration(seconds: 30));
    final data = jsonDecode(r.body) as Map<String, dynamic>;
    if (r.statusCode >= 400 || data['ok'] == false) {
      throw Exception(data['error']?.toString() ?? 'HTTP ${r.statusCode}');
    }
    return data;
  }

  Future<Map<String, dynamic>> importSpotifyStatus({String jobId = ''}) async {
    final query = jobId.isNotEmpty ? {'job_id': jobId} : null;
    final r = await _client.get(_uri('/api/import-spotify/status', query)).timeout(const Duration(seconds: 8));
    return _decode(r);
  }

  Future<Map<String, dynamic>> manifest() async {
    final r = await _client.get(_uri('/api/manifest')).timeout(const Duration(seconds: 12));
    return _decode(r);
  }

  String voiceDropFileUrl(String dropId) {
    final id = Uri.encodeComponent(dropId);
    return '${settings.apiBaseUrl.replaceAll(RegExp(r'/+$'), '')}/api/voice-drop/file/$id';
  }

  Map<String, dynamic> _decode(http.Response r) {
    Map<String, dynamic> data = {};
    try {
      data = jsonDecode(r.body) as Map<String, dynamic>;
    } catch (_) {
      if (r.statusCode >= 400) {
        throw Exception('Resposta invalida (HTTP ${r.statusCode})');
      }
    }
    if (r.statusCode >= 400 || data['ok'] == false) {
      throw Exception(data['error']?.toString() ?? 'HTTP ${r.statusCode}');
    }
    return data;
  }

  void dispose() => _client.close();
}

/// Textos e formatação do overlay de votação (alinhado ao site).
abstract final class VoteUi {
  static String formatTimer(num? seconds) {
    final total = (seconds ?? 0).toInt().clamp(0, 9999);
    final m = total ~/ 60;
    final s = total % 60;
    return '${m.toString().padLeft(2, '0')}:${s.toString().padLeft(2, '0')}';
  }

  static String eyebrow(Map<String, dynamic> vote) {
    if (vote['solo'] == true) return 'SÓ VOCÊ NO AR';
    return 'VOTAÇÃO AO VIVO';
  }

  static String meta(Map<String, dynamic> vote) {
    if (vote['solo'] == true) {
      return '${vote['yes_label'] ?? 'Sim'} ou ${vote['no_label'] ?? 'Não'} — só você decide';
    }
    final eligible = vote['eligible_snapshot'] ?? 0;
    return '$eligible ouvintes ouvindo · ${vote['yes_label'] ?? 'Sim'} vs ${vote['no_label'] ?? 'Não'}';
  }

  static String statusForPhase(Map<String, dynamic> vote) {
    final phase = vote['phase']?.toString() ?? '';
    final type = vote['type']?.toString() ?? '';
    final duration = _durationSec(vote);

    if (phase == 'executing') {
      return 'Executando o veredito da galera...';
    }
    if (phase == 'closed') {
      return vote['message']?.toString() ??
          (vote['execution'] as Map?)?['message']?.toString() ??
          'Votação encerrada.';
    }
    if (phase == 'lottery') {
      return 'Empate! Sorteio rock no ar...';
    }
    if (vote['solo'] == true) {
      return 'Confirma em até ${duration}s — ao votar, a troca é na hora.';
    }
    return switch (type) {
      'skip_track' => 'Vote agora — ${duration}s. Empate vira sorteio rock: pula ou deixa rolar.',
      'library_request' => 'Vote agora — ${duration}s. Tocar já pula pra faixa; Na fila entra sem pular. Empate = sorteio.',
      'library_clear' => 'Vote agora — ${duration}s. Zerar apaga a playlist local. Empate = sorteio.',
      'spotify_import' => 'Vote agora — ${duration}s. Tocar já começa a playlist; Na fila só enfileira. Empate = sorteio.',
      _ => 'Vote agora — ${duration}s. Quem não votar conta como não. Empate = sorteio.',
    };
  }

  static int _durationSec(Map<String, dynamic> vote) {
    if (vote['solo'] == true) {
      return ((vote['duration_sec'] as num?) ?? 6).toInt().clamp(1, 120);
    }
    return ((vote['duration_sec'] as num?) ?? 20).toInt().clamp(1, 120);
  }
}

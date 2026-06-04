import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../core/app_release_config.dart';
import '../core/theme/app_colors.dart';
import '../core/theme/app_decorations.dart';

/// Exibe o aviso jurídico de uso restrito da plataforma caseira.
Future<void> showLegalUsageDialog(BuildContext context) {
  return showDialog<void>(
    context: context,
    barrierColor: Colors.black87,
    builder: (ctx) => const _LegalUsageDialog(),
  );
}

class _LegalUsageDialog extends StatelessWidget {
  const _LegalUsageDialog();

  static const String _docUrl =
      'https://github.com/${AppReleaseConfig.githubRepo}/blob/main/docs/LEGAL_AUDIO.md';

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final bodyStyle = theme.textTheme.bodyMedium?.copyWith(
      color: AppColors.muted,
      height: 1.55,
      fontSize: 13.5,
    );
    final headingStyle = theme.textTheme.titleSmall?.copyWith(
      color: AppColors.text,
      fontWeight: FontWeight.w700,
      letterSpacing: 0.4,
    );

    return Dialog(
      backgroundColor: Colors.transparent,
      insetPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 24),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 520, maxHeight: 640),
        child: DecoratedBox(
          decoration: AppDecorations.glassPanel(radius: BorderRadius.circular(12)),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Container(
                padding: const EdgeInsets.fromLTRB(20, 20, 12, 16),
                decoration: const BoxDecoration(
                  gradient: AppDecorations.panelGlow,
                  borderRadius: BorderRadius.vertical(top: Radius.circular(12)),
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Áudio e uso legal',
                            style: theme.textTheme.titleLarge?.copyWith(
                              fontWeight: FontWeight.w700,
                              letterSpacing: 0.2,
                            ),
                          ),
                          const SizedBox(height: 6),
                          Text(
                            'Aviso sobre a plataforma RADIO NO GRALE / RadioPoggers',
                            style: theme.textTheme.bodySmall?.copyWith(color: AppColors.muted),
                          ),
                        ],
                      ),
                    ),
                    IconButton(
                      visualDensity: VisualDensity.compact,
                      onPressed: () => Navigator.pop(context),
                      icon: const Icon(Icons.close, color: AppColors.muted),
                    ),
                  ],
                ),
              ),
              const Divider(height: 1, color: AppColors.lineStrong),
              Expanded(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.fromLTRB(20, 16, 20, 8),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '1. Natureza da plataforma',
                        style: headingStyle,
                      ),
                      const SizedBox(height: 8),
                      Text(
                        'A RadioPoggers (RADIO NO GRALE) é uma solução técnica caseira, '
                        'desenvolvida e operada em ambiente privado, destinada exclusivamente '
                        'à experimentação de rádio online entre um grupo fechado de amigos, '
                        'sem fins comerciais, sem distribuição pública do serviço e sem '
                        'disponibilização em lojas oficiais de aplicativos.',
                        style: bodyStyle,
                      ),
                      const SizedBox(height: 18),
                      Text('2. Uso autorizado', style: headingStyle),
                      const SizedBox(height: 8),
                      Text(
                        'O acesso, a instalação e o uso do aplicativo ou do painel web '
                        'pressupõem convite direto do operador e participação na rede privada '
                        'indicada por ele (por exemplo, ZeroTier ou Tailscale). É vedada a divulgação '
                        'do link de stream, das credenciais, do IP do operador ou de cópias '
                        'do software a terceiros não autorizados pelo grupo.',
                        style: bodyStyle,
                      ),
                      const SizedBox(height: 18),
                      Text('3. Conteúdo de áudio e direitos autorais', style: headingStyle),
                      const SizedBox(height: 8),
                      Text(
                        'Cada participante é responsável por garantir que as faixas enviadas, '
                        'solicitadas ou transmitidas possuam autorização adequada para o uso '
                        'pretendido — incluindo obras próprias, licenças que permitam '
                        'retransmissão/streaming ou autorização expressa de titulares. '
                        'Não utilize a plataforma para retransmitir obras sem licença, '
                        'contornar proteções tecnológicas (DRM), violar termos de serviços '
                        'de terceiros (Spotify, YouTube, etc.) ou disponibilizar acervo a '
                        'público além do círculo privado acordado.',
                        style: bodyStyle,
                      ),
                      const SizedBox(height: 18),
                      Text('4. Ferramentas auxiliares', style: headingStyle),
                      const SizedBox(height: 8),
                      Text(
                        'Integrações como metadados do Spotify ou importação local existem '
                        'apenas como apoio técnico. Qualquer download, conversão ou inclusão '
                        'no AzuraCast deve ocorrer somente quando houver direito ou permissão '
                        'prévia para tal uso.',
                        style: bodyStyle,
                      ),
                      const SizedBox(height: 18),
                      Text('5. Limitação de responsabilidade', style: headingStyle),
                      const SizedBox(height: 8),
                      Text(
                        'Os mantenedores da ferramenta fornecem software “no estado em que se '
                        'encontra”, sem garantia de adequação a fins específicos. O operador '
                        'e cada ouvinte assumem integralmente os riscos decorrentes do conteúdo '
                        'transmitido, do compartilhamento de arquivos e de eventual exposição '
                        'pública não autorizada da estação.',
                        style: bodyStyle,
                      ),
                      const SizedBox(height: 18),
                      Text('6. Conformidade no Brasil', style: headingStyle),
                      const SizedBox(height: 8),
                      Text(
                        'Se a estação deixar de ser uso estritamente privado entre amigos e '
                        'passar a operar de forma pública ou comercial, podem aplicar-se '
                        'obrigações adicionais (incluindo direitos conexos e ECAD). '
                        'Nesse caso, busque orientação jurídica especializada antes de '
                        'ampliar a audiência.',
                        style: bodyStyle,
                      ),
                      const SizedBox(height: 16),
                      DecoratedBox(
                        decoration: AppDecorations.brutalCard(),
                        child: Padding(
                          padding: const EdgeInsets.all(12),
                          child: Text(
                            'Este aviso não substitui consulta a advogado. '
                            'Ao continuar usando o app, você declara ter lido e compreendido '
                            'que a plataforma é caseira, privada e restrita ao grupo de amigos '
                            'autorizado pelo operador.',
                            style: bodyStyle?.copyWith(
                              fontSize: 12,
                              fontStyle: FontStyle.italic,
                              color: AppColors.text.withValues(alpha: 0.85),
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const Divider(height: 1, color: AppColors.lineStrong),
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
                child: Row(
                  children: [
                    TextButton(
                      onPressed: () => launchUrl(Uri.parse(_docUrl), mode: LaunchMode.externalApplication),
                      child: const Text('Documento completo'),
                    ),
                    const Spacer(),
                    FilledButton(
                      onPressed: () => Navigator.pop(context),
                      child: const Text('Li e compreendo'),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

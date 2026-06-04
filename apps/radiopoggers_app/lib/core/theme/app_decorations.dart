import 'package:flutter/material.dart';

import 'app_colors.dart';

abstract final class AppDecorations {
  static const LinearGradient accentGradient = LinearGradient(
    colors: [AppColors.accent, AppColors.accentHot],
    begin: Alignment.centerLeft,
    end: Alignment.centerRight,
  );

  /// Degradê suave vermelho → fundo escuro (cabeçalho das abas, igual ao MAIS).
  static const LinearGradient panelGlow = LinearGradient(
    colors: [Color(0x22E11D2E), Color(0x00070707)],
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
  );

  /// Variante com base sólida para headers customizados (fora do AppBar).
  static const LinearGradient screenHeaderGlow = LinearGradient(
    colors: [Color(0x22E11D2E), Color(0xFF070707)],
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
  );

  static BoxDecoration screenHeader({bool borderBottom = true}) => BoxDecoration(
        gradient: screenHeaderGlow,
        border: borderBottom
            ? Border(bottom: BorderSide(color: AppColors.lineStrong.withValues(alpha: 0.35)))
            : null,
      );

  static BoxDecoration glassPanel({BorderRadius? radius}) => BoxDecoration(
        color: AppColors.panel,
        borderRadius: radius ?? BorderRadius.circular(10),
        border: Border.all(color: AppColors.lineStrong),
        boxShadow: const [
          BoxShadow(color: Color(0x66000000), blurRadius: 24, offset: Offset(0, 8)),
        ],
      );

  static BoxDecoration brutalCard({Color? border}) => BoxDecoration(
        color: AppColors.bgElevated,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: border ?? AppColors.lineStrong, width: 1.5),
        boxShadow: [
          BoxShadow(
            color: AppColors.accent.withValues(alpha: 0.12),
            offset: const Offset(4, 4),
            blurRadius: 0,
          ),
        ],
      );

  static BoxDecoration vinylSlot() => BoxDecoration(
        color: Colors.black,
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: AppColors.lineStrong, width: 2),
        boxShadow: [
          BoxShadow(
            color: AppColors.accent.withValues(alpha: 0.35),
            blurRadius: 28,
            spreadRadius: -4,
          ),
        ],
      );

  static BoxDecoration shelfBoard() => BoxDecoration(
        gradient: const LinearGradient(
          colors: [AppColors.shelfWoodLight, AppColors.shelfWood, Color(0xFF120C08)],
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
        ),
        borderRadius: BorderRadius.circular(6),
        boxShadow: const [
          BoxShadow(color: Color(0x99000000), blurRadius: 16, offset: Offset(0, 6)),
        ],
        border: Border(
          top: BorderSide(color: AppColors.lineStrong.withValues(alpha: 0.5)),
          bottom: BorderSide(color: Colors.black, width: 4),
        ),
      );

  static BoxDecoration broadcastHero() => BoxDecoration(
        gradient: RadialGradient(
          center: const Alignment(0, -0.35),
          radius: 1.2,
          colors: [
            AppColors.accent.withValues(alpha: 0.22),
            AppColors.bgElevated,
            AppColors.bg,
          ],
        ),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.lineStrong.withValues(alpha: 0.45)),
      );

  static BoxDecoration recordSleeve({bool active = false}) => BoxDecoration(
        borderRadius: BorderRadius.circular(6),
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            const Color(0xFF222222),
            active ? const Color(0xFF2A1418) : const Color(0xFF141414),
          ],
        ),
        border: Border.all(
          color: active ? AppColors.accentHot : AppColors.lineStrong.withValues(alpha: 0.55),
          width: active ? 2 : 1,
        ),
        boxShadow: [
          if (active)
            BoxShadow(color: AppColors.accent.withValues(alpha: 0.45), blurRadius: 18, spreadRadius: -2)
          else
            const BoxShadow(color: Color(0x66000000), blurRadius: 8, offset: Offset(0, 4)),
        ],
      );

  static BoxDecoration storeSign() => BoxDecoration(
        gradient: accentGradient,
        borderRadius: BorderRadius.circular(4),
        boxShadow: [
          BoxShadow(color: AppColors.accent.withValues(alpha: 0.5), blurRadius: 20, offset: const Offset(0, 4)),
        ],
      );
}

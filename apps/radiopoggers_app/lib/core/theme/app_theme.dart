import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import 'app_colors.dart';

abstract final class AppTheme {
  static ThemeData build() {
    final base = ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      scaffoldBackgroundColor: AppColors.bg,
      colorScheme: const ColorScheme.dark(
        surface: AppColors.bgElevated,
        primary: AppColors.accent,
        secondary: AppColors.accentHot,
        onSurface: AppColors.text,
        outline: AppColors.lineStrong,
      ),
    );

    final display = GoogleFonts.bebasNeueTextTheme(base.textTheme).apply(
      bodyColor: AppColors.text,
      displayColor: AppColors.text,
    );
    final mono = GoogleFonts.ibmPlexMonoTextTheme(display);
    final body = display.copyWith(
      bodyLarge: const TextStyle(fontFamily: 'Inter', fontSize: 15, color: AppColors.text),
      bodyMedium: const TextStyle(fontFamily: 'Inter', fontSize: 14, color: AppColors.text),
      labelSmall: mono.labelSmall?.copyWith(
        letterSpacing: 2,
        fontSize: 10,
        color: AppColors.accent,
        fontWeight: FontWeight.w600,
      ),
    );

    return base.copyWith(
      textTheme: body,
      appBarTheme: AppBarTheme(
        backgroundColor: AppColors.bg,
        foregroundColor: AppColors.text,
        elevation: 0,
        titleTextStyle: GoogleFonts.bebasNeue(fontSize: 22, letterSpacing: 1),
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: AppColors.bgElevated,
        indicatorColor: AppColors.accentDim,
        labelTextStyle: WidgetStateProperty.resolveWith((states) {
          return GoogleFonts.ibmPlexMono(
            fontSize: 10,
            fontWeight: FontWeight.w600,
            letterSpacing: 1.2,
            color: states.contains(WidgetState.selected) ? AppColors.accentHot : AppColors.muted,
          );
        }),
      ),
      navigationRailTheme: NavigationRailThemeData(
        backgroundColor: AppColors.bgElevated,
        selectedIconTheme: const IconThemeData(color: AppColors.accentHot),
        unselectedIconTheme: const IconThemeData(color: AppColors.muted),
        indicatorColor: AppColors.accentDim,
        labelType: NavigationRailLabelType.all,
      ),
      cardTheme: CardThemeData(
        color: AppColors.panel,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(8),
          side: const BorderSide(color: AppColors.lineStrong),
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: AppColors.accent,
          foregroundColor: Colors.white,
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
          textStyle: GoogleFonts.ibmPlexMono(fontWeight: FontWeight.w600, fontSize: 12),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: AppColors.bgElevated,
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(4), borderSide: const BorderSide(color: AppColors.lineStrong)),
        enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(4), borderSide: const BorderSide(color: AppColors.line)),
        focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(4), borderSide: const BorderSide(color: AppColors.accent)),
        labelStyle: const TextStyle(color: AppColors.muted, fontSize: 12),
      ),
      dividerColor: AppColors.line,
      dialogTheme: DialogThemeData(
        backgroundColor: AppColors.bgElevated,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: const BorderSide(color: AppColors.lineStrong),
        ),
        titleTextStyle: GoogleFonts.bebasNeue(fontSize: 24, color: AppColors.text),
      ),
      bottomSheetTheme: const BottomSheetThemeData(
        backgroundColor: AppColors.bgElevated,
        modalBackgroundColor: AppColors.bgElevated,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
        ),
      ),
      snackBarTheme: SnackBarThemeData(
        backgroundColor: AppColors.bgElevated,
        contentTextStyle: const TextStyle(color: AppColors.text, fontSize: 13),
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(8),
          side: const BorderSide(color: AppColors.lineStrong),
        ),
      ),
    );
  }
}

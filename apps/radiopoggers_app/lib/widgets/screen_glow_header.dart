import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../core/theme/app_colors.dart';
import '../core/theme/app_decorations.dart';
import '../services/audio_reactive_meter.dart';
import 'header_pulse_backdrop.dart';

/// Faixa do pulse que invade o conteúdo abaixo do cabeçalho.
const double kHeaderPulseBleed = 34;

/// Cabeçalho fixo — degradê + pulse no canto superior direito.
class ScreenCleanHeaderBar extends StatelessWidget {
  const ScreenCleanHeaderBar({
    super.key,
    required this.title,
    required this.meter,
    this.actions,
    this.pulseActive = true,
    this.pulseIntensity = 0.45,
  });

  final String title;
  final AudioReactiveMeter meter;
  final List<Widget>? actions;
  final bool pulseActive;
  final double pulseIntensity;

  @override
  Widget build(BuildContext context) {
    final top = MediaQuery.paddingOf(context).top;
    final toolbarH = top + kToolbarHeight;

    return SizedBox(
      height: toolbarH,
      child: Stack(
        clipBehavior: Clip.none,
        children: [
          Container(
            height: toolbarH,
            decoration: const BoxDecoration(gradient: AppDecorations.panelGlow),
            padding: EdgeInsets.only(top: top, left: 8, right: 4),
            child: NavigationToolbar(
              leading: const SizedBox.shrink(),
              middle: Text(
                title,
                style: GoogleFonts.bebasNeue(fontSize: 26, letterSpacing: 0.5),
              ),
              trailing: actions == null || actions!.isEmpty
                  ? null
                  : Row(mainAxisSize: MainAxisSize.min, children: actions!),
              centerMiddle: false,
            ),
          ),
          Positioned(
            top: 0,
            right: 0,
            child: HeaderPulseBackdrop(
              meter: meter,
              active: pulseActive,
              intensity: pulseIntensity,
              width: math.min(MediaQuery.sizeOf(context).width * 0.52, 400),
              height: toolbarH * 0.95,
              bleedBottom: kHeaderPulseBleed,
            ),
          ),
        ],
      ),
    );
  }
}

/// SliverAppBar — título + ações + pulse à direita (estilo site).
class ScreenCleanSliverAppBar extends StatelessWidget {
  const ScreenCleanSliverAppBar({
    super.key,
    required this.meter,
    this.title,
    this.titleWidget,
    this.actions,
    this.pinned = true,
    this.pulseActive = true,
    this.pulseIntensity = 0.45,
  });

  final AudioReactiveMeter meter;
  final String? title;
  final Widget? titleWidget;
  final List<Widget>? actions;
  final bool pinned;
  final bool pulseActive;
  final double pulseIntensity;

  @override
  Widget build(BuildContext context) {
    final top = MediaQuery.paddingOf(context).top;
    final toolbarH = kToolbarHeight + top;
    final pulseW = math.min(MediaQuery.sizeOf(context).width * 0.52, 400.0);

    return SliverAppBar(
      pinned: pinned,
      clipBehavior: Clip.none,
      backgroundColor: AppColors.bg,
      surfaceTintColor: Colors.transparent,
      elevation: 0,
      scrolledUnderElevation: 0,
      toolbarHeight: kToolbarHeight,
      flexibleSpace: Stack(
        clipBehavior: Clip.none,
        fit: StackFit.expand,
        children: [
          const DecoratedBox(
            decoration: BoxDecoration(gradient: AppDecorations.panelGlow),
            child: SizedBox.expand(),
          ),
          Positioned(
            top: 0,
            right: 0,
            child: HeaderPulseBackdrop(
              meter: meter,
              active: pulseActive,
              intensity: pulseIntensity,
              width: pulseW,
              height: toolbarH * 0.92,
              bleedBottom: kHeaderPulseBleed,
            ),
          ),
        ],
      ),
      title: titleWidget ??
          (title != null
              ? Text(title!, style: GoogleFonts.bebasNeue(fontSize: 26, letterSpacing: 0.5))
              : null),
      actions: actions,
    );
  }
}

/// AppBar em Scaffold (ex.: Mais).
class ScreenGlowAppBar extends StatelessWidget implements PreferredSizeWidget {
  const ScreenGlowAppBar({
    super.key,
    required this.meter,
    this.title,
    this.titleWidget,
    this.actions,
    this.automaticallyImplyLeading = false,
    this.pulseActive = true,
    this.pulseIntensity = 0.45,
  });

  final AudioReactiveMeter meter;
  final String? title;
  final Widget? titleWidget;
  final List<Widget>? actions;
  final bool automaticallyImplyLeading;
  final bool pulseActive;
  final double pulseIntensity;

  @override
  Size get preferredSize => const Size.fromHeight(kToolbarHeight);

  @override
  Widget build(BuildContext context) {
    final top = MediaQuery.paddingOf(context).top;
    final toolbarH = kToolbarHeight + top;
    final pulseW = math.min(MediaQuery.sizeOf(context).width * 0.52, 400.0);

    return AppBar(
      automaticallyImplyLeading: automaticallyImplyLeading,
      clipBehavior: Clip.none,
      backgroundColor: AppColors.bg,
      surfaceTintColor: Colors.transparent,
      elevation: 0,
      scrolledUnderElevation: 0,
      toolbarHeight: kToolbarHeight,
      flexibleSpace: Stack(
        clipBehavior: Clip.none,
        fit: StackFit.expand,
        children: [
          const DecoratedBox(
            decoration: BoxDecoration(gradient: AppDecorations.panelGlow),
            child: SizedBox.expand(),
          ),
          Positioned(
            top: 0,
            right: 0,
            child: HeaderPulseBackdrop(
              meter: meter,
              active: pulseActive,
              intensity: pulseIntensity,
              width: pulseW,
              height: toolbarH * 0.92,
              bleedBottom: kHeaderPulseBleed,
            ),
          ),
        ],
      ),
      title: titleWidget ??
          (title != null
              ? Text(title!, style: GoogleFonts.bebasNeue(fontSize: 26, letterSpacing: 0.5))
              : null),
      actions: actions,
    );
  }
}

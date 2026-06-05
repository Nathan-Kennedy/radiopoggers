import 'package:flutter/material.dart';

import '../../services/app_controller.dart';
import '../../widgets/ambient_background.dart';
import '../../widgets/system_status_banner.dart';
import '../library/library_screen.dart';
import '../more/more_screen.dart';
import '../on_air/on_air_screen.dart';
import '../spotify/tocar_screen.dart';
import '../vote/vote_direct_modal.dart';
import '../vote/vote_overlay.dart';

class AppShell extends StatefulWidget {
  const AppShell({super.key, required this.controller});
  final AppController controller;

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  int _index = 0;

  @override
  Widget build(BuildContext context) {
    final c = widget.controller;
    final wide = MediaQuery.sizeOf(context).width >= 900;
    final pages = [
      OnAirScreen(controller: c),
      LibraryScreen(controller: c),
      TocarScreen(controller: c),
      MoreScreen(controller: c),
    ];

    final banner = c.systemBannerMessage;
    final bannerSeverity = c.systemBannerSeverity;

    return AmbientBackground(
      child: Stack(
        children: [
          Scaffold(
            backgroundColor: Colors.transparent,
            body: Column(
              children: [
                if (banner != null)
                  SystemStatusBanner(message: banner, severity: bannerSeverity),
                Expanded(
                  child: Row(
                    children: [
                      if (wide)
                        NavigationRail(
                          selectedIndex: _index,
                          onDestinationSelected: (i) => setState(() => _index = i),
                          labelType: NavigationRailLabelType.all,
                          destinations: const [
                            NavigationRailDestination(icon: Icon(Icons.sensors), label: Text('RÁDIO')),
                            NavigationRailDestination(icon: Icon(Icons.album_outlined), label: Text('ESTANTE')),
                            NavigationRailDestination(icon: Icon(Icons.play_circle_outline), label: Text('TOCAR')),
                            NavigationRailDestination(icon: Icon(Icons.more_horiz), label: Text('MAIS')),
                          ],
                        ),
                      Expanded(child: pages[_index]),
                    ],
                  ),
                ),
              ],
            ),
            bottomNavigationBar: wide
                ? null
                : NavigationBar(
                    selectedIndex: _index,
                    onDestinationSelected: (i) => setState(() => _index = i),
                    destinations: const [
                      NavigationDestination(icon: Icon(Icons.sensors), label: 'Rádio'),
                      NavigationDestination(icon: Icon(Icons.album_outlined), label: 'Estante'),
                      NavigationDestination(icon: Icon(Icons.play_circle_outline), label: 'Tocar'),
                      NavigationDestination(icon: Icon(Icons.more_horiz), label: 'Mais'),
                    ],
                  ),
          ),
          if (c.voteDirectVisible) VoteDirectModal(controller: c),
          if (c.voteOverlayVisible) VoteOverlay(controller: c),
        ],
      ),
    );
  }
}

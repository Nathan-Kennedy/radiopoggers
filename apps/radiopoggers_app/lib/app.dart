import 'package:flutter/material.dart';

import 'core/theme/app_theme.dart';
import 'features/setup/setup_screen.dart';
import 'features/shell/app_shell.dart';
import 'services/app_controller.dart';
import 'services/app_update_service.dart';
import 'widgets/mandatory_update_gate.dart';

class RadioPoggersApp extends StatefulWidget {
  const RadioPoggersApp({super.key});

  @override
  State<RadioPoggersApp> createState() => _RadioPoggersAppState();
}

class _RadioPoggersAppState extends State<RadioPoggersApp> {
  late final AppController controller;

  @override
  void initState() {
    super.initState();
    controller = AppController();
    controller.addListener(_onChange);
  }

  void _onChange() {
    setState(() {});
    _scheduleUpdateCheck();
  }

  bool _updateCheckScheduled = false;

  void _scheduleUpdateCheck() {
    if (mandatoryUpdateGateEnabled()) return;
    if (_updateCheckScheduled || controller.loading || !controller.settings.setupComplete) return;
    _updateCheckScheduled = true;
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      if (!mounted) return;
      await AppUpdateService.promptIfUpdateAvailable(context);
    });
  }

  @override
  void dispose() {
    controller.removeListener(_onChange);
    controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'RADIO NO GRALE',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.build(),
      home: controller.loading
          ? const Scaffold(body: Center(child: CircularProgressIndicator(color: Color(0xFFE11D2E))))
          : MandatoryUpdateGate(
              enabled: mandatoryUpdateGateEnabled(),
              child: controller.settings.setupComplete
                  ? AppShell(controller: controller)
                  : SetupScreen(controller: controller),
            ),
    );
  }
}

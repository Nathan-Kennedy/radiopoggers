(() => {
  "use strict";

  const defaultConfig = {
    azuracastBaseUrl: "http://localhost:8080",
    azuracastPanelUrl: "http://localhost:8080",
    stationShortcode: "radiopoggers",
    stationId: 0,
    streamUrl: "",
    streamMode: "hls",
    hlsUrl: "",
    nowPlayingMode: "auto",
    demoMode: "auto",
    demoNowPlayingUrl: "data/demo-nowplaying.json",
    demoAudio: true,
    localApiUrl: "http://127.0.0.1:8765",
    spotifyManifestUrl: "../data/spotify-imported.json",
    libraryCatalogUrl: "../data/library-catalog.json",
    libraryAutoRefreshMs: 15000,
    pollIntervalMs: 15000,
    mikuNarratorEnabled: true,
    mikuNarratorPlaybackGain: 1,
    mikuVoiceDetuneCents: 0,
    hoshinoVoicePlaybackRate: 1.0,
  streamProgressLatencySec: 0,
  streamProgressLatencyFallbackSec: 4,
  streamLoudnessNormalize: true,
  voteEnabled: true,
  voteDurationSec: 20,
  voteSoloDurationSec: 6,
  audienceHeartbeatMs: 12000,
  stationDisplayName: "ALTA CUPULA",
    fallbackCover: "assets/img/cover-fallback.svg"
  };

  const config = {
    ...defaultConfig,
    ...(window.RADIOPOGGERS_CONFIG || {})
  };

  const asciiFrames = window.RADIOPOGGERS_ASCII_FRAMES || [];
  const asciiGenerate = window.RADIOPOGGERS_ASCII_GENERATE;
  const asciiPaint = window.RADIOPOGGERS_ASCII_PAINT;
  const asciiPlayPaint = window.RADIOPOGGERS_ASCII_PLAY_PAINT;
  const asciiIdlePaint = window.RADIOPOGGERS_ASCII_IDLE_PAINT;
  const asciiOffPaint = window.RADIOPOGGERS_ASCII_OFF_PAINT;
  const asciiMikuPaint = window.RADIOPOGGERS_ASCII_MIKU_PAINT;
  const asciiHoshinoCaptionPaint = window.RADIOPOGGERS_ASCII_HOSHINO_CAPTION_PAINT;
  const asciiPickerMikuPaint = window.RADIOPOGGERS_ASCII_PICKER_MIKU_PAINT;
  const asciiPickerHoshinoPaint = window.RADIOPOGGERS_ASCII_PICKER_HOSHINO_PAINT;
  const asciiOffGifUrl = window.RADIOPOGGERS_ASCII_OFF_GIF_URL || "assets/ascii-animation%20off.gif";
  const asciiMikuFrameMs = Math.max(Number(window.RADIOPOGGERS_ASCII_MIKU_FRAME_MS) || asciiFrameMs, 40);
  const asciiInit = window.RADIOPOGGERS_ASCII_INIT;
  const asciiFrameMs = Math.max(Number(window.RADIOPOGGERS_ASCII_FRAME_MS) || 100, 40);

  const pollIntervalMs = Math.max(Number(config.pollIntervalMs) || 15000, 5000);
  const pollIntervalPlayingMs = Math.max(pollIntervalMs, 8000);
  const STREAM_RECONNECT_MS = 80;
  const STREAM_RECONNECT_COOLDOWN_MS = 1200;
  const STREAM_BUFFER_AHEAD_MIN_SEC = 0.35;
  const STREAM_STANDBY_START_MS = 2200;
  const fallbackCover = config.fallbackCover || defaultConfig.fallbackCover;
  const mobileHttpsPort = Math.max(Number(config.mobileHttpsPort) || 5443, 1);

  function isMobileDevice() {
    if (window.matchMedia?.("(pointer: coarse)").matches) {
      return true;
    }
    return /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent || "");
  }

  function getMobileHttpsFrontendUrl() {
    const host = window.location.hostname || "127.0.0.1";
    const path = window.location.pathname.includes("/frontend/")
      ? window.location.pathname
      : "/frontend/";
    return `https://${host}:${mobileHttpsPort}${path}`;
  }

  function maybeRedirectHttpToHttpsForMicrophone() {
    if (window.isSecureContext || window.location.protocol !== "http:") {
      return false;
    }

    const host = window.location.hostname || "";
    if (!host || host === "localhost" || host === "127.0.0.1") {
      return false;
    }

    const target = getMobileHttpsFrontendUrl();
    if (target === window.location.href) {
      return false;
    }

    try {
      sessionStorage.setItem("radiopoggers_https_redirect", target);
    }
    catch (error) {
      // Ignora.
    }

    window.location.replace(target);
    return true;
  }

  function isHttpsFrontendGateway() {
    return window.location.protocol === "https:" && Boolean(window.location.hostname);
  }

  function httpsGatewayOrigin() {
    return String(window.location.origin || "").replace(/\/+$/, "");
  }

  function configuredAzuracastHost() {
    try {
      return new URL(String(config.azuracastBaseUrl || "").trim()).hostname || "";
    }
    catch (error) {
      return "";
    }
  }

  function azuracastPublicBase() {
    if (isHttpsFrontendGateway()) {
      return `${httpsGatewayOrigin()}/azuracast`;
    }
    return normalizeBaseUrl(config.azuracastBaseUrl || "http://localhost");
  }

  function rewriteHttpResourceForHttpsGateway(rawUrl) {
    const raw = String(rawUrl || "").trim();
    if (!raw || !isHttpsFrontendGateway() || !/^https?:\/\//i.test(raw)) {
      return raw;
    }

    try {
      const parsed = new URL(raw);
      if (parsed.protocol !== "http:") {
        return raw;
      }

      const pageHost = window.location.hostname;
      const azHost = configuredAzuracastHost();
      if (parsed.hostname !== pageHost && parsed.hostname !== azHost && parsed.hostname !== "localhost" && parsed.hostname !== "127.0.0.1") {
        return raw;
      }

      return `${httpsGatewayOrigin()}/azuracast${parsed.pathname}${parsed.search}`;
    }
    catch (error) {
      return raw;
    }
  }

  function resolveArtUrl(url) {
    const raw = String(url || "").trim();
    if (!raw) {
      return fallbackCover;
    }

    if (/^https?:\/\//i.test(raw)) {
      try {
        const parsed = new URL(raw);

        const gatewayUrl = rewriteHttpResourceForHttpsGateway(raw);
        if (gatewayUrl !== raw) {
          return gatewayUrl;
        }

        if (parsed.hostname === "localhost" || parsed.hostname === "127.0.0.1") {
          const publicBase = azuracastPublicBase();
          if (publicBase) {
            return `${publicBase.replace(/\/+$/, "")}${parsed.pathname}${parsed.search}`;
          }
        }
      }
      catch (error) {
        return raw;
      }
      return raw;
    }

    if (raw.startsWith("/")) {
      const publicBase = azuracastPublicBase();
      return publicBase ? `${publicBase}${raw}` : raw;
    }

    return raw;
  }

  function bindCoverImageFallback() {
    if (document.body.dataset.coverFallbackBound === "1") {
      return;
    }
    document.body.dataset.coverFallbackBound = "1";
    document.body.addEventListener("error", (event) => {
      const target = event.target;
      if (!(target instanceof HTMLImageElement)) {
        return;
      }
      if (target.dataset.coverFallbackApplied === "1") {
        return;
      }
      if (String(target.src || "").includes("cover-fallback")) {
        return;
      }
      target.dataset.coverFallbackApplied = "1";
      target.src = fallbackCover;
    }, true);
  }

  const state = {
    nowPlayingKey: "",
    trackFollowUpTimer: null,
    trackBurstTimer: null,
    duration: 0,
    elapsedAtSync: 0,
    syncedAt: Date.now(),
    playedAt: 0,
    progressLatencySmooth: 0,
    mediaHandlersReady: false,
    activeDemoStream: false,
    demoAudio: null,
    playlistImportInProgress: false,
    shelfPreview: {
      trackId: "",
      title: "",
      radioWasPlaying: false
    },
    librarySearchTimer: null,
    libraryLoadGeneration: 0,
    libraryFetchController: null,
    libraryFiltersCache: null,
    libraryCatalogRevision: null,
    libraryCatalogWatcherTimer: null,
    libraryUsesStaticCatalog: false,
    resolvedLocalApiBase: "",
    azuracastRequestsAvailable: null,
    customPlaylist: [],
    uiCache: {
      coverArt: "",
      historyKey: "",
      listenerCount: "",
      streamQuality: "",
      automationState: "",
      liveLabel: "",
      trackTitle: "",
      trackArtist: "",
      trackAlbum: "",
      transmissionOnline: null
    },
    streamMonitor: {
      waitingSince: 0,
      recoveryTimer: null,
      recoveryAttempts: 0,
      baseStreamUrl: "",
      reconnecting: false,
      lastReconnectAt: 0,
      activeIsBackup: false,
      swapping: false,
      standbyPrimeTimer: null,
      bufferWatchTimer: null,
      lowBufferTicks: 0,
      hls: {
        primary: null,
        backup: null
      }
    },
    streamDuck: null,
    lastNowPlayingData: null,
    nowPlayingUnreachable: false,
    transmissionState: "connecting",
    maintenance: { active: false, level: "maintenance", message: "" },
    nowPlayingPollTimer: null,
    asciiLoopTimer: null,
    asciiMode: "idle",
    asciiOffGifFallback: false,
    audioPulse: {
      ctx: null,
      analyser: null,
      source: null,
      data: null,
      smoothLevel: 0,
      hotLevel: 0,
      raf: null,
      startTimer: null,
      mode: "",
      barSmooth: null,
      idlePhase: 0
    },
    voiceDrop: {
      listenerId: "",
      recording: false,
      uploading: false,
      ducking: false,
      apiReady: false,
      mikuSpeaking: false,
      mikuCaption: {
        active: false,
        exiting: false,
        fullText: "",
        raf: null,
        asciiTimer: null,
        asciiTick: 0,
        dismissTimer: null,
        exitTimer: null,
        playbackToken: 0,
        lastVisibleCount: -1,
        completed: false
      },
      pendingPlayback: null,
      pendingMikuDrop: null,
      inFlightDropIds: [],
      playedIds: [],
      recorder: null,
      stream: null,
      chunks: [],
      timer: null,
      tickTimer: null,
      startedAt: 0,
      lastPlayedDropId: "",
      playbackCtx: null,
      playbackSource: null,
      playbackToken: 0,
      previewPlaybackEnded: null,
      bufferCacheByDropId: {},
      sidechainAnalyser: null,
      waveRaf: null,
      waveform: null,
      fallbackOutputGain: null,
      fallbackOutputCtx: null
    },
    vote: {
      active: null,
      pendingDirect: null,
      eventSource: null,
      pollTimer: null,
      heartbeatTimer: null,
      cooldownTicker: null,
      actionCooldownSec: 45,
      actionCooldownRemainingSec: 0,
      countdownTimer: null,
      lotterySpinTimer: null,
      lastHandledClosedId: "",
      alertedVoteId: "",
      alertCtx: null
    },
    hoshino: {
      trackKey: "",
      trackChangeTimer: null,
      midSpoke: false,
      generating: false,
      lastSpokeAt: 0,
      activeCaptionNarrator: "miku"
    },
    narratorPicker: {
      asciiTimer: null,
      mikuTick: 0,
      hoshinoTick: 0,
      previewBusy: null,
      samples: {
        miku: [],
        hoshino: []
      }
    }
  };

  const RESUME_PLAYBACK_KEY = "radiopoggers_resume_playback";
  const CUSTOM_PLAYLIST_KEY = "radiopoggers_custom_playlist";
  const LISTENER_ID_KEY = "radiopoggers_listener_id";
  const VOTE_ACTION_COOLDOWN_TYPES = new Set(["skip_track", "library_request", "library_clear"]);
  const VOICE_DROP_MAX_MS = 15000;
  const VOICE_DROP_DUCK_RATIO = 0.16;
  const DUCK_FLOOR = 0.1;
  const STREAM_LOUDNESS_TARGET_RMS = 0.13;
  const STREAM_LOUDNESS_MAX_GAIN = 2.35;
  const STREAM_LOUDNESS_MIN_GAIN = 0.58;
  const STREAM_LOUDNESS_CALIBRATION_MS = 3400;
  const STREAM_LOUDNESS_CALIBRATION_DELAY_MS = 1400;
  const STREAM_LOUDNESS_MIN_SIGNAL_RMS = 0.006;
  const DUCK_ATTACK_SEC = 0.012;
  const DUCK_RELEASE_SEC = 0.48;
  const DUCK_PRE_DIP = 0.2;
  const VOICE_SIDECHAIN_SENSITIVITY = 4.4;
  const MIKU_LISTENER_ID = "miku-narrator";
  const HOSHINO_LISTENER_ID = "hoshino-narrator";
  const NARRATOR_STORAGE_KEY = "radiopoggers_narrator";
  const NARRATOR_LISTENER_IDS = new Set([MIKU_LISTENER_ID, HOSHINO_LISTENER_ID]);
  const MIKU_CAPTION_HOLD_AFTER_MS = 650;
  const MIKU_CAPTION_EXIT_MS = 420;
  const NARRATOR_PREVIEW_MANIFEST_URL = "assets/narrator-samples/manifest.json";

  const $ = (selector) => document.querySelector(selector);

  const els = {
    appShell: $("#appShell"),
    asciiBackdrop: $("#asciiBackdrop"),
    asciiBackdropOffGif: $("#asciiBackdropOffGif"),
    audioPulseLight: $("#audioPulseLight"),
    audioPulseCanvas: $("#audioPulseCanvas"),
    audio: $("#radioAudio"),
    audioBackup: $("#radioAudioBackup"),
    coverGlow: $("#coverGlow"),
    connectionStatus: $("#connectionStatus"),
    liveLabel: $("#liveLabel"),
    liveEyebrow: $("#liveLabel") ? $("#liveLabel").closest(".eyebrow") : null,
    trackSectionLabel: $("#trackSectionLabel"),
    progressLabel: $("#progressLabel"),
    stationTitle: $("#stationTitle"),
    listenerCount: $("#listenerCount"),
    streamQuality: $("#streamQuality"),
    automationState: $("#automationState"),
    coverArt: $("#coverArt"),
    trackMeta: $("#trackMeta"),
    trackTitle: $("#trackTitle"),
    trackArtist: $("#trackArtist"),
    trackAlbum: $("#trackAlbum"),
    elapsedTime: $("#elapsedTime"),
    durationTime: $("#durationTime"),
    progressFill: $("#progressFill"),
    playButton: $("#playButton"),
    skipTrackButton: $("#skipTrackButton"),
    muteButton: $("#muteButton"),
    muteLabel: $("#muteLabel"),
    volumeSlider: $("#volumeSlider"),
    streamMessage: $("#streamMessage"),
    historyList: $("#historyList"),
    spotifyImportForm: $("#spotifyImportForm"),
    spotifyUrlInput: $("#spotifyUrlInput"),
    spotifyImportButton: $("#spotifyImportButton"),
    spotifyImportStatus: $("#spotifyImportStatus"),
    spotifyPlaylistTitle: $("#spotifyPlaylistTitle"),
    spotifyPlaylistSummary: $("#spotifyPlaylistSummary"),
    spotifyPlaylistList: $("#spotifyPlaylistList"),
    librarySearchInput: $("#librarySearchInput"),
    libraryArtistFilter: $("#libraryArtistFilter"),
    libraryAlbumFilter: $("#libraryAlbumFilter"),
    librarySummary: $("#librarySummary"),
    libraryList: $("#libraryList"),
    shelfPreviewAudio: $("#shelfPreviewAudio"),
    shelfPreviewBar: $("#shelfPreviewBar"),
    shelfPreviewTitle: $("#shelfPreviewTitle"),
    shelfPreviewStop: $("#shelfPreviewStop"),
    libraryCustomPanel: $("#libraryCustomPanel"),
    libraryCustomCount: $("#libraryCustomCount"),
    libraryCustomHint: $("#libraryCustomHint"),
    libraryCustomList: $("#libraryCustomList"),
    libraryExportButton: $("#libraryExportButton"),
    libraryRequestButton: $("#libraryRequestButton"),
    libraryClearCustomButton: $("#libraryClearCustomButton"),
    voiceDropButton: $("#voiceDropButton"),
    voiceDropStopButton: $("#voiceDropStopButton"),
    voiceDropRecording: $("#voiceDropRecording"),
    voiceDropWave: $("#voiceDropWave"),
    voiceDropTimer: $("#voiceDropTimer"),
    voiceDropStatus: $("#voiceDropStatus"),
    voiceDropPanel: document.querySelector(".voice-drop-panel"),
    voiceDropAudio: $("#voiceDropAudio"),
    panelLink: $("#panelLink"),
    skipTrackButton: $("#skipTrackButton"),
    voteActionsHint: $("#voteActionsHint"),
    voteOverlay: $("#voteOverlay"),
    voteOverlayEyebrow: $("#voteOverlayEyebrow"),
    voteOverlayTitle: $("#voteOverlayTitle"),
    voteOverlayMeta: $("#voteOverlayMeta"),
    voteOverlayTimer: $("#voteOverlayTimer"),
    voteYesLabel: $("#voteYesLabel"),
    voteNoLabel: $("#voteNoLabel"),
    voteYesFill: $("#voteYesFill"),
    voteNoFill: $("#voteNoFill"),
    voteYesCount: $("#voteYesCount"),
    voteNoCount: $("#voteNoCount"),
    voteOverlayChoices: $("#voteOverlayChoices"),
    voteChoiceYes: $("#voteChoiceYes"),
    voteChoiceNo: $("#voteChoiceNo"),
    voteLottery: $("#voteLottery"),
    voteLotteryWheel: $("#voteLotteryWheel"),
    voteLotteryResult: $("#voteLotteryResult"),
    voteOverlayStatus: $("#voteOverlayStatus"),
    voteDirectModal: $("#voteDirectModal"),
    voteDirectTitle: $("#voteDirectTitle"),
    voteDirectYes: $("#voteDirectYes"),
    voteDirectNo: $("#voteDirectNo"),
    voteDirectCancel: $("#voteDirectCancel"),
    narratorPickerButton: $("#narratorPickerButton"),
    narratorPickerModal: $("#narratorPickerModal"),
    narratorPickMiku: $("#narratorPickMiku"),
    narratorPickHoshino: $("#narratorPickHoshino"),
    narratorPickerClose: $("#narratorPickerClose"),
    narratorPickerMikuAscii: $("#narratorPickerMikuAscii"),
    narratorPickerHoshinoAscii: $("#narratorPickerHoshinoAscii"),
    narratorPreviewMiku: $("#narratorPreviewMiku"),
    narratorPreviewHoshino: $("#narratorPreviewHoshino")
  };

  function normalizeBaseUrl(url) {
    return String(url || "").replace(/\/+$/, "");
  }

  function localApiPort() {
    const configured = normalizeBaseUrl(config.localApiUrl || "");
    if (!configured) {
      return "8765";
    }

    try {
      return new URL(configured).port || "8765";
    }
    catch (_error) {
      return "8765";
    }
  }

  function localApiBase() {
    if (isHttpsFrontendGateway()) {
      return `${httpsGatewayOrigin()}/radiopoggers-api`;
    }
    return normalizeBaseUrl(state.resolvedLocalApiBase || config.localApiUrl || "");
  }

  async function probeLocalApiBase(force = false) {
    if (state.resolvedLocalApiBase && !force) {
      return localApiBase();
    }

    const port = localApiPort();
    const candidates = [];
    const pushCandidate = (value) => {
      const base = normalizeBaseUrl(value || "");
      if (base && !candidates.includes(base)) {
        candidates.push(base);
      }
    };

    if (isHttpsFrontendGateway()) {
      pushCandidate(`${httpsGatewayOrigin()}/radiopoggers-api`);
    }

    pushCandidate(config.localApiUrl);
    if (window.location.hostname) {
      pushCandidate(`http://${window.location.hostname}:${port}`);
    }
    pushCandidate(`http://127.0.0.1:${port}`);
    pushCandidate(`http://localhost:${port}`);

    for (const base of candidates) {
      const controller = new AbortController();
      const timer = window.setTimeout(() => controller.abort(), 2500);

      try {
        const response = await fetch(`${base}/api/health`, {
          signal: controller.signal,
          cache: "no-store"
        });
        if (response.ok) {
          if (!isHttpsFrontendGateway()) {
            state.resolvedLocalApiBase = base;
          }
          return base;
        }
      }
      catch (_error) {
        // Tenta o proximo candidato.
      }
      finally {
        window.clearTimeout(timer);
      }
    }

    state.resolvedLocalApiBase = "";
    return localApiBase();
  }

  function endpointList() {
    const base = azuracastPublicBase();
    const station = encodeURIComponent(config.stationShortcode);
    const staticEndpoint = `${base}/api/nowplaying_static/${station}.json`;
    const listEndpoint = `${base}/api/nowplaying`;
    const stationId = Number(config.stationId || 0);

    if (config.nowPlayingMode === "static") {
      return [{ url: staticEndpoint, kind: "object" }];
    }

    if (config.nowPlayingMode === "api") {
      const endpoints = [{ url: listEndpoint, kind: "list" }];
      if (stationId > 0) {
        endpoints.unshift({ url: `${base}/api/nowplaying/${stationId}`, kind: "object" });
      }
      return endpoints;
    }

    const endpoints = [
      { url: listEndpoint, kind: "list" },
      { url: staticEndpoint, kind: "object" }
    ];
    if (stationId > 0) {
      endpoints.unshift({ url: `${base}/api/nowplaying/${stationId}`, kind: "object" });
    }
    return endpoints;
  }

  async function fetchAzuraCastNowPlaying() {
    const endpoints = endpointList();
    let lastError = null;

    for (const endpoint of endpoints) {
      try {
        const payload = await fetchJson(endpoint.url);

        if (endpoint.kind === "list") {
          if (!Array.isArray(payload)) {
            continue;
          }

          const entry = payload.find((item) => item?.station?.shortcode === config.stationShortcode);
          if (entry) {
            return entry;
          }
          continue;
        }

        return payload;
      }
      catch (error) {
        lastError = error;
      }
    }

    throw lastError || new Error("Nao foi possivel consultar o AzuraCast.");
  }

  function formatFetchError(error) {
    if (!error) {
      return "erro desconhecido";
    }

    if (error.name === "AbortError") {
      return "tempo esgotado — tente de novo";
    }

    if (error.message === "Failed to fetch") {
      return "sem conexao com a API local";
    }

    return error.message || String(error);
  }

  async function fetchJson(url, options = {}) {
    const timeoutMs = Math.max(Number(options.timeoutMs) || 8000, 2000);
    const externalSignal = options.signal;
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
    const cacheBust = url.includes("?") ? `&_=${Date.now()}` : `?_=${Date.now()}`;

    if (externalSignal) {
      if (externalSignal.aborted) {
        controller.abort();
      }
      else {
        externalSignal.addEventListener("abort", () => controller.abort(), { once: true });
      }
    }

    try {
      const response = await fetch(`${url}${cacheBust}`, {
        cache: "no-store",
        signal: controller.signal
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      return response.json();
    }
    catch (error) {
      throw new Error(formatFetchError(error));
    }
    finally {
      window.clearTimeout(timeout);
    }
  }

  async function fetchLibraryJson(url, signal) {
    return fetchJson(url, { timeoutMs: 45000, signal });
  }

  async function postJson(url, payload) {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 3600000);

    try {
      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(payload),
        signal: controller.signal
      });

      let data = null;
      const raw = await response.text();
      if (raw) {
        try {
          data = JSON.parse(raw);
        }
        catch (parseError) {
          throw new Error(`Resposta invalida da API (HTTP ${response.status}). Reinicie a API local.`);
        }
      }

      if (!response.ok || data?.ok === false) {
        const err = new Error(data?.error || data?.message || `HTTP ${response.status}`);
        err.status = response.status;
        err.payload = data || {};
        throw err;
      }

      return data;
    }
    catch (error) {
      if (error.name === "AbortError") {
        throw new Error("A operacao demorou demais. Tente novamente.");
      }

      if (error.message === "Failed to fetch") {
        throw new Error(
          "Nao alcancei a API local. Rode .\\scripts\\start-local-api.ps1, abra o site por http://127.0.0.1 (nao file://) e use Ctrl+F5."
        );
      }

      throw error;
    }
    finally {
      window.clearTimeout(timeout);
    }
  }

  async function ensureLocalApiReachable() {
    const base = localApiBase();
    if (!base) {
      throw new Error("API local nao configurada em frontend/config.js.");
    }

    await fetchJson(`${base}/api/health`);
    return base;
  }

  async function inspectSpotifyPlaylist(spotifyUrl) {
    const apiBase = await ensureLocalApiReachable();
    return fetchJson(
      `${apiBase}/api/import-spotify/inspect?spotifyUrl=${encodeURIComponent(spotifyUrl)}`
    );
  }

  async function offerSpotifyPlayDecision(manifest, votePayload, options = {}) {
    const summary = manifest?.summary || {};
    const ready = Number(summary.ready || 0);
    const pending = Number(summary.pending_local_audio || 0);
    const title = manifest?.source?.title || votePayload?.playlist_title || "Playlist";

    els.spotifyImportStatus.classList.remove("is-busy");
    els.spotifyImportStatus.textContent = (
      options.reused
        ? `${title} ja esta na biblioteca (${ready} pronta(s)${pending ? `, ${pending} pendente(s)` : ""}). `
        : `${ready} faixa(s) pronta(s)${pending ? `, ${pending} pendente(s)` : ""}. `
    ) + "Confirme abaixo: tocar ja ou deixar a faixa atual.";

    if (!votePayload?.track_id && !votePayload?.first_track_id) {
      setMessage("Playlist sem faixa pronta para colocar no ar.");
      return;
    }

    if (!isStreamPlayingForAudience()) {
      setMessage("De play na radio para decidir o que tocar no ar.");
    }

    const payload = {
      ...votePayload,
      playlist_title: votePayload.playlist_title || title
    };
    await beginVoteFlow("spotify_import", payload);
  }

  async function pollSpotifyImportJob(jobId) {
    const base = localApiBase();
    const started = Date.now();

    while (true) {
      const status = await fetchJson(
        `${base}/api/import-spotify/status?job_id=${encodeURIComponent(jobId)}`
      );

      if (status.message && els.spotifyImportStatus) {
        els.spotifyImportStatus.textContent = status.message;
        els.spotifyImportStatus.classList.add("is-busy");
      }

      if (status.library_catalog) {
        await maybeRefreshLibraryFromMeta(status.library_catalog, {
          force: status.phase === "catalog" || status.phase === "sync" || status.phase === "done",
          silent: true
        });
      }

      if (status.status === "done" && status.result) {
        return status.result;
      }

      if (status.status === "error") {
        throw new Error(status.error || status.message || "Importacao falhou.");
      }

      if (Date.now() - started > 3600000) {
        throw new Error("Importacao demorou demais (limite de 1 hora).");
      }

      await new Promise((resolve) => window.setTimeout(resolve, 2000));
    }
  }

  async function fetchDemoNowPlaying() {
    const demo = await fetchJson(config.demoNowPlayingUrl || defaultConfig.demoNowPlayingUrl);
    demo.__demo = true;
    return demo;
  }

  async function fetchNowPlaying() {
    if (config.demoMode === true || config.demoMode === "only") {
      return fetchDemoNowPlaying();
    }

    let localApiUnreachable = false;
    if (config.localApiUrl) {
      try {
        return await fetchJson(`${localApiBase()}/api/nowplaying`);
      }
      catch (error) {
        localApiUnreachable = true;
        // Se a API local cair, ainda tenta ler o AzuraCast diretamente.
      }
    }

    try {
      return await fetchAzuraCastNowPlaying();
    }
    catch (error) {
      if (config.demoMode === "auto" && !localApiUnreachable) {
        return fetchDemoNowPlaying();
      }
      throw error;
    }
  }

  function resolveSong(song) {
    const fallback = {
      title: "RadioPoggers",
      artist: "Ao vivo",
      album: "Stream privado",
      art: fallbackCover,
      text: "RadioPoggers"
    };

    if (!song) {
      return fallback;
    }

    const text = song.text || "";
    const parts = text.includes(" - ") ? text.split(" - ") : [];

    return {
      title: song.title || parts.slice(1).join(" - ") || text || fallback.title,
      artist: song.artist || parts[0] || fallback.artist,
      album: song.album || fallback.album,
      art: resolveArtUrl(song.art) || fallbackCover,
      text: text || fallback.text
    };
  }

  function resolveStreamUrl(data) {
    if (useHlsPlayback()) {
      const hlsUrl = resolveHlsStreamUrl(data);
      if (hlsUrl) {
        return hlsUrl;
      }
    }

    if (config.streamUrl && config.streamUrl.trim()) {
      return rewriteHttpResourceForHttpsGateway(config.streamUrl.trim());
    }

    const station = data && data.station ? data.station : {};
    const mounts = Array.isArray(station.mounts) ? station.mounts : [];
    const defaultMount = mounts.find((mount) => mount.is_default) || mounts[0];

    const listenUrl = station.listen_url ||
      station.listenUrl ||
      (defaultMount && (defaultMount.url || defaultMount.listen_url)) ||
      "";

    return rewriteHttpResourceForHttpsGateway(listenUrl);
  }

  function useHlsPlayback() {
    const mode = String(config.streamMode || "hls").trim().toLowerCase();
    return mode === "hls" || mode === "auto";
  }

  function resolveHlsStreamUrl(data) {
    if (config.hlsUrl && config.hlsUrl.trim()) {
      return rewriteHttpResourceForHttpsGateway(config.hlsUrl.trim());
    }

    const station = data && data.station ? data.station : {};
    if (station.hls_url) {
      return rewriteHttpResourceForHttpsGateway(station.hls_url);
    }

    if (station.hls_enabled === false) {
      return "";
    }

    const base = azuracastPublicBase();
    const shortcode = config.stationShortcode || station.shortcode;
    if (shortcode) {
      return `${base}/hls/${shortcode}/live.m3u8`;
    }

    return "";
  }

  function resolveQuality(data) {
    const mounts = data && data.station && Array.isArray(data.station.mounts)
      ? data.station.mounts
      : [];
    const defaultMount = mounts.find((mount) => mount.is_default) || mounts[0];

    if (defaultMount && defaultMount.bitrate) {
      return `${defaultMount.bitrate}kbps`;
    }

    if (defaultMount && defaultMount.format) {
      return defaultMount.format;
    }

    return "--";
  }

  function formatTime(seconds) {
    if (!Number.isFinite(seconds) || seconds <= 0) {
      return "0:00";
    }

    const total = Math.floor(seconds);
    const minutes = Math.floor(total / 60);
    const rest = String(total % 60).padStart(2, "0");
    return `${minutes}:${rest}`;
  }

  function isValidPlayedAt(playedAt, nowSeconds, duration) {
    if (!Number.isFinite(playedAt) || playedAt <= 0) {
      return false;
    }

    if (playedAt > nowSeconds + 30) {
      return false;
    }

    if (duration > 0 && playedAt < nowSeconds - duration - 120) {
      return false;
    }

    return true;
  }

  function shouldApplyStreamLatencyOffset() {
    if (state.activeDemoStream) {
      return false;
    }

    const audio = getActiveStreamEl();
    if (!audio || audio.paused) {
      return false;
    }

    return Boolean(state.lastNowPlayingData && !state.lastNowPlayingData.__demo);
  }

  function measureStreamProgressLatencySec() {
    const manual = Number(config.streamProgressLatencySec || 0);
    if (Number.isFinite(manual) && manual > 0) {
      return manual;
    }

    if (!shouldApplyStreamLatencyOffset()) {
      return 0;
    }

    const audio = getActiveStreamEl();
    const hls = getHlsForElement(audio);
    if (hls) {
      if (Number.isFinite(hls.latency) && hls.latency > 0) {
        return hls.latency;
      }

      const liveEdge = hls.liveSyncPosition;
      if (Number.isFinite(liveEdge) && liveEdge > 0 && Number.isFinite(audio.currentTime)) {
        return Math.max(0, liveEdge - audio.currentTime);
      }
    }

    const fallback = Number(config.streamProgressLatencyFallbackSec || 4);
    return Number.isFinite(fallback) && fallback > 0 ? fallback : 4;
  }

  function updateProgressLatencyEstimate() {
    if (!shouldApplyStreamLatencyOffset()) {
      return;
    }

    const measured = measureStreamProgressLatencySec();
    if (!Number.isFinite(measured) || measured < 0) {
      return;
    }

    const smooth = state.progressLatencySmooth;
    state.progressLatencySmooth = smooth > 0 ? (smooth * 0.82) + (measured * 0.18) : measured;
  }

  function getProgressLatencySec() {
    if (!shouldApplyStreamLatencyOffset()) {
      return 0;
    }

    if (state.progressLatencySmooth > 0) {
      return state.progressLatencySmooth;
    }

    return measureStreamProgressLatencySec();
  }

  function getRawElapsedSeconds() {
    if (state.playedAt > 0) {
      return Math.max(0, Date.now() / 1000 - state.playedAt);
    }

    return state.elapsedAtSync + ((Date.now() - state.syncedAt) / 1000);
  }

  function syncProgressFromNowPlaying(nowPlaying, song) {
    const duration = Number(nowPlaying.duration || song.duration || 0);
    const playedAt = Number(nowPlaying.played_at || nowPlaying.playedAt || 0);
    const remaining = Number(nowPlaying.remaining);
    let elapsed = Number(nowPlaying.elapsed);
    const nowSeconds = Date.now() / 1000;
    const playedAtValid = isValidPlayedAt(playedAt, nowSeconds, duration);

    if (playedAtValid) {
      elapsed = Math.max(0, nowSeconds - playedAt);
    }
    else if (Number.isFinite(remaining) && duration > 0) {
      elapsed = Math.max(0, duration - remaining);
    }

    if (!Number.isFinite(elapsed) || elapsed < 0) {
      elapsed = 0;
    }

    state.duration = duration > 0 ? duration : 0;

    if (playedAtValid) {
      if (state.playedAt !== playedAt) {
        state.playedAt = playedAt;
        state.progressLatencySmooth = 0;
      }
      state.elapsedAtSync = elapsed;
      state.syncedAt = Date.now();
      return;
    }

    const previousRaw = getRawElapsedSeconds();
    state.playedAt = 0;
    state.elapsedAtSync = elapsed;
    state.syncedAt = Date.now();

    if (Math.abs(previousRaw - elapsed) > 2.5) {
      state.progressLatencySmooth = 0;
    }
  }

  function getElapsedSeconds() {
    const raw = getRawElapsedSeconds();
    if (!shouldApplyStreamLatencyOffset()) {
      return raw;
    }

    return Math.max(0, raw - getProgressLatencySec());
  }

  function renderProgress() {
    updateProgressLatencyEstimate();

    const elapsed = getElapsedSeconds();
    const safeElapsed = state.duration > 0 ? Math.min(elapsed, state.duration) : elapsed;
    const percent = state.duration > 0 ? (safeElapsed / state.duration) * 100 : 0;
    const audio = getActiveStreamEl();
    const progressTransition = audio && !audio.paused && !state.activeDemoStream
      ? "width 120ms linear"
      : "width 350ms linear";

    els.elapsedTime.textContent = formatTime(safeElapsed);
    els.durationTime.textContent = state.duration > 0 ? formatTime(state.duration) : "--:--";
    els.progressFill.style.transition = progressTransition;
    els.progressFill.style.width = `${Math.max(0, Math.min(percent, 100))}%`;
  }

  function nowPlayingKey(data) {
    const nowPlaying = data.now_playing || data.nowPlaying || {};
    const song = nowPlaying.song || {};
    const meta = data.radio_poggers_metadata || {};
    return [
      nowPlaying.sh_id || "",
      song.id || "",
      meta.path || "",
      song.title || "",
      song.artist || "",
      song.text || ""
    ].join("|");
  }

  function clearTrackChangeTimers() {
    window.clearTimeout(state.trackFollowUpTimer);
    window.clearTimeout(state.trackBurstTimer);
    state.trackFollowUpTimer = null;
    state.trackBurstTimer = null;
  }

  function scheduleTrackChangeBurst() {
    clearTrackChangeTimers();
    state.trackFollowUpTimer = window.setTimeout(() => {
      refreshNowPlaying({ silent: true });
    }, 2500);
  }

  function reloadPageForTrackChange(shouldResumePlayback) {
    sessionStorage.setItem(RESUME_PLAYBACK_KEY, shouldResumePlayback ? "1" : "0");
    window.location.reload();
  }

  function resumePlaybackIfNeeded() {
    if (sessionStorage.getItem(RESUME_PLAYBACK_KEY) !== "1") {
      return;
    }

    sessionStorage.removeItem(RESUME_PLAYBACK_KEY);
    refreshNowPlaying({ silent: true }).then(() => {
      primeStreamPlayback().catch(() => {
        setMessage("Clique em Play para retomar o audio.");
      });
    });
  }

  function setStatus(label, mode) {
    els.connectionStatus.textContent = label;
    els.connectionStatus.classList.toggle("is-online", mode === "online");
    els.connectionStatus.classList.toggle("is-error", mode === "error");
    els.connectionStatus.classList.toggle("is-demo", mode === "demo");
  }

  function resolveTransmissionMode(data) {
    if (!data) {
      return "offline";
    }
    if (data.__demo) {
      return "demo";
    }
    if (data.is_online === false) {
      return "offline";
    }
    return "online";
  }

  function isTransmissionOffline() {
    return state.transmissionState === "offline" || state.nowPlayingUnreachable;
  }

  function applyTransmissionState(mode, { reason = "" } = {}) {
    const prev = state.transmissionState;
    state.transmissionState = mode;

    const offline = mode === "offline";
    const demo = mode === "demo";
    const online = mode === "online";

    if (els.appShell) {
      els.appShell.classList.toggle("is-transmission-offline", offline);
      els.appShell.classList.toggle("is-transmission-demo", demo);
      els.appShell.classList.toggle("is-transmission-online", online);
    }

    if (els.liveEyebrow) {
      els.liveEyebrow.classList.toggle("is-offline", offline);
      els.liveEyebrow.classList.toggle("is-demo", demo);
      els.liveEyebrow.classList.toggle("is-live", online);
    }

    const maintenanceBlocks = state.maintenance?.active === true && state.maintenance?.level === "maintenance";
    if (els.playButton) {
      els.playButton.disabled = offline || maintenanceBlocks;
    }
    if (els.skipTrackButton) {
      els.skipTrackButton.disabled = offline || maintenanceBlocks;
    }

    if (offline) {
      const detail = reason === "station"
        ? "AzuraCast reporta a estacao desligada."
        : "API local e AzuraCast inacessiveis.";

      if (els.liveLabel) {
        els.liveLabel.textContent = "Fora do ar";
      }
      if (els.trackSectionLabel) {
        els.trackSectionLabel.textContent = "Off air";
      }
      if (els.progressLabel) {
        els.progressLabel.textContent = "OFF AIR";
      }
      if (els.trackTitle) {
        els.trackTitle.textContent = "Transmissao desligada";
      }
      if (els.trackArtist) {
        els.trackArtist.textContent = "Nenhum stream ativo no momento";
      }
      if (els.trackAlbum) {
        els.trackAlbum.textContent = detail;
      }
      if (els.listenerCount) {
        els.listenerCount.textContent = "--";
      }
      if (els.streamQuality) {
        els.streamQuality.textContent = "--";
      }
      if (els.automationState) {
        els.automationState.textContent = "Off";
      }
      if (els.coverArt) {
        els.coverArt.src = fallbackCover;
      }

      state.duration = 0;
      state.elapsedAtSync = 0;
      renderProgress();
      pauseAllStreamElements();
      if (state.demoAudio) {
        stopDemoAudio();
      }
      updatePlaybackUi(false);
      document.title = `${config.stationDisplayName || "RADIO NO GRALE"} — Offline`;

      if (prev !== "offline") {
        refreshAsciiBackdropMode();
      }
      return;
    }

    if (els.playButton) {
      els.playButton.disabled = false;
    }
    if (els.skipTrackButton && isVoteEnabled()) {
      els.skipTrackButton.disabled = false;
    }

    if (demo && els.liveLabel) {
      els.liveLabel.textContent = "Modo demo";
    }
    if (demo && els.trackSectionLabel) {
      els.trackSectionLabel.textContent = "Demo";
    }
    if (demo && els.progressLabel) {
      els.progressLabel.textContent = "DEMO";
    }

    if (online && els.trackSectionLabel) {
      els.trackSectionLabel.textContent = "On air";
    }
    if (online && els.progressLabel) {
      els.progressLabel.textContent = "NOW PLAYING";
    }

    if (prev === "offline" && mode !== "offline") {
      refreshAsciiBackdropMode();
    }
  }

  function applyMaintenanceNotice(maintenance) {
    const m = maintenance && typeof maintenance === "object" ? maintenance : { active: false };
    const active = m.active === true;
    const level = String(m.level || "maintenance").toLowerCase();
    const message = String(m.message || "").trim();
    state.maintenance = { active, level, message };

    if (els.appShell) {
      els.appShell.classList.toggle("is-maintenance", active && level === "maintenance");
      els.appShell.classList.toggle("is-maintenance-warning", active && level === "warning");
    }

    if (!active) {
      return;
    }

    const defaultMsg = level === "warning"
      ? "Aviso: instabilidade temporária. Alguns recursos podem falhar."
      : "Rádio em manutenção. O play fica desativado até o operador terminar a atualização.";
    setMessage(message || defaultMsg, { force: true });

    if (level === "maintenance") {
      if (els.liveLabel) {
        els.liveLabel.textContent = "Manutenção";
      }
      const audio = getActiveStreamEl();
      if (audio && !audio.paused) {
        audio.pause();
      }
      if (state.activeDemoStream && state.demoAudio) {
        state.demoAudio.pause();
      }
    }

    if (els.playButton) {
      els.playButton.disabled = level === "maintenance" || isTransmissionOffline();
    }
    if (els.skipTrackButton) {
      els.skipTrackButton.disabled = level === "maintenance" || isTransmissionOffline();
    }
  }

  function setMessage(message, { force = false } = {}) {
    const caption = state.voiceDrop.mikuCaption;
    if (!force && (caption.active || caption.exiting)) {
      return;
    }
    if (els.streamMessage) {
      els.streamMessage.classList.remove("is-miku-caption", "is-miku-caption-exiting");
      els.streamMessage.classList.add("is-stream-message-return");
      els.streamMessage.textContent = message;
      window.setTimeout(() => {
        if (els.streamMessage) {
          els.streamMessage.classList.remove("is-stream-message-return");
        }
      }, 520);
    }
  }

  function restoreStreamMessageAfterMiku() {
    if (state.activeDemoStream) {
      setMessage("Demo tocando. Quando o AzuraCast estiver online, o player usa o stream real.", { force: true });
      return;
    }

    const audio = getActiveStreamEl();
    if (audio && !audio.paused) {
      setMessage("Tocando ao vivo.", { force: true });
      return;
    }

    if (audio && audio.paused) {
      setMessage("Clique em Play para iniciar o audio.", { force: true });
      return;
    }

    setMessage("Clique em Play para iniciar o audio.", { force: true });
  }

  function buildMikuCaptionWordsHtml(fullText, visibleCount) {
    const words = fullText.match(/\S+|\s+/g) || [];
    let consumed = 0;
    const htmlParts = [];

    for (const token of words) {
      const tokenStart = consumed;
      const tokenEnd = consumed + token.length;
      consumed = tokenEnd;

      if (tokenEnd <= visibleCount) {
        const wordClass = token.trim() ? "miku-caption-word is-done" : "miku-caption-space";
        htmlParts.push(`<span class="${wordClass}">${escapeHtml(token)}</span>`);
        continue;
      }

      if (tokenStart < visibleCount) {
        const partial = token.slice(0, visibleCount - tokenStart);
        htmlParts.push(`<span class="miku-caption-word is-typing">${escapeHtml(partial)}</span>`);
      }
      break;
    }

    return htmlParts.join("");
  }

  function buildMikuCaptionShellHtml(narrator = "miku") {
    const isHoshino = narrator === "hoshino";
    const badge = isHoshino ? "HOSHINO · NO AR" : "MIKU · NO AR";
    const shellClass = isHoshino ? "miku-caption-shell is-hoshino" : "miku-caption-shell is-miku";
    return `
      <span class="${shellClass}" aria-live="polite">
        <span class="miku-caption-layout">
          <canvas class="miku-caption-ascii" aria-hidden="true"></canvas>
          <span class="miku-caption-body">
            <span class="miku-caption-badge">
              <span class="miku-caption-badge__dot" aria-hidden="true"></span>
              <span class="miku-caption-badge__text">${badge}</span>
            </span>
            <span class="miku-caption-text">
              <span class="miku-caption-words"></span>
              <span class="miku-caption-cursor" aria-hidden="true"><span class="miku-caption-cursor__core"></span></span>
            </span>
          </span>
        </span>
      </span>
    `;
  }

  function mountMikuCaptionShell(narrator = "miku") {
    if (!els.streamMessage) {
      return null;
    }

    const isHoshino = narrator === "hoshino";
    els.streamMessage.classList.add("is-miku-caption");
    els.streamMessage.classList.toggle("is-hoshino-caption", isHoshino);
    els.streamMessage.innerHTML = buildMikuCaptionShellHtml(narrator);
    return els.streamMessage.querySelector(".miku-caption-shell");
  }

  function getMikuCaptionElements() {
    if (!els.streamMessage) {
      return null;
    }

    const shell = els.streamMessage.querySelector(".miku-caption-shell");
    if (!shell) {
      return null;
    }

    return {
      shell,
      ascii: shell.querySelector(".miku-caption-ascii"),
      words: shell.querySelector(".miku-caption-words"),
      cursor: shell.querySelector(".miku-caption-cursor")
    };
  }

  function stopMikuCaptionAscii() {
    const caption = state.voiceDrop.mikuCaption;
    if (caption.asciiTimer) {
      window.clearTimeout(caption.asciiTimer);
      caption.asciiTimer = null;
    }
    caption.asciiTick = 0;
  }

  function paintMikuCaptionAsciiFrame(canvas) {
    const narrator = state.hoshino.activeCaptionNarrator || "miku";
    const paintFn = narrator === "hoshino" && typeof asciiHoshinoCaptionPaint === "function"
      ? asciiHoshinoCaptionPaint
      : asciiMikuPaint;
    if (!canvas || typeof paintFn !== "function") {
      return;
    }

    paintFn(canvas, state.voiceDrop.mikuCaption.asciiTick);
    state.voiceDrop.mikuCaption.asciiTick += 1;
  }

  function startMikuCaptionAscii(canvas) {
    stopMikuCaptionAscii();

    if (!canvas) {
      return;
    }

    const runFrame = () => {
      if (!state.voiceDrop.mikuCaption.active) {
        stopMikuCaptionAscii();
        return;
      }

      paintMikuCaptionAsciiFrame(canvas);
      state.voiceDrop.mikuCaption.asciiTimer = window.setTimeout(runFrame, asciiMikuFrameMs);
    };

    if (typeof asciiInit === "function") {
      asciiInit()
        .then(runFrame)
        .catch(() => {});
      return;
    }

    runFrame();
  }

  function updateMikuCaptionContent(fullText, visibleCount, { showCursor = true, isComplete = false } = {}) {
    const nodes = getMikuCaptionElements();
    if (!nodes || !nodes.words) {
      return;
    }

    const nextWordsHtml = buildMikuCaptionWordsHtml(fullText, visibleCount);
    if (nodes.words.innerHTML !== nextWordsHtml) {
      nodes.words.innerHTML = nextWordsHtml;
    }

    if (nodes.cursor) {
      nodes.cursor.hidden = !showCursor || isComplete;
    }

    nodes.shell.classList.toggle("is-complete", isComplete);
    nodes.shell.classList.toggle("is-holding", isComplete);
  }

  function renderMikuCaption(fullText, progress, { showCursor = true } = {}) {
    if (!els.streamMessage || !fullText) {
      return;
    }

    const safeProgress = Math.min(Math.max(Number(progress) || 0, 0), 1);
    const visibleCount = Math.max(Math.ceil(fullText.length * safeProgress), safeProgress > 0 ? 1 : 0);
    const isComplete = safeProgress >= 1;

    if (!getMikuCaptionElements()) {
      mountMikuCaptionShell();
    }

    updateMikuCaptionContent(fullText, visibleCount, {
      showCursor: showCursor && !isComplete,
      isComplete
    });
  }

  function clearMikuCaptionDismissTimers() {
    const caption = state.voiceDrop.mikuCaption;
    if (caption.dismissTimer) {
      window.clearTimeout(caption.dismissTimer);
      caption.dismissTimer = null;
    }
    if (caption.exitTimer) {
      window.clearTimeout(caption.exitTimer);
      caption.exitTimer = null;
    }
  }

  function scheduleMikuCaptionDismiss() {
    const caption = state.voiceDrop.mikuCaption;
    if (!caption.active || caption.exiting) {
      return;
    }

    clearMikuCaptionDismissTimers();
    caption.dismissTimer = window.setTimeout(() => {
      caption.dismissTimer = null;
      beginMikuCaptionExit();
    }, MIKU_CAPTION_HOLD_AFTER_MS);
  }

  function beginMikuCaptionExit() {
    const caption = state.voiceDrop.mikuCaption;
    if (!caption.active || caption.exiting) {
      return;
    }

    clearMikuCaptionDismissTimers();
    caption.exiting = true;

    if (caption.raf) {
      cancelAnimationFrame(caption.raf);
      caption.raf = null;
    }

    const nodes = getMikuCaptionElements();
    if (nodes?.shell) {
      nodes.shell.classList.remove("is-complete");
      nodes.shell.classList.add("is-exiting", "is-holding");
      if (nodes.cursor) {
        nodes.cursor.hidden = true;
      }
    }

    if (els.streamMessage) {
      els.streamMessage.classList.add("is-miku-caption-exiting");
    }

    caption.exitTimer = window.setTimeout(() => {
      caption.exitTimer = null;
      stopMikuCaptionSync({ restoreMessage: true, immediate: true });
    }, MIKU_CAPTION_EXIT_MS);
  }

  function stopMikuCaptionSync({ restoreMessage = true, immediate = false } = {}) {
    const caption = state.voiceDrop.mikuCaption;

    if (!immediate && caption.active && !caption.exiting) {
      beginMikuCaptionExit();
      return;
    }

    clearMikuCaptionDismissTimers();

    if (caption.raf) {
      cancelAnimationFrame(caption.raf);
      caption.raf = null;
    }
    stopMikuCaptionAscii();
    caption.active = false;
    caption.exiting = false;
    caption.fullText = "";
    caption.playbackToken = 0;
    caption.lastVisibleCount = -1;
    caption.completed = false;

    if (els.streamMessage) {
      els.streamMessage.classList.remove("is-miku-caption-exiting", "is-hoshino-caption");
    }

    if (restoreMessage) {
      restoreStreamMessageAfterMiku();
    }
  }

  function startMikuCaptionSync(fullText, audioBuffer, playbackToken, playbackCtx, narrator = "miku", playbackRate = 1) {
    const caption = String(fullText || "").trim();
    if (!caption || !els.streamMessage || !audioBuffer || !playbackCtx) {
      return;
    }

    stopMikuCaptionSync({ restoreMessage: false, immediate: true });
    state.hoshino.activeCaptionNarrator = narrator === "hoshino" ? "hoshino" : "miku";
    const shell = mountMikuCaptionShell(state.hoshino.activeCaptionNarrator);
    const nodes = getMikuCaptionElements();
    startMikuCaptionAscii(nodes?.ascii || shell?.querySelector(".miku-caption-ascii"));

    const duration = Math.max(Number(audioBuffer.duration) / Math.max(Number(playbackRate) || 1, 0.1), 0.1);
    const startAt = playbackCtx.currentTime;
    state.voiceDrop.mikuCaption.active = true;
    state.voiceDrop.mikuCaption.fullText = caption;
    state.voiceDrop.mikuCaption.playbackToken = playbackToken;
    state.voiceDrop.mikuCaption.lastVisibleCount = -1;
    state.voiceDrop.mikuCaption.completed = false;

    const tick = () => {
      if (
        state.voiceDrop.playbackToken !== playbackToken
        || !state.voiceDrop.mikuCaption.active
      ) {
        if (state.voiceDrop.playbackToken !== playbackToken) {
          state.voiceDrop.mikuCaption.active = false;
        }
        return;
      }

      const elapsed = playbackCtx.currentTime - startAt;
      const progress = Math.min(Math.max(elapsed / duration, 0), 1);
      const visibleCount = Math.max(Math.ceil(caption.length * progress), progress > 0 ? 1 : 0);
      const isComplete = progress >= 1;

      if (
        visibleCount !== state.voiceDrop.mikuCaption.lastVisibleCount
        || (isComplete && !state.voiceDrop.mikuCaption.completed)
      ) {
        state.voiceDrop.mikuCaption.lastVisibleCount = visibleCount;
        state.voiceDrop.mikuCaption.completed = isComplete;
        updateMikuCaptionContent(caption, visibleCount, { showCursor: !isComplete, isComplete });
      }

      if (progress < 1) {
        state.voiceDrop.mikuCaption.raf = requestAnimationFrame(tick);
      }
      else {
        state.voiceDrop.mikuCaption.raf = null;
      }
    };

    updateMikuCaptionContent(caption, 0, { showCursor: true, isComplete: false });
    state.voiceDrop.mikuCaption.raf = requestAnimationFrame(tick);
  }

  function renderHistory(history) {
    if (!Array.isArray(history) || history.length === 0) {
      els.historyList.innerHTML = "<li>O historico aparece quando o AzuraCast enviar dados.</li>";
      return;
    }

    els.historyList.innerHTML = history.slice(0, 5).map((item) => {
      const song = resolveSong(item.song);
      return `
        <li class="history-item">
          <img src="${escapeAttribute(song.art)}" alt="">
          <span>
            <strong>${escapeHtml(song.title)}</strong>
            <small>${escapeHtml(song.artist)}</small>
          </span>
        </li>
      `;
    }).join("");
  }

  function renderSpotifyManifest(manifest) {
    const source = manifest.source || {};
    const summary = manifest.summary || {};
    const items = Array.isArray(manifest.items) ? manifest.items : [];
    const title = source.title || "Playlist Spotify";
    const ready = summary.ready ?? items.filter((item) => item.status === "ready").length;
    const pending = summary.pending_local_audio ?? items.filter((item) => item.status === "pending_local_audio").length;

    els.spotifyPlaylistTitle.textContent = title;
    els.spotifyPlaylistSummary.textContent = `${items.length} faixas: ${ready} prontas, ${pending} pendentes.`;

    if (!items.length) {
      els.spotifyPlaylistList.innerHTML = "<li>Manifesto vazio.</li>";
      return;
    }

    els.spotifyPlaylistList.innerHTML = items.slice(0, 8).map((item) => {
      const artists = Array.isArray(item.artists) ? item.artists.join(", ") : "";
      const status = item.status === "ready" ? "Pronta" : "Pendente";
      const statusClass = item.status === "ready" ? "status-ready" : "status-pending";

      return `
        <li class="history-item playlist-item">
          <span class="playlist-rank">${escapeHtml(String(item.playlist_position || item.track_number || ""))}</span>
          <span>
            <strong>${escapeHtml(item.title || "Faixa sem nome")}</strong>
            <small>${escapeHtml(artists)} <em class="${statusClass}">${status}</em></small>
          </span>
        </li>
      `;
    }).join("");
  }

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function escapeAttribute(value) {
    return escapeHtml(value).replace(/`/g, "&#096;");
  }

  function updateCover(artUrl) {
    const art = resolveArtUrl(artUrl) || fallbackCover;
    if (state.uiCache.coverArt === art) {
      return;
    }

    state.uiCache.coverArt = art;
    els.coverArt.src = art;
    els.coverGlow.style.backgroundImage = `url("${String(art).replace(/"/g, "%22")}")`;
  }

  function resolveBaseStreamUrl(url) {
    if (!url) {
      return "";
    }

    try {
      const parsed = new URL(url, window.location.href);
      parsed.search = "";
      parsed.hash = "";
      return parsed.href;
    }
    catch (error) {
      return String(url).split("?")[0].split("#")[0];
    }
  }

  function streamUrlsEquivalent(currentUrl, nextUrl) {
    if (!currentUrl || !nextUrl) {
      return currentUrl === nextUrl;
    }

    return resolveBaseStreamUrl(currentUrl) === resolveBaseStreamUrl(nextUrl);
  }

  function rememberStreamUrl(streamUrl) {
    if (!streamUrl || streamUrl.startsWith("demo://")) {
      return;
    }

    state.streamMonitor.baseStreamUrl = resolveBaseStreamUrl(
      new URL(streamUrl, window.location.href).href
    );
  }

  function buildFreshStreamUrl(baseUrl) {
    const url = new URL(baseUrl, window.location.href);
    url.searchParams.set("rp", String(Date.now()));
    return url.href;
  }

  function getHlsSlotForElement(element) {
    return element === els.audioBackup ? "backup" : "primary";
  }

  function getHlsForElement(element) {
    if (!element) {
      return null;
    }

    return state.streamMonitor.hls[getHlsSlotForElement(element)];
  }

  function destroyHlsForElement(element) {
    const slot = getHlsSlotForElement(element);
    if (state.streamMonitor.hls[slot]) {
      state.streamMonitor.hls[slot].destroy();
      state.streamMonitor.hls[slot] = null;
    }
  }

  function destroyAllHlsInstances() {
    destroyHlsForElement(els.audio);
    destroyHlsForElement(els.audioBackup);
  }

  function attachHlsToElement(element, url) {
    return new Promise((resolve, reject) => {
      if (!window.Hls) {
        reject(new Error("hls.js nao carregou. Confira vendor/hls.min.js."));
        return;
      }

      const resolvedUrl = new URL(url, window.location.href).href;
      destroyHlsForElement(element);

      if (window.Hls.isSupported()) {
        const slot = getHlsSlotForElement(element);
        const hls = new window.Hls({
          enableWorker: true,
          lowLatencyMode: false,
          backBufferLength: 45,
          maxBufferLength: 45,
          maxMaxBufferLength: 90,
          liveSyncDurationCount: 5,
          liveMaxLatencyDurationCount: 12,
          fragLoadingMaxRetry: 8,
          manifestLoadingMaxRetry: 8,
          levelLoadingMaxRetry: 8
        });

        state.streamMonitor.hls[slot] = hls;
        hls.attachMedia(element);
        hls.loadSource(resolvedUrl);

        hls.on(window.Hls.Events.MANIFEST_PARSED, () => {
          state.progressLatencySmooth = 0;
          resolve(hls);
        });

        hls.on(window.Hls.Events.FRAG_BUFFERED, () => {
          updateProgressLatencyEstimate();
        });

        hls.on(window.Hls.Events.ERROR, (_event, data) => {
          if (!data.fatal) {
            return;
          }

          if (data.type === window.Hls.ErrorTypes.NETWORK_ERROR) {
            hls.startLoad();
            return;
          }

          if (data.type === window.Hls.ErrorTypes.MEDIA_ERROR) {
            hls.recoverMediaError();
            return;
          }

          destroyHlsForElement(element);
          reject(new Error("Erro fatal no stream HLS."));
        });
        return;
      }

      if (element.canPlayType("application/vnd.apple.mpegurl")) {
        element.src = resolvedUrl;
        element.addEventListener("loadedmetadata", () => resolve(null), { once: true });
        element.addEventListener("error", () => reject(new Error("Erro ao carregar HLS nativo.")), { once: true });
        return;
      }

      reject(new Error("Este navegador nao suporta HLS."));
    });
  }

  async function primeHlsPlayback() {
    let hlsUrl = resolveHlsStreamUrl(state.lastNowPlayingData);

    if (!hlsUrl) {
      await refreshNowPlaying({ silent: true });
      hlsUrl = resolveHlsStreamUrl(state.lastNowPlayingData);
    }

    if (!hlsUrl) {
      throw new Error("Stream HLS indisponivel. Rode .\\scripts\\enable-azuracast-hls.ps1");
    }

    rememberStreamUrl(hlsUrl);

    const active = getActiveStreamEl();
    const standby = getStandbyStreamEl();

    await attachHlsToElement(active, hlsUrl);
    active.preload = "auto";
    await active.play();

    if (standby) {
      standby.pause();
      destroyHlsForElement(standby);
      applyStreamElementVolume(standby, getEffectiveStreamVolume(), false);
    }

    syncStreamElementVolumes();
    await ensureStreamDuckGraphReady();
    flushPendingMikuVoiceDrop();
  }

  async function reconnectHlsStream() {
    const active = getActiveStreamEl();
    const hls = getHlsForElement(active);

    if (hls) {
      hls.startLoad();
      try {
        await active.play();
      }
      catch (error) {
        // Ignora bloqueio de autoplay.
      }
      return true;
    }

    await primeHlsPlayback();
    return true;
  }

  function getActiveStreamEl() {
    return state.streamMonitor.activeIsBackup ? els.audioBackup : els.audio;
  }

  function getStandbyStreamEl() {
    return state.streamMonitor.activeIsBackup ? els.audio : els.audioBackup;
  }

  function getStreamBufferAheadSec(audio) {
    if (!audio || !audio.buffered || audio.buffered.length === 0) {
      return 0;
    }

    const current = audio.currentTime;
    for (let index = 0; index < audio.buffered.length; index += 1) {
      const start = audio.buffered.start(index);
      const end = audio.buffered.end(index);
      if (current >= start - 0.05 && current <= end + 0.05) {
        return Math.max(0, end - current);
      }
    }

    return 0;
  }

  function isStreamDuckGraphReady() {
    return Boolean(state.streamDuck && state.streamDuck.ctx && state.streamDuck.duckGain);
  }

  function isStreamLoudnessEnabled() {
    return config.streamLoudnessNormalize !== false;
  }

  function connectStreamMusicOutput(ctx, elementGainPrimary, elementGainBackup, duckGain) {
    if (!isStreamLoudnessEnabled()) {
      elementGainPrimary.connect(duckGain);
      elementGainBackup.connect(duckGain);
      return null;
    }

    const makeupGain = ctx.createGain();
    makeupGain.gain.value = 1;

    const analyser = ctx.createAnalyser();
    analyser.fftSize = 2048;
    analyser.smoothingTimeConstant = 0.72;

    const compressor = ctx.createDynamicsCompressor();
    compressor.threshold.value = -20;
    compressor.knee.value = 10;
    compressor.ratio.value = 2.8;
    compressor.attack.value = 0.008;
    compressor.release.value = 0.3;

    const limiter = ctx.createDynamicsCompressor();
    limiter.threshold.value = -3.5;
    limiter.knee.value = 0;
    limiter.ratio.value = 12;
    limiter.attack.value = 0.003;
    limiter.release.value = 0.06;

    elementGainPrimary.connect(makeupGain);
    elementGainBackup.connect(makeupGain);
    makeupGain.connect(analyser);
    analyser.connect(compressor);
    compressor.connect(limiter);
    limiter.connect(duckGain);

    return {
      makeupGain,
      analyser,
      compressor,
      limiter,
      calibrationRaf: null,
      startTimer: null,
      calibrationStartedAt: 0,
      samples: [],
      data: new Float32Array(analyser.fftSize)
    };
  }

  function stopStreamLoudnessCalibration() {
    const loudness = state.streamDuck?.loudness;
    if (!loudness) {
      return;
    }

    if (loudness.startTimer) {
      window.clearTimeout(loudness.startTimer);
      loudness.startTimer = null;
    }

    if (loudness.calibrationRaf) {
      cancelAnimationFrame(loudness.calibrationRaf);
      loudness.calibrationRaf = null;
    }

    loudness.samples = [];
  }

  function applyStreamLoudnessMakeupGain(samples) {
    const loudness = state.streamDuck?.loudness;
    if (!loudness?.makeupGain || !Array.isArray(samples) || !samples.length) {
      return;
    }

    const usable = samples.filter((rms) => rms >= STREAM_LOUDNESS_MIN_SIGNAL_RMS);
    if (!usable.length) {
      return;
    }

    usable.sort((left, right) => left - right);
    const measuredRms = usable[Math.floor(usable.length / 2)];
    if (measuredRms <= 0) {
      return;
    }

    let targetGain = STREAM_LOUDNESS_TARGET_RMS / measuredRms;
    targetGain = Math.min(Math.max(targetGain, STREAM_LOUDNESS_MIN_GAIN), STREAM_LOUDNESS_MAX_GAIN);

    const ctx = state.streamDuck.ctx;
    const now = ctx.currentTime;
    loudness.makeupGain.gain.cancelScheduledValues(now);
    loudness.makeupGain.gain.setTargetAtTime(targetGain, now, 0.42);
  }

  function beginStreamLoudnessMeasurement() {
    const loudness = state.streamDuck?.loudness;
    if (!loudness?.analyser || !isStreamLoudnessEnabled() || !isLiveStreamPlaying()) {
      return;
    }

    if (isMikuSpeaking()) {
      return;
    }

    stopStreamLoudnessCalibration();

    const ctx = state.streamDuck.ctx;
    const now = ctx.currentTime;
    loudness.makeupGain.gain.cancelScheduledValues(now);
    loudness.makeupGain.gain.setTargetAtTime(1, now, 0.06);
    loudness.calibrationStartedAt = Date.now();
    loudness.samples = [];

    const measure = () => {
      if (!isStreamDuckGraphReady() || !state.streamDuck.loudness) {
        return;
      }

      if (isMikuSpeaking()) {
        stopStreamLoudnessCalibration();
        return;
      }

      loudness.analyser.getFloatTimeDomainData(loudness.data);
      let sum = 0;
      for (let index = 0; index < loudness.data.length; index += 1) {
        const sample = loudness.data[index];
        sum += sample * sample;
      }
      loudness.samples.push(Math.sqrt(sum / loudness.data.length));

      if ((Date.now() - loudness.calibrationStartedAt) < STREAM_LOUDNESS_CALIBRATION_MS) {
        loudness.calibrationRaf = requestAnimationFrame(measure);
        return;
      }

      loudness.calibrationRaf = null;
      applyStreamLoudnessMakeupGain(loudness.samples);
      loudness.samples = [];
    };

    loudness.calibrationRaf = requestAnimationFrame(measure);
  }

  function scheduleStreamLoudnessCalibration() {
    if (!isStreamLoudnessEnabled() || !isStreamDuckGraphReady() || !state.streamDuck.loudness) {
      return;
    }

    stopStreamLoudnessCalibration();

    state.streamDuck.loudness.startTimer = window.setTimeout(() => {
      if (state.streamDuck?.loudness) {
        state.streamDuck.loudness.startTimer = null;
      }
      beginStreamLoudnessMeasurement();
    }, STREAM_LOUDNESS_CALIBRATION_DELAY_MS);
  }

  function getStreamSliderVolume() {
    const sliderVolume = Number(els.volumeSlider.value) / 100;
    const active = getActiveStreamEl();
    const hardMuted = Boolean(active && active.muted && sliderVolume > 0);

    return {
      volume: Math.max(0, Math.min(sliderVolume, 1)),
      muted: sliderVolume === 0 || hardMuted
    };
  }

  function ensureVoiceFallbackOutputGain(ctx) {
    if (!ctx) {
      return null;
    }

    if (!state.voiceDrop.fallbackOutputGain || state.voiceDrop.fallbackOutputCtx !== ctx) {
      if (state.voiceDrop.fallbackOutputGain) {
        try {
          state.voiceDrop.fallbackOutputGain.disconnect();
        }
        catch (error) {
          // Ignora.
        }
      }

      const gain = ctx.createGain();
      const destination = (isStreamDuckGraphReady() && state.streamDuck.ctx === ctx)
        ? state.streamDuck.masterGain
        : ctx.destination;
      gain.connect(destination);
      state.voiceDrop.fallbackOutputGain = gain;
      state.voiceDrop.fallbackOutputCtx = ctx;
    }

    return state.voiceDrop.fallbackOutputGain;
  }

  function resolveVoiceOutputNode(ctx) {
    if (isStreamDuckGraphReady() && state.streamDuck.ctx === ctx) {
      return state.streamDuck.voiceGain;
    }

    return ensureVoiceFallbackOutputGain(ctx);
  }

  function syncVoiceOutputVolume() {
    const levels = getStreamSliderVolume();
    const output = levels.muted ? 0 : levels.volume;
    const now = isStreamDuckGraphReady() && state.streamDuck.ctx
      ? state.streamDuck.ctx.currentTime
      : (state.voiceDrop.fallbackOutputCtx ? state.voiceDrop.fallbackOutputCtx.currentTime : 0);

    if (isStreamDuckGraphReady() && state.streamDuck.masterGain) {
      state.streamDuck.masterGain.gain.setTargetAtTime(output, now, 0.02);
    }

    if (state.voiceDrop.fallbackOutputGain) {
      const fallbackCtx = state.voiceDrop.fallbackOutputCtx;
      const fallbackNow = fallbackCtx ? fallbackCtx.currentTime : now;
      const usesSharedMaster = isStreamDuckGraphReady()
        && fallbackCtx
        && state.streamDuck.ctx === fallbackCtx;

      state.voiceDrop.fallbackOutputGain.gain.setTargetAtTime(
        usesSharedMaster ? 1 : output,
        fallbackNow,
        0.02
      );
    }
  }

  function ensureStreamDuckGraph() {
    if (isStreamDuckGraphReady()) {
      return state.streamDuck.ctx;
    }

    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass || !els.audio || !els.audioBackup) {
      return null;
    }

    try {
      const ctx = new AudioContextClass();
      const masterGain = ctx.createGain();
      const duckGain = ctx.createGain();
      const voiceGain = ctx.createGain();
      const elementGainPrimary = ctx.createGain();
      const elementGainBackup = ctx.createGain();

      masterGain.gain.value = getStreamSliderVolume().volume;
      duckGain.gain.value = 1;
      voiceGain.gain.value = 1;
      elementGainPrimary.gain.value = 1;
      elementGainBackup.gain.value = 0;

      const loudness = connectStreamMusicOutput(ctx, elementGainPrimary, elementGainBackup, duckGain);
      duckGain.connect(masterGain);
      masterGain.connect(ctx.destination);
      voiceGain.connect(masterGain);

      const sourcePrimary = ctx.createMediaElementSource(els.audio);
      const sourceBackup = ctx.createMediaElementSource(els.audioBackup);
      sourcePrimary.connect(elementGainPrimary);
      sourceBackup.connect(elementGainBackup);

      state.streamDuck = {
        ctx,
        masterGain,
        duckGain,
        voiceGain,
        loudness,
        elementGains: {
          primary: elementGainPrimary,
          backup: elementGainBackup
        },
        sidechain: {
          active: false,
          raf: null,
          analyser: null,
          envelope: 0,
          data: null
        }
      };

      syncStreamDuckRouting();

      return ctx;
    }
    catch (error) {
      state.streamDuck = null;
      return null;
    }
  }

  async function ensureStreamDuckGraphReady() {
    const ctx = ensureStreamDuckGraph();
    if (!ctx) {
      return false;
    }

    if (!state.streamDuck.sidechain.active && state.streamDuck.duckGain) {
      state.streamDuck.duckGain.gain.cancelScheduledValues(ctx.currentTime);
      state.streamDuck.duckGain.gain.value = 1;
    }

    if (ctx.state === "suspended") {
      try {
        await ctx.resume();
      }
      catch (error) {
        return false;
      }
    }

    syncStreamDuckRouting();
    return true;
  }

  function syncStreamDuckRouting() {
    if (!isStreamDuckGraphReady()) {
      return;
    }

    const duck = state.streamDuck;
    const levels = getStreamSliderVolume();
    const activeIsBackup = state.streamMonitor.activeIsBackup;
    const now = duck.ctx.currentTime;

    duck.masterGain.gain.setTargetAtTime(levels.muted ? 0 : levels.volume, now, 0.02);
    duck.elementGains.primary.gain.setTargetAtTime(!activeIsBackup && !levels.muted ? 1 : 0, now, 0.015);
    duck.elementGains.backup.gain.setTargetAtTime(activeIsBackup && !levels.muted ? 1 : 0, now, 0.015);
    syncVoiceOutputVolume();
  }

  function computeSidechainEnvelope(analyser, data) {
    analyser.getByteTimeDomainData(data);

    let sum = 0;
    for (let index = 0; index < data.length; index += 1) {
      const sample = (data[index] - 128) / 128;
      sum += sample * sample;
    }

    const rms = Math.sqrt(sum / data.length);
    return Math.min(1, rms * VOICE_SIDECHAIN_SENSITIVITY);
  }

  function sidechainDuckTarget(envelope) {
    return DUCK_FLOOR + ((1 - envelope) * (1 - DUCK_FLOOR));
  }

  function startVoiceDropSidechain(analyser) {
    const duck = state.streamDuck;
    if (!isStreamDuckGraphReady() || !analyser || !duck) {
      return false;
    }

    stopVoiceDropSidechain(false);

    const ctx = duck.ctx;
    if (ctx.state === "suspended") {
      ctx.resume().catch(() => {});
    }

    duck.sidechain.active = true;
    duck.sidechain.analyser = analyser;
    duck.sidechain.envelope = 0;
    duck.sidechain.data = new Uint8Array(analyser.fftSize);
    state.voiceDrop.ducking = true;

    duck.duckGain.gain.cancelScheduledValues(ctx.currentTime);
    duck.duckGain.gain.setTargetAtTime(DUCK_PRE_DIP, ctx.currentTime, DUCK_ATTACK_SEC);

    const tickVoiceDropSidechain = () => {
      if (!duck.sidechain.active || !duck.sidechain.analyser) {
        return;
      }

      const voiceLevel = computeSidechainEnvelope(
        duck.sidechain.analyser,
        duck.sidechain.data
      );
      const followRate = voiceLevel > duck.sidechain.envelope ? 0.5 : 0.16;
      duck.sidechain.envelope += (voiceLevel - duck.sidechain.envelope) * followRate;

      const target = sidechainDuckTarget(duck.sidechain.envelope);
      const timeConstant = voiceLevel > 0.06 ? DUCK_ATTACK_SEC : DUCK_RELEASE_SEC;

      duck.duckGain.gain.setTargetAtTime(target, ctx.currentTime, timeConstant);
      duck.sidechain.raf = requestAnimationFrame(tickVoiceDropSidechain);
    };

    tickVoiceDropSidechain();
    return true;
  }

  function stopVoiceDropSidechain(restoreGain = true) {
    const duck = state.streamDuck;
    if (!duck) {
      state.voiceDrop.ducking = false;
      return;
    }

    duck.sidechain.active = false;

    if (duck.sidechain.raf) {
      cancelAnimationFrame(duck.sidechain.raf);
      duck.sidechain.raf = null;
    }

    duck.sidechain.analyser = null;
    duck.sidechain.envelope = 0;
    duck.sidechain.data = null;
    state.voiceDrop.ducking = false;

    if (restoreGain && duck.ctx && duck.duckGain) {
      duck.duckGain.gain.cancelScheduledValues(duck.ctx.currentTime);
      duck.duckGain.gain.setTargetAtTime(1, duck.ctx.currentTime, DUCK_RELEASE_SEC);
    }
  }

  function getEffectiveStreamVolume() {
    const levels = getStreamSliderVolume();
    const effectiveVolume = (state.voiceDrop.ducking && !isStreamDuckGraphReady())
      ? levels.volume * VOICE_DROP_DUCK_RATIO
      : levels.volume;

    return {
      volume: Math.max(0, Math.min(effectiveVolume, 1)),
      muted: levels.muted
    };
  }

  function applyStreamElementVolume(element, levels, audible) {
    if (!element) {
      return;
    }

    if (isStreamDuckGraphReady()) {
      element.volume = 1;
      element.muted = !audible;
      syncStreamDuckRouting();
      return;
    }

    if (audible) {
      element.volume = levels.volume;
      element.muted = levels.muted;
      return;
    }

    element.volume = 0;
    element.muted = true;
  }

  function syncStreamElementVolumes() {
    const levels = getEffectiveStreamVolume();
    applyStreamElementVolume(getActiveStreamEl(), levels, true);

    const standby = getStandbyStreamEl();
    if (standby) {
      applyStreamElementVolume(standby, levels, false);
    }

    if (isStreamDuckGraphReady()) {
      syncStreamDuckRouting();
    }
  }

  function clearStandbyPrimeTimer() {
    if (state.streamMonitor.standbyPrimeTimer) {
      window.clearTimeout(state.streamMonitor.standbyPrimeTimer);
      state.streamMonitor.standbyPrimeTimer = null;
    }
  }

  function scheduleStandbyStreamPrime() {
    if (useHlsPlayback()) {
      return;
    }

    clearStandbyPrimeTimer();

    state.streamMonitor.standbyPrimeTimer = window.setTimeout(async () => {
      state.streamMonitor.standbyPrimeTimer = null;
      if (!isLiveStreamPlaying()) {
        return;
      }

      await startStandbyStream();
    }, STREAM_STANDBY_START_MS);
  }

  async function startStandbyStream() {
    const baseUrl = state.streamMonitor.baseStreamUrl;
    const standby = getStandbyStreamEl();

    if (!baseUrl || !standby) {
      return;
    }

    standby.src = buildFreshStreamUrl(baseUrl);
    standby.preload = "auto";
    applyStreamElementVolume(standby, getEffectiveStreamVolume(), false);

    try {
      await standby.play();
    }
    catch (error) {
      // Standby e best-effort; o ativo continua tocando.
    }
  }

  function isStandbyStreamReady() {
    const standby = getStandbyStreamEl();
    return Boolean(
      standby &&
      standby.src &&
      !standby.paused &&
      standby.readyState >= 2 &&
      getStreamBufferAheadSec(standby) >= STREAM_BUFFER_AHEAD_MIN_SEC
    );
  }

  async function primeStreamPlayback() {
    if (useHlsPlayback()) {
      await primeHlsPlayback();
      return;
    }

    let baseUrl = state.streamMonitor.baseStreamUrl;

    if (!baseUrl && config.streamUrl && config.streamUrl.trim()) {
      baseUrl = resolveBaseStreamUrl(new URL(config.streamUrl.trim(), window.location.href).href);
    }

    if (!baseUrl && els.audio && els.audio.src) {
      baseUrl = resolveBaseStreamUrl(els.audio.src);
    }

    if (!baseUrl) {
      await refreshNowPlaying({ silent: true });
      baseUrl = state.streamMonitor.baseStreamUrl;
    }

    if (!baseUrl) {
      throw new Error("Stream indisponivel.");
    }

    rememberStreamUrl(baseUrl);

    const active = getActiveStreamEl();
    const standby = getStandbyStreamEl();

    if (!active.src || !streamUrlsEquivalent(active.src, baseUrl)) {
      active.src = buildFreshStreamUrl(baseUrl);
    }

    active.preload = "auto";
    await active.play();

    if (standby) {
      standby.pause();
      applyStreamElementVolume(standby, getEffectiveStreamVolume(), false);
    }

    syncStreamElementVolumes();
    await ensureStreamDuckGraphReady();
    scheduleStandbyStreamPrime();
    flushPendingMikuVoiceDrop();
  }

  function pauseAllStreamElements() {
    clearStandbyPrimeTimer();
    stopAudioPulseLight();
    destroyAllHlsInstances();

    if (els.audio) {
      els.audio.pause();
      els.audio.removeAttribute("src");
    }
    if (els.audioBackup) {
      els.audioBackup.pause();
      els.audioBackup.removeAttribute("src");
    }
  }

  async function swapToStandbyStream() {
    if (useHlsPlayback()) {
      return false;
    }

    if (!isStandbyStreamReady()) {
      return false;
    }

    const active = getActiveStreamEl();
    const standby = getStandbyStreamEl();
    const levels = getEffectiveStreamVolume();

    state.streamMonitor.swapping = true;

    try {
      applyStreamElementVolume(standby, levels, true);
      await standby.play();

      active.pause();
      applyStreamElementVolume(active, levels, false);
      state.streamMonitor.activeIsBackup = !state.streamMonitor.activeIsBackup;
      await ensureStreamDuckGraphReady();
      syncStreamDuckRouting();
      resetStreamMonitor();
      scheduleStandbyStreamPrime();
      if (isAsciiMusicPlaying()) {
        startStreamAudioPulse(getActiveStreamEl());
      }
      return true;
    }
    catch (error) {
      return false;
    }
    finally {
      state.streamMonitor.swapping = false;
    }
  }

  function startStreamBufferWatch() {
    if (useHlsPlayback()) {
      return;
    }

    if (state.streamMonitor.bufferWatchTimer) {
      return;
    }

    state.streamMonitor.bufferWatchTimer = window.setInterval(() => {
      if (!isLiveStreamPlaying() || state.streamMonitor.reconnecting || state.streamMonitor.swapping) {
        return;
      }

      const ahead = getStreamBufferAheadSec(getActiveStreamEl());
      if (ahead > 0 && ahead < STREAM_BUFFER_AHEAD_MIN_SEC) {
        state.streamMonitor.lowBufferTicks += 1;
        if (state.streamMonitor.lowBufferTicks >= 2) {
          state.streamMonitor.lowBufferTicks = 0;
          swapToStandbyStream();
        }
        return;
      }

      state.streamMonitor.lowBufferTicks = 0;
    }, 220);
  }

  function updateAudioSource(streamUrl) {
    if (!streamUrl) {
      return;
    }

    if (streamUrl.startsWith("demo://")) {
      state.activeDemoStream = true;
      pauseAllStreamElements();
      return;
    }

    state.activeDemoStream = false;

    if (useHlsPlayback()) {
      const hlsUrl = resolveHlsStreamUrl(state.lastNowPlayingData) || streamUrl;
      rememberStreamUrl(hlsUrl);
      return;
    }

    const resolved = new URL(streamUrl, window.location.href).href;
    rememberStreamUrl(resolved);

    if (streamUrlsEquivalent(getActiveStreamEl().src, resolved)) {
      return;
    }

    const shouldResume = !getActiveStreamEl().paused;
    getActiveStreamEl().src = resolved;

    if (shouldResume) {
      primeStreamPlayback().catch(() => {
        setMessage("O navegador bloqueou a retomada automatica do audio.");
      });
    }
  }

  function updateFromNowPlaying(data) {
    state.lastNowPlayingData = data;
    const trackKey = nowPlayingKey(data);
    const trackChanged = Boolean(state.nowPlayingKey) && trackKey !== state.nowPlayingKey;
    state.nowPlayingKey = trackKey;

    const station = data.station || {};
    const nowPlaying = data.now_playing || data.nowPlaying || {};
    const song = resolveSong(nowPlaying.song);
    const listeners = data.listeners || {};
    const isLive = Boolean(data.live && data.live.is_live);
    const isOnline = data.is_online !== false;
    state.nowPlayingUnreachable = false;
    const wasTransmissionOnline = state.uiCache.transmissionOnline;
    state.uiCache.transmissionOnline = isOnline;
    const mode = resolveTransmissionMode(data);
    const streamUrl = resolveStreamUrl(data);
    const listenerLabel = String(listeners.current ?? listeners.unique ?? "--");
    const qualityLabel = resolveQuality(data);
    const automationLabel = isLive ? "DJ ao vivo" : "AutoDJ";
    const liveLabel = isLive ? "DJ ao vivo" : "Ao vivo";

    applyTransmissionState(mode, { reason: mode === "offline" ? "station" : "" });

    if (mode === "offline") {
      setStatus("Offline", "error");
      setMessage("Estacao offline no AzuraCast. Reinicie a radio ou aguarde o AutoDJ.");
      if (wasTransmissionOnline !== isOnline) {
        refreshAsciiBackdropMode();
      }
      return;
    }

    setStatus(mode === "demo" ? "Demo" : "Online", mode === "demo" ? "demo" : "online");

    if (config.stationDisplayName || station.name) {
      els.stationTitle.textContent = config.stationDisplayName || station.name || "ALTA CUPULA";
    }

    if (state.uiCache.trackTitle !== song.title) {
      state.uiCache.trackTitle = song.title;
      els.trackTitle.textContent = song.title;
    }

    if (state.uiCache.trackArtist !== song.artist) {
      state.uiCache.trackArtist = song.artist;
      els.trackArtist.textContent = song.artist;
    }

    if (state.uiCache.trackAlbum !== song.album) {
      state.uiCache.trackAlbum = song.album;
      els.trackAlbum.textContent = song.album;
    }

    if (state.uiCache.listenerCount !== listenerLabel) {
      state.uiCache.listenerCount = listenerLabel;
      els.listenerCount.textContent = listenerLabel;
    }

    if (state.uiCache.streamQuality !== qualityLabel) {
      state.uiCache.streamQuality = qualityLabel;
      els.streamQuality.textContent = qualityLabel;
    }

    if (state.uiCache.automationState !== automationLabel) {
      state.uiCache.automationState = automationLabel;
      els.automationState.textContent = automationLabel;
    }

    if (state.uiCache.liveLabel !== liveLabel && mode === "online") {
      state.uiCache.liveLabel = liveLabel;
      els.liveLabel.textContent = liveLabel;
    }

    if (trackChanged) {
      document.title = `${song.title} — ${config.stationDisplayName || "ALTA CUPULA"}`;
      els.trackMeta.classList.add("is-track-changing");
      window.setTimeout(() => els.trackMeta.classList.remove("is-track-changing"), 700);

      if (config.reloadOnTrackChange !== false && !data.__demo) {
        reloadPageForTrackChange(!getActiveStreamEl().paused);
        return;
      }

      scheduleTrackChangeBurst();
      scheduleStreamLoudnessCalibration();
    }
    else {
      document.title = config.stationDisplayName || "ALTA CUPULA";
    }

    syncProgressFromNowPlaying(nowPlaying, song);
    renderProgress();

    updateCover(song.art);
    updateAudioSource(streamUrl);

    const history = data.song_history || data.songHistory;
    const nextHistoryKey = historyCacheKey(history);
    if (nextHistoryKey !== state.uiCache.historyKey) {
      state.uiCache.historyKey = nextHistoryKey;
      runWhenIdle(() => renderHistory(history), 1800);
    }

    updateMediaSession(song);
    syncVoiceDropFromNowPlaying(data.voice_drop);
    flushPendingMikuVoiceDrop();
    maybeScheduleHoshinoNarration(data);
    syncVoteFromNowPlaying(data.audience_vote);

    if (!data.__demo && wasTransmissionOnline !== isOnline) {
      refreshAsciiBackdropMode();
    }

    if (data.__demo) {
      setMessage(isDemoAudioPlaying()
        ? "Demo tocando. Quando o AzuraCast estiver online, o player usa o stream real."
        : "Modo demo ativo. Clique em Play para testar o audio gerado no navegador.");
    }
    else if (streamUrl) {
      if (!state.streamMonitor.waitingSince) {
        setMessage(getActiveStreamEl().paused ? "Clique em Play para iniciar o audio." : "Tocando ao vivo.");
      }
    }
    else {
      setMessage("Stream ainda nao encontrado. Configure a estacao no AzuraCast ou preencha streamUrl.");
    }
  }

  async function refreshNowPlaying({ silent = false } = {}) {
    if (!silent) {
      setStatus("Atualizando", "");
    }

    try {
      const data = await fetchNowPlaying();
      updateFromNowPlaying(data);
    }
    catch (error) {
      state.nowPlayingUnreachable = true;
      state.lastNowPlayingData = null;
      applyTransmissionState("offline", { reason: "unreachable" });
      setStatus("Offline", "error");
      setMessage("Transmissao indisponivel. Suba a API (8765) e o AzuraCast, ou veja docs/LIGAR_DESLIGAR.md.");
      renderProgress();
    }
  }

  function isValidSpotifyUrl(value) {
    try {
      const url = new URL(value);
      if (url.hostname.toLowerCase() !== "open.spotify.com") {
        return false;
      }

      return /\/(playlist|track)\/[A-Za-z0-9]+/.test(url.pathname);
    }
    catch (error) {
      return false;
    }
  }

  function spotifyUrlKey(value) {
    const match = String(value || "").match(/\/(playlist|track)\/([A-Za-z0-9]+)/i);
    return match ? `${match[1].toLowerCase()}:${match[2]}` : String(value || "").trim().toLowerCase();
  }

  async function startSpotifyImportJob(spotifyUrl) {
    const apiBase = await ensureLocalApiReachable();

    try {
      return await postJson(`${apiBase}/api/import-spotify`, { spotifyUrl });
    }
    catch (error) {
      if (Number(error.status) !== 409) {
        throw error;
      }

      const payload = error.payload && typeof error.payload === "object" ? error.payload : {};
      const activeJobId = String(payload.active_job_id || "").trim();
      const activeKey = String(payload.active_spotify_key || payload.active_spotify_url || "").trim();
      const requestedKey = spotifyUrlKey(spotifyUrl);
      const activeKeyNormalized = activeKey.includes(":")
        ? activeKey.toLowerCase()
        : spotifyUrlKey(activeKey);

      if (activeJobId && activeKeyNormalized === requestedKey) {
        return {
          ok: true,
          job_id: activeJobId,
          status: "running",
          message: "Importacao em andamento. Retomando acompanhamento...",
          resumed: true
        };
      }

      throw new Error(
        payload.error || "Outra playlist esta sendo importada agora. Aguarde terminar antes de enviar outro link."
      );
    }
  }

  function setPlaylistImportBusy(isBusy) {
    state.playlistImportInProgress = isBusy;
    els.spotifyImportButton.disabled = isBusy;
    els.spotifyUrlInput.disabled = isBusy;
    els.spotifyImportForm.classList.toggle("is-locked", isBusy);
    els.spotifyImportStatus.classList.toggle("is-busy", isBusy);
    els.spotifyImportButton.textContent = isBusy ? "Tocando..." : "Tocar";
  }

  async function loadSpotifyManifest() {
    const manifestUrls = [];

    if (config.localApiUrl) {
      manifestUrls.push(`${localApiBase()}/api/manifest`);
    }

    manifestUrls.push(
      config.spotifyManifestUrl || defaultConfig.spotifyManifestUrl,
      "../data/spotify-imported.json"
    );

    try {
      let manifest = null;
      let lastError = null;

      for (const url of manifestUrls) {
        try {
          manifest = await fetchJson(url);
          break;
        }
        catch (error) {
          lastError = error;
        }
      }

      if (!manifest) {
        throw lastError || new Error("Manifesto indisponivel.");
      }

      renderSpotifyManifest(manifest);
    }
    catch (error) {
      els.spotifyPlaylistTitle.textContent = "Playlist indisponivel";
      els.spotifyPlaylistSummary.textContent = "Gere o manifesto, ligue a API local ou ajuste spotifyManifestUrl.";
      els.spotifyPlaylistList.innerHTML = "<li>Nao foi possivel carregar o manifesto da playlist.</li>";
    }
  }

  async function importSpotifyPlaylist(event) {
    event.preventDefault();

    if (state.playlistImportInProgress) {
      els.spotifyImportStatus.classList.add("is-busy");
      els.spotifyImportStatus.textContent = (
        "Aguarde: a playlist anterior ainda esta sendo baixada e sincronizada. " +
        "Nao envie outro link ate terminar."
      );
      return;
    }

    const spotifyUrl = els.spotifyUrlInput.value.trim();
    if (!spotifyUrl) {
      els.spotifyImportStatus.textContent = "Cole um link do Spotify antes de clicar em Tocar.";
      return;
    }

    if (!isValidSpotifyUrl(spotifyUrl)) {
      els.spotifyImportStatus.textContent = "Link invalido. Use uma playlist ou faixa do open.spotify.com.";
      return;
    }

    if (!config.localApiUrl) {
      els.spotifyImportStatus.textContent = "API local nao configurada em frontend/config.js.";
      return;
    }

    setPlaylistImportBusy(true);
    startLibraryCatalogWatcher();
    els.spotifyImportStatus.textContent = (
      "Conectando a API e iniciando importacao... Isso pode levar varios minutos. " +
      "Aguarde aqui e nao envie outro link ate concluir."
    );

    try {
      const apiBase = await ensureLocalApiReachable();
      const inspect = await inspectSpotifyPlaylist(spotifyUrl);

      if (inspect.already_imported && inspect.manifest) {
        renderSpotifyManifest(inspect.manifest);
        setPlaylistImportBusy(false);
        await offerSpotifyPlayDecision(
          inspect.manifest,
          inspect.vote_payload,
          { reused: true }
        );
        await refreshLibraryShelf({ force: true, silent: true });
        return;
      }

      const start = await startSpotifyImportJob(spotifyUrl);
      if (!start.job_id) {
        throw new Error("A API nao retornou o identificador da importacao.");
      }

      els.spotifyImportStatus.textContent = start.message || "Importacao em andamento...";
      const result = await pollSpotifyImportJob(start.job_id);
      renderSpotifyManifest(result.manifest);

      const download = result.download || {};
      const sync = result.sync || {};

      if (sync.synced > 0) {
        window.setTimeout(() => refreshNowPlaying({ silent: true }), 2500);
      }

      if (config.voteEnabled !== false && result.vote_payload) {
        await offerSpotifyPlayDecision(result.manifest, result.vote_payload);
      }
      else if (!result.vote_payload) {
        const summary = result.manifest?.summary || {};
        els.spotifyImportStatus.classList.remove("is-busy");
        els.spotifyImportStatus.textContent = (
          `${summary.ready || 0} faixa(s) pronta(s). Nenhuma pronta para votacao no ar.`
        );
      }

      await refreshLibraryShelf({ force: true, silent: true });
    }
    catch (error) {
      els.spotifyImportStatus.classList.add("is-busy");
      const hint = error.message.includes("API local")
        ? ""
        : " Confira se a API esta rodando (.\\scripts\\start-local-api.ps1).";
      els.spotifyImportStatus.textContent = `Nao consegui importar: ${error.message}.${hint}`;
    }
    finally {
      setPlaylistImportBusy(false);
    }
  }

  async function togglePlayback() {
    if (isTransmissionOffline()) {
      setMessage("Transmissao offline. Ligue a API e o AzuraCast para ouvir ao vivo.");
      return;
    }

    if (state.shelfPreview.trackId) {
      stopShelfPreview({ resumeRadio: false });
    }

    if (!getActiveStreamEl().src && !getHlsForElement(getActiveStreamEl())) {
      await refreshNowPlaying({ silent: true });
    }

    if (state.activeDemoStream) {
      if (isDemoAudioPlaying()) {
        stopDemoAudio();
      }
      else {
        await startDemoAudio();
      }
      return;
    }

    if (getActiveStreamEl().paused) {
      try {
        await primeStreamPlayback();
      }
      catch (error) {
        setMessage("O navegador nao liberou o audio. Confira o stream e tente novamente.");
      }
    }
    else {
      pauseAllStreamElements();
      updatePlaybackUi(false);
      setMessage("Audio pausado.");
    }
  }

  function isDemoAudioPlaying() {
    return Boolean(state.demoAudio && state.demoAudio.playing);
  }

  async function startDemoAudio() {
    if (!config.demoAudio) {
      setMessage("Modo demo sem audio. Configure o AzuraCast para tocar o stream real.");
      return;
    }

    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) {
      setMessage("Este navegador nao suporta Web Audio API para o demo.");
      return;
    }

    if (!state.demoAudio) {
      const context = new AudioContextClass();
      const gain = context.createGain();
      const master = context.createGain();
      const oscillator = context.createOscillator();
      const lfo = context.createOscillator();
      const lfoGain = context.createGain();

      oscillator.type = "sine";
      oscillator.frequency.value = 176;
      lfo.type = "sine";
      lfo.frequency.value = 0.18;
      lfoGain.gain.value = 18;
      gain.gain.value = 0;
      master.gain.value = Number(els.volumeSlider.value) / 100 * 0.18;

      lfo.connect(lfoGain);
      lfoGain.connect(oscillator.frequency);
      oscillator.connect(gain);
      gain.connect(master);
      const analyser = context.createAnalyser();
      analyser.fftSize = 512;
      analyser.smoothingTimeConstant = 0.68;
      analyser.minDecibels = -82;
      analyser.maxDecibels = -10;
      master.connect(analyser);
      analyser.connect(context.destination);
      oscillator.start();
      lfo.start();

      state.demoAudio = {
        context,
        gain,
        master,
        analyser,
        playing: false
      };
    }

    await state.demoAudio.context.resume();
    state.demoAudio.gain.gain.cancelScheduledValues(state.demoAudio.context.currentTime);
    state.demoAudio.gain.gain.setTargetAtTime(1, state.demoAudio.context.currentTime, 0.04);
    state.demoAudio.playing = true;
    updatePlaybackUi(true);
    setMessage("Demo tocando. Quando o AzuraCast estiver online, o player usa o stream real.");
  }

  function stopDemoAudio() {
    if (!state.demoAudio) {
      return;
    }

    state.demoAudio.gain.gain.cancelScheduledValues(state.demoAudio.context.currentTime);
    state.demoAudio.gain.gain.setTargetAtTime(0, state.demoAudio.context.currentTime, 0.04);
    state.demoAudio.playing = false;
    updatePlaybackUi(false);
    setMessage("Audio demo pausado.");
  }

  function updatePlaybackUi(isPlaying) {
    els.appShell.classList.toggle("is-paused", !isPlaying);
    els.playButton.classList.toggle("is-playing", isPlaying);
    els.playButton.setAttribute("aria-label", isPlaying ? "Pausar radio" : "Tocar radio");

    if ("mediaSession" in navigator) {
      navigator.mediaSession.playbackState = isPlaying ? "playing" : "paused";
    }

    syncAudioPulseLight(isPlaying);
  }

  function clearAudioPulseCanvas() {
    const canvas = els.audioPulseCanvas;
    if (!canvas) {
      return;
    }

    const ctx = canvas.getContext("2d");
    if (!ctx) {
      return;
    }

    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
  }

  function resizeAudioPulseCanvas() {
    const canvas = els.audioPulseCanvas;
    const wrap = els.audioPulseLight;
    if (!canvas || !wrap) {
      return { width: 0, height: 0, dpr: 1 };
    }

    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const rect = wrap.getBoundingClientRect();
    const width = Math.max(1, Math.floor(rect.width));
    const height = Math.max(1, Math.floor(rect.height));

    canvas.width = Math.floor(width * dpr);
    canvas.height = Math.floor(height * dpr);
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;

    const ctx = canvas.getContext("2d");
    if (ctx) {
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    return { width, height, dpr };
  }

  function renderAudioPulseCanvas(data, level, hot) {
    const canvas = els.audioPulseCanvas;
    if (!canvas) {
      return;
    }

    const idle = !data;
    const { width, height } = resizeAudioPulseCanvas();
    const ctx = canvas.getContext("2d");
    if (!ctx || width <= 0 || height <= 0) {
      return;
    }

    const time = performance.now() * 0.001;
    const barCount = 42;
    const motion = idle ? 0.1 : 1;

    ctx.clearRect(0, 0, width, height);

    if (!state.audioPulse.barSmooth || state.audioPulse.barSmooth.length !== barCount) {
      state.audioPulse.barSmooth = new Float32Array(barCount);
    }

    const barWidth = width / barCount;
    for (let index = 0; index < barCount; index += 1) {
      let target;
      if (idle) {
        target = 0.04 + Math.sin(time * 0.35 + index * 0.18) * 0.02;
      }
      else {
        const bin = Math.floor((index / barCount) * Math.min(72, data.length));
        target = data[bin] / 255;
      }
      const smoothRate = idle ? 0.14 : 0.32;
      state.audioPulse.barSmooth[index] += (target - state.audioPulse.barSmooth[index]) * smoothRate;
      const value = state.audioPulse.barSmooth[index];
      const barHeight = value * height * 0.58 * (0.4 + level * 0.6);
      const x = width - (index + 1) * barWidth;
      const y = height - barHeight;
      const grad = ctx.createLinearGradient(x, height, x, y);

      grad.addColorStop(0, `rgba(80, 8, 16, ${0.04 + value * 0.1})`);
      grad.addColorStop(0.45, `rgba(180, 22, 36, ${0.12 + value * 0.22 + hot * 0.08})`);
      grad.addColorStop(1, `rgba(255, 65, 82, ${0.2 + value * 0.32 + hot * 0.12})`);

      ctx.fillStyle = grad;
      ctx.fillRect(x + 1, y, Math.max(1, barWidth - 2), barHeight);
    }

    const waveLayers = [
      { amp: 0.13, speed: 1.15, freq: 5.8, opacity: 0.1, width: 1.4, y: 0.34 },
      { amp: 0.1, speed: 0.82, freq: 4.2, opacity: 0.08, width: 1.8, y: 0.46 },
      { amp: 0.085, speed: 1.4, freq: 7.6, opacity: 0.07, width: 1.1, y: 0.56 },
      { amp: 0.065, speed: 0.58, freq: 3, opacity: 0.06, width: 2.2, y: 0.24 }
    ];

    waveLayers.forEach((layer, layerIndex) => {
      ctx.beginPath();
      const amplitude = layer.amp * height * (0.6 + level * 0.55) * motion;
      const yBase = height * layer.y;

      for (let x = 0; x <= width; x += 2) {
        const t = x / width;
        const mod = idle
          ? 0.52
          : 0.5 + (data[Math.min(data.length - 1, Math.floor(t * 28))] / 255) * 0.55;
        const wave =
          Math.sin((t * layer.freq * Math.PI) + (time * layer.speed * motion) + (layerIndex * 1.3)) *
          Math.sin((t * 2.1) + (time * 0.45 * motion) + layerIndex) *
          amplitude *
          mod;
        const y = yBase + wave;

        if (x === 0) {
          ctx.moveTo(x, y);
        }
        else {
          ctx.lineTo(x, y);
        }
      }

      ctx.strokeStyle = `rgba(255, 52, 70, ${layer.opacity + (level * 0.14) + (hot * 0.07)})`;
      ctx.lineWidth = layer.width;
      ctx.lineCap = "round";
      ctx.stroke();
    });

    ctx.beginPath();
    const rippleBase = height - 6 - (level * 14);
    for (let x = 0; x <= width; x += 3) {
      const t = x / width;
      const bassMod = idle
        ? 0.04
        : data[Math.min(data.length - 1, Math.floor(t * 16))] / 255;
      const ripple = Math.sin((t * 14) + (time * 2.4 * motion)) *
        (2 + (level * 10) + (hot * 8) + (bassMod * 6)) *
        motion;

      if (x === 0) {
        ctx.moveTo(x, rippleBase + ripple);
      }
      else {
        ctx.lineTo(x, rippleBase + ripple);
      }
    }

    ctx.strokeStyle = `rgba(255, 38, 58, ${0.14 + (level * 0.28) + (hot * 0.1)})`;
    ctx.lineWidth = 1.4;
    ctx.stroke();

    ctx.beginPath();
    const glowY = height * 0.72;
    for (let x = 0; x <= width; x += 4) {
      const t = x / width;
      const glow = Math.sin((t * 9) - (time * 1.6)) * (1.5 + level * 4);
      if (x === 0) {
        ctx.moveTo(x, glowY + glow);
      }
      else {
        ctx.lineTo(x, glowY + glow);
      }
    }

    ctx.strokeStyle = `rgba(225, 29, 46, ${0.05 + level * 0.12})`;
    ctx.lineWidth = 3;
    ctx.stroke();
  }

  function stopAudioPulseLight({ clearCanvas = true } = {}) {
    if (state.audioPulse.raf) {
      cancelAnimationFrame(state.audioPulse.raf);
      state.audioPulse.raf = null;
    }

    if (state.audioPulse.startTimer) {
      window.clearTimeout(state.audioPulse.startTimer);
      state.audioPulse.startTimer = null;
    }

    if (state.audioPulse.source) {
      try {
        state.audioPulse.source.disconnect();
      }
      catch (error) {
        // Ja desconectado.
      }
      state.audioPulse.source = null;
    }

    if (state.audioPulse.analyser && state.audioPulse.mode === "stream") {
      try {
        state.audioPulse.analyser.disconnect();
      }
      catch (error) {
        // Ja desconectado.
      }
      state.audioPulse.analyser = null;
    }

    state.audioPulse.mode = "";
    state.audioPulse.smoothLevel = 0;
    state.audioPulse.hotLevel = 0;
    state.audioPulse.data = null;
    state.audioPulse.barSmooth = null;

    if (els.audioPulseLight) {
      els.audioPulseLight.classList.remove("is-active");
    }

    if (clearCanvas) {
      clearAudioPulseCanvas();
    }
  }

  function tickAudioPulseIdle() {
    if (!els.audioPulseLight || isAsciiMusicPlaying()) {
      return;
    }

    const time = performance.now() * 0.001;
    const level = 0.06 + Math.sin(time * 0.4) * 0.015;
    renderAudioPulseCanvas(null, level, 0);
    state.audioPulse.raf = requestAnimationFrame(tickAudioPulseIdle);
  }

  function startAudioPulseIdle() {
    stopAudioPulseLight({ clearCanvas: false });
    state.audioPulse.mode = "idle";
    if (els.audioPulseLight) {
      els.audioPulseLight.classList.add("is-idle");
    }
    tickAudioPulseIdle();
  }

  function tickAudioPulseLight() {
    const analyser = state.audioPulse.analyser;
    if (!analyser || !els.audioPulseLight || !isAsciiMusicPlaying()) {
      stopAudioPulseLight();
      return;
    }

    if (!state.audioPulse.data) {
      state.audioPulse.data = new Uint8Array(analyser.frequencyBinCount);
    }

    analyser.getByteFrequencyData(state.audioPulse.data);
    const data = state.audioPulse.data;

    let bassSum = 0;
    const bassEnd = Math.min(14, data.length);
    for (let index = 0; index < bassEnd; index += 1) {
      bassSum += data[index];
    }
    const bass = bassSum / (bassEnd * 255);

    let midSum = 0;
    const midEnd = Math.min(48, data.length);
    for (let index = bassEnd; index < midEnd; index += 1) {
      midSum += data[index];
    }
    const mid = midSum / Math.max(1, (midEnd - bassEnd) * 255);

    const raw = Math.min(1, bass * 0.78 + mid * 0.22);
    state.audioPulse.smoothLevel += (raw - state.audioPulse.smoothLevel) * 0.34;
    state.audioPulse.hotLevel *= 0.82;

    if (raw > state.audioPulse.smoothLevel + 0.12) {
      state.audioPulse.hotLevel = Math.min(
        1,
        state.audioPulse.hotLevel + ((raw - state.audioPulse.smoothLevel) * 1.6)
      );
    }

    renderAudioPulseCanvas(data, state.audioPulse.smoothLevel, state.audioPulse.hotLevel);
    state.audioPulse.raf = requestAnimationFrame(tickAudioPulseLight);
  }

  function startStreamAudioPulse(element) {
    stopAudioPulseLight();

    if (!element || typeof element.captureStream !== "function") {
      return;
    }

    state.audioPulse.startTimer = window.setTimeout(() => {
      state.audioPulse.startTimer = null;

      if (!isAsciiMusicPlaying() || element !== getActiveStreamEl()) {
        return;
      }

      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (!AudioContextClass) {
        return;
      }

      if (!state.audioPulse.ctx) {
        state.audioPulse.ctx = new AudioContextClass();
      }

      const ctx = state.audioPulse.ctx;
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 512;
      analyser.smoothingTimeConstant = 0.68;
      analyser.minDecibels = -82;
      analyser.maxDecibels = -10;

      try {
        const stream = element.captureStream();
        const source = ctx.createMediaStreamSource(stream);
        source.connect(analyser);
        state.audioPulse.source = source;
        state.audioPulse.analyser = analyser;
        state.audioPulse.mode = "stream";
        state.audioPulse.data = new Uint8Array(analyser.frequencyBinCount);
        ctx.resume().catch(() => {});
        els.audioPulseLight.classList.remove("is-idle");
        els.audioPulseLight.classList.add("is-active");
        tickAudioPulseLight();
      }
      catch (error) {
        // Navegador bloqueou analise do stream.
      }
    }, 150);
  }

  function startDemoAudioPulse() {
    stopAudioPulseLight();

    if (!state.demoAudio || !state.demoAudio.analyser) {
      return;
    }

    state.audioPulse.analyser = state.demoAudio.analyser;
    state.audioPulse.mode = "demo";
    state.audioPulse.data = new Uint8Array(state.demoAudio.analyser.frequencyBinCount);
    els.audioPulseLight.classList.remove("is-idle");
    els.audioPulseLight.classList.add("is-active");
    tickAudioPulseLight();
  }

  function syncAudioPulseLight(isPlaying) {
    if (els.audioPulseLight) {
      els.audioPulseLight.classList.remove("is-idle");
    }

    if (!isPlaying || !isAsciiMusicPlaying()) {
      startAudioPulseIdle();
      return;
    }

    if (state.activeDemoStream && isDemoAudioPlaying()) {
      startDemoAudioPulse();
      return;
    }

    startStreamAudioPulse(getActiveStreamEl());
  }

  function updateMediaSession(song) {
    if (!("mediaSession" in navigator) || !("MediaMetadata" in window)) {
      return;
    }

    navigator.mediaSession.metadata = new MediaMetadata({
      title: song.title,
      artist: song.artist,
      album: song.album,
      artwork: [
        { src: resolveArtUrl(song.art) || fallbackCover, sizes: "512x512" }
      ]
    });

    if (!state.mediaHandlersReady) {
      const handlers = {
        play: () => primeStreamPlayback(),
        pause: () => {
          pauseAllStreamElements();
          updatePlaybackUi(false);
        },
        stop: () => {
          pauseAllStreamElements();
          updatePlaybackUi(false);
        }
      };

      Object.entries(handlers).forEach(([action, handler]) => {
        try {
          navigator.mediaSession.setActionHandler(action, handler);
        }
        catch (error) {
          // Alguns navegadores nao suportam todas as acoes.
        }
      });

      state.mediaHandlersReady = true;
    }
  }

  function isLiveStreamPlaying() {
    const active = getActiveStreamEl();
    if (!active || active.paused || state.activeDemoStream) {
      return false;
    }

    if (useHlsPlayback()) {
      return Boolean(getHlsForElement(active) || active.src);
    }

    return Boolean(active.src);
  }

  function runWhenIdle(task, timeoutMs) {
    if (isLiveStreamPlaying() && typeof window.requestIdleCallback === "function") {
      window.requestIdleCallback(task, { timeout: timeoutMs || 1500 });
      return;
    }

    task();
  }

  function historyCacheKey(history) {
    if (!Array.isArray(history) || history.length === 0) {
      return "";
    }

    return history.slice(0, 5).map((item) => {
      const song = item.song || {};
      return [
        song.id || "",
        song.title || "",
        song.artist || "",
        song.text || ""
      ].join(":");
    }).join("|");
  }

  function scheduleNowPlayingPoll() {
    if (state.nowPlayingPollTimer) {
      window.clearInterval(state.nowPlayingPollTimer);
      state.nowPlayingPollTimer = null;
    }

    const intervalMs = isLiveStreamPlaying() ? pollIntervalPlayingMs : pollIntervalMs;
    state.nowPlayingPollTimer = window.setInterval(() => {
      refreshNowPlaying({ silent: true });
    }, intervalMs);
  }

  function clearStreamRecoveryTimer() {
    if (state.streamMonitor.recoveryTimer) {
      window.clearTimeout(state.streamMonitor.recoveryTimer);
      state.streamMonitor.recoveryTimer = null;
    }
  }

  function resetStreamMonitor() {
    state.streamMonitor.waitingSince = 0;
    state.streamMonitor.recoveryAttempts = 0;
    clearStreamRecoveryTimer();
  }

  async function reconnectLiveStream({ force = false } = {}) {
    if (useHlsPlayback()) {
      const now = Date.now();
      if (!force && now - state.streamMonitor.lastReconnectAt < STREAM_RECONNECT_COOLDOWN_MS) {
        return false;
      }

      state.streamMonitor.lastReconnectAt = now;
      return reconnectHlsStream();
    }

    const baseUrl = state.streamMonitor.baseStreamUrl ||
      (getActiveStreamEl().src ? resolveBaseStreamUrl(getActiveStreamEl().src) : "");

    if (!baseUrl || state.streamMonitor.reconnecting) {
      return false;
    }

    const now = Date.now();
    if (!force && now - state.streamMonitor.lastReconnectAt < STREAM_RECONNECT_COOLDOWN_MS) {
      getActiveStreamEl().play().catch(() => {});
      return false;
    }

    state.streamMonitor.reconnecting = true;
    state.streamMonitor.lastReconnectAt = now;
    state.streamMonitor.recoveryAttempts += 1;

    const active = getActiveStreamEl();
    const standby = getStandbyStreamEl();
    const shouldPlay = !active.paused;

    try {
      if (standby) {
        standby.pause();
        applyStreamElementVolume(standby, getEffectiveStreamVolume(), false);
      }

      active.src = buildFreshStreamUrl(baseUrl);
      syncStreamElementVolumes();

      if (shouldPlay) {
        await active.play();
      }

      scheduleStandbyStreamPrime();
      resetStreamMonitor();
      return true;
    }
    catch (error) {
      return false;
    }
    finally {
      state.streamMonitor.reconnecting = false;
    }
  }

  function handleStreamWaiting() {
    if (!isLiveStreamPlaying()) {
      return;
    }

    if (!state.streamMonitor.waitingSince) {
      state.streamMonitor.waitingSince = Date.now();
    }

    getActiveStreamEl().play().catch(() => {});

    if (useHlsPlayback()) {
      const hls = getHlsForElement(getActiveStreamEl());
      if (hls) {
        hls.startLoad();
      }
    }

    if (state.streamMonitor.recoveryTimer) {
      return;
    }

    state.streamMonitor.recoveryTimer = window.setTimeout(async () => {
      state.streamMonitor.recoveryTimer = null;

      if (!isLiveStreamPlaying() || !state.streamMonitor.waitingSince) {
        return;
      }

      const swapped = useHlsPlayback()
        ? false
        : await swapToStandbyStream();
      if (!swapped && state.streamMonitor.waitingSince) {
        await reconnectLiveStream({ force: true });
      }
    }, STREAM_RECONNECT_MS);
  }

  function bindStreamElementStability(element) {
    if (!element) {
      return;
    }

    element.addEventListener("waiting", () => {
      if (element !== getActiveStreamEl()) {
        return;
      }

      if (isLiveStreamPlaying()) {
        handleStreamWaiting();
        return;
      }

      setMessage("Carregando audio...");
    });

    element.addEventListener("stalled", () => {
      if (element === getActiveStreamEl() && isLiveStreamPlaying()) {
        handleStreamWaiting();
      }
    });

    element.addEventListener("canplay", () => {
      if (element === getActiveStreamEl() && isLiveStreamPlaying()) {
        resetStreamMonitor();
      }
    });
  }

  function bindStreamStability() {
    bindStreamElementStability(els.audio);
    bindStreamElementStability(els.audioBackup);
  }

  function updateMuteUi() {
    const levels = getEffectiveStreamVolume();
    const isMuted = levels.muted || getActiveStreamEl().muted;
    els.muteButton.classList.toggle("is-muted", isMuted);
    els.muteButton.setAttribute("aria-label", isMuted ? "Ativar som" : "Silenciar");
    if (els.muteLabel) {
      els.muteLabel.textContent = isMuted ? "Mudo" : "Som";
    }
  }

  function updateVolume() {
    syncStreamElementVolumes();
    syncVoiceOutputVolume();
    syncShelfPreviewVolume();
    const levels = getEffectiveStreamVolume();
    updateMuteUi();

    if (state.demoAudio) {
      state.demoAudio.master.gain.value = levels.muted ? 0 : levels.volume * 0.18;
    }
  }

  function getSelectedNarrator() {
    try {
      const stored = String(window.localStorage.getItem(NARRATOR_STORAGE_KEY) || "").trim().toLowerCase();
      return stored === "hoshino" ? "hoshino" : "miku";
    }
    catch (error) {
      return "miku";
    }
  }

  function setSelectedNarrator(narrator) {
    const safe = narrator === "hoshino" ? "hoshino" : "miku";
    try {
      window.localStorage.setItem(NARRATOR_STORAGE_KEY, safe);
    }
    catch (error) {
      // ignore storage failures
    }
    updateNarratorPickerUi();
    if (els.narratorPickerButton) {
      els.narratorPickerButton.classList.toggle("is-hoshino-active", safe === "hoshino");
    }
  }

  function isHoshinoNarratorSelected() {
    return getSelectedNarrator() === "hoshino";
  }

  function resolveNarratorFromDrop(drop) {
    const listenerId = String(drop?.listener_id || "").trim();
    if (listenerId === HOSHINO_LISTENER_ID) {
      return "hoshino";
    }
    if (listenerId === MIKU_LISTENER_ID) {
      return "miku";
    }
    return "";
  }

  function isNarratorDrop(drop) {
    return NARRATOR_LISTENER_IDS.has(String(drop?.listener_id || "").trim());
  }

  function narratorApiBase() {
    return localApiBase();
  }

  function cancelHoshinoTrackChangeTimer() {
    if (state.hoshino.trackChangeTimer) {
      window.clearTimeout(state.hoshino.trackChangeTimer);
      state.hoshino.trackChangeTimer = null;
    }
  }

  function extractNowPlayingTrack(data) {
    const nowPlaying = data?.now_playing;
    if (!nowPlaying || typeof nowPlaying !== "object") {
      return null;
    }
    const song = nowPlaying.song;
    if (!song || typeof song !== "object") {
      return null;
    }
    const title = String(song.title || song.text || "").trim();
    if (!title) {
      return null;
    }
    return {
      title,
      artist: String(song.artist || "").trim() || "Artista desconhecido",
      album: String(song.album || "").trim(),
      genre: String(song.genre || "").trim(),
      elapsed: Math.max(Number(nowPlaying.elapsed) || 0, 0),
      duration: Math.max(Number(nowPlaying.duration) || Number(song.length) || 0, 0),
      hints: data.narrator_hints && typeof data.narrator_hints === "object" ? data.narrator_hints : {}
    };
  }

  async function requestHoshinoNarration({ title, artist, album = "", genre = "", moment = "track_change" } = {}) {
    if (!isHoshinoNarratorSelected()) {
      return false;
    }

    const base = narratorApiBase();
    if (!base) {
      return false;
    }

    if (state.hoshino.generating) {
      return false;
    }

    const safeTitle = String(title || "").trim();
    if (!safeTitle) {
      return false;
    }

    state.hoshino.generating = true;
    try {
      const result = await postJson(`${base}/api/hoshino/narrate`, {
        title: safeTitle,
        artist: String(artist || "").trim() || "Artista desconhecido",
        album: String(album || "").trim(),
        genre: String(genre || "").trim(),
        moment: String(moment || "track_change").trim()
      });
      const drop = result?.voice_drop;
      if (!drop?.id) {
        return false;
      }
      state.hoshino.lastSpokeAt = Date.now();
      state.hoshino.activeCaptionNarrator = "hoshino";
      await playVoiceDrop(drop, { skipIfSender: false });
      return true;
    }
    catch (error) {
      if (!isHoshinoNarratorSelected()) {
        return false;
      }
      setVoiceDropStatus(`Hoshino indisponivel: ${error.message}`);
      return false;
    }
    finally {
      state.hoshino.generating = false;
    }
  }

  function maybeScheduleHoshinoNarration(data) {
    if (!isHoshinoNarratorSelected() || !data || data.__demo) {
      return;
    }

    const live = data.live;
    if (live && live.is_live) {
      return;
    }

    if (isVoteSessionActive()) {
      return;
    }

    const track = extractNowPlayingTrack(data);
    if (!track) {
      return;
    }

    const hints = track.hints || {};
    const trackKey = String(hints.track_key || "").trim();
    const delaySec = Math.max(Number(hints.track_change_delay_sec) || 10, 0);
    const midCooldownMs = Math.max(Number(hints.mid_cooldown_sec) || 22, 0) * 1000;
    const minTrackSec = Math.max(Number(hints.mid_min_track_seconds) || 48, 0);

    if (trackKey && trackKey !== state.hoshino.trackKey) {
      state.hoshino.trackKey = trackKey;
      state.hoshino.midSpoke = false;
      cancelHoshinoTrackChangeTimer();
      state.hoshino.trackChangeTimer = window.setTimeout(() => {
        state.hoshino.trackChangeTimer = null;
        if (!isHoshinoNarratorSelected() || isVoteSessionActive()) {
          return;
        }
        void requestHoshinoNarration({
          title: track.title,
          artist: track.artist,
          album: track.album,
          genre: track.genre,
          moment: "track_change"
        });
      }, delaySec * 1000);
    }

    if (
      state.hoshino.generating
      || state.hoshino.midSpoke
      || !hints.mid_will_speak
      || track.duration < minTrackSec
      || track.duration <= 0
      || (Date.now() - state.hoshino.lastSpokeAt) < midCooldownMs
    ) {
      return;
    }

    const targetRatio = Math.max(Number(hints.mid_target_ratio) || 0.5, 0);
    if ((track.elapsed / track.duration) < targetRatio) {
      return;
    }

    state.hoshino.midSpoke = true;
    void requestHoshinoNarration({
      title: track.title,
      artist: track.artist,
      album: track.album,
      genre: track.genre,
      moment: String(hints.mid_moment || "mid_track").trim() || "mid_track"
    });
  }

  async function triggerHoshinoVoteNarration(vote) {
    if (!isHoshinoNarratorSelected() || !vote?.narrator_moment) {
      return;
    }

    const payload = vote.payload && typeof vote.payload === "object" ? vote.payload : {};
    const title = String(payload.title || vote.title || els.trackTitle?.textContent || "essa faixa").trim();
    const artist = String(payload.artist || els.trackArtist?.textContent || "Artista desconhecido").trim();

    await requestHoshinoNarration({
      title: title || "essa faixa",
      artist: artist || "Artista desconhecido",
      album: String(payload.album || "").trim(),
      genre: String(payload.genre || "").trim(),
      moment: String(vote.narrator_moment).trim()
    });
  }

  function syncNarratorPickerBodyLock() {
    const open = Boolean(els.narratorPickerModal && !els.narratorPickerModal.classList.contains("is-hidden"));
    document.body.classList.toggle("narrator-picker-open", open);
  }

  function stopNarratorPickerAscii() {
    if (state.narratorPicker.asciiTimer) {
      window.clearTimeout(state.narratorPicker.asciiTimer);
      state.narratorPicker.asciiTimer = null;
    }
  }

  function paintNarratorPickerAsciiFrame() {
    if (typeof asciiPickerMikuPaint === "function" && els.narratorPickerMikuAscii) {
      asciiPickerMikuPaint(els.narratorPickerMikuAscii, state.narratorPicker.mikuTick);
      state.narratorPicker.mikuTick += 1;
    }
    if (typeof asciiPickerHoshinoPaint === "function" && els.narratorPickerHoshinoAscii) {
      asciiPickerHoshinoPaint(els.narratorPickerHoshinoAscii, state.narratorPicker.hoshinoTick);
      state.narratorPicker.hoshinoTick += 1;
    }
  }

  function startNarratorPickerAscii() {
    stopNarratorPickerAscii();
    const run = () => {
      if (!els.narratorPickerModal || els.narratorPickerModal.classList.contains("is-hidden")) {
        stopNarratorPickerAscii();
        return;
      }
      paintNarratorPickerAsciiFrame();
      state.narratorPicker.asciiTimer = window.setTimeout(run, asciiFrameMs);
    };

    if (typeof asciiInit === "function") {
      asciiInit().then(run).catch(run);
      return;
    }
    run();
  }

  function updateNarratorPickerUi() {
    const selected = getSelectedNarrator();
    if (els.narratorPickMiku) {
      els.narratorPickMiku.classList.toggle("is-selected", selected === "miku");
    }
    if (els.narratorPickHoshino) {
      els.narratorPickHoshino.classList.toggle("is-selected", selected === "hoshino");
    }
    if (els.narratorPickerButton) {
      els.narratorPickerButton.classList.toggle("is-hoshino-active", selected === "hoshino");
    }
    updateNarratorPreviewButtons();
  }

  function getNarratorPreviewButton(narrator) {
    return narrator === "hoshino" ? els.narratorPreviewHoshino : els.narratorPreviewMiku;
  }

  function updateNarratorPreviewButtons() {
    ["miku", "hoshino"].forEach((narrator) => {
      const button = getNarratorPreviewButton(narrator);
      if (!button) {
        return;
      }
      const busy = Boolean(state.narratorPicker.previewBusy);
      const isLoading = state.narratorPicker.previewBusy === narrator;
      button.disabled = busy;
      button.textContent = isLoading ? "Tocando..." : "Ouvir amostra";
      button.setAttribute("aria-busy", isLoading ? "true" : "false");
    });
  }

  function narratorPreviewAssetUrl(relativePath) {
    const base = new URL(NARRATOR_PREVIEW_MANIFEST_URL, window.location.href);
    return new URL(String(relativePath || "").replace(/^\//, ""), base).href;
  }

  async function loadNarratorPreviewSamples() {
    try {
      const manifest = await fetchJson(NARRATOR_PREVIEW_MANIFEST_URL);
      state.narratorPicker.samples = {
        miku: Array.isArray(manifest.miku) ? manifest.miku : [],
        hoshino: Array.isArray(manifest.hoshino) ? manifest.hoshino : []
      };
    }
    catch (error) {
      state.narratorPicker.samples = { miku: [], hoshino: [] };
    }
  }

  function pickRandomNarratorPreviewSample(narrator) {
    const pool = state.narratorPicker.samples[narrator] || [];
    if (!pool.length) {
      return null;
    }
    return pool[Math.floor(Math.random() * pool.length)];
  }

  async function decodeNarratorPreviewAudio(url, narrator = "miku") {
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const raw = await response.arrayBuffer();
    await ensureStreamDuckGraphReady();
    const ctx = getVoiceDropPlaybackContext();
    if (ctx.state === "suspended") {
      await ctx.resume();
    }

    const variant = narrator === "hoshino" ? "hoshino" : "miku";
    const processed = await applyBroadcastVoiceEffect(raw.slice(0), { variant });
    return copyAudioBufferToContext(processed.buffer, ctx);
  }

  function clearNarratorPreviewBusy() {
    state.narratorPicker.previewBusy = null;
    updateNarratorPreviewButtons();
  }

  function isNarratorPreviewPlaying() {
    return Boolean(state.narratorPicker.previewBusy);
  }

  async function previewNarratorVoice(narrator) {
    const safeNarrator = narrator === "hoshino" ? "hoshino" : "miku";
    if (isNarratorPreviewPlaying()) {
      return false;
    }

    const sample = pickRandomNarratorPreviewSample(safeNarrator);
    if (!sample?.file) {
      setVoiceDropStatus("Amostras de voz indisponiveis.");
      return false;
    }

    state.narratorPicker.previewBusy = safeNarrator;
    updateNarratorPreviewButtons();

    let playbackStarted = false;
    try {
      const audioBuffer = await decodeNarratorPreviewAudio(
        narratorPreviewAssetUrl(sample.file),
        safeNarrator
      );
      state.hoshino.activeCaptionNarrator = safeNarrator;
      await ensureStreamDuckGraphReady();
      const previewGain = safeNarrator === "miku"
        ? Number(config.mikuNarratorPreviewGain || 1)
        : 1;
      await startVoiceDropPlayback(audioBuffer, {
        detuneCents: safeNarrator === "miku" ? Number(config.mikuVoiceDetuneCents || 0) : 0,
        isNarrator: true,
        narrator: safeNarrator,
        caption: String(sample.caption || "").trim(),
        narratorPreview: true,
        playbackGain: previewGain,
        onPlaybackEnded: clearNarratorPreviewBusy
      });
      playbackStarted = true;
      return true;
    }
    catch (error) {
      setVoiceDropStatus(`Teste de voz (${safeNarrator}): ${error.message}`);
      return false;
    }
    finally {
      if (!playbackStarted) {
        clearNarratorPreviewBusy();
      }
    }
  }

  function hideNarratorPickerModal() {
    if (!els.narratorPickerModal) {
      return;
    }
    els.narratorPickerModal.classList.add("is-hidden");
    els.narratorPickerModal.setAttribute("aria-hidden", "true");
    stopNarratorPickerAscii();
    syncNarratorPickerBodyLock();
  }

  function showNarratorPickerModal() {
    if (!els.narratorPickerModal) {
      return;
    }
    updateNarratorPickerUi();
    els.narratorPickerModal.classList.remove("is-hidden");
    els.narratorPickerModal.setAttribute("aria-hidden", "false");
    syncNarratorPickerBodyLock();
    startNarratorPickerAscii();
  }

  function chooseNarrator(narrator) {
    setSelectedNarrator(narrator);
    hideNarratorPickerModal();
    if (narrator === "hoshino") {
      setMessage("Hoshino ativa so pra voce — locucao personalizada com voz Kore.", { force: true });
    }
    else {
      setMessage("Miku de volta — locucao global da radio.", { force: true });
    }
  }

  function getListenerId() {
    if (state.voiceDrop.listenerId) {
      return state.voiceDrop.listenerId;
    }

    let listenerId = window.localStorage.getItem(LISTENER_ID_KEY);
    if (!listenerId) {
      listenerId = window.crypto && window.crypto.randomUUID
        ? window.crypto.randomUUID()
        : `listener-${Date.now()}`;
      window.localStorage.setItem(LISTENER_ID_KEY, listenerId);
    }

    state.voiceDrop.listenerId = listenerId;
    return listenerId;
  }

  function rememberVoiceDropId(dropId) {
    if (!dropId || state.voiceDrop.playedIds.includes(dropId)) {
      return false;
    }

    state.voiceDrop.playedIds.push(dropId);
    if (state.voiceDrop.playedIds.length > 40) {
      state.voiceDrop.playedIds = state.voiceDrop.playedIds.slice(-40);
    }

    return true;
  }

  function isVoiceDropInFlight(dropId) {
    return Boolean(dropId) && state.voiceDrop.inFlightDropIds.includes(dropId);
  }

  function markVoiceDropInFlight(dropId, active) {
    if (!dropId) {
      return;
    }

    if (active) {
      if (!state.voiceDrop.inFlightDropIds.includes(dropId)) {
        state.voiceDrop.inFlightDropIds.push(dropId);
      }
      return;
    }

    state.voiceDrop.inFlightDropIds = state.voiceDrop.inFlightDropIds.filter((id) => id !== dropId);
  }

  function queuePendingMikuVoiceDrop(drop) {
    if (!drop || !drop.id) {
      return;
    }

    state.voiceDrop.pendingMikuDrop = drop;
  }

  function flushPendingMikuVoiceDrop() {
    const pending = state.voiceDrop.pendingMikuDrop;
    if (!pending || !pending.id || !isLiveStreamPlaying()) {
      return;
    }

    if (pending.listener_id === MIKU_LISTENER_ID && isHoshinoNarratorSelected()) {
      state.voiceDrop.pendingMikuDrop = null;
      return;
    }

    if (state.voiceDrop.playedIds.includes(pending.id) || isVoiceDropInFlight(pending.id)) {
      state.voiceDrop.pendingMikuDrop = null;
      return;
    }

    state.voiceDrop.pendingMikuDrop = null;
    void playVoiceDrop(pending, { skipIfSender: true });
  }

  function duckRadioVolume() {
    if (isStreamDuckGraphReady()) {
      return;
    }

    if (state.voiceDrop.ducking) {
      return;
    }

    state.voiceDrop.ducking = true;
    updateVolume();
  }

  function applyManualStreamDuck() {
    if (!isStreamDuckGraphReady()) {
      duckRadioVolume();
      return;
    }

    const duck = state.streamDuck;
    state.voiceDrop.ducking = true;
    duck.duckGain.gain.cancelScheduledValues(duck.ctx.currentTime);
    duck.duckGain.gain.setTargetAtTime(DUCK_PRE_DIP, duck.ctx.currentTime, DUCK_ATTACK_SEC);
  }

  function copyAudioBufferToContext(buffer, ctx) {
    if (!buffer || !ctx || buffer.sampleRate <= 0) {
      return buffer;
    }

    const channels = buffer.numberOfChannels;
    const copied = ctx.createBuffer(channels, buffer.length, buffer.sampleRate);
    for (let channel = 0; channel < channels; channel += 1) {
      copied.copyToChannel(buffer.getChannelData(channel), channel);
    }
    return copied;
  }

  function attachVoiceSourceWithDucking(source) {
    const ctx = source.context;
    const outputNode = resolveVoiceOutputNode(ctx);

    syncVoiceOutputVolume();

    if (!outputNode) {
      duckRadioVolume();
      return false;
    }

    if (isStreamDuckGraphReady() && state.streamDuck.ctx === ctx) {
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 512;
      analyser.smoothingTimeConstant = 0.58;
      analyser.minDecibels = -84;
      analyser.maxDecibels = -8;

      source.connect(analyser);
      analyser.connect(outputNode);
      state.voiceDrop.sidechainAnalyser = analyser;

      if (startVoiceDropSidechain(analyser)) {
        return true;
      }

      applyManualStreamDuck();
      return false;
    }

    source.connect(outputNode);
    duckRadioVolume();
    return false;
  }

  function restoreRadioVolume() {
    if (isStreamDuckGraphReady()) {
      stopVoiceDropSidechain();
      return;
    }

    if (!state.voiceDrop.ducking) {
      return;
    }

    state.voiceDrop.ducking = false;
    updateVolume();
  }

  function formatVoiceDropTimer(ms) {
    const totalSeconds = Math.max(Math.ceil(ms / 1000), 0);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${minutes}:${String(seconds).padStart(2, "0")}`;
  }

  function initVoiceDropWaveBars() {
    if (!els.voiceDropWave || els.voiceDropWave.childElementCount > 0) {
      return;
    }

    const barCount = 34;
    for (let index = 0; index < barCount; index += 1) {
      const bar = document.createElement("span");
      bar.className = "voice-drop-wave__bar";
      bar.style.height = "4px";
      els.voiceDropWave.appendChild(bar);
    }
  }

  function resetVoiceDropWaveBars() {
    if (!els.voiceDropWave) {
      return;
    }

    els.voiceDropWave.querySelectorAll(".voice-drop-wave__bar").forEach((bar) => {
      bar.style.height = "4px";
      bar.style.opacity = "0.35";
    });
  }

  function stopVoiceDropWaveform() {
    if (state.voiceDrop.waveRaf) {
      cancelAnimationFrame(state.voiceDrop.waveRaf);
      state.voiceDrop.waveRaf = null;
    }

    if (state.voiceDrop.waveform?.ctx) {
      state.voiceDrop.waveform.ctx.close().catch(() => {});
    }

    state.voiceDrop.waveform = null;
    resetVoiceDropWaveBars();
  }

  function startVoiceDropWaveform(stream) {
    stopVoiceDropWaveform();

    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass || !els.voiceDropWave || !stream) {
      return;
    }

    const ctx = new AudioContextClass();
    const source = ctx.createMediaStreamSource(stream);
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 256;
    analyser.smoothingTimeConstant = 0.74;
    source.connect(analyser);

    const data = new Uint8Array(analyser.frequencyBinCount);
    const bars = Array.from(els.voiceDropWave.querySelectorAll(".voice-drop-wave__bar"));

    state.voiceDrop.waveform = { ctx, analyser, data, bars };

    const tickVoiceDropWaveform = () => {
      if (!state.voiceDrop.recording || !state.voiceDrop.waveform) {
        return;
      }

      analyser.getByteFrequencyData(data);

      bars.forEach((bar, index) => {
        const bin = Math.floor((index / bars.length) * Math.min(52, data.length));
        const value = data[bin] / 255;
        const height = 4 + (value * 22);
        bar.style.height = `${height.toFixed(1)}px`;
        bar.style.opacity = String(0.32 + (value * 0.68));
      });

      state.voiceDrop.waveRaf = requestAnimationFrame(tickVoiceDropWaveform);
    };

    if (ctx.state === "suspended") {
      ctx.resume().catch(() => {});
    }

    tickVoiceDropWaveform();
  }

  function setVoiceDropStatus(message) {
    if (els.voiceDropStatus) {
      els.voiceDropStatus.textContent = message;
    }
  }

  function setVoiceDropRecordingUi(isRecording) {
    state.voiceDrop.recording = isRecording;

    if (els.voiceDropPanel) {
      els.voiceDropPanel.classList.toggle("is-recording", isRecording);
    }

    if (els.voiceDropButton) {
      els.voiceDropButton.classList.toggle("is-hidden", isRecording);
    }

    if (els.voiceDropRecording) {
      els.voiceDropRecording.classList.toggle("is-hidden", !isRecording);
    }

    if (!isRecording) {
      stopVoiceDropWaveform();
    }

    updateVoiceDropButtonState();
  }

  function isVoteSessionActive() {
    if (state.vote.pendingDirect) {
      return true;
    }

    const vote = state.vote.active;
    return Boolean(vote && vote.phase && vote.phase !== "closed");
  }

  function isMikuSpeaking() {
    return Boolean(state.voiceDrop.mikuSpeaking);
  }

  function isVoiceDropRecordingBlocked() {
    return isMikuSpeaking() || isVoteSessionActive();
  }

  function voiceDropBlockedMessage() {
    const narratorName = isHoshinoNarratorSelected() ? "Hoshino" : "Miku";
    if (isMikuSpeaking() && isVoteSessionActive()) {
      return `Aguarde a ${narratorName} e a votacao terminarem para gravar sua voz.`;
    }
    if (isMikuSpeaking()) {
      return `Aguarde a ${narratorName} terminar a locucao para gravar sua voz.`;
    }
    if (isVoteSessionActive()) {
      return "Votacao ao vivo — microfone liberado quando a votacao encerrar.";
    }
    return "Microfone indisponivel no momento.";
  }

  function updateVoiceDropButtonState() {
    if (!els.voiceDropButton) {
      return;
    }

    const sessionBlocked = isVoiceDropRecordingBlocked();
    els.voiceDropButton.disabled = !state.voiceDrop.apiReady
      || sessionBlocked
      || state.voiceDrop.recording
      || state.voiceDrop.uploading;

    if (els.voiceDropPanel) {
      els.voiceDropPanel.classList.toggle(
        "is-air-blocked",
        sessionBlocked && !state.voiceDrop.recording && !state.voiceDrop.uploading
      );
    }

    if (
      sessionBlocked
      && !state.voiceDrop.recording
      && !state.voiceDrop.uploading
      && state.voiceDrop.apiReady
    ) {
      setVoiceDropStatus(voiceDropBlockedMessage());
    }
  }

  function shouldDeferListenerVoiceDrop(drop) {
    return !isNarratorDrop(drop)
      && (isMikuSpeaking() || isVoteSessionActive());
  }

  function queueListenerVoiceDropPlayback(drop, options) {
    state.voiceDrop.pendingPlayback = {
      drop,
      options: {
        skipIfSender: options.skipIfSender !== false,
        localBlob: options.localBlob || null,
        localBuffer: options.localBuffer || null
      }
    };
    setVoiceDropStatus("Sua chamada entra no ar assim que a Miku ou a votacao liberarem.");
    updateVoiceDropButtonState();
  }

  async function flushPendingVoiceDropPlayback() {
    const pending = state.voiceDrop.pendingPlayback;
    if (!pending || !pending.drop) {
      return;
    }

    if (shouldDeferListenerVoiceDrop(pending.drop)) {
      return;
    }

    state.voiceDrop.pendingPlayback = null;
    await playVoiceDrop(pending.drop, pending.options || {});
  }

  function markMikuSpeaking(active, { flushPending = false } = {}) {
    state.voiceDrop.mikuSpeaking = Boolean(active);
    if (!active) {
      if (state.voiceDrop.mikuCaption.active) {
        scheduleMikuCaptionDismiss();
      }
      else {
        stopMikuCaptionSync({ restoreMessage: true, immediate: true });
      }
    }
    updateVoiceDropButtonState();
    if (!active && flushPending) {
      void flushPendingVoiceDropPlayback();
    }
  }

  function clearVoiceDropTimers() {
    if (state.voiceDrop.timer) {
      window.clearTimeout(state.voiceDrop.timer);
      state.voiceDrop.timer = null;
    }

    if (state.voiceDrop.tickTimer) {
      window.clearInterval(state.voiceDrop.tickTimer);
      state.voiceDrop.tickTimer = null;
    }
  }

  function stopVoiceDropStream() {
    if (state.voiceDrop.stream) {
      state.voiceDrop.stream.getTracks().forEach((track) => track.stop());
      state.voiceDrop.stream = null;
    }
  }

  function audioBufferToWavBlob(buffer) {
    const channels = buffer.numberOfChannels;
    const sampleRate = buffer.sampleRate;
    const frameCount = buffer.length;
    const bytesPerSample = 2;
    const blockAlign = channels * bytesPerSample;
    const dataSize = frameCount * blockAlign;
    const arrayBuffer = new ArrayBuffer(44 + dataSize);
    const view = new DataView(arrayBuffer);

    function writeString(offset, text) {
      for (let index = 0; index < text.length; index += 1) {
        view.setUint8(offset + index, text.charCodeAt(index));
      }
    }

    writeString(0, "RIFF");
    view.setUint32(4, 36 + dataSize, true);
    writeString(8, "WAVE");
    writeString(12, "fmt ");
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, channels, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * blockAlign, true);
    view.setUint16(32, blockAlign, true);
    view.setUint16(34, bytesPerSample * 8, true);
    writeString(36, "data");
    view.setUint32(40, dataSize, true);

    let offset = 44;
    for (let frame = 0; frame < frameCount; frame += 1) {
      for (let channel = 0; channel < channels; channel += 1) {
        const sample = Math.max(-1, Math.min(1, buffer.getChannelData(channel)[frame]));
        view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
        offset += 2;
      }
    }

    return new Blob([arrayBuffer], { type: "audio/wav" });
  }

  function createSoftClipCurve(drive) {
    const length = 65536;
    const curve = new Float32Array(length);
    const amount = drive || 2.2;

    for (let index = 0; index < length; index += 1) {
      const x = (index * 2) / (length - 1) - 1;
      curve[index] = Math.tanh(amount * x) / Math.tanh(amount);
    }

    return curve;
  }

  function connectBroadcastVoiceChain(offline, source, output, { variant = "broadcast" } = {}) {
    const isMiku = variant === "miku";
    const isHoshino = variant === "hoshino";
    const isNarrator = isMiku || isHoshino;
    const highPass = offline.createBiquadFilter();
    highPass.type = "highpass";
    highPass.frequency.value = 90;
    highPass.Q.value = 0.707;

    const warmth = offline.createBiquadFilter();
    warmth.type = "peaking";
    warmth.frequency.value = isHoshino ? 240 : (isMiku ? 260 : 210);
    warmth.Q.value = 0.85;
    warmth.gain.value = isHoshino ? 2.0 : (isMiku ? 2.6 : 2.8);

    const body = offline.createBiquadFilter();
    body.type = "peaking";
    body.frequency.value = isHoshino ? 360 : (isMiku ? 380 : 420);
    body.Q.value = 0.7;
    body.gain.value = isHoshino ? 0.8 : (isMiku ? 1.2 : -1.5);

    const presence = offline.createBiquadFilter();
    presence.type = "peaking";
    presence.frequency.value = isHoshino ? 2600 : (isMiku ? 2800 : 3400);
    presence.Q.value = isHoshino ? 0.85 : (isMiku ? 0.9 : 1.05);
    presence.gain.value = isHoshino ? 2.0 : (isMiku ? 2.8 : 5);

    const clarity = offline.createBiquadFilter();
    clarity.type = "peaking";
    clarity.frequency.value = isHoshino ? 4000 : (isMiku ? 4200 : 5200);
    clarity.Q.value = 1.2;
    clarity.gain.value = isHoshino ? 0.5 : (isMiku ? 0.6 : 2.2);

    const deEss = offline.createBiquadFilter();
    deEss.type = "peaking";
    deEss.frequency.value = 6800;
    deEss.Q.value = 2.4;
    deEss.gain.value = -4;

    const airShelf = offline.createBiquadFilter();
    airShelf.type = "highshelf";
    airShelf.frequency.value = 9500;
    airShelf.gain.value = -1.8;

    const broadcastBand = offline.createBiquadFilter();
    broadcastBand.type = "lowpass";
    broadcastBand.frequency.value = 12000;
    broadcastBand.Q.value = 0.707;

    const compressor = offline.createDynamicsCompressor();
    compressor.threshold.value = -12;
    compressor.knee.value = 12;
    compressor.ratio.value = 2.4;
    compressor.attack.value = 0.012;
    compressor.release.value = 0.24;

    const saturator = offline.createWaveShaper();
    saturator.curve = createSoftClipCurve(isHoshino ? 1.85 : 2.35);
    saturator.oversample = "2x";

    const dryGain = offline.createGain();
    dryGain.gain.value = isMiku ? 1.02 : (isNarrator ? 0.96 : 0.9);

    const roomSend = offline.createGain();
    roomSend.gain.value = isHoshino ? 0.75 : 1;

    const roomDelayA = offline.createDelay(0.1);
    roomDelayA.delayTime.value = 0.036;

    const roomDelayB = offline.createDelay(0.1);
    roomDelayB.delayTime.value = 0.058;

    const roomGainA = offline.createGain();
    roomGainA.gain.value = isHoshino ? 0.055 : 0.09;

    const roomGainB = offline.createGain();
    roomGainB.gain.value = isHoshino ? 0.03 : 0.05;

    const roomTone = offline.createBiquadFilter();
    roomTone.type = "bandpass";
    roomTone.frequency.value = 2800;
    roomTone.Q.value = 0.55;

    const roomOut = offline.createGain();
    roomOut.gain.value = 0.95;

    const mixBus = offline.createGain();
    mixBus.gain.value = 1;

    source.connect(highPass);
    highPass.connect(warmth);
    warmth.connect(body);
    body.connect(presence);
    presence.connect(clarity);
    clarity.connect(deEss);
    deEss.connect(airShelf);
    airShelf.connect(broadcastBand);
    broadcastBand.connect(compressor);
    compressor.connect(saturator);

    saturator.connect(dryGain);
    dryGain.connect(mixBus);

    saturator.connect(roomSend);
    roomSend.connect(roomDelayA);
    roomSend.connect(roomDelayB);
    roomDelayA.connect(roomGainA);
    roomDelayB.connect(roomGainB);
    roomGainA.connect(roomTone);
    roomGainB.connect(roomTone);
    roomTone.connect(roomOut);
    roomOut.connect(mixBus);

    mixBus.connect(output);
  }

  async function applyBroadcastVoiceEffect(arrayBuffer, { variant = "broadcast" } = {}) {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) {
      throw new Error("Web Audio API indisponivel.");
    }

    const decodeCtx = new AudioContextClass();
    const audioBuffer = await decodeCtx.decodeAudioData(arrayBuffer.slice(0));
    await decodeCtx.close();

    const sampleRate = audioBuffer.sampleRate || 44100;
    const roomTailSec = 0.16;
    const voiceDurationSec = audioBuffer.duration;
    const totalDurationSec = voiceDurationSec + roomTailSec;
    const totalSamples = Math.ceil(totalDurationSec * sampleRate);
    const offline = new OfflineAudioContext(1, totalSamples, sampleRate);

    const source = offline.createBufferSource();
    source.buffer = audioBuffer;

    const mixBus = offline.createGain();
    mixBus.gain.value = 1;

    const limiter = offline.createDynamicsCompressor();
    limiter.threshold.value = -4;
    limiter.knee.value = 8;
    limiter.ratio.value = 6;
    limiter.attack.value = 0.004;
    limiter.release.value = 0.2;

    connectBroadcastVoiceChain(offline, source, mixBus, { variant });

    mixBus.connect(limiter);
    limiter.connect(offline.destination);

    source.start(0);
    const rendered = await offline.startRendering();

    return {
      blob: audioBufferToWavBlob(rendered),
      buffer: rendered,
      durationMs: Math.ceil(rendered.duration * 1000)
    };
  }

  async function uploadVoiceDrop(blob, durationMs) {
    if (!config.localApiUrl) {
      throw new Error("API local nao configurada.");
    }

    const url = `${localApiBase()}/api/voice-drop`;
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 120000);

    try {
      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": blob.type || "audio/wav",
          "X-Duration-Ms": String(durationMs),
          "X-Listener-Id": getListenerId()
        },
        body: blob,
        signal: controller.signal
      });

      let data = null;
      try {
        data = await response.json();
      }
      catch (parseError) {
        throw new Error(`Resposta invalida da API (HTTP ${response.status}). Reinicie a API local.`);
      }

      if (!response.ok || data.ok === false) {
        throw new Error(data.error || data.message || `HTTP ${response.status}`);
      }

      return data;
    }
    catch (error) {
      if (error.name === "AbortError") {
        throw new Error("Envio demorou demais. Tente uma chamada mais curta.");
      }

      if (error.message === "Failed to fetch") {
        throw new Error("Nao alcancei a API local. Rode .\\scripts\\start-local-api.ps1 e use Ctrl+F5.");
      }

      throw error;
    }
    finally {
      window.clearTimeout(timeout);
    }
  }

  function getVoiceDropMicErrorMessage(error) {
    const name = String(error?.name || "");
    if (name === "NotAllowedError" || name === "PermissionDeniedError") {
      return "Microfone bloqueado. Nas permissoes do site, permita o microfone e toque no botao de novo.";
    }
    if (name === "NotFoundError" || name === "DevicesNotFoundError") {
      return "Nenhum microfone encontrado neste aparelho.";
    }
    if (name === "NotReadableError" || name === "TrackStartError") {
      return "Microfone em uso por outro app. Feche chamadas ou gravadores e tente de novo.";
    }
    if (!window.isSecureContext) {
      return `O Chrome so libera o microfone em HTTPS (nao em http://IP). Abra: ${getMobileHttpsFrontendUrl()}`;
    }
    return "Microfone indisponivel. Libere o acesso nas permissoes do navegador e tente de novo.";
  }

  function updateVoiceDropMicHint() {
    if (!els.voiceDropStatus || state.voiceDrop.recording || state.voiceDrop.uploading) {
      return;
    }
    if (isVoiceDropRecordingBlocked()) {
      setVoiceDropStatus(voiceDropBlockedMessage());
      return;
    }
    if (!state.voiceDrop.apiReady) {
      return;
    }
    if (!window.isSecureContext) {
      setVoiceDropStatus(
        `Microfone no Chrome exige HTTPS. Abra ${getMobileHttpsFrontendUrl()} ` +
        "(aceite o certificado). Carregando infinito? Rode no PC: .\\scripts\\test-https-frontend.ps1 e .\\scripts\\open-lan-firewall.ps1"
      );
      return;
    }
    setVoiceDropStatus("Toque no microfone. O navegador vai pedir permissao para gravar sua voz.");
  }

  async function checkVoiceDropApi() {
    if (!config.localApiUrl || !els.voiceDropStatus) {
      return;
    }

    try {
      const health = await fetchJson(`${localApiBase()}/api/health`);
      state.azuracastRequestsAvailable = health.azuracast?.requests_available === true;
      applyMaintenanceNotice(health.maintenance);
      applyVoteCooldownStatus(health.vote_system || {});
      renderCustomPlaylistPanel();

      if (!health.voice_drop) {
        state.voiceDrop.apiReady = false;
        setVoiceDropStatus("Reinicie a API local (.\\scripts\\start-local-api.ps1) para ativar chamadas na radio.");
        updateVoiceDropButtonState();
      }
      else {
        state.voiceDrop.apiReady = true;
        updateVoiceDropMicHint();
        updateVoiceDropButtonState();
      }

      if (health.miku && health.miku.resolved_backend === "none") {
        setMessage("Miku precisa do VOICEVOX. Rode .\\scripts\\install-voicevox-miku.ps1");
      }
      else if (health.miku && String(health.miku.resolved_backend || "").startsWith("edge")) {
        setMessage("Miku no edge-tts (voz generica). Para entonacao estilo Miku: .\\scripts\\install-voicevox-miku.ps1");
      }
      else if (state.azuracastRequestsAvailable === false) {
        setMessage(
          "Pedir na estante exige API key do AzuraCast em data/azuracast-api-key.txt. " +
          "Reinicie .\\scripts\\start-local-api.ps1 depois de salvar a chave."
        );
      }
    }
    catch (error) {
      state.voiceDrop.apiReady = false;
      state.azuracastRequestsAvailable = null;
      applyMaintenanceNotice(null);
      renderCustomPlaylistPanel();
      setVoiceDropStatus("API local offline. Rode .\\scripts\\start-local-api.ps1 na porta 8765.");
      setMessage("API local offline (porta 8765). O operador pode estar atualizando o servidor.", { force: true });
      updateVoiceDropButtonState();
    }
  }

  function resolveVoiceDropUrl(relativeUrl) {
    if (!relativeUrl) {
      return "";
    }

    if (/^https?:\/\//i.test(relativeUrl)) {
      return rewriteHttpResourceForHttpsGateway(relativeUrl);
    }

    if (config.localApiUrl) {
      return `${localApiBase()}${relativeUrl.startsWith("/") ? "" : "/"}${relativeUrl}`;
    }

    return relativeUrl;
  }

  function getVoiceDropPlaybackContext() {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) {
      throw new Error("Web Audio API indisponivel.");
    }

    const streamCtx = ensureStreamDuckGraph();
    if (streamCtx) {
      state.voiceDrop.playbackCtx = streamCtx;
      return streamCtx;
    }

    if (!state.voiceDrop.playbackCtx) {
      state.voiceDrop.playbackCtx = new AudioContextClass();
    }

    ensureVoiceFallbackOutputGain(state.voiceDrop.playbackCtx);
    syncVoiceOutputVolume();
    return state.voiceDrop.playbackCtx;
  }

  function stopVoiceDropPlayback() {
    const previewEnded = state.voiceDrop.previewPlaybackEnded;
    state.voiceDrop.previewPlaybackEnded = null;
    state.voiceDrop.playbackToken += 1;
    stopVoiceDropSidechain(false);

    if (!state.voiceDrop.playbackSource) {
      if (typeof previewEnded === "function") {
        previewEnded();
      }
      return;
    }

    try {
      state.voiceDrop.playbackSource.stop();
    }
    catch (error) {
      // Ja parou.
    }

    state.voiceDrop.playbackSource.disconnect();
    state.voiceDrop.playbackSource = null;

    if (state.voiceDrop.sidechainAnalyser) {
      try {
        state.voiceDrop.sidechainAnalyser.disconnect();
      }
      catch (error) {
        // Ignora.
      }

      state.voiceDrop.sidechainAnalyser = null;
    }

    if (typeof previewEnded === "function") {
      previewEnded();
    }
  }

  function trimVoiceDropBufferCache() {
    const cache = state.voiceDrop.bufferCacheByDropId;
    const ids = Object.keys(cache);
    if (ids.length <= 4) {
      return;
    }

    ids.slice(0, ids.length - 4).forEach((id) => {
      delete cache[id];
    });
  }

  async function loadVoiceDropAudioBuffer(drop, localBlob, localBuffer) {
    const cacheKey = String(drop.id || "");
    if (cacheKey && state.voiceDrop.bufferCacheByDropId[cacheKey]) {
      return state.voiceDrop.bufferCacheByDropId[cacheKey];
    }

    if (localBuffer instanceof AudioBuffer) {
      if (cacheKey) {
        state.voiceDrop.bufferCacheByDropId[cacheKey] = localBuffer;
        trimVoiceDropBufferCache();
      }
      return localBuffer;
    }

    let blob = localBlob;
    if (!(blob instanceof Blob)) {
      const httpUrl = resolveVoiceDropUrl(drop.url);
      if (!httpUrl) {
        throw new Error("URL da chamada indisponivel.");
      }

      const response = await fetch(httpUrl, { cache: "no-store" });
      if (!response.ok) {
        throw new Error(`Falha ao baixar chamada (HTTP ${response.status}).`);
      }

      blob = await response.blob();
    }

    await ensureStreamDuckGraphReady();
    const ctx = getVoiceDropPlaybackContext();
    if (ctx.state === "suspended") {
      await ctx.resume();
    }

    const arrayBuffer = await blob.arrayBuffer();
    const narrator = resolveNarratorFromDrop(drop);
    let audioBuffer;

    if (narrator) {
      const variant = narrator === "hoshino" ? "hoshino" : "miku";
      const processed = await applyBroadcastVoiceEffect(arrayBuffer.slice(0), { variant });
      audioBuffer = copyAudioBufferToContext(processed.buffer, ctx);
    }
    else {
      audioBuffer = await ctx.decodeAudioData(arrayBuffer.slice(0));
    }

    if (cacheKey) {
      state.voiceDrop.bufferCacheByDropId[cacheKey] = audioBuffer;
      trimVoiceDropBufferCache();
    }

    return audioBuffer;
  }

  async function startVoiceDropPlayback(
    audioBuffer,
    {
      detuneCents = 0,
      isNarrator = false,
      narrator = "miku",
      caption = "",
      narratorPreview = false,
      playbackGain = 1,
      onPlaybackEnded = null
    } = {}
  ) {
    stopVoiceDropPlayback();
    const token = ++state.voiceDrop.playbackToken;

    await ensureStreamDuckGraphReady();

    const ctx = getVoiceDropPlaybackContext();
    if (ctx.state === "suspended") {
      await ctx.resume();
    }

    const source = ctx.createBufferSource();
    source.buffer = copyAudioBufferToContext(audioBuffer, ctx);
    let captionPlaybackRate = 1;
    if (narrator === "hoshino" && typeof source.playbackRate !== "undefined") {
      const rate = Number(config.hoshinoVoicePlaybackRate || 1);
      if (Number.isFinite(rate) && rate > 1.001) {
        captionPlaybackRate = Math.min(Math.max(rate, 1), 1.25);
        source.playbackRate.value = captionPlaybackRate;
      }
    }
    else if (detuneCents && typeof source.detune !== "undefined") {
      source.detune.value = detuneCents;
    }

    const gainValue = Math.min(Math.max(Number(playbackGain) || 1, 0.5), 2.5);
    let outputSource = source;
    if (Math.abs(gainValue - 1) > 0.01) {
      const gainNode = ctx.createGain();
      gainNode.gain.value = gainValue;
      source.connect(gainNode);
      outputSource = gainNode;
    }

    state.voiceDrop.playbackSource = source;
    state.voiceDrop.previewPlaybackEnded = narratorPreview && typeof onPlaybackEnded === "function"
      ? onPlaybackEnded
      : null;

    if (isNarrator) {
      state.voiceDrop.mikuSpeaking = true;
      updateVoiceDropButtonState();
      if (caption) {
        startMikuCaptionSync(caption, audioBuffer, token, ctx, narrator, captionPlaybackRate);
      }
    }

    attachVoiceSourceWithDucking(outputSource);

    source.onended = () => {
      if (token !== state.voiceDrop.playbackToken) {
        return;
      }

      const wasNarratorPreview = narratorPreview;
      stopVoiceDropPlayback();
      restoreRadioVolume();

      if (isNarrator) {
        markMikuSpeaking(false, { flushPending: !wasNarratorPreview });
      }
    };

    source.start(0);
  }

  async function playVoiceDrop(drop, {
    skipIfSender = true,
    localBlob = null,
    localBuffer = null,
    preview = false,
    skipInFlightGuard = false
  } = {}) {
    if (!drop || !drop.id) {
      return false;
    }

    if (skipIfSender && drop.listener_id === getListenerId()) {
      return false;
    }

    if (!preview && shouldDeferListenerVoiceDrop(drop)) {
      queueListenerVoiceDropPlayback(drop, { skipIfSender, localBlob, localBuffer });
      return false;
    }

    if (!preview && state.voiceDrop.playedIds.includes(drop.id)) {
      return false;
    }

    if (!preview && !skipInFlightGuard && isVoiceDropInFlight(drop.id)) {
      return false;
    }

    if (!preview && !isVoiceDropInFlight(drop.id)) {
      markVoiceDropInFlight(drop.id, true);
    }
    state.voiceDrop.lastPlayedDropId = drop.id;
    const narrator = resolveNarratorFromDrop(drop);
    const isNarrator = Boolean(narrator);
    const detuneCents = isNarrator && narrator !== "hoshino"
      ? Number(config.mikuVoiceDetuneCents || 0)
      : 0;

    try {
      await ensureStreamDuckGraphReady();
      const audioBuffer = await loadVoiceDropAudioBuffer(drop, localBlob, localBuffer);
      const caption = isNarrator ? String(drop.caption || drop.text || "").trim() : "";
      const playbackGain = 1;
      await startVoiceDropPlayback(audioBuffer, {
        detuneCents,
        isNarrator,
        narrator: narrator || "miku",
        caption,
        playbackGain
      });
      if (!preview) {
        rememberVoiceDropId(drop.id);
      }
      if (isNarrator && !caption) {
        const label = narrator === "hoshino" ? "Hoshino" : "Miku";
        setMessage(`${label} na locucao da Radio no Grale.`, { force: true });
      }
      else if (!isNarrator) {
        setVoiceDropStatus("Chamada no ar na Alta Cupula.");
      }
      return true;
    }
    catch (error) {
      if (isNarrator) {
        markMikuSpeaking(false, { flushPending: false });
      }
      restoreRadioVolume();
      setVoiceDropStatus(`Nao consegui tocar a chamada: ${error.message}`);
      return false;
    }
    finally {
      markVoiceDropInFlight(drop.id, false);
    }
  }

  function syncVoiceDropFromNowPlaying(voiceDrop) {
    if (!voiceDrop || !voiceDrop.id) {
      return;
    }

    if (state.voiceDrop.recording || state.voiceDrop.uploading) {
      return;
    }

    if (isNarratorPreviewPlaying()) {
      return;
    }

    if (voiceDrop.listener_id === MIKU_LISTENER_ID && isHoshinoNarratorSelected()) {
      return;
    }

    if (voiceDrop.listener_id === MIKU_LISTENER_ID && config.mikuNarratorEnabled === false) {
      return;
    }

    if (!isLiveStreamPlaying() && voiceDrop.listener_id === MIKU_LISTENER_ID) {
      queuePendingMikuVoiceDrop(voiceDrop);
      return;
    }

    if (state.voiceDrop.playedIds.includes(voiceDrop.id) || isVoiceDropInFlight(voiceDrop.id)) {
      return;
    }

    markVoiceDropInFlight(voiceDrop.id, true);
    void playVoiceDrop(voiceDrop, { skipIfSender: true, skipInFlightGuard: true });
  }

  const VOTE_DIRECT_COPY = {
    skip_track: {
      title: "Pular a faixa?",
      yes: "Pular",
      no: "Deixa rolar"
    },
    library_request: {
      title: "Pedir na radio?",
      yes: "Tocar ja",
      no: "Na fila"
    },
    library_clear: {
      title: "Zerar Minha playlist?",
      yes: "Zerar",
      no: "Manter"
    },
    spotify_import: {
      title: "Playlist pronta!",
      yes: "Tocar ja (pula)",
      no: "Deixa rolar"
    }
  };

  function voteApiBase() {
    return localApiBase();
  }

  function isVoteEnabled() {
    return config.voteEnabled !== false && Boolean(voteApiBase());
  }

  function isStreamPlayingForAudience() {
    const audio = getActiveStreamEl();
    if (!audio) {
      return false;
    }
    if (state.activeDemoStream) {
      return isDemoAudioPlaying();
    }
    return !audio.paused;
  }

  function applyVoteCooldownStatus(payload) {
    if (!payload || typeof payload !== "object") {
      return;
    }

    const configured = Number(payload.action_cooldown_sec);
    if (Number.isFinite(configured) && configured > 0) {
      state.vote.actionCooldownSec = configured;
    }

    const remaining = Number(payload.action_cooldown_remaining_sec);
    if (Number.isFinite(remaining)) {
      state.vote.actionCooldownRemainingSec = Math.max(remaining, 0);
    }

    updateVoteActionButtons();
  }

  function voteActionCooldownBlocked(voteType) {
    if (!VOTE_ACTION_COOLDOWN_TYPES.has(String(voteType || ""))) {
      return false;
    }
    return state.vote.actionCooldownRemainingSec > 0;
  }

  function voteActionCooldownMessage() {
    const waitSec = Math.ceil(state.vote.actionCooldownRemainingSec);
    return (
      `Aguarde ${waitSec}s antes de pular, pedir musica ou zerar a playlist ` +
      "(intervalo protege a radio e a locucao da Miku)."
    );
  }

  function updateVoteActionButtons() {
    const blocked = state.vote.actionCooldownRemainingSec > 0;
    const waitLabel = blocked ? ` (${Math.ceil(state.vote.actionCooldownRemainingSec)}s)` : "";

    if (els.skipTrackButton) {
      els.skipTrackButton.disabled = blocked;
      els.skipTrackButton.title = blocked ? voteActionCooldownMessage() : "Abrir votacao para pular a faixa";
      if (els.skipTrackButton.dataset.cooldownBound !== "1") {
        els.skipTrackButton.dataset.cooldownBound = "1";
        const baseLabel = els.skipTrackButton.dataset.baseLabel || els.skipTrackButton.textContent || "Pular faixa";
        els.skipTrackButton.dataset.baseLabel = baseLabel;
      }
      const baseSkip = els.skipTrackButton.dataset.baseLabel || "Pular faixa";
      els.skipTrackButton.textContent = blocked ? `${baseSkip}${waitLabel}` : baseSkip;
    }

    renderCustomPlaylistPanel();
  }

  function startVoteActionCooldownTicker() {
    if (state.vote.cooldownTicker) {
      return;
    }

    state.vote.cooldownTicker = window.setInterval(() => {
      if (state.vote.actionCooldownRemainingSec <= 0) {
        return;
      }

      state.vote.actionCooldownRemainingSec = Math.max(state.vote.actionCooldownRemainingSec - 1, 0);
      updateVoteActionButtons();
    }, 1000);
  }

  async function sendAudienceHeartbeat() {
    if (!isVoteEnabled()) {
      return;
    }

    try {
      const result = await postJson(`${voteApiBase()}/api/audience/heartbeat`, {
        listener_id: getListenerId(),
        playing: isStreamPlayingForAudience()
      });
      applyVoteCooldownStatus(result);
    }
    catch (error) {
      // heartbeat silencioso
    }
  }

  function scheduleAudienceHeartbeat() {
    if (!isVoteEnabled()) {
      return;
    }

    const intervalMs = Math.max(Number(config.audienceHeartbeatMs || 12000), 5000);
    sendAudienceHeartbeat();
    if (state.vote.heartbeatTimer) {
      window.clearInterval(state.vote.heartbeatTimer);
    }
    state.vote.heartbeatTimer = window.setInterval(sendAudienceHeartbeat, intervalMs);
  }

  async function fetchAudienceCount() {
    const response = await fetch(`${voteApiBase()}/api/audience/count`, { cache: "no-store" });
    const data = await response.json();
    if (!response.ok || data.ok === false) {
      throw new Error(data.error || data.message || `HTTP ${response.status}`);
    }
    return data;
  }

  function syncVoteModalBodyLock() {
    const overlayOpen = Boolean(els.voteOverlay && !els.voteOverlay.classList.contains("is-hidden"));
    const directOpen = Boolean(els.voteDirectModal && !els.voteDirectModal.classList.contains("is-hidden"));
    document.body.classList.toggle("vote-modal-open", overlayOpen || directOpen);
  }

  function hideVoteOverlay() {
    if (els.voteOverlay) {
      els.voteOverlay.classList.add("is-hidden");
      els.voteOverlay.classList.remove("is-lottery-rock");
      els.voteOverlay.setAttribute("aria-hidden", "true");
    }
    if (state.vote.lotterySpinTimer) {
      window.clearInterval(state.vote.lotterySpinTimer);
      state.vote.lotterySpinTimer = null;
    }
    if (els.voteLottery) {
      els.voteLottery.classList.add("is-hidden");
      els.voteLottery.classList.remove("is-spinning", "is-result", "is-yes", "is-no");
      els.voteLottery.setAttribute("aria-hidden", "true");
    }
    if (els.voteOverlayChoices) {
      els.voteOverlayChoices.classList.remove("is-hidden");
    }
    syncVoteModalBodyLock();
  }

  function hideVoteDirectModal() {
    if (els.voteDirectModal) {
      els.voteDirectModal.classList.add("is-hidden");
      els.voteDirectModal.setAttribute("aria-hidden", "true");
    }
    state.vote.pendingDirect = null;
    updateVoiceDropButtonState();
    syncVoteModalBodyLock();
  }

  function showVoteDirectModal(voteType, payload) {
    hideVoteOverlay();
    const copy = VOTE_DIRECT_COPY[voteType] || VOTE_DIRECT_COPY.library_request;
    state.vote.pendingDirect = { type: voteType, payload: payload || {} };
    if (els.voteDirectTitle) {
      if (voteType === "library_request" && payload?.title) {
        const artist = payload.artist ? ` — ${payload.artist}` : "";
        els.voteDirectTitle.textContent = `Pedir ${payload.title}${artist}?`;
      }
      else if (voteType === "library_clear") {
        const count = Number(payload?.track_count || payload?.count || 0);
        const suffix = count > 0 ? ` (${count} faixa(s))` : "";
        els.voteDirectTitle.textContent = `Zerar Minha playlist${suffix}?`;
      }
      else if (voteType === "spotify_import" && payload?.playlist_title) {
        els.voteDirectTitle.textContent = `${payload.playlist_title} — tocar agora?`;
      }
      else if (voteType === "spotify_import" && payload?.title) {
        els.voteDirectTitle.textContent = `Comecar com ${payload.title}?`;
      }
      else {
        els.voteDirectTitle.textContent = copy.title;
      }
    }
    if (els.voteDirectYes) {
      els.voteDirectYes.textContent = copy.yes;
    }
    if (els.voteDirectNo) {
      els.voteDirectNo.textContent = copy.no;
    }
    if (els.voteDirectModal) {
      els.voteDirectModal.classList.remove("is-hidden");
      els.voteDirectModal.setAttribute("aria-hidden", "false");
    }
    updateVoiceDropButtonState();
    syncVoteModalBodyLock();
  }

  function formatVoteTimer(seconds) {
    const safe = Math.max(Number(seconds) || 0, 0);
    const minutes = Math.floor(safe / 60);
    const rest = String(safe % 60).padStart(2, "0");
    return `${minutes}:${rest}`;
  }

  function getVoteAlertVolume() {
    const levels = getEffectiveStreamVolume();
    if (levels.muted) {
      return 0;
    }
    return Math.min(0.52, Math.max(0.16, levels.volume * 0.4));
  }

  async function playVoteAlertSound() {
    const volume = getVoteAlertVolume();
    if (volume <= 0) {
      return;
    }

    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) {
      return;
    }

    await ensureStreamDuckGraphReady();
    const duckReady = isStreamDuckGraphReady();
    const ctx = duckReady ? state.streamDuck.ctx : (state.vote.alertCtx || new AudioContextClass());

    if (!duckReady && !state.vote.alertCtx) {
      state.vote.alertCtx = ctx;
    }

    try {
      await ctx.resume();
    }
    catch (_error) {
      return;
    }

    const now = ctx.currentTime;
    const duration = 0.52;
    const master = ctx.createGain();
    master.gain.setValueAtTime(0.0001, now);
    master.gain.exponentialRampToValueAtTime(volume, now + 0.01);
    master.gain.exponentialRampToValueAtTime(0.0001, now + duration);

    if (duckReady) {
      master.connect(state.streamDuck.masterGain);
    }
    else {
      master.connect(ctx.destination);
    }

    const chord = [
      { freq: 82.41, type: "sawtooth", level: 0.46 },
      { freq: 123.47, type: "square", level: 0.3 },
      { freq: 164.81, type: "sawtooth", level: 0.24 },
      { freq: 220, type: "square", level: 0.18 }
    ];

    chord.forEach(({ freq, type, level }) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = type;
      osc.frequency.setValueAtTime(freq, now);
      osc.frequency.exponentialRampToValueAtTime(freq * 1.08, now + 0.045);
      gain.gain.value = level;
      osc.connect(gain);
      gain.connect(master);
      osc.start(now);
      osc.stop(now + duration + 0.03);
    });

    const bufferSize = Math.floor(ctx.sampleRate * 0.09);
    const noiseBuffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
    const noiseData = noiseBuffer.getChannelData(0);
    for (let index = 0; index < bufferSize; index += 1) {
      noiseData[index] = (Math.random() * 2 - 1) * (1 - index / bufferSize);
    }

    const noise = ctx.createBufferSource();
    noise.buffer = noiseBuffer;
    const noiseFilter = ctx.createBiquadFilter();
    noiseFilter.type = "highpass";
    noiseFilter.frequency.value = 1400;
    const noiseGain = ctx.createGain();
    noiseGain.gain.setValueAtTime(0.34, now + 0.035);
    noiseGain.gain.exponentialRampToValueAtTime(0.0001, now + 0.13);
    noise.connect(noiseFilter);
    noiseFilter.connect(noiseGain);
    noiseGain.connect(master);
    noise.start(now + 0.035);
    noise.stop(now + 0.14);
  }

  function isSoloVote(vote) {
    return Boolean(vote?.solo);
  }

  function getVoteDurationSec(vote) {
    if (isSoloVote(vote)) {
      return Math.max(Number(vote?.duration_sec) || Number(config.voteSoloDurationSec) || 6, 1);
    }
    return Math.max(Number(vote?.duration_sec) || Number(config.voteDurationSec) || 20, 1);
  }

  function notifyVoteStarted(vote) {
    if (!vote || vote.phase !== "open" || !vote.id || isSoloVote(vote)) {
      return;
    }
    if (state.vote.alertedVoteId === vote.id) {
      return;
    }
    state.vote.alertedVoteId = vote.id;
    playVoteAlertSound();
  }

  function renderVoteOverlay(vote) {
    if (!vote || !els.voteOverlay) {
      hideVoteOverlay();
      return;
    }

    hideVoteDirectModal();
    state.vote.active = vote;
    els.voteOverlay.classList.remove("is-hidden");
    els.voteOverlay.setAttribute("aria-hidden", "false");
    syncVoteModalBodyLock();

    if (els.voteOverlayEyebrow) {
      els.voteOverlayEyebrow.textContent = isSoloVote(vote) ? "So voce no ar" : "Votacao ao vivo";
    }
    if (els.voteOverlayTitle) {
      els.voteOverlayTitle.textContent = vote.title || "Votacao ao vivo";
    }
    if (els.voteOverlayMeta) {
      if (isSoloVote(vote)) {
        els.voteOverlayMeta.textContent = `${vote.yes_label || "Sim"} ou ${vote.no_label || "Nao"} — so voce decide`;
      }
      else {
        els.voteOverlayMeta.textContent = `${vote.eligible_snapshot || 0} ouvintes ouvindo · ${vote.yes_label || "Sim"} vs ${vote.no_label || "Nao"}`;
      }
    }
    if (els.voteYesLabel) {
      els.voteYesLabel.textContent = vote.yes_label || "Sim";
    }
    if (els.voteNoLabel) {
      els.voteNoLabel.textContent = vote.no_label || "Nao";
    }
    if (els.voteChoiceYes) {
      els.voteChoiceYes.textContent = vote.yes_label || "Sim";
    }
    if (els.voteChoiceNo) {
      els.voteChoiceNo.textContent = vote.no_label || "Nao";
    }

    const yesVotes = Number(vote.yes_votes || 0);
    const noVotes = Number(vote.no_votes || 0) + Number(vote.abstain || 0);
    const total = Math.max(yesVotes + noVotes, 1);
    if (els.voteYesCount) {
      els.voteYesCount.textContent = String(yesVotes);
    }
    if (els.voteNoCount) {
      els.voteNoCount.textContent = String(noVotes);
    }
    if (els.voteYesFill) {
      els.voteYesFill.style.width = `${(yesVotes / total) * 100}%`;
    }
    if (els.voteNoFill) {
      els.voteNoFill.style.width = `${(noVotes / total) * 100}%`;
    }
    if (els.voteOverlayTimer) {
      els.voteOverlayTimer.textContent = formatVoteTimer(vote.remaining_sec);
    }

    const phase = String(vote.phase || "open");
    const votingOpen = phase === "open";
    if (els.voteChoiceYes) {
      els.voteChoiceYes.disabled = !votingOpen;
    }
    if (els.voteChoiceNo) {
      els.voteChoiceNo.disabled = !votingOpen;
    }

    if (phase === "lottery") {
      showVoteLottery(vote.lottery_winner);
    }
    else if (els.voteLottery) {
      els.voteLottery.classList.add("is-hidden");
      els.voteLottery.setAttribute("aria-hidden", "true");
      if (els.voteOverlayChoices) {
        els.voteOverlayChoices.classList.toggle("is-hidden", !votingOpen);
      }
    }

    if (els.voteOverlayStatus) {
      const durationSec = getVoteDurationSec(vote);
      if (phase === "executing") {
        els.voteOverlayStatus.textContent = "Executando o veredito da galera...";
      }
      else if (phase === "closed") {
        els.voteOverlayStatus.textContent = vote.message || vote.execution?.message || "Votacao encerrada.";
      }
      else if (phase === "lottery") {
        els.voteOverlayStatus.textContent = "Empate! Sorteio rock no ar...";
      }
      else if (isSoloVote(vote)) {
        els.voteOverlayStatus.textContent = `Confirma em ate ${durationSec}s — ao votar, a troca e na hora.`;
      }
      else if (vote.type === "skip_track") {
        els.voteOverlayStatus.textContent = `Vote agora — ${durationSec} segundos. Empate vira sorteio rock: pula ou deixa rolar.`;
      }
      else if (vote.type === "library_request") {
        els.voteOverlayStatus.textContent = `Vote agora — ${durationSec}s. Tocar ja pula pra faixa; Na fila entra sem pular. Empate = sorteio.`;
      }
      else if (vote.type === "library_clear") {
        els.voteOverlayStatus.textContent = `Vote agora — ${durationSec}s. Zerar apaga Minha playlist neste navegador. Empate = sorteio.`;
      }
      else if (vote.type === "spotify_import") {
        els.voteOverlayStatus.textContent = `Vote agora — ${durationSec}s. Tocar ja comeca a playlist; Na fila so enfileira. Empate = sorteio.`;
      }
      else {
        els.voteOverlayStatus.textContent = `Vote agora — ${durationSec} segundos. Quem nao votar conta como nao. Empate = sorteio.`;
      }
    }

    if (state.vote.countdownTimer) {
      window.clearInterval(state.vote.countdownTimer);
      state.vote.countdownTimer = null;
    }
    if (phase === "open") {
      state.vote.countdownTimer = window.setInterval(() => {
        const current = state.vote.active;
        if (!current || current.id !== vote.id || current.phase !== "open") {
          return;
        }
        const nextRemaining = Math.max(Number(current.remaining_sec || 0) - 1, 0);
        current.remaining_sec = nextRemaining;
        if (els.voteOverlayTimer) {
          els.voteOverlayTimer.textContent = formatVoteTimer(nextRemaining);
        }
        if (nextRemaining <= 0 && state.vote.countdownTimer) {
          window.clearInterval(state.vote.countdownTimer);
          state.vote.countdownTimer = null;
        }
      }, 1000);
    }
  }

  function showVoteLottery(winner) {
    if (!els.voteLottery) {
      return;
    }

    if (els.voteOverlayChoices) {
      els.voteOverlayChoices.classList.add("is-hidden");
    }

    if (state.vote.lotterySpinTimer) {
      window.clearInterval(state.vote.lotterySpinTimer);
      state.vote.lotterySpinTimer = null;
    }

    els.voteLottery.classList.remove("is-hidden", "is-result", "is-yes", "is-no");
    els.voteLottery.classList.add("is-spinning");
    els.voteLottery.setAttribute("aria-hidden", "false");

    if (els.voteOverlay) {
      els.voteOverlay.classList.add("is-lottery-rock");
    }

    const wheelFace = els.voteLotteryWheel
      ? (els.voteLotteryWheel.querySelector(".vote-lottery__wheel-face") || els.voteLotteryWheel)
      : null;

    if (els.voteLotteryWheel) {
      els.voteLotteryWheel.style.removeProperty("--lottery-stop");
    }

    if (els.voteLotteryResult) {
      els.voteLotteryResult.textContent = "Roleta do rock no vermelho...";
    }

    void playVoteAlertSound();

    const spinLabels = ["ROCK", "PULA!", "NAO!", "METAL", "FOGO", "SORTE", "GRALE", "POW!"];
    let spinIndex = 0;

    if (wheelFace) {
      wheelFace.textContent = spinLabels[0];
    }

    state.vote.lotterySpinTimer = window.setInterval(() => {
      spinIndex += 1;
      if (wheelFace) {
        wheelFace.textContent = spinLabels[spinIndex % spinLabels.length];
      }
    }, 85);

    window.setTimeout(() => {
      if (state.vote.lotterySpinTimer) {
        window.clearInterval(state.vote.lotterySpinTimer);
        state.vote.lotterySpinTimer = null;
      }

      const yesWon = String(winner || "").toLowerCase() === "yes";

      if (els.voteLotteryWheel) {
        els.voteLotteryWheel.style.setProperty("--lottery-stop", yesWon ? "18deg" : "-24deg");
      }

      if (els.voteLottery) {
        els.voteLottery.classList.remove("is-spinning");
        els.voteLottery.classList.add("is-result", yesWon ? "is-yes" : "is-no");
      }

      if (wheelFace) {
        wheelFace.textContent = yesWon ? "PULA!" : "NAO!";
      }
      if (els.voteLotteryResult) {
        els.voteLotteryResult.textContent = yesWon
          ? "A roleta EXPLODIU: VAI PULAR!"
          : "A roleta segurou: DEIXA ROLAR!";
      }
    }, 2800);
  }

  function handleVoteClosed(vote) {
    if (!vote || !vote.id || state.vote.lastHandledClosedId === vote.id) {
      return;
    }
    state.vote.lastHandledClosedId = vote.id;
    renderVoteOverlay(vote);
    const execution = vote.execution;
    const failed = execution && execution.ok === false;
    const message = failed
      ? (execution.error || execution.message || vote.message || "Comando falhou.")
      : (vote.message || execution?.message || "Votacao encerrada.");
    if (
      vote.type === "library_clear"
      && !failed
      && execution?.clear_custom_playlist === true
    ) {
      clearCustomPlaylist();
    }
    setMessage(message);
    void triggerHoshinoVoteNarration(vote);
    const closeDelay = isSoloVote(vote) ? 900 : 2600;
    window.setTimeout(() => {
      hideVoteOverlay();
      state.vote.active = null;
      updateVoiceDropButtonState();
      void flushPendingVoiceDropPlayback();
      refreshNowPlaying({ silent: true });
    }, closeDelay);
  }

  function applyVoteUpdate(vote) {
    if (!vote) {
      hideVoteOverlay();
      state.vote.active = null;
      updateVoiceDropButtonState();
      void flushPendingVoiceDropPlayback();
      return;
    }

    if (vote.phase === "closed") {
      handleVoteClosed(vote);
      return;
    }

    notifyVoteStarted(vote);
    renderVoteOverlay(vote);
    updateVoiceDropButtonState();
  }

  function syncVoteFromNowPlaying(vote) {
    if (!isVoteEnabled()) {
      return;
    }
    if (vote && vote.phase && vote.phase !== "closed") {
      applyVoteUpdate(vote);
    }
  }

  function stopVoteRealtime() {
    if (state.vote.eventSource) {
      state.vote.eventSource.close();
      state.vote.eventSource = null;
    }
    if (state.vote.pollTimer) {
      window.clearInterval(state.vote.pollTimer);
      state.vote.pollTimer = null;
    }
  }

  function startVoteRealtime() {
    if (!isVoteEnabled()) {
      return;
    }

    stopVoteRealtime();
    const base = voteApiBase();
    if (typeof EventSource !== "undefined") {
      try {
        const source = new EventSource(`${base}/api/vote/events`);
        source.onmessage = (event) => {
          try {
            const payload = JSON.parse(event.data);
            if (payload.event === "vote_started" && payload.vote) {
              notifyVoteStarted(payload.vote);
            }
            if (payload.vote) {
              applyVoteUpdate(payload.vote);
            }
            if (payload.event === "vote_lottery" && payload.winner) {
              showVoteLottery(payload.winner);
            }
          }
          catch (parseError) {
            // ignore malformed SSE payloads
          }
        };
        source.onerror = () => {
          source.close();
          state.vote.eventSource = null;
          startVotePollFallback();
        };
        state.vote.eventSource = source;
        return;
      }
      catch (error) {
        startVotePollFallback();
      }
    }
    else {
      startVotePollFallback();
    }
  }

  function startVotePollFallback() {
    if (state.vote.pollTimer) {
      return;
    }
    state.vote.pollTimer = window.setInterval(async () => {
      try {
        const response = await fetch(`${voteApiBase()}/api/vote/active`, { cache: "no-store" });
        const data = await response.json();
        applyVoteUpdate(data.vote || null);
      }
      catch (error) {
        // poll silencioso
      }
    }, 1000);
  }

  async function castAudienceVote(choice) {
    const vote = state.vote.active;
    if (!vote || vote.phase !== "open") {
      return;
    }

    try {
      const result = await postJson(`${voteApiBase()}/api/vote/cast`, {
        vote_id: vote.id,
        listener_id: getListenerId(),
        choice
      });
      applyVoteUpdate(result.vote);
    }
    catch (error) {
      setMessage(`Voto falhou: ${error.message}`);
    }
  }

  async function executeDirectVote(choice) {
    const pending = state.vote.pendingDirect;
    if (!pending) {
      return;
    }

    const payload = pending.payload || {};

    try {
      const result = await postJson(`${voteApiBase()}/api/vote/execute-direct`, {
        type: pending.type,
        proposer_id: getListenerId(),
        choice,
        payload
      });
      hideVoteDirectModal();
      setMessage(result.message || "Comando executado.");
      if (
        pending.type === "library_clear"
        && choice === "yes"
        && result.execution?.clear_custom_playlist !== false
      ) {
        clearCustomPlaylist();
      }
      applyVoteCooldownStatus(result);
      if (result.narrator_moment) {
        void triggerHoshinoVoteNarration({
          narrator_moment: result.narrator_moment,
          payload,
          title: payload.title || els.trackTitle?.textContent || "essa faixa"
        });
      }
      window.setTimeout(() => refreshNowPlaying({ silent: true }), 2000);
    }
    catch (error) {
      const message = String(error.message || "");
      if (
        (message.includes("votacao coletiva") || message.includes("Mais de um ouvinte"))
        && usesCollectiveVoteUi(pending.type)
      ) {
        hideVoteDirectModal();
        await beginVoteFlow(pending.type, payload);
        return;
      }
      setMessage(`Comando falhou: ${message}`);
    }
  }

  function usesCollectiveVoteUi(voteType) {
    return voteType === "library_request" || voteType === "library_clear" || voteType === "spotify_import";
  }

  async function beginVoteFlow(voteType, payload) {
    const safePayload = payload || {};

    if (voteActionCooldownBlocked(voteType)) {
      setMessage(voteActionCooldownMessage());
      return;
    }

    if (!isVoteEnabled()) {
      if (voteType === "library_request") {
        const result = await postJson(`${voteApiBase()}/api/library/request`, {
          track_id: safePayload.track_id
        });
        setMessage(result.message || "Pedido enviado.");
        return;
      }
      setMessage("Votacao desligada ou API local indisponivel.");
      return;
    }

    try {
      await sendAudienceHeartbeat();
      const audience = await fetchAudienceCount();
      const totalOnSite = Number(audience.total_on_site || 0);
      const soloOnSite = totalOnSite <= 1;

      if (soloOnSite) {
        showVoteDirectModal(voteType, safePayload);
        setMessage(
          usesCollectiveVoteUi(voteType)
            ? "So voce no ar — Tocar ja pula pra faixa; Na fila so enfileira."
            : "So voce no ar — confirme no modal."
        );
        return;
      }

      const result = await postJson(`${voteApiBase()}/api/vote/start`, {
        type: voteType,
        proposer_id: getListenerId(),
        payload: safePayload
      });

      if (!result?.vote) {
        throw new Error("A API nao retornou a sessao de votacao.");
      }

      applyVoteCooldownStatus(result);
      applyVoteUpdate(result.vote);

      if (isSoloVote(result.vote)) {
        setMessage(
          usesCollectiveVoteUi(voteType)
            ? `So voce no ar — vote Tocar ja ou Na fila em ate ${getVoteDurationSec(result.vote)}s.`
            : `So voce no ar — vote em ate ${getVoteDurationSec(result.vote)}s.`
        );
      }
      else {
        setMessage("Votacao aberta! A galera decide agora (empate vira sorteio).");
      }
    }
    catch (error) {
      const message = String(error.message || "");
      if (message.includes("votacao em andamento")) {
        try {
          const active = await fetch(`${voteApiBase()}/api/vote/active`, { cache: "no-store" });
          const data = await active.json();
          if (data.vote) {
            applyVoteUpdate(data.vote);
            setMessage("Ja existe uma votacao em andamento — participe abaixo.");
            return;
          }
        }
        catch (activeError) {
          // ignore
        }
      }
      setMessage(`Votacao falhou: ${message}`);
    }
  }

  function libraryRequestBlockedMessage() {
    if (!canUseLibraryActions()) {
      return "Preview e pedido na radio exigem a API local. Rode .\\scripts\\start-local-api.ps1 e recarregue a pagina.";
    }
    return (
      "Pedir na radio exige API key do AzuraCast em data/azuracast-api-key.txt " +
      "(painel → My API Keys). Reinicie a API local depois de salvar."
    );
  }

  function canRequestOnRadio() {
    return canUseLibraryActions() && state.azuracastRequestsAvailable === true;
  }

  async function requestLibraryTrackWithVote(trackId) {
    const resolvedId = resolveLibraryPreviewId(trackId);
    const catalogTrack = findLibraryTrackById(resolvedId);
    const customTrack = state.customPlaylist.find((item) => String(item.id) === String(resolvedId));
    const track = catalogTrack || customTrack;
    if (!track) {
      setMessage("Faixa nao encontrada.");
      return;
    }

    if (!canRequestOnRadio()) {
      setMessage(libraryRequestBlockedMessage());
      return;
    }

    await beginVoteFlow("library_request", {
      track_id: resolvedId,
      title: track.title || "Faixa",
      artist: Array.isArray(track.artists) ? track.artists.join(", ") : (track.artist || "Artista")
    });
  }

  async function finalizeVoiceDropRecording() {
    if (!state.voiceDrop.recorder || state.voiceDrop.recorder.state === "inactive") {
      return;
    }

    const durationMs = Math.min(
      Math.max(Date.now() - state.voiceDrop.startedAt, 500),
      VOICE_DROP_MAX_MS
    );

    const recorder = state.voiceDrop.recorder;
    const chunks = state.voiceDrop.chunks;

    const blob = await new Promise((resolve) => {
      recorder.addEventListener("stop", () => {
        resolve(new Blob(chunks, { type: recorder.mimeType || "audio/webm" }));
      }, { once: true });
      recorder.stop();
    });

    clearVoiceDropTimers();
    stopVoiceDropStream();
    setVoiceDropRecordingUi(false);

    if (els.voiceDropTimer) {
      els.voiceDropTimer.textContent = formatVoiceDropTimer(VOICE_DROP_MAX_MS);
    }

    state.voiceDrop.uploading = true;
    updateVoiceDropButtonState();

    setVoiceDropStatus("Tratando voz de locutor e enviando para a radio...");

    try {
      const rawBuffer = await blob.arrayBuffer();
      await new Promise((resolve) => window.setTimeout(resolve, 0));
      const processed = await applyBroadcastVoiceEffect(rawBuffer);
      const result = await uploadVoiceDrop(processed.blob, processed.durationMs);
      const drop = result.voice_drop;

      if (drop) {
        await ensureStreamDuckGraphReady();
        const played = await playVoiceDrop(drop, {
          skipIfSender: false,
          localBlob: processed.blob,
          localBuffer: processed.buffer
        });
        setVoiceDropStatus(
          played
            ? "Sua chamada entrou no ar. Todos no site estao ouvindo."
            : state.voiceDrop.pendingPlayback
              ? "Chamada enviada — entra no ar quando a Miku ou a votacao liberarem."
              : "Chamada enviada, mas o navegador nao liberou a reproducao local."
        );
      }
      else {
        setVoiceDropStatus(result.message || "Chamada enviada.");
      }
    }
    catch (error) {
      setVoiceDropStatus(`Nao consegui enviar a chamada: ${error.message}`);
    }
    finally {
      state.voiceDrop.uploading = false;
      state.voiceDrop.recorder = null;
      state.voiceDrop.chunks = [];
      updateVoiceDropButtonState();
    }
  }

  async function startVoiceDropRecording() {
    if (state.voiceDrop.recording || state.voiceDrop.uploading) {
      return;
    }

    if (isVoiceDropRecordingBlocked()) {
      setVoiceDropStatus(voiceDropBlockedMessage());
      updateVoiceDropButtonState();
      return;
    }

    if (!window.isSecureContext) {
      setVoiceDropStatus(
        `Microfone no Chrome exige HTTPS. Abra ${getMobileHttpsFrontendUrl()} ` +
        "(aceite o certificado). Carregando infinito? No PC: .\\scripts\\test-https-frontend.ps1"
      );
      return;
    }

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setVoiceDropStatus(
        "Microfone indisponivel nesta pagina. Use HTTPS (porta 5443) ou localhost no PC."
      );
      return;
    }

    if (!config.localApiUrl) {
      setVoiceDropStatus("Configure a API local em frontend/config.js para enviar chamadas.");
      return;
    }

    try {
      setVoiceDropStatus("Pedindo permissao do microfone...");
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: false
        }
      });

      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : (MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "");

      const recorderOptions = mimeType ? { mimeType, audioBitsPerSecond: 128000 } : {};
      const recorder = Object.keys(recorderOptions).length
        ? new MediaRecorder(stream, recorderOptions)
        : new MediaRecorder(stream);
      state.voiceDrop.stream = stream;
      state.voiceDrop.recorder = recorder;
      state.voiceDrop.chunks = [];
      state.voiceDrop.startedAt = Date.now();

      recorder.addEventListener("dataavailable", (event) => {
        if (event.data && event.data.size > 0) {
          state.voiceDrop.chunks.push(event.data);
        }
      });

      recorder.start();
      setVoiceDropRecordingUi(true);
      startVoiceDropWaveform(stream);
      setVoiceDropStatus("Gravando... fale agora. Sua voz entra na Alta Cupula.");

      state.voiceDrop.tickTimer = window.setInterval(() => {
        const remaining = VOICE_DROP_MAX_MS - (Date.now() - state.voiceDrop.startedAt);
        if (els.voiceDropTimer) {
          els.voiceDropTimer.textContent = formatVoiceDropTimer(remaining);
        }
      }, 200);

      state.voiceDrop.timer = window.setTimeout(() => {
        finalizeVoiceDropRecording();
      }, VOICE_DROP_MAX_MS);
    }
    catch (error) {
      stopVoiceDropStream();
      setVoiceDropRecordingUi(false);
      setVoiceDropStatus(getVoiceDropMicErrorMessage(error));
    }
  }

  function bindVoiceDropEvents() {
    initVoiceDropWaveBars();

    if (els.voiceDropButton) {
      els.voiceDropButton.addEventListener("click", startVoiceDropRecording);
    }

    if (els.voiceDropStopButton) {
      els.voiceDropStopButton.addEventListener("click", finalizeVoiceDropRecording);
    }
  }

  function registerServiceWorker() {
    if (!("serviceWorker" in navigator)) {
      return;
    }

    if (!/^https?:$/.test(window.location.protocol)) {
      return;
    }

    navigator.serviceWorker.register("sw.js").catch(() => {
      setMessage("Service worker indisponivel neste navegador.");
    });
  }

  function renderAsciiFrame(frameData) {
    if (!els.asciiBackdrop) {
      return;
    }

    if (typeof frameData === "string") {
      els.asciiBackdrop.textContent = frameData;
      return;
    }

    const renderColored = window.RADIOPOGGERS_ASCII_RENDER;
    if (typeof renderColored === "function") {
      els.asciiBackdrop.innerHTML = renderColored(frameData);
      return;
    }

    els.asciiBackdrop.textContent = frameData
      .map((line) => line.map((part) => part.t).join(""))
      .join("\n");
  }

  function isAsciiMusicPlaying() {
    if (isTransmissionOffline()) {
      return false;
    }
    return isLiveStreamPlaying() || isDemoAudioPlaying();
  }

  function resolveAsciiMode() {
    if (isTransmissionOffline()) {
      return "off";
    }
    if (isAsciiMusicPlaying()) {
      return "play";
    }
    return "idle";
  }

  function syncAsciiOffGifFallback(useGif) {
    state.asciiOffGifFallback = Boolean(useGif);
    if (els.asciiBackdropOffGif) {
      els.asciiBackdropOffGif.classList.toggle("is-visible", state.asciiOffGifFallback);
      els.asciiBackdropOffGif.setAttribute("aria-hidden", state.asciiOffGifFallback ? "true" : "true");
    }
    if (els.asciiBackdrop) {
      els.asciiBackdrop.classList.toggle("is-hidden", state.asciiOffGifFallback);
    }
  }

  function resolveAsciiPaintFn() {
    const mode = resolveAsciiMode();
    if (mode === "play") {
      return typeof asciiPlayPaint === "function"
        ? asciiPlayPaint
        : asciiPaint;
    }

    if (mode === "off") {
      return typeof asciiOffPaint === "function" ? asciiOffPaint : null;
    }

    if (typeof asciiIdlePaint === "function") {
      return asciiIdlePaint;
    }

    return asciiPaint;
  }

  function refreshAsciiBackdropMode() {
    const nextMode = resolveAsciiMode();
    const modeChanged = nextMode !== state.asciiMode;
    state.asciiMode = nextMode;

    if (els.asciiBackdrop) {
      els.asciiBackdrop.classList.toggle("is-off-air", nextMode === "off");
    }

    if (nextMode === "off" && typeof asciiOffPaint !== "function") {
      syncAsciiOffGifFallback(true);
      if (els.asciiBackdropOffGif && !els.asciiBackdropOffGif.getAttribute("src")) {
        els.asciiBackdropOffGif.src = asciiOffGifUrl;
      }
    }
    else {
      syncAsciiOffGifFallback(false);
    }

    return modeChanged;
  }

  function getAsciiFrameIntervalMs(hasCanvasPaint, hasGenerator) {
    return hasCanvasPaint ? asciiFrameMs : (hasGenerator ? 110 : 380);
  }

  function startAsciiBackdrop() {
    const hasCanvasPaint = typeof asciiPaint === "function" ||
      typeof asciiPlayPaint === "function" ||
      typeof asciiIdlePaint === "function";
    const hasGenerator = typeof asciiGenerate === "function";
    if (!els.asciiBackdrop || (!hasCanvasPaint && !hasGenerator && !asciiFrames.length)) {
      return;
    }

    let tick = 0;
    state.asciiMode = resolveAsciiMode();
    const reducedMotion = window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const renderTick = () => {
      if (refreshAsciiBackdropMode()) {
        tick = 0;
      }

      if (state.asciiOffGifFallback) {
        return;
      }

      const paintFn = resolveAsciiPaintFn();
      if (typeof paintFn === "function") {
        paintFn(els.asciiBackdrop, tick);
        return;
      }

      const nextFrame = hasGenerator ? asciiGenerate(tick) : asciiFrames[tick % asciiFrames.length];
      renderAsciiFrame(nextFrame);
    };

    const scheduleNextAsciiFrame = () => {
      if (state.asciiLoopTimer) {
        window.clearTimeout(state.asciiLoopTimer);
      }

      if (reducedMotion) {
        return;
      }

      state.asciiLoopTimer = window.setTimeout(() => {
        tick += 1;
        renderTick();
        scheduleNextAsciiFrame();
      }, getAsciiFrameIntervalMs(hasCanvasPaint, hasGenerator));
    };

    const beginLoop = () => {
      renderTick();
      scheduleNextAsciiFrame();
    };

    if (typeof asciiInit === "function") {
      asciiInit()
        .then(beginLoop)
        .catch(() => {
          if (isTransmissionOffline()) {
            refreshAsciiBackdropMode();
            beginLoop();
            return;
          }
          setMessage("Animacao ASCII indisponivel.");
        });
      return;
    }

    beginLoop();
  }

  function loadCustomPlaylist() {
    try {
      const raw = window.localStorage.getItem(CUSTOM_PLAYLIST_KEY);
      const parsed = raw ? JSON.parse(raw) : [];
      state.customPlaylist = Array.isArray(parsed) ? parsed : [];
    }
    catch (error) {
      state.customPlaylist = [];
    }
    renderCustomPlaylistPanel();
  }

  function saveCustomPlaylist() {
    window.localStorage.setItem(CUSTOM_PLAYLIST_KEY, JSON.stringify(state.customPlaylist));
    renderCustomPlaylistPanel();
  }

  function renderCustomPlaylistPanel() {
    const count = state.customPlaylist.length;

    if (els.libraryCustomCount) {
      els.libraryCustomCount.textContent = `${count} faixa(s)`;
    }

    if (els.libraryCustomPanel) {
      els.libraryCustomPanel.classList.toggle("has-tracks", count > 0);
    }

    if (els.libraryCustomHint) {
      if (count > 0 && !canRequestOnRadio()) {
        els.libraryCustomHint.textContent = libraryRequestBlockedMessage();
      }
      else if (state.vote.actionCooldownRemainingSec > 0) {
        els.libraryCustomHint.textContent = voteActionCooldownMessage();
      }
      else {
        els.libraryCustomHint.textContent = count > 0
          ? "Ouvir e so previa local. Use Pedir na faixa; intervalo entre pular, pedir ou zerar."
          : "Toque em + Lista na estante para montar sua selecao, ou Pedir direto na faixa.";
      }
    }

    const voteCooldownBlocked = state.vote.actionCooldownRemainingSec > 0;

    if (els.libraryRequestButton) {
      els.libraryRequestButton.disabled = count === 0 || !canRequestOnRadio() || voteCooldownBlocked;
      els.libraryRequestButton.title = voteCooldownBlocked ? voteActionCooldownMessage() : "";
    }

    if (els.libraryClearCustomButton) {
      els.libraryClearCustomButton.disabled = count === 0 || voteCooldownBlocked;
      els.libraryClearCustomButton.title = voteCooldownBlocked
        ? voteActionCooldownMessage()
        : "Abrir votacao para zerar Minha playlist";
    }

    if (!els.libraryCustomList) {
      return;
    }

    if (!count) {
      els.libraryCustomList.innerHTML = "<li class=\"library-custom-empty\">Nenhuma faixa selecionada ainda.</li>";
      return;
    }

    els.libraryCustomList.innerHTML = state.customPlaylist.map((item, index) => {
      const catalogTrack = findLibraryTrackById(item.id);
      const artists = Array.isArray(item.artists) && item.artists.length
        ? item.artists.join(", ")
        : (Array.isArray(catalogTrack?.artists) ? catalogTrack.artists.join(", ") : "");
      const album = item.album || catalogTrack?.album || "";
      const albumSuffix = album ? ` · ${album}` : "";
      const cover = resolveArtUrl(catalogTrack?.cover_url) || fallbackCover;
      const trackId = escapeAttribute(item.id || "");
      const isFirst = index === 0;

      return `
        <li class="history-item library-custom-item${isFirst ? " is-first-in-queue" : ""}" data-track-id="${trackId}">
          <img src="${escapeAttribute(cover)}" alt="">
          <span>
            <strong>${escapeHtml(item.title || catalogTrack?.title || "Faixa sem nome")}</strong>
            <small>${escapeHtml(artists)}${escapeHtml(albumSuffix)}${isFirst ? " · proxima no pedido" : ""}</small>
          </span>
          <span class="library-item-actions library-item-actions--custom">
            <button
              class="library-action-button library-action-button--request custom-request-button"
              type="button"
              data-shelf-request="${trackId}"
              data-shelf-title="${escapeAttribute(item.title || catalogTrack?.title || "Faixa")}"
              ${canRequestOnRadio() ? "" : "disabled"}
              aria-label="Pedir ${escapeAttribute(item.title || catalogTrack?.title || "faixa")} na radio"
            >Pedir</button>
            <button class="library-action-button library-action-button--remove remove-track-button" type="button" data-track-id="${trackId}" aria-label="Remover da lista">Remover</button>
          </span>
        </li>
      `;
    }).join("");
  }

  function isTrackInCustomPlaylist(trackId) {
    const safeId = String(trackId || "");
    return state.customPlaylist.some((item) => String(item.id) === safeId);
  }

  function toggleCustomPlaylistTrack(track) {
    const trackId = resolveLibraryPreviewId(track);
    if (!trackId) {
      return;
    }

    if (isTrackInCustomPlaylist(trackId)) {
      state.customPlaylist = state.customPlaylist.filter((item) => String(item.id) === trackId);
    }
    else {
      state.customPlaylist.push({
        id: trackId,
        title: track.title || "",
        artists: Array.isArray(track.artists) ? track.artists : [],
        album: track.album || ""
      });
    }

    saveCustomPlaylist();
    renderLibraryList(window.__libraryTracks || []);
  }

  function exportCustomPlaylist() {
    if (!state.customPlaylist.length) {
      setMessage("Minha playlist esta vazia. Marque faixas com + Lista.");
      return;
    }

    const text = state.customPlaylist
      .map((item) => {
        const artists = Array.isArray(item.artists) ? item.artists.join(", ") : "";
        return `${artists} - ${item.title}`.trim();
      })
      .join("\n");

    navigator.clipboard.writeText(text).then(() => {
      setMessage("Lista copiada para a area de transferencia.");
    }).catch(() => {
      setMessage(text);
    });
  }

  function clearCustomPlaylist() {
    state.customPlaylist = [];
    saveCustomPlaylist();
    renderLibraryList(window.__libraryTracks || []);
  }

  async function beginClearCustomPlaylistVote() {
    if (!state.customPlaylist.length) {
      setMessage("Minha playlist ja esta vazia.");
      return;
    }

    await beginVoteFlow("library_clear", {
      track_count: state.customPlaylist.length
    });
  }

  function libraryTrackMatchesId(track, trackId) {
    const safeId = String(trackId || "");
    if (!safeId || !track) {
      return false;
    }

    return (
      String(track.id || "") === safeId
      || String(track.spotify_id || "") === safeId
    );
  }

  function findLibraryTrackById(trackId) {
    const safeId = String(trackId || "");
    if (!safeId) {
      return null;
    }

    const fromBrowse = (window.__libraryTracks || []).find((item) => libraryTrackMatchesId(item, safeId));
    if (fromBrowse) {
      return fromBrowse;
    }

    const fromCustom = state.customPlaylist.find((item) => String(item.id) === safeId);
    if (!fromCustom) {
      return null;
    }

    const catalogMatch = (window.__libraryTracks || []).find((item) => libraryTracksAreSameSong(item, fromCustom));
    return catalogMatch || fromCustom;
  }

  function resolveLibraryPreviewId(trackOrId) {
    const track = typeof trackOrId === "object" && trackOrId
      ? trackOrId
      : findLibraryTrackById(trackOrId);
    return String(track?.id || track?.spotify_id || trackOrId || "").trim();
  }

  function removeCustomPlaylistTrack(trackId) {
    const safeId = String(trackId || "");
    if (!safeId || !isTrackInCustomPlaylist(safeId)) {
      return;
    }

    state.customPlaylist = state.customPlaylist.filter((item) => item.id !== safeId);
    saveCustomPlaylist();
    renderLibraryList(window.__libraryTracks || []);
  }

  function handleLibraryTrackClick(event, options = {}) {
    const target = event.target;
    if (!(target instanceof Element)) {
      return;
    }

    if (target.closest("[data-shelf-listen]") || target.closest("[data-shelf-request]")) {
      return;
    }

    const actionButton = target.closest("[data-track-id]");
    if (!actionButton) {
      return;
    }

    const trackId = actionButton.getAttribute("data-track-id");
    if (!trackId) {
      return;
    }

    if (actionButton.classList.contains("remove-track-button")) {
      removeCustomPlaylistTrack(trackId);
      return;
    }

    if (options.allowCustomToggle && actionButton.classList.contains("custom-track-button")) {
      const track = findLibraryTrackById(trackId);
      if (track) {
        toggleCustomPlaylistTrack(track);
      }
    }
  }

  function refreshLibraryTrackUi() {
    renderLibraryList(window.__libraryTracks || []);
    renderCustomPlaylistPanel();
  }

  function canUseLibraryActions() {
    return Boolean(localApiBase());
  }

  function libraryTrackDedupKey(track) {
    const spotifyId = String(track?.spotify_id || "").trim();
    if (spotifyId) {
      return `spotify:${spotifyId}`;
    }

    const isrc = String(track?.isrc || "").trim();
    if (isrc) {
      return `isrc:${isrc}`;
    }

    const artists = Array.isArray(track?.artists) ? track.artists : [];
    const artistText = normalizeSearchText(artists.join(" "));
    const titleText = normalizeSearchText(track?.title || "");
    if (artistText) {
      return `text:${titleText}:${artistText}`;
    }

    return `title:${titleText}`;
  }

  function libraryTracksAreSameSong(left, right) {
    const leftSpotify = String(left?.spotify_id || "").trim();
    const rightSpotify = String(right?.spotify_id || "").trim();
    if (leftSpotify && rightSpotify) {
      return leftSpotify === rightSpotify;
    }

    const leftIsrc = String(left?.isrc || "").trim();
    const rightIsrc = String(right?.isrc || "").trim();
    if (leftIsrc && rightIsrc) {
      return leftIsrc === rightIsrc;
    }

    const leftTitle = normalizeSearchText(left?.title || "");
    const rightTitle = normalizeSearchText(right?.title || "");
    if (!leftTitle || leftTitle !== rightTitle) {
      return false;
    }

    if (leftSpotify || rightSpotify) {
      return true;
    }

    const leftArtists = Array.isArray(left?.artists) ? left.artists : [];
    const rightArtists = Array.isArray(right?.artists) ? right.artists : [];
    const leftArtistText = normalizeSearchText(leftArtists.join(" "));
    const rightArtistText = normalizeSearchText(rightArtists.join(" "));

    if (!leftArtistText || !rightArtistText) {
      return true;
    }

    return leftArtistText === rightArtistText;
  }

  function mergeLibraryTrackForDisplay(existing, incoming) {
    const merged = { ...existing };
    const spotifyId = String(incoming?.spotify_id || existing?.spotify_id || "").trim();

    merged.title = incoming?.title || existing?.title;
    merged.artists = (incoming?.artists && incoming.artists.length) ? incoming.artists : existing?.artists;
    merged.album = incoming?.album || existing?.album;
    merged.cover_url = incoming?.cover_url || existing?.cover_url;
    merged.spotify_id = incoming?.spotify_id || existing?.spotify_id;
    merged.isrc = incoming?.isrc || existing?.isrc;
    merged.local_file = incoming?.local_file || existing?.local_file;
    merged.id = spotifyId || incoming?.id || existing?.id;

    return merged;
  }

  function deduplicateLibraryTracks(tracks) {
    const consolidated = [];

    for (const track of Array.isArray(tracks) ? tracks : []) {
      const index = consolidated.findIndex((existing) => libraryTracksAreSameSong(existing, track));
      if (index === -1) {
        consolidated.push({ ...track });
      }
      else {
        consolidated[index] = mergeLibraryTrackForDisplay(consolidated[index], track);
      }
    }

    return consolidated.sort((left, right) => {
      const leftArtists = normalizeSearchText((left.artists || []).join(" "));
      const rightArtists = normalizeSearchText((right.artists || []).join(" "));
      if (leftArtists !== rightArtists) {
        return leftArtists.localeCompare(rightArtists);
      }

      return normalizeSearchText(left.title || "").localeCompare(normalizeSearchText(right.title || ""));
    });
  }

  function libraryQueryParams() {
    return {
      q: els.librarySearchInput ? els.librarySearchInput.value.trim() : "",
      artist: els.libraryArtistFilter ? els.libraryArtistFilter.value.trim() : "",
      album: els.libraryAlbumFilter ? els.libraryAlbumFilter.value.trim() : "",
      limit: 100,
      offset: 0
    };
  }

  function buildLibraryUrl(params, options = {}) {
    const search = new URLSearchParams();
    if (params.q) {
      search.set("q", params.q);
    }
    if (params.artist) {
      search.set("artist", params.artist);
    }
    if (params.album) {
      search.set("album", params.album);
    }
    search.set("limit", String(params.limit || 100));
    search.set("offset", String(params.offset || 0));
    if (options.forceRefresh) {
      search.set("refresh", "1");
    }
    return `${localApiBase()}/api/library?${search.toString()}`;
  }

  function libraryRevisionNumber(meta) {
    if (!meta || meta.revision === undefined || meta.revision === null) {
      return null;
    }
    return Number(meta.revision);
  }

  function applyLibraryCatalogMeta(meta) {
    const revision = libraryRevisionNumber(meta);
    if (revision === null || Number.isNaN(revision)) {
      return;
    }
    state.libraryCatalogRevision = revision;
  }

  function libraryCatalogRevisionChanged(meta) {
    const revision = libraryRevisionNumber(meta);
    if (revision === null || Number.isNaN(revision)) {
      return false;
    }
    if (state.libraryCatalogRevision === null) {
      applyLibraryCatalogMeta(meta);
      return false;
    }
    return revision !== Number(state.libraryCatalogRevision);
  }

  async function fetchLibraryCatalogMeta(options = {}) {
    if (!canUseLibraryActions()) {
      return null;
    }

    const search = options.forceRefresh ? "?refresh=1" : "";
    return fetchJson(
      `${localApiBase()}/api/library/meta${search}`,
      { timeoutMs: 8000 }
    ).then((payload) => payload.catalog || payload.catalog_meta || null);
  }

  async function maybeRefreshLibraryFromMeta(meta, options = {}) {
    const force = Boolean(options.force);
    const silent = options.silent !== false;

    if (!meta) {
      return false;
    }

    if (!force && !libraryCatalogRevisionChanged(meta)) {
      return false;
    }

    applyLibraryCatalogMeta(meta);
    await refreshLibraryShelf({ force, silent });
    return true;
  }

  async function refreshLibraryShelf(options = {}) {
    state.libraryFiltersCache = null;
    await loadLibraryCatalog({
      silent: Boolean(options.silent),
      forceRefresh: Boolean(options.force)
    });
  }

  function stopLibraryCatalogWatcher() {
    if (state.libraryCatalogWatcherTimer) {
      window.clearInterval(state.libraryCatalogWatcherTimer);
      state.libraryCatalogWatcherTimer = null;
    }
  }

  function startLibraryCatalogWatcher() {
    if (!canUseLibraryActions()) {
      return;
    }

    const intervalMs = Math.max(Number(config.libraryAutoRefreshMs) || 15000, 8000);
    stopLibraryCatalogWatcher();

    state.libraryCatalogWatcherTimer = window.setInterval(async () => {
      if (document.visibilityState === "hidden" && !state.playlistImportInProgress) {
        return;
      }

      try {
        const meta = await fetchLibraryCatalogMeta();
        await maybeRefreshLibraryFromMeta(meta, { silent: true });
      }
      catch (error) {
        // watcher silencioso
      }
    }, intervalMs);
  }

  function normalizeSearchText(value) {
    return String(value || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, " ")
      .trim();
  }

  function filterLibraryTracksClient(tracks, params) {
    const queryKey = normalizeSearchText(params.q);
    const artistKey = normalizeSearchText(params.artist);
    const albumKey = normalizeSearchText(params.album);
    const limit = Math.max(Math.min(Number(params.limit) || 100, 200), 1);
    const offset = Math.max(Number(params.offset) || 0, 0);

    const filtered = (Array.isArray(tracks) ? tracks : []).filter((track) => {
      const trackArtists = Array.isArray(track.artists) ? track.artists : [];
      const artistText = normalizeSearchText(trackArtists.join(", "));
      const titleText = normalizeSearchText(track.title);
      const albumText = normalizeSearchText(track.album);
      const haystack = normalizeSearchText(`${artistText} ${titleText} ${albumText}`);

      if (artistKey && !artistText.includes(artistKey)) {
        return false;
      }
      if (albumKey && !albumText.includes(albumKey)) {
        return false;
      }
      if (queryKey && !haystack.includes(queryKey)) {
        return false;
      }

      return true;
    });

    const deduped = deduplicateLibraryTracks(filtered);

    return {
      tracks: deduped.slice(offset, offset + limit),
      total: deduped.length
    };
  }

  function libraryFiltersFromTracks(tracks) {
    const artists = new Set();
    const albums = new Set();

    for (const track of Array.isArray(tracks) ? tracks : []) {
      for (const artist of track.artists || []) {
        if (artist) {
          artists.add(String(artist));
        }
      }
      if (track.album) {
        albums.add(String(track.album));
      }
    }

    return {
      artists: [...artists].sort((a, b) => normalizeSearchText(a).localeCompare(normalizeSearchText(b))),
      albums: [...albums].sort((a, b) => normalizeSearchText(a).localeCompare(normalizeSearchText(b)))
    };
  }

  function staticLibraryCatalogUrl() {
    return config.libraryCatalogUrl || defaultConfig.libraryCatalogUrl || "../data/library-catalog.json";
  }

  async function fetchLibraryCatalogSource(signal, options = {}) {
    const params = libraryQueryParams();

    if (canUseLibraryActions()) {
      try {
        const payload = await fetchLibraryJson(buildLibraryUrl(params, options), signal);
        const tracks = deduplicateLibraryTracks(Array.isArray(payload.tracks) ? payload.tracks : []);
        applyLibraryCatalogMeta(payload.catalog_meta);

        return {
          ...payload,
          tracks,
          total: Number(payload.total ?? tracks.length),
          __source: "api",
          __previewLimited: false
        };
      }
      catch (apiError) {
        try {
          const payload = await fetchLibraryJson(staticLibraryCatalogUrl(), signal);
          const filtered = filterLibraryTracksClient(payload.tracks || [], params);
          return {
            ...payload,
            tracks: filtered.tracks,
            total: filtered.total,
            __source: "file",
            __previewLimited: true,
            __fallbackReason: apiError.message
          };
        }
        catch (fileError) {
          throw apiError;
        }
      }
    }

    const payload = await fetchLibraryJson(staticLibraryCatalogUrl(), signal);
    const filtered = filterLibraryTracksClient(payload.tracks || [], params);

    return {
      ...payload,
      tracks: filtered.tracks,
      total: filtered.total,
      __source: "file",
      __previewLimited: true
    };
  }

  function renderLibraryFilters(filters) {
    if (!els.libraryArtistFilter || !els.libraryAlbumFilter) {
      return;
    }

    const artists = Array.isArray(filters.artists) ? filters.artists : [];
    const albums = Array.isArray(filters.albums) ? filters.albums : [];
    const currentArtist = els.libraryArtistFilter.value;
    const currentAlbum = els.libraryAlbumFilter.value;

    els.libraryArtistFilter.innerHTML = [
      "<option value=\"\">Todos</option>",
      ...artists.map((artist) => `<option value="${escapeAttribute(artist)}">${escapeHtml(artist)}</option>`)
    ].join("");

    els.libraryAlbumFilter.innerHTML = [
      "<option value=\"\">Todos</option>",
      ...albums.map((album) => `<option value="${escapeAttribute(album)}">${escapeHtml(album)}</option>`)
    ].join("");

    if (currentArtist) {
      els.libraryArtistFilter.value = currentArtist;
    }
    if (currentAlbum) {
      els.libraryAlbumFilter.value = currentAlbum;
    }
  }

  async function loadLibraryFilters(options = {}) {
    if (!els.libraryArtistFilter) {
      return;
    }

    if (state.libraryFiltersCache && !options.force) {
      renderLibraryFilters(state.libraryFiltersCache);
      return;
    }

    if (config.localApiUrl) {
      try {
        const refresh = options.forceRefresh ? "?refresh=1" : "";
        const payload = await fetchLibraryJson(
          `${localApiBase()}/api/library/filters${refresh}`
        );
        applyLibraryCatalogMeta(payload.catalog_meta);
        const filters = payload.filters || {};
        state.libraryFiltersCache = filters;
        renderLibraryFilters(filters);
        return;
      }
      catch (error) {
        // Tenta derivar filtros do catalogo estatico abaixo.
      }
    }

    try {
      const catalog = await fetchLibraryJson(staticLibraryCatalogUrl());
      const filters = libraryFiltersFromTracks(catalog.tracks || []);
      state.libraryFiltersCache = filters;
      renderLibraryFilters(filters);
    }
    catch (error) {
      // Filtros sao opcionais; a lista principal continua funcionando.
    }
  }

  function renderLibraryList(tracks) {
    window.__libraryTracks = tracks;

    if (!els.libraryList) {
      return;
    }

    if (!Array.isArray(tracks) || tracks.length === 0) {
      els.libraryList.innerHTML = "<li>Nenhuma faixa encontrada.</li>";
      return;
    }

    els.libraryList.innerHTML = tracks.map((track) => {
      const artists = Array.isArray(track.artists) ? track.artists.join(", ") : "";
      const album = track.album ? ` · ${track.album}` : "";
      const cover = resolveArtUrl(track.cover_url) || fallbackCover;
      const previewId = resolveLibraryPreviewId(track);
      const trackId = escapeAttribute(previewId || track.id || "");
      const isPreviewing = String(state.shelfPreview.trackId) === String(previewId);
      const previewPlaying = isPreviewing && isShelfPreviewPlaying();
      const inCustom = isTrackInCustomPlaylist(previewId);

      return `
        <li class="history-item library-item${isPreviewing ? " is-previewing" : ""}${inCustom ? " is-in-custom" : ""}" data-track-id="${trackId}">
          <img src="${escapeAttribute(cover)}" alt="">
          <span>
            <strong>${escapeHtml(track.title || "Faixa sem nome")}</strong>
            <small>${escapeHtml(artists)}${escapeHtml(album)}</small>
          </span>
          <span class="library-item-actions library-item-actions--browse">
            <button
              type="button"
              class="shelf-listen-btn${previewPlaying ? " is-playing" : ""}"
              data-shelf-listen="${trackId}"
              data-shelf-title="${escapeAttribute(track.title || "Faixa")}"
              aria-pressed="${previewPlaying ? "true" : "false"}"
              aria-label="Ouvir previa local de ${escapeAttribute(track.title || "faixa")}"
            >
              <span class="shelf-listen-btn__icon" aria-hidden="true">${previewPlaying ? "■" : "▶"}</span>
              <span class="shelf-listen-btn__label">${previewPlaying ? "Parar" : "Ouvir"}</span>
            </button>
            <button class="library-action-button library-action-button--list custom-track-button${inCustom ? " is-active" : ""}" type="button" data-track-id="${trackId}" aria-pressed="${inCustom ? "true" : "false"}">${inCustom ? "Na lista" : "+ Lista"}</button>
            <button
              type="button"
              class="library-action-button library-action-button--request"
              data-shelf-request="${trackId}"
              data-shelf-title="${escapeAttribute(track.title || "Faixa")}"
              ${canRequestOnRadio() ? "" : "disabled"}
              aria-label="Pedir ${escapeAttribute(track.title || "faixa")} na radio"
            >Pedir</button>
          </span>
        </li>
      `;
    }).join("");
  }

  async function loadLibraryCatalog(options = {}) {
    if (!els.libraryList) {
      return;
    }

    if (!config.localApiUrl && !config.libraryCatalogUrl) {
      if (els.librarySummary) {
        els.librarySummary.textContent = "Configure localApiUrl ou libraryCatalogUrl em frontend/config.js.";
      }
      return;
    }

    const generation = (state.libraryLoadGeneration || 0) + 1;
    state.libraryLoadGeneration = generation;

    if (state.libraryFetchController) {
      state.libraryFetchController.abort();
    }

    const controller = new AbortController();
    state.libraryFetchController = controller;

    if (els.librarySummary && !options.silent) {
      els.librarySummary.textContent = "Carregando estante de discos...";
    }

    try {
      await probeLocalApiBase(Boolean(options.forceRefresh));
      const payload = await fetchLibraryCatalogSource(controller.signal, {
        forceRefresh: Boolean(options.forceRefresh)
      });
      if (generation !== state.libraryLoadGeneration) {
        return;
      }

      const total = payload.total ?? (payload.tracks || []).length;
      const summary = payload.summary || {};
      state.libraryUsesStaticCatalog = payload.__source === "file";

      if (payload.__source === "api") {
        void loadLibraryFilters({
          force: Boolean(options.forceRefresh),
          forceRefresh: Boolean(options.forceRefresh)
        });
      }
      else {
        state.libraryFiltersCache = libraryFiltersFromTracks(payload.tracks || []);
        renderLibraryFilters(state.libraryFiltersCache);
      }

      if (els.librarySummary) {
        const sourceHint = payload.__previewLimited
          ? (
            payload.__fallbackReason
              ? ` API lenta/offline (${payload.__fallbackReason}) — preview limitado.`
              : " Modo arquivo local — configure localApiUrl e reinicie a API para Ouvir/Pedir."
          )
          : "";
        const catalogTotal = summary.tracks || total;
        els.librarySummary.textContent = (
          `${total} faixa(s) na estante · ${catalogTotal} no catalogo.${sourceHint}`
        ).trim();
      }

      renderLibraryList(payload.tracks || []);
      renderCustomPlaylistPanel();
    }
    catch (error) {
      if (generation !== state.libraryLoadGeneration) {
        return;
      }

      if (controller.signal.aborted && String(error.message || "").includes("tempo esgotado")) {
        return;
      }

      if (els.librarySummary) {
        els.librarySummary.textContent = (
          `Estante indisponivel (${error.message || "erro"}). Rode .\\scripts\\start-local-api.ps1 e use Ctrl+F5.`
        );
      }
      els.libraryList.innerHTML = "<li>Nao foi possivel carregar a estante de discos.</li>";
    }
    finally {
      if (state.libraryFetchController === controller) {
        state.libraryFetchController = null;
      }
    }
  }

  function scheduleLibraryReload() {
    if (state.librarySearchTimer) {
      window.clearTimeout(state.librarySearchTimer);
    }

    state.librarySearchTimer = window.setTimeout(() => {
      loadLibraryCatalog();
    }, 300);
  }

  function getShelfPreviewAudio() {
    if (!els.shelfPreviewAudio) {
      els.shelfPreviewAudio = document.getElementById("shelfPreviewAudio");
    }
    return els.shelfPreviewAudio;
  }

  function isShelfPreviewPlaying() {
    const audio = getShelfPreviewAudio();
    return Boolean(state.shelfPreview.trackId && audio && !audio.paused && !audio.ended);
  }

  function formatMediaPlaybackError(error) {
    if (!error) {
      return "erro desconhecido";
    }

    if (error.name === "NotAllowedError") {
      return "o navegador bloqueou o audio — clique em Ouvir de novo";
    }

    return error.message || String(error);
  }

  function syncShelfPreviewVolume() {
    const audio = getShelfPreviewAudio();
    if (!audio) {
      return;
    }

    const levels = getStreamSliderVolume();
    audio.volume = levels.muted ? 0 : Math.max(levels.volume, 0.05);
    audio.muted = levels.muted;
  }

  function updateShelfPreviewBar() {
    if (!els.shelfPreviewBar) {
      return;
    }

    const active = Boolean(state.shelfPreview.trackId);
    els.shelfPreviewBar.classList.toggle("is-hidden", !active);

    if (els.shelfPreviewTitle) {
      els.shelfPreviewTitle.textContent = active ? (state.shelfPreview.title || "Faixa") : "—";
    }
  }

  function syncShelfListenButtons() {
    if (!els.libraryList) {
      return;
    }

    els.libraryList.querySelectorAll("[data-shelf-listen]").forEach((button) => {
      const id = button.getAttribute("data-shelf-listen") || "";
      const playing = String(state.shelfPreview.trackId) === String(id) && isShelfPreviewPlaying();
      button.classList.toggle("is-playing", playing);
      button.classList.remove("is-loading");
      button.setAttribute("aria-pressed", playing ? "true" : "false");

      const icon = button.querySelector(".shelf-listen-btn__icon");
      const label = button.querySelector(".shelf-listen-btn__label");
      if (icon) {
        icon.textContent = playing ? "■" : "▶";
      }
      if (label) {
        label.textContent = playing ? "Parar" : "Ouvir";
      }
    });
  }

  function pauseLocalRadioForShelfPreview() {
    state.shelfPreview.radioWasPlaying = false;

    if (state.activeDemoStream) {
      state.shelfPreview.radioWasPlaying = isDemoAudioPlaying();
      if (state.shelfPreview.radioWasPlaying) {
        stopDemoAudio();
      }
      return;
    }

    const active = getActiveStreamEl();
    const hlsActive = Boolean(getHlsForElement(active));
    state.shelfPreview.radioWasPlaying = Boolean(
      active && !active.paused && (active.src || hlsActive)
    );

    if (!state.shelfPreview.radioWasPlaying) {
      return;
    }

    clearStandbyPrimeTimer();
    stopAudioPulseLight();
    active.pause();

    const standby = getStandbyStreamEl();
    if (standby) {
      standby.pause();
    }

    updatePlaybackUi(false);
  }

  function resumeLocalRadioAfterShelfPreview() {
    if (!state.shelfPreview.radioWasPlaying) {
      return;
    }

    state.shelfPreview.radioWasPlaying = false;

    if (state.activeDemoStream) {
      void startDemoAudio();
      return;
    }

    void primeStreamPlayback()
      .then(() => setMessage("Radio de volta no ar."))
      .catch(() => setMessage("Previa encerrada. Clique em Play para retomar a radio."));
  }

  function stopShelfPreview(options = {}) {
    const resumeRadio = options.resumeRadio !== false;
    const audio = getShelfPreviewAudio();

    if (audio) {
      audio.pause();
      audio.removeAttribute("src");
      try {
        audio.load();
      }
      catch (_error) {
        // ignore
      }
    }

    state.shelfPreview.trackId = "";
    state.shelfPreview.title = "";
    updateShelfPreviewBar();
    syncShelfListenButtons();
    refreshLibraryTrackUi();

    if (resumeRadio) {
      resumeLocalRadioAfterShelfPreview();
    }
  }

  function buildShelfPreviewUrl(trackId) {
    return `${localApiBase()}/api/library/preview/${encodeURIComponent(trackId)}`;
  }

  function shelfPreviewStatus(message) {
    setMessage(message);
  }

  function handleShelfRequestClick(event) {
    const button = event.target.closest("[data-shelf-request]");
    if (!button) {
      return;
    }

    const inLibrary = els.libraryList && els.libraryList.contains(button);
    const inCustom = els.libraryCustomList && els.libraryCustomList.contains(button);
    if (!inLibrary && !inCustom) {
      return;
    }

    event.preventDefault();
    event.stopPropagation();

    const trackId = (button.getAttribute("data-shelf-request") || "").trim();
    if (!trackId) {
      setMessage("Faixa invalida.");
      return;
    }

    if (button.disabled) {
      setMessage(libraryRequestBlockedMessage());
      return;
    }

    void requestLibraryTrack(trackId);
  }

  async function handleShelfListenClick(event) {
    const button = event.target.closest("[data-shelf-listen]");
    if (!button || !els.libraryList || !els.libraryList.contains(button)) {
      return;
    }

    event.preventDefault();
    event.stopPropagation();

    const trackId = (button.getAttribute("data-shelf-listen") || "").trim();
    if (!trackId) {
      shelfPreviewStatus("Faixa invalida.");
      return;
    }

    if (!canUseLibraryActions()) {
      shelfPreviewStatus(
        "Ouvir precisa da API local. Suba .\\scripts\\start-local-api.ps1 e de Ctrl+F5."
      );
      return;
    }

    await probeLocalApiBase();
    if (!state.resolvedLocalApiBase) {
      shelfPreviewStatus(
        "API local offline. Rode .\\scripts\\start-local-api.ps1 (porta 8765) e recarregue com Ctrl+F5."
      );
      return;
    }

    const audio = getShelfPreviewAudio();
    if (!audio) {
      shelfPreviewStatus("Player de previa indisponivel. Recarregue a pagina (Ctrl+F5).");
      return;
    }

    const track = findLibraryTrackById(trackId);
    const title = track?.title || button.getAttribute("data-shelf-title") || "Faixa";

    if (state.shelfPreview.trackId === trackId && isShelfPreviewPlaying()) {
      stopShelfPreview({ resumeRadio: true });
      shelfPreviewStatus("Previa parada.");
      return;
    }

    state.shelfPreview.trackId = trackId;
    state.shelfPreview.title = title;
    button.classList.add("is-loading");
    updateShelfPreviewBar();
    syncShelfListenButtons();
    shelfPreviewStatus(`Carregando previa de ${title} — so neste navegador, nao vai pro ar.`);

    pauseLocalRadioForShelfPreview();
    syncShelfPreviewVolume();

    const url = buildShelfPreviewUrl(trackId);
    audio.pause();
    audio.removeAttribute("crossorigin");
    audio.src = url;
    audio.load();

    const finishLoading = () => {
      button.classList.remove("is-loading");
      syncShelfListenButtons();
    };

    const onStarted = () => {
      finishLoading();
      shelfPreviewStatus(`Ouvindo ${title} — previa local (so voce). Parar encerra.`);
    };

    const onFailed = (error) => {
      finishLoading();
      stopShelfPreview({ resumeRadio: true });
      const hint = window.location.protocol === "file:"
        ? " Abra por http://127.0.0.1 (nao file://)."
        : " Confira se a API responde em /api/library/preview/...";
      shelfPreviewStatus(`Previa falhou: ${formatMediaPlaybackError(error)}.${hint}`);
    };

    let playbackStarted = false;
    const playWhenReady = () => {
      if (playbackStarted) {
        return;
      }
      playbackStarted = true;

      const promise = audio.play();
      if (!promise) {
        onStarted();
        return;
      }
      promise.then(onStarted).catch(onFailed);
    };

    audio.addEventListener("canplay", playWhenReady, { once: true });
    audio.addEventListener("error", () => onFailed(audio.error || new Error("erro de midia")), { once: true });

    if (audio.readyState >= HTMLMediaElement.HAVE_FUTURE_DATA) {
      playWhenReady();
    }
  }

  function initShelfPreview() {
    const audio = getShelfPreviewAudio();
    if (!audio) {
      return;
    }

    if (!audio.dataset.shelfBound) {
      audio.dataset.shelfBound = "1";
      audio.addEventListener("ended", () => {
        stopShelfPreview({ resumeRadio: true });
        shelfPreviewStatus("Previa terminou.");
      });
      audio.addEventListener("playing", () => {
        updateShelfPreviewBar();
        syncShelfListenButtons();
      });
      audio.addEventListener("pause", syncShelfListenButtons);
    }

    if (!document.documentElement.dataset.shelfListenBound) {
      document.documentElement.dataset.shelfListenBound = "1";
      document.addEventListener("click", handleShelfListenClick, true);
      document.addEventListener("click", handleShelfRequestClick, true);
    }

    if (els.shelfPreviewStop && !els.shelfPreviewStop.dataset.shelfBound) {
      els.shelfPreviewStop.dataset.shelfBound = "1";
      els.shelfPreviewStop.addEventListener("click", () => {
        stopShelfPreview({ resumeRadio: true });
        shelfPreviewStatus("Previa parada.");
      });
    }
  }

  async function requestLibraryTrack(trackId) {
    const resolvedId = resolveLibraryPreviewId(trackId);
    if (!resolvedId) {
      return;
    }

    if (!canUseLibraryActions()) {
      setMessage("Preview e pedido na radio exigem a API local. Rode .\\scripts\\start-local-api.ps1 e recarregue a pagina.");
      return;
    }

    await requestLibraryTrackWithVote(resolvedId);
  }

  async function requestPrimaryCustomPlaylistTrack() {
    if (!state.customPlaylist.length) {
      setMessage("Minha playlist esta vazia. Marque faixas com + Lista na estante.");
      return;
    }

    const primary = state.customPlaylist[0];
    await requestLibraryTrack(primary.id);
  }

  function bindLibraryEvents() {
    if (!els.libraryList) {
      return;
    }

    [
      els.librarySearchInput,
      els.libraryArtistFilter,
      els.libraryAlbumFilter
    ].forEach((element) => {
      if (!element) {
        return;
      }

      element.addEventListener("input", scheduleLibraryReload);
      element.addEventListener("change", scheduleLibraryReload);
    });

    els.libraryList.addEventListener("click", (event) => {
      handleLibraryTrackClick(event, { allowCustomToggle: true });
    });

    if (els.libraryCustomList) {
      els.libraryCustomList.addEventListener("click", (event) => {
        handleLibraryTrackClick(event);
      });
    }

    if (els.libraryRequestButton) {
      els.libraryRequestButton.addEventListener("click", () => {
        void requestPrimaryCustomPlaylistTrack();
      });
    }

    if (els.libraryExportButton) {
      els.libraryExportButton.addEventListener("click", exportCustomPlaylist);
    }

    if (els.libraryClearCustomButton) {
      els.libraryClearCustomButton.addEventListener("click", () => {
        void beginClearCustomPlaylistVote();
      });
    }

    initShelfPreview();
  }

  function bindStreamPlaybackEvents(element) {
    if (!element) {
      return;
    }

    element.addEventListener("playing", () => {
      if (element !== getActiveStreamEl() || state.streamMonitor.swapping) {
        return;
      }

      resetStreamMonitor();
      updatePlaybackUi(true);
      setMessage("Tocando ao vivo.");
      scheduleNowPlayingPoll();
      scheduleStreamLoudnessCalibration();
    });

    element.addEventListener("pause", () => {
      if (element !== getActiveStreamEl() || state.streamMonitor.swapping) {
        return;
      }

      if (!getActiveStreamEl().paused) {
        return;
      }

      resetStreamMonitor();
      updatePlaybackUi(false);
      setMessage("Audio pausado.");
      scheduleNowPlayingPoll();
    });

    element.addEventListener("error", () => {
      if (element !== getActiveStreamEl()) {
        return;
      }

      updatePlaybackUi(false);
      setMessage("Erro ao tocar o stream. Confira a URL da estacao.");
    });
  }

  function bindEvents() {
    els.playButton.addEventListener("click", togglePlayback);
    els.spotifyImportForm.addEventListener("submit", importSpotifyPlaylist);
    els.volumeSlider.addEventListener("input", updateVolume);
    els.muteButton.addEventListener("click", () => {
      const active = getActiveStreamEl();
      active.muted = !active.muted;
      const backup = getStandbyStreamEl();
      if (backup) {
        backup.muted = active.muted;
      }
      updateVolume();
    });

    bindStreamPlaybackEvents(els.audio);
    bindStreamPlaybackEvents(els.audioBackup);

    if (els.skipTrackButton) {
      els.skipTrackButton.addEventListener("click", () => {
        beginVoteFlow("skip_track", {
          title: els.trackTitle?.textContent || "Faixa atual",
          artist: els.trackArtist?.textContent || "Artista"
        });
      });
    }

    if (els.voteChoiceYes) {
      els.voteChoiceYes.addEventListener("click", () => castAudienceVote("yes"));
    }
    if (els.voteChoiceNo) {
      els.voteChoiceNo.addEventListener("click", () => castAudienceVote("no"));
    }
    if (els.voteDirectYes) {
      els.voteDirectYes.addEventListener("click", () => executeDirectVote("yes"));
    }
    if (els.voteDirectNo) {
      els.voteDirectNo.addEventListener("click", () => executeDirectVote("no"));
    }
    if (els.voteDirectCancel) {
      els.voteDirectCancel.addEventListener("click", hideVoteDirectModal);
    }

    if (els.narratorPickerButton) {
      els.narratorPickerButton.addEventListener("click", showNarratorPickerModal);
    }
    if (els.narratorPickMiku) {
      els.narratorPickMiku.addEventListener("click", () => chooseNarrator("miku"));
    }
    if (els.narratorPickHoshino) {
      els.narratorPickHoshino.addEventListener("click", () => chooseNarrator("hoshino"));
    }
    if (els.narratorPreviewMiku) {
      els.narratorPreviewMiku.addEventListener("click", (event) => {
        event.stopPropagation();
        void previewNarratorVoice("miku");
      });
    }
    if (els.narratorPreviewHoshino) {
      els.narratorPreviewHoshino.addEventListener("click", (event) => {
        event.stopPropagation();
        void previewNarratorVoice("hoshino");
      });
    }
    if (els.narratorPickerClose) {
      els.narratorPickerClose.addEventListener("click", hideNarratorPickerModal);
    }
    if (els.narratorPickerModal) {
      els.narratorPickerModal.querySelector(".vote-modal__backdrop")
        ?.addEventListener("click", hideNarratorPickerModal);
    }
  }

  function init() {
    if (maybeRedirectHttpToHttpsForMicrophone()) {
      return;
    }

    state.vote.actionCooldownSec = Math.max(Number(config.voteActionCooldownSec || 45), 0);
    els.stationTitle.textContent = config.stationDisplayName;
    if (window.location.protocol === "file:" && els.spotifyImportStatus) {
      els.spotifyImportStatus.textContent = (
        "Abra o player por HTTP (ex.: http://127.0.0.1:5500/frontend/index.html). " +
        "Arquivo local (file://) bloqueia import Spotify e API."
      );
    }
    els.panelLink.href = config.azuracastPanelUrl || config.azuracastBaseUrl;
    els.appShell.classList.add("is-paused");
    if (els.audio) {
      els.audio.preload = "auto";
    }
    if (els.audioBackup) {
      els.audioBackup.preload = "auto";
    }
    updateVolume();
    startAsciiBackdrop();
    bindEvents();
    bindStreamStability();
    bindLibraryEvents();
    bindVoiceDropEvents();
    bindCoverImageFallback();
    updateNarratorPickerUi();
    getListenerId();
    void (async () => {
      await probeLocalApiBase();
      checkVoiceDropApi();
      window.setInterval(() => checkVoiceDropApi(), 20000);
      loadLibraryCatalog();
    })();
    loadCustomPlaylist();
    resumePlaybackIfNeeded();
    if (sessionStorage.getItem(RESUME_PLAYBACK_KEY) !== "1") {
      refreshNowPlaying();
    }
    startLibraryCatalogWatcher();
    loadSpotifyManifest();
    void loadNarratorPreviewSamples();
    scheduleNowPlayingPoll();
    startStreamBufferWatch();
    scheduleAudienceHeartbeat();
    startVoteActionCooldownTicker();
    startVoteRealtime();
    window.setInterval(renderProgress, 500);
    registerServiceWorker();
  }

  init();
})();


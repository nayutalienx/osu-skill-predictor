const state = {
  settingsVisible: false,
  refreshInFlight: false,
  intervalId: null,
};

const els = {
  refreshButton: document.getElementById("refresh-button"),
  toggleSetupButton: document.getElementById("toggle-setup-button"),
  quitButton: document.getElementById("quit-button"),
  saveSettingsButton: document.getElementById("save-settings-button"),
  startTosuButton: document.getElementById("start-tosu-button"),
  oauthLink: document.getElementById("oauth-link"),
  setupPanel: document.getElementById("setup-panel"),
  setupHint: document.getElementById("setup-hint"),
  setupFeedback: document.getElementById("setup-feedback"),
  statusMessage: document.getElementById("status-message"),
  statusSources: document.getElementById("status-sources"),
  statusTimestamp: document.getElementById("status-timestamp"),
  progressBar: document.getElementById("progress-bar"),
  playerGrid: document.getElementById("player-grid"),
  beatmapGrid: document.getElementById("beatmap-grid"),
  predictionGrid: document.getElementById("prediction-grid"),
  tosuBaseUrl: document.getElementById("tosu-base-url"),
  tosuExecutablePath: document.getElementById("tosu-executable-path"),
  osuClientId: document.getElementById("osu-client-id"),
  osuClientSecret: document.getElementById("osu-client-secret"),
  playerSource: document.getElementById("player-source"),
  manualUsername: document.getElementById("manual-username"),
  offlineMode: document.getElementById("offline-mode"),
  offlinePp: document.getElementById("offline-pp"),
  offlineAccuracy: document.getElementById("offline-accuracy"),
  offlinePlayCount: document.getElementById("offline-play-count"),
  offlineGlobalRank: document.getElementById("offline-global-rank"),
  offlineCountry: document.getElementById("offline-country"),
  overlayEnabled: document.getElementById("overlay-enabled"),
  overlayPosition: document.getElementById("overlay-position"),
  overlayX: document.getElementById("overlay-x"),
  overlayY: document.getElementById("overlay-y"),
  overlayDisplay: document.getElementById("overlay-display"),
  refreshUserButton: document.getElementById("refresh-user-button"),
};

function fmtNumber(value, digits = 2, suffix = "") {
  if (value === null || value === undefined || value === "") {
    return "n/a";
  }
  if (typeof value === "number") {
    return `${value.toFixed(digits)}${suffix}`;
  }
  return `${value}${suffix}`;
}

function fmtInt(value) {
  if (value === null || value === undefined || value === "") {
    return "n/a";
  }
  return Number(value).toLocaleString();
}

function metricRow(label, value) {
  const row = document.createElement("div");
  row.className = "metric-row";
  const left = document.createElement("div");
  left.className = "metric-label";
  left.textContent = label;
  const right = document.createElement("div");
  right.className = "metric-value";
  right.textContent = value;
  row.append(left, right);
  return row;
}

function setSetupVisible(visible) {
  state.settingsVisible = visible;
  els.setupPanel.classList.toggle("hidden", !visible);
  els.toggleSetupButton.textContent = visible ? "Hide setup" : "Open setup";
}

function renderSettings(settings) {
  els.tosuBaseUrl.value = settings.tosu_base_url || "";
  els.tosuExecutablePath.value = settings.tosu_executable_path || "";
  els.osuClientId.value = settings.osu_client_id || "";
  els.osuClientSecret.value = settings.osu_client_secret || "";
  els.playerSource.value = settings.player_source || "tosu";
  els.manualUsername.value = settings.manual_username || "";
  els.offlineMode.checked = settings.offline_mode || false;
  els.offlinePp.value = settings.offline_pp || 0;
  els.offlineAccuracy.value = settings.offline_accuracy || 0;
  els.offlinePlayCount.value = settings.offline_play_count || 0;
  els.offlineGlobalRank.value = settings.offline_global_rank || 0;
  els.offlineCountry.value = settings.offline_country || "";
  els.overlayEnabled.checked = settings.overlay_enabled || false;
  els.overlayPosition.value = settings.overlay_position || "top-right";
  els.overlayX.value = settings.overlay_x || 0;
  els.overlayY.value = settings.overlay_y || 0;
  els.overlayDisplay.value = settings.overlay_display || 0;
  els.oauthLink.href = settings.oauth_settings_url;
  if (settings.setup_required) {
    setSetupVisible(true);
  }
}

function renderStatus(snapshot) {
  document.body.classList.remove("status-ok", "status-waiting", "status-error", "status-unsupported");
  document.body.classList.add(`status-${snapshot.status}`);
  els.statusMessage.textContent = snapshot.message;
  els.statusSources.textContent = `Sources: ${Object.entries(snapshot.sources || {}).map(([k, v]) => `${k}=${v}`).join(", ") || "n/a"}`;
  els.statusTimestamp.textContent = `Last refresh: ${snapshot.refreshed_at || "n/a"}`;
  els.progressBar.style.width = snapshot.status === "ok" ? "100%" : snapshot.status === "waiting" ? "42%" : "18%";
  if (snapshot.setup_required) {
    setSetupVisible(true);
  }
}

function renderPlayer(player) {
  els.playerGrid.replaceChildren(
    metricRow("Username", player?.username || "n/a"),
    metricRow("User ID", fmtInt(player?.user_id)),
    metricRow("PP", fmtNumber(player?.pp)),
    metricRow("Accuracy", fmtNumber(player?.accuracy, 2, "%")),
    metricRow("Play count", fmtInt(player?.play_count)),
    metricRow("Global rank", fmtInt(player?.global_rank)),
    metricRow("Country", player?.country_code || "n/a"),
    metricRow("Mode", player?.mode || "n/a"),
  );
}

function renderBeatmap(beatmap) {
  els.beatmapGrid.replaceChildren(
    metricRow("Title", beatmap?.title || "n/a"),
    metricRow("Artist", beatmap?.artist || "n/a"),
    metricRow("Difficulty", beatmap?.version || "n/a"),
    metricRow("Mapper", beatmap?.mapper || "n/a"),
    metricRow("Beatmap ID", fmtInt(beatmap?.beatmap_id)),
    metricRow("Beatmapset ID", fmtInt(beatmap?.beatmapset_id)),
    metricRow("Client", beatmap?.client_name || "n/a"),
    metricRow("Mods", beatmap?.mods_raw || "(NM)"),
    metricRow("Stars", fmtNumber(beatmap?.star_rating)),
    metricRow("BPM", fmtNumber(beatmap?.bpm, 1)),
    metricRow("AR / OD / CS", `${fmtNumber(beatmap?.ar, 1)} / ${fmtNumber(beatmap?.od, 1)} / ${fmtNumber(beatmap?.cs, 1)}`),
    metricRow(
      "Lengths",
      `${fmtInt(beatmap?.hit_length_sec)}s hit / ${fmtInt(beatmap?.total_length_sec)}s total`,
    ),
    metricRow("Pass / Play", `${fmtInt(beatmap?.passcount)} / ${fmtInt(beatmap?.playcount)}`),
  );
}

function renderPrediction(prediction) {
  els.predictionGrid.replaceChildren(
    metricRow("Pass probability", prediction ? fmtNumber(prediction.pass_probability * 100, 2, "%") : "n/a"),
    metricRow("Predicted accuracy", prediction ? fmtNumber(prediction.predicted_accuracy, 2, "%") : "n/a"),
    metricRow("Difficulty gap", prediction ? fmtNumber(prediction.difficulty_gap, 2) : "n/a"),
    metricRow("Recommendation", prediction?.recommendation || "Prediction unavailable"),
    metricRow("Classifier", prediction?.classifier_model || "n/a"),
    metricRow("Regressor", prediction?.regressor_model || "n/a"),
    metricRow("Artifact version", prediction?.artifact_version || "n/a"),
  );
}

function renderOverlay(snapshot) {
  if (!snapshot) return;
  const enabled = state.overlayEnabled && snapshot.status === "ok" && snapshot.prediction;
  const playing = snapshot.is_playing;
  const show = enabled && !playing;
  els.overlay.classList.toggle("hidden", !show);
  if (show) {
    const map = snapshot.beatmap;
    const mapName = map ? [map.artist, map.title].filter(Boolean).join(" - ") || map.version || "" : "";
    els.overlayMap.textContent = mapName || "n/a";
    els.overlayPass.textContent = `Pass: ${fmtNumber(snapshot.prediction.pass_probability * 100, 1, "%")}`;
    els.overlayAcc.textContent = `Acc: ${fmtNumber(snapshot.prediction.predicted_accuracy, 1, "%")}`;
  }
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    ...options,
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

async function loadSettings() {
  const settings = await fetchJson("/api/live/settings");
  renderSettings(settings);
}

async function refreshSnapshot() {
  if (state.refreshInFlight) return;
  state.refreshInFlight = true;
  els.progressBar.style.width = "50%";
  els.progressBar.classList.add("updating");
  try {
    const snapshot = await fetchJson("/api/live/snapshot");
    renderStatus(snapshot);
    renderPlayer(snapshot.player);
    renderBeatmap(snapshot.beatmap);
    renderPrediction(snapshot.prediction);
  } catch (error) {
    renderStatus({
      status: "error",
      message: "Could not reach the local web service.",
      refreshed_at: new Date().toISOString(),
      setup_required: false,
      sources: { web: "error" },
    });
  } finally {
    els.progressBar.classList.remove("updating");
    state.refreshInFlight = false;
  }
}

async function saveSettings() {
  els.setupFeedback.textContent = "Saving settings...";
  try {
    const payload = {
      tosu_base_url: els.tosuBaseUrl.value.trim(),
      tosu_executable_path: els.tosuExecutablePath.value.trim(),
      osu_client_id: els.osuClientId.value.trim(),
      osu_client_secret: els.osuClientSecret.value.trim(),
      player_source: els.playerSource.value,
      manual_username: els.manualUsername.value.trim(),
      offline_mode: els.offlineMode.checked,
      offline_pp: parseFloat(els.offlinePp.value) || 0,
      offline_accuracy: parseFloat(els.offlineAccuracy.value) || 0,
      offline_play_count: parseInt(els.offlinePlayCount.value) || 0,
      offline_global_rank: parseInt(els.offlineGlobalRank.value) || 0,
      offline_country: els.offlineCountry.value.trim(),
      overlay_enabled: els.overlayEnabled.checked,
      overlay_position: els.overlayPosition.value,
      overlay_x: parseInt(els.overlayX.value) || 0,
      overlay_y: parseInt(els.overlayY.value) || 0,
      overlay_display: parseInt(els.overlayDisplay.value) || 0,
    };
    const settings = await fetchJson("/api/live/settings", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    renderSettings(settings);
    els.setupFeedback.textContent = "Settings applied.";
    await refreshSnapshot();
  } catch (error) {
    els.setupFeedback.textContent = "Could not save settings. Check all fields and try again.";
  }
}

async function startTosu() {
  els.setupFeedback.textContent = "Starting bundled tosu...";
  try {
    const result = await fetchJson("/api/live/tosu/start", { method: "POST" });
    els.setupFeedback.textContent = `tosu status: ${result.status}`;
    await refreshSnapshot();
  } catch (error) {
    els.setupFeedback.textContent = "Could not start tosu.";
  }
}

function renderOverlay(snapshot) {
  if (!snapshot) return;
  const enabled = state.overlayEnabled && snapshot.status === "ok" && snapshot.prediction;
  const playing = snapshot.is_playing;
  const show = enabled && !playing;
  els.overlay.classList.toggle("hidden", !show);
  if (show) {
    const map = snapshot.beatmap;
    const mapName = map ? [map.artist, map.title].filter(Boolean).join(" - ") || map.version || "" : "";
    els.overlayMap.textContent = mapName || "n/a";
    els.overlayPass.textContent = `Pass: ${fmtNumber(snapshot.prediction.pass_probability * 100, 1, "%")}`;
    els.overlayAcc.textContent = `Acc: ${fmtNumber(snapshot.prediction.predicted_accuracy, 1, "%")}`;
  }
}

async function quitApp() {
  if (!confirm("Quit the application?")) return;
  try {
    await fetchJson("/api/live/shutdown", { method: "POST" });
  } catch (_) {
    // server may already be gone
  }
  window.close();
}

function startPolling() {
  if (state.intervalId !== null) {
    clearInterval(state.intervalId);
  }
  state.intervalId = window.setInterval(refreshSnapshot, 3500);
}

async function refreshUser() {
  try {
    await fetchJson("/api/live/user/refresh", { method: "POST" });
  } catch (_) {}
  await refreshSnapshot();
}

els.refreshButton.addEventListener("click", refreshSnapshot);
els.toggleSetupButton.addEventListener("click", () => setSetupVisible(!state.settingsVisible));
els.quitButton.addEventListener("click", quitApp);
els.saveSettingsButton.addEventListener("click", saveSettings);
els.startTosuButton.addEventListener("click", startTosu);
els.refreshUserButton.addEventListener("click", refreshUser);

loadSettings().then(refreshSnapshot).then(startPolling);

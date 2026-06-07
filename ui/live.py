from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from typing import Any
from urllib.parse import unquote

import requests

from app.predict import PredictionService
from app.schemas import PredictionRequest

OSU_OAUTH_SETTINGS_URL = "https://osu.ppy.sh/home/account/edit"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_local_env() -> None:
    for env_path in (repo_root() / ".env.local", repo_root() / ".env"):
        if not env_path.exists():
            continue
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("'").strip('"'))


def app_settings_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "osu-skill-predictor"
    return Path.home() / ".osu-skill-predictor"


def web_settings_path() -> Path:
    return app_settings_dir() / "web_settings.json"


def load_web_settings() -> dict[str, Any]:
    path = web_settings_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_web_settings(payload: dict[str, Any]) -> Path:
    path = web_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


@dataclass(frozen=True)
class LiveConfig:
    tosu_base_url: str = "http://127.0.0.1:24050"
    tosu_executable_path: str = ""
    osu_api_base_url: str = "https://osu.ppy.sh/api/v2"
    osu_token_url: str = "https://osu.ppy.sh/oauth/token"
    ruleset: str = "osu"
    request_timeout_seconds: float = 12.0
    beatmap_cache_ttl_seconds: int = 900
    user_cache_ttl_seconds: int = 86400
    osu_client_id: str = ""
    osu_client_secret: str = ""
    web_port: int = 8765
    player_source: str = "tosu"
    manual_username: str = ""
    offline_mode: bool = False
    offline_pp: float = 0.0
    offline_accuracy: float = 0.0
    offline_play_count: int = 0
    offline_global_rank: int = 0
    offline_country: str = ""
    overlay_enabled: bool = False
    overlay_position: str = "top-right"
    overlay_x: int = 0
    overlay_y: int = 0
    overlay_display: int = 0

    @classmethod
    def from_env(cls) -> "LiveConfig":
        load_local_env()
        settings = load_web_settings()
        return cls(
            tosu_base_url=str(settings.get("tosu_base_url") or os.environ.get("OSU_WEB_TOSU_BASE_URL", cls.tosu_base_url)).rstrip("/"),
            tosu_executable_path=str(
                settings.get("tosu_executable_path") or os.environ.get("OSU_WEB_TOSU_EXECUTABLE_PATH", cls.tosu_executable_path)
            ),
            osu_api_base_url=str(
                settings.get("osu_api_base_url") or os.environ.get("OSU_WEB_OSU_API_BASE_URL", cls.osu_api_base_url)
            ).rstrip("/"),
            osu_token_url=str(
                settings.get("osu_token_url") or os.environ.get("OSU_WEB_OSU_TOKEN_URL", cls.osu_token_url)
            ).rstrip("/"),
            ruleset=str(settings.get("ruleset") or os.environ.get("OSU_WEB_RULESET", cls.ruleset)),
            request_timeout_seconds=float(
                settings.get("request_timeout_seconds")
                or os.environ.get("OSU_WEB_REQUEST_TIMEOUT_SECONDS", cls.request_timeout_seconds)
            ),
            beatmap_cache_ttl_seconds=int(
                settings.get("beatmap_cache_ttl_seconds")
                or os.environ.get("OSU_WEB_BEATMAP_CACHE_TTL_SECONDS", cls.beatmap_cache_ttl_seconds)
            ),
            user_cache_ttl_seconds=int(
                settings.get("user_cache_ttl_seconds")
                or os.environ.get("OSU_WEB_USER_CACHE_TTL_SECONDS", cls.user_cache_ttl_seconds)
            ),
            osu_client_id=str(settings.get("osu_client_id") or os.environ.get("OSU_CLIENT_ID", "")),
            osu_client_secret=str(settings.get("osu_client_secret") or os.environ.get("OSU_CLIENT_SECRET", "")),
            web_port=int(settings.get("web_port") or os.environ.get("OSU_WEB_PORT", cls.web_port)),
            player_source=str(settings.get("player_source") or cls.player_source),
            manual_username=str(settings.get("manual_username") or ""),
            offline_mode=bool(settings.get("offline_mode", cls.offline_mode)),
            offline_pp=float(settings.get("offline_pp", cls.offline_pp)),
            offline_accuracy=float(settings.get("offline_accuracy", cls.offline_accuracy)),
            offline_play_count=int(settings.get("offline_play_count", cls.offline_play_count)),
            offline_global_rank=int(settings.get("offline_global_rank", cls.offline_global_rank)),
            offline_country=str(settings.get("offline_country", "")),
            overlay_enabled=bool(settings.get("overlay_enabled", cls.overlay_enabled)),
            overlay_position=str(settings.get("overlay_position", cls.overlay_position)),
            overlay_x=int(settings.get("overlay_x", cls.overlay_x)),
            overlay_y=int(settings.get("overlay_y", cls.overlay_y)),
            overlay_display=int(settings.get("overlay_display", cls.overlay_display)),
        )


def _nested(payload: dict[str, Any], *path: str) -> Any:
    value: Any = payload
    for segment in path:
        if not isinstance(value, dict):
            return None
        value = value.get(segment)
    return value


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_country(profile: dict[str, Any]) -> str | None:
    raw = profile.get("countryCode")
    if raw is None:
        return None
    if isinstance(raw, dict):
        name = str(raw.get("name", "")).strip()
        return name or None
    return str(raw).strip() or None


def _is_playing(payload: dict[str, Any]) -> bool:
    menu = payload.get("menu") or {}
    if _as_int(menu.get("state")) == 2:
        return True
    play = payload.get("play") or {}
    if _as_int(play.get("score")) and _as_int(play.get("score")) > 0:
        return True
    return False


def normalize_mods(mods: Any) -> str:
    if mods is None:
        return ""
    if isinstance(mods, str):
        return mods.strip().upper().replace(" ", "")
    if isinstance(mods, list):
        items: list[str] = []
        for mod in mods:
            if isinstance(mod, str):
                items.append(mod.strip().upper())
            elif isinstance(mod, dict):
                acronym = mod.get("acronym")
                if acronym:
                    items.append(str(acronym).strip().upper())
        return "".join(items)
    if isinstance(mods, dict):
        acronym = mods.get("acronym")
        return str(acronym).strip().upper() if acronym else ""
    return str(mods).strip().upper().replace(" ", "")


@dataclass(frozen=True)
class TosuLiveState:
    raw_payload: dict[str, Any]
    client_name: str
    ruleset: str
    user_id: int | None
    username: str
    user_pp: float | None
    user_accuracy: float | None
    user_play_count: int | None
    user_global_rank: int | None
    country_code: str | None
    beatmap_id: int | None
    beatmapset_id: int | None
    artist: str
    title: str
    version: str
    mapper: str
    mods_raw: str
    beatmap_star_rating: float | None
    beatmap_bpm: float | None
    beatmap_ar: float | None
    beatmap_od: float | None
    beatmap_cs: float | None
    beatmap_hit_length_sec: int | None
    beatmap_total_length_sec: int | None
    passcount: int | None
    playcount: int | None
    refreshed_at: str
    is_playing: bool = False


def parse_tosu_v2_state(payload: dict[str, Any]) -> TosuLiveState:
    if payload.get("error"):
        raise RuntimeError(f"tosu returned error: {payload.get('error')}")

    profile = payload.get("profile") or {}
    beatmap = payload.get("beatmap") or {}
    play = payload.get("play") or {}
    stats = beatmap.get("stats") or {}
    beatmap_time = beatmap.get("time") or {}
    bpm = stats.get("bpm") or {}

    first_object_ms = _as_int(beatmap_time.get("firstObject"))
    last_object_ms = _as_int(beatmap_time.get("lastObject"))
    mp3_length_ms = _as_int(beatmap_time.get("mp3Length"))

    hit_length_sec = None
    if first_object_ms is not None and last_object_ms is not None and last_object_ms >= first_object_ms:
        hit_length_sec = int(round((last_object_ms - first_object_ms) / 1000.0))

    total_length_sec = None
    if mp3_length_ms is not None and mp3_length_ms >= 0:
        total_length_sec = int(round(mp3_length_ms / 1000.0))

    ruleset = str(_nested(profile, "mode", "name") or _nested(beatmap, "mode", "name") or "").lower()
    if not ruleset:
        ruleset = "unknown"

    return TosuLiveState(
        raw_payload=payload,
        client_name=str(payload.get("client") or "unknown"),
        ruleset=ruleset,
        user_id=_as_int(profile.get("id")),
        username=str(profile.get("name") or play.get("playerName") or ""),
        user_pp=_as_float(profile.get("pp")),
        user_accuracy=_as_float(profile.get("accuracy")),
        user_play_count=_as_int(profile.get("playCount")),
        user_global_rank=_as_int(profile.get("globalRank")),
        country_code=_parse_country(profile),
        beatmap_id=_as_int(beatmap.get("id")),
        beatmapset_id=_as_int(beatmap.get("set")),
        artist=str(beatmap.get("artist") or beatmap.get("artistUnicode") or ""),
        title=str(beatmap.get("title") or beatmap.get("titleUnicode") or ""),
        version=str(beatmap.get("version") or ""),
        mapper=str(beatmap.get("mapper") or ""),
        mods_raw=normalize_mods(play.get("mods")),
        beatmap_star_rating=_as_float(_nested(stats, "stars", "total")),
        beatmap_bpm=_as_float(bpm.get("common") or bpm.get("realtime") or bpm.get("max") or bpm.get("min")),
        beatmap_ar=_as_float(_nested(stats, "ar", "converted")),
        beatmap_od=_as_float(_nested(stats, "od", "converted")),
        beatmap_cs=_as_float(_nested(stats, "cs", "converted")),
        beatmap_hit_length_sec=hit_length_sec,
        beatmap_total_length_sec=total_length_sec,
        passcount=None,
        playcount=None,
        refreshed_at=utc_now_iso(),
        is_playing=_is_playing(payload),
    )


class TosuClient:
    def __init__(self, *, base_url: str, timeout_seconds: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._session = requests.Session()

    def endpoint_reachable(self) -> bool:
        try:
            response = self._session.get(f"{self._base_url}/json/v2", timeout=1.5, headers={"Accept": "application/json"})
            return 200 <= response.status_code < 500
        except requests.RequestException:
            return False

    def fetch_live_state(self) -> TosuLiveState:
        response = self._session.get(
            f"{self._base_url}/json/v2",
            timeout=self._timeout_seconds,
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        return parse_tosu_v2_state(response.json())


@dataclass(frozen=True)
class OsuBeatmapApiSnapshot:
    beatmap_id: int
    beatmapset_id: int | None
    passcount: int | None
    playcount: int | None
    artist: str | None
    title: str | None
    version: str | None
    mapper: str | None


@dataclass(frozen=True)
class OsuUserApiSnapshot:
    user_id: int
    username: str
    pp: float | None
    accuracy: float | None
    play_count: int | None
    global_rank: int | None
    country_code: str | None


class OsuApiClient:
    def __init__(
        self,
        *,
        api_base_url: str,
        token_url: str,
        timeout_seconds: float,
        ruleset: str,
        client_id: str,
        client_secret: str,
    ) -> None:
        self._api_base_url = api_base_url.rstrip("/")
        self._token_url = token_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._ruleset = ruleset
        self._client_id = client_id
        self._client_secret = client_secret
        self._session = requests.Session()
        self._access_token: str | None = None
        self._access_token_expires_at: datetime | None = None

    @property
    def configured(self) -> bool:
        return bool(self._client_id and self._client_secret)

    def _ensure_access_token(self) -> str:
        if not self.configured:
            raise RuntimeError("Missing osu! OAuth client credentials")
        if self._access_token and self._access_token_expires_at and datetime.now(timezone.utc) < self._access_token_expires_at:
            return self._access_token

        response = self._session.post(
            self._token_url,
            timeout=self._timeout_seconds,
            json={
                "client_id": int(self._client_id),
                "client_secret": self._client_secret,
                "grant_type": "client_credentials",
                "scope": "public",
            },
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        payload = response.json()
        self._access_token = str(payload["access_token"])
        expires_in = int(payload.get("expires_in", 3600))
        self._access_token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=max(60, expires_in - 60))
        return self._access_token

    def _authorized_get(self, path: str) -> dict[str, Any]:
        token = self._ensure_access_token()
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                response = self._session.get(
                    f"{self._api_base_url}{path}",
                    timeout=self._timeout_seconds,
                    headers={"Accept": "application/json", "Authorization": f"Bearer {token}"},
                )
                if response.status_code == 503:
                    if attempt < 2:
                        time.sleep(1.0 * (attempt + 1))
                        continue
                response.raise_for_status()
                return response.json()
            except requests.exceptions.ReadTimeout as exc:
                last_exc = exc
                if attempt < 2:
                    time.sleep(1.0 * (attempt + 1))
                    continue
                raise
            except requests.exceptions.HTTPError as exc:
                last_exc = exc
                if attempt < 2 and hasattr(exc, "response") and getattr(exc.response, "status_code", 0) == 503:
                    time.sleep(1.0 * (attempt + 1))
                    continue
                raise
            except requests.RequestException as exc:
                last_exc = exc
                if attempt < 2:
                    time.sleep(1.0 * (attempt + 1))
                    continue
                raise
        assert last_exc is not None
        raise last_exc

    def get_beatmap(self, beatmap_id: int) -> OsuBeatmapApiSnapshot:
        payload = self._authorized_get(f"/beatmaps/{beatmap_id}")
        return OsuBeatmapApiSnapshot(
            beatmap_id=int(payload["id"]),
            beatmapset_id=_as_int(payload.get("beatmapset_id")),
            passcount=_as_int(payload.get("passcount")),
            playcount=_as_int(payload.get("playcount")),
            artist=str(payload.get("beatmapset", {}).get("artist") or payload.get("artist") or "") or None,
            title=str(payload.get("beatmapset", {}).get("title") or payload.get("title") or "") or None,
            version=str(payload.get("version") or "") or None,
            mapper=str(payload.get("beatmapset", {}).get("creator") or payload.get("mapper") or "") or None,
        )

    def get_user(self, *, user_id: int | None, username: str | None) -> OsuUserApiSnapshot:
        locator = str(user_id) if user_id is not None else str(username or "")
        payload = self._authorized_get(f"/users/{locator}/{self._ruleset}")
        stats = payload.get("statistics") or {}
        return OsuUserApiSnapshot(
            user_id=int(payload["id"]),
            username=str(payload.get("username") or ""),
            pp=_as_float(stats.get("pp")),
            accuracy=_as_float(stats.get("hit_accuracy")),
            play_count=_as_int(stats.get("play_count")),
            global_rank=_as_int(stats.get("global_rank")),
            country_code=str(payload.get("country_code") or "") or None,
        )


class TosuManager:
    def __init__(self, config: LiveConfig) -> None:
        self._config = config
        self._process: subprocess.Popen[str] | None = None
        self._last_launch_monotonic = 0.0
        self._pid_path = app_settings_dir() / "tosu-web.pid"

    def _bundled_tosu_source_dir(self) -> Path | None:
        bundle_dir = repo_root() / "tosu"
        if (bundle_dir / "tosu.exe").exists():
            return bundle_dir
        return None

    def _runtime_tosu_dir(self) -> Path:
        return app_settings_dir() / "tosu-runtime-web"

    def _patch_tosu_env(self, tosu_dir: Path) -> None:
        env_path = tosu_dir / "tosu.env"
        if not env_path.exists():
            return
        lines = env_path.read_text(encoding="utf-8").splitlines()
        wanted = {
            "OPEN_DASHBOARD_ON_STARTUP": "false",
            "ENABLE_AUTOUPDATE": "false",
        }
        updated: list[str] = []
        seen: set[str] = set()
        for line in lines:
            if "=" not in line:
                updated.append(line)
                continue
            key, _, _value = line.partition("=")
            normalized_key = key.strip()
            if normalized_key in wanted:
                updated.append(f"{normalized_key}={wanted[normalized_key]}")
                seen.add(normalized_key)
            else:
                updated.append(line)
        for key, value in wanted.items():
            if key not in seen:
                updated.insert(0, f"{key}={value}")
        env_path.write_text("\n".join(updated) + "\n", encoding="utf-8")

    def _ensure_runtime_tosu_dir(self) -> Path | None:
        source_dir = self._bundled_tosu_source_dir()
        if source_dir is None:
            return None
        target_dir = self._runtime_tosu_dir()
        source_exe = source_dir / "tosu.exe"
        target_exe = target_dir / "tosu.exe"
        needs_refresh = not target_exe.exists()
        if not needs_refresh and target_exe.exists():
            source_stat = source_exe.stat()
            target_stat = target_exe.stat()
            needs_refresh = source_stat.st_size != target_stat.st_size or int(source_stat.st_mtime) != int(target_stat.st_mtime)
        if needs_refresh:
            if target_dir.exists():
                shutil.rmtree(target_dir)
            shutil.copytree(source_dir, target_dir)
        self._patch_tosu_env(target_dir)
        return target_dir

    def _candidate_tosu_paths(self) -> list[Path]:
        candidates: list[Path] = []
        runtime_dir = self._ensure_runtime_tosu_dir()
        if runtime_dir is not None:
            candidates.append(runtime_dir / "tosu.exe")
        configured = self._config.tosu_executable_path.strip()
        if configured:
            candidates.append(Path(configured))
        for path in [
            Path.home() / "AppData" / "Local" / "Programs" / "tosu" / "tosu.exe",
            Path.home() / "AppData" / "Local" / "tosu" / "tosu.exe",
            Path("C:/Program Files/tosu/tosu.exe"),
            Path("C:/Program Files (x86)/tosu/tosu.exe"),
        ]:
            if path not in candidates:
                candidates.append(path)
        return candidates

    def resolve_executable(self) -> Path | None:
        for candidate in self._candidate_tosu_paths():
            if candidate.exists():
                return candidate
        return None

    def _read_pid(self) -> int | None:
        if not self._pid_path.exists():
            return None
        try:
            return int(self._pid_path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            return None

    def _write_pid(self, pid: int) -> None:
        self._pid_path.parent.mkdir(parents=True, exist_ok=True)
        self._pid_path.write_text(str(pid), encoding="utf-8")

    def _stored_process_alive(self) -> bool:
        pid = self._read_pid()
        if pid is None:
            return False
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def _runtime_env(self) -> dict[str, str]:
        env = dict(os.environ)
        env["OPEN_DASHBOARD_ON_STARTUP"] = "false"
        env["ENABLE_AUTOUPDATE"] = "false"
        return env

    def start_if_needed(self, client: TosuClient) -> str:
        if client.endpoint_reachable():
            return "running"
        if self._process is not None and self._process.poll() is None:
            return "starting"
        if self._stored_process_alive():
            return "starting"
        if time.monotonic() - self._last_launch_monotonic < 10:
            return "starting"
        path = self.resolve_executable()
        if path is None:
            return "missing"
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self._process = subprocess.Popen(
            [str(path)],
            cwd=str(path.parent),
            creationflags=creationflags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            env=self._runtime_env(),
        )
        self._write_pid(self._process.pid)
        self._last_launch_monotonic = time.monotonic()
        return "started"

    def shutdown(self) -> str:
        if self._process is not None and self._process.poll() is None:
            self._process.kill()
            self._process = None
            self._clean_pid()
            return "stopped"
        if self._stored_process_alive():
            pid = self._read_pid()
            if pid is not None:
                try:
                    os.kill(pid, 9)
                except OSError:
                    pass
            self._clean_pid()
            return "stopped"
        self._clean_pid()
        return "not_running"

    def _clean_pid(self) -> None:
        if self._pid_path.exists():
            self._pid_path.unlink(missing_ok=True)


@dataclass(frozen=True)
class PlayerCard:
    username: str | None
    user_id: int | None
    pp: float | None
    accuracy: float | None
    play_count: int | None
    global_rank: int | None
    country_code: str | None
    mode: str | None


@dataclass(frozen=True)
class BeatmapCard:
    title: str | None
    artist: str | None
    version: str | None
    mapper: str | None
    beatmap_id: int | None
    beatmapset_id: int | None
    client_name: str | None
    mods_raw: str
    star_rating: float | None
    bpm: float | None
    ar: float | None
    od: float | None
    cs: float | None
    hit_length_sec: int | None
    total_length_sec: int | None
    passcount: int | None
    playcount: int | None


@dataclass(frozen=True)
class PredictionCard:
    pass_probability: float
    predicted_accuracy: float
    difficulty_gap: float
    recommendation: str
    classifier_model: str
    regressor_model: str
    artifact_version: str


class LiveService:
    def __init__(self, *, config: LiveConfig, prediction_service: PredictionService) -> None:
        self._config = config
        self._prediction_service = prediction_service
        self._tosu_client = TosuClient(base_url=config.tosu_base_url, timeout_seconds=config.request_timeout_seconds)
        self._tosu_manager = TosuManager(config)
        self._osu_api_client = OsuApiClient(
            api_base_url=config.osu_api_base_url,
            token_url=config.osu_token_url,
            timeout_seconds=config.request_timeout_seconds,
            ruleset=config.ruleset,
            client_id=config.osu_client_id,
            client_secret=config.osu_client_secret,
        )
        self._beatmap_cache: dict[int, tuple[float, OsuBeatmapApiSnapshot]] = {}
        self._user_cache: dict[int, tuple[float, OsuUserApiSnapshot]] = {}
        self._user_cache_by_name: dict[str, tuple[float, OsuUserApiSnapshot]] = {}

    @classmethod
    def from_env(cls, prediction_service: PredictionService) -> "LiveService":
        return cls(config=LiveConfig.from_env(), prediction_service=prediction_service)

    @property
    def config(self) -> LiveConfig:
        return self._config

    def settings_payload(self) -> dict[str, Any]:
        return {
            "tosu_base_url": self._config.tosu_base_url,
            "tosu_executable_path": self._config.tosu_executable_path,
            "osu_client_id": self._config.osu_client_id,
            "osu_client_secret": self._config.osu_client_secret,
            "setup_required": not bool(self._config.osu_client_id and self._config.osu_client_secret),
            "oauth_settings_url": OSU_OAUTH_SETTINGS_URL,
            "callback_url_hint": "http://localhost:1337",
            "web_port": self._config.web_port,
            "player_source": self._config.player_source,
            "manual_username": self._config.manual_username,
            "offline_mode": self._config.offline_mode,
            "offline_pp": self._config.offline_pp,
            "offline_accuracy": self._config.offline_accuracy,
            "offline_play_count": self._config.offline_play_count,
            "offline_global_rank": self._config.offline_global_rank,
            "offline_country": self._config.offline_country,
            "overlay_enabled": self._config.overlay_enabled,
            "overlay_position": self._config.overlay_position,
            "overlay_x": self._config.overlay_x,
            "overlay_y": self._config.overlay_y,
            "overlay_display": self._config.overlay_display,
        }

    def update_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        old_client_id = self._config.osu_client_id
        old_client_secret = self._config.osu_client_secret
        new_client_id = str(payload.get("osu_client_id", self._config.osu_client_id))
        new_client_secret = str(payload.get("osu_client_secret", self._config.osu_client_secret))
        save_web_settings(
            {
                "tosu_base_url": str(payload.get("tosu_base_url", self._config.tosu_base_url)).rstrip("/"),
                "tosu_executable_path": str(payload.get("tosu_executable_path", self._config.tosu_executable_path)),
                "osu_api_base_url": self._config.osu_api_base_url,
                "osu_token_url": self._config.osu_token_url,
                "ruleset": self._config.ruleset,
                "request_timeout_seconds": self._config.request_timeout_seconds,
                "beatmap_cache_ttl_seconds": self._config.beatmap_cache_ttl_seconds,
                "user_cache_ttl_seconds": self._config.user_cache_ttl_seconds,
                "osu_client_id": new_client_id,
                "osu_client_secret": new_client_secret,
                "web_port": self._config.web_port,
                "player_source": str(payload.get("player_source", self._config.player_source)),
                "manual_username": str(payload.get("manual_username", self._config.manual_username)),
                "offline_mode": bool(payload.get("offline_mode", self._config.offline_mode)),
                "offline_pp": float(payload.get("offline_pp", self._config.offline_pp)),
                "offline_accuracy": float(payload.get("offline_accuracy", self._config.offline_accuracy)),
                "offline_play_count": int(payload.get("offline_play_count", self._config.offline_play_count)),
                "offline_global_rank": int(payload.get("offline_global_rank", self._config.offline_global_rank)),
                "offline_country": str(payload.get("offline_country", self._config.offline_country)),
                "overlay_enabled": bool(payload.get("overlay_enabled", self._config.overlay_enabled)),
                "overlay_position": str(payload.get("overlay_position", self._config.overlay_position)),
                "overlay_x": int(payload.get("overlay_x", self._config.overlay_x)),
                "overlay_y": int(payload.get("overlay_y", self._config.overlay_y)),
                "overlay_display": int(payload.get("overlay_display", self._config.overlay_display)),
            }
        )
        self._config = LiveConfig.from_env()
        self._tosu_client = TosuClient(base_url=self._config.tosu_base_url, timeout_seconds=self._config.request_timeout_seconds)
        self._tosu_manager = TosuManager(self._config)
        self._osu_api_client = OsuApiClient(
            api_base_url=self._config.osu_api_base_url,
            token_url=self._config.osu_token_url,
            timeout_seconds=self._config.request_timeout_seconds,
            ruleset=self._config.ruleset,
            client_id=self._config.osu_client_id,
            client_secret=self._config.osu_client_secret,
        )
        if old_client_id != new_client_id or old_client_secret != new_client_secret:
            self._beatmap_cache.clear()
            self._user_cache.clear()
            self._user_cache_by_name.clear()
        return self.settings_payload()

    def start_tosu(self) -> dict[str, Any]:
        return {"status": self._tosu_manager.start_if_needed(self._tosu_client)}

    def shutdown(self) -> dict[str, Any]:
        return {"tosu_status": self._tosu_manager.shutdown()}

    def refresh_user_cache(self) -> dict[str, Any]:
        self._user_cache.clear()
        self._user_cache_by_name.clear()
        return {"status": "ok"}

    def _cached_beatmap(self, beatmap_id: int) -> OsuBeatmapApiSnapshot:
        cached = self._beatmap_cache.get(beatmap_id)
        if cached and cached[0] > time.time():
            return cached[1]
        if beatmap_id <= 0:
            raise RuntimeError(f"Invalid beatmap_id from tosu: {beatmap_id}")
        snapshot = self._osu_api_client.get_beatmap(beatmap_id)
        self._beatmap_cache[beatmap_id] = (time.time() + self._config.beatmap_cache_ttl_seconds, snapshot)
        return snapshot

    def _cached_user(self, *, user_id: int | None, username: str | None) -> OsuUserApiSnapshot:
        safe_id = user_id if user_id is not None and user_id > 0 else None
        name_key = (username or "").strip().lower() if username else None

        if safe_id is not None:
            cached = self._user_cache.get(safe_id)
            if cached and cached[0] > time.time():
                return cached[1]

        if name_key:
            cached = self._user_cache_by_name.get(name_key)
            if cached and cached[0] > time.time():
                return cached[1]

        snapshot = self._osu_api_client.get_user(user_id=safe_id, username=username)
        expiry = time.time() + self._config.user_cache_ttl_seconds
        self._user_cache[snapshot.user_id] = (expiry, snapshot)
        if name_key:
            self._user_cache_by_name[name_key] = (expiry, snapshot)
        return snapshot

    def _fetch_live_state_with_retry(self, *, allow_startup_wait: bool) -> TosuLiveState:
        attempts = 10 if allow_startup_wait else 1
        last_exc: Exception | None = None
        for attempt in range(attempts):
            try:
                return self._tosu_client.fetch_live_state()
            except requests.RequestException as exc:
                last_exc = exc
                if attempt < attempts - 1:
                    time.sleep(0.5)
                    continue
                raise
        assert last_exc is not None
        raise last_exc

    def _player_payload(self, live_state: TosuLiveState) -> PlayerCard:
        return PlayerCard(
            username=live_state.username or None,
            user_id=live_state.user_id,
            pp=live_state.user_pp,
            accuracy=live_state.user_accuracy,
            play_count=live_state.user_play_count,
            global_rank=live_state.user_global_rank,
            country_code=live_state.country_code,
            mode=live_state.ruleset,
        )

    def _beatmap_payload(self, live_state: TosuLiveState) -> BeatmapCard:
        return BeatmapCard(
            title=live_state.title or None,
            artist=live_state.artist or None,
            version=live_state.version or None,
            mapper=live_state.mapper or None,
            beatmap_id=live_state.beatmap_id,
            beatmapset_id=live_state.beatmapset_id,
            client_name=live_state.client_name or None,
            mods_raw=live_state.mods_raw or "",
            star_rating=live_state.beatmap_star_rating,
            bpm=live_state.beatmap_bpm,
            ar=live_state.beatmap_ar,
            od=live_state.beatmap_od,
            cs=live_state.beatmap_cs,
            hit_length_sec=live_state.beatmap_hit_length_sec,
            total_length_sec=live_state.beatmap_total_length_sec,
            passcount=live_state.passcount,
            playcount=live_state.playcount,
        )

    def _enrich_live_state(self, live_state: TosuLiveState) -> TosuLiveState:
        beatmap_snapshot = None
        if live_state.beatmap_id is not None and live_state.beatmap_id > 0:
            beatmap_snapshot = self._cached_beatmap(live_state.beatmap_id)

        user_snapshot = None
        if (live_state.user_id is not None and live_state.user_id > 0) or live_state.username:
            user_snapshot = self._cached_user(user_id=live_state.user_id, username=live_state.username or None)

        api = user_snapshot
        return TosuLiveState(
            raw_payload=live_state.raw_payload,
            client_name=live_state.client_name,
            ruleset=live_state.ruleset,
            user_id=api.user_id if api else None,
            username=live_state.username or (api.username if api else ""),
            user_pp=api.pp if api else None,
            user_accuracy=api.accuracy if api else None,
            user_play_count=api.play_count if api else None,
            user_global_rank=api.global_rank if api else None,
            country_code=api.country_code if api else None,
            beatmap_id=live_state.beatmap_id,
            beatmapset_id=live_state.beatmapset_id if live_state.beatmapset_id is not None else (beatmap_snapshot.beatmapset_id if beatmap_snapshot else None),
            artist=live_state.artist or (beatmap_snapshot.artist if beatmap_snapshot else "") or "",
            title=live_state.title or (beatmap_snapshot.title if beatmap_snapshot else "") or "",
            version=live_state.version or (beatmap_snapshot.version if beatmap_snapshot else "") or "",
            mapper=live_state.mapper or (beatmap_snapshot.mapper if beatmap_snapshot else "") or "",
            mods_raw=live_state.mods_raw,
            beatmap_star_rating=live_state.beatmap_star_rating,
            beatmap_bpm=live_state.beatmap_bpm,
            beatmap_ar=live_state.beatmap_ar,
            beatmap_od=live_state.beatmap_od,
            beatmap_cs=live_state.beatmap_cs,
            beatmap_hit_length_sec=live_state.beatmap_hit_length_sec,
            beatmap_total_length_sec=live_state.beatmap_total_length_sec,
            passcount=beatmap_snapshot.passcount if beatmap_snapshot else live_state.passcount,
            playcount=beatmap_snapshot.playcount if beatmap_snapshot else live_state.playcount,
            refreshed_at=live_state.refreshed_at,
        )

    def _prediction_payload(self, live_state: TosuLiveState) -> dict[str, Any]:
        request = PredictionRequest(
            user_pp=float(live_state.user_pp),
            user_accuracy=float(live_state.user_accuracy),
            user_play_count=int(live_state.user_play_count),
            beatmap_star_rating=float(live_state.beatmap_star_rating),
            beatmap_bpm=float(live_state.beatmap_bpm),
            beatmap_ar=float(live_state.beatmap_ar),
            beatmap_od=float(live_state.beatmap_od),
            beatmap_cs=float(live_state.beatmap_cs),
            beatmap_hit_length_sec=int(live_state.beatmap_hit_length_sec),
            beatmap_total_length_sec=int(live_state.beatmap_total_length_sec),
            beatmap_passcount=int(live_state.passcount),
            beatmap_playcount=int(live_state.playcount),
            mods_raw=live_state.mods_raw,
        )
        return request.model_dump()

    def _prediction_card(self, payload: dict[str, Any]) -> PredictionCard:
        prediction = self._prediction_service.predict(PredictionRequest(**payload))
        return PredictionCard(
            pass_probability=prediction.pass_probability,
            predicted_accuracy=prediction.predicted_accuracy,
            difficulty_gap=prediction.difficulty_gap,
            recommendation=prediction.recommendation,
            classifier_model=prediction.classifier_model,
            regressor_model=prediction.regressor_model,
            artifact_version=prediction.artifact_version,
        )

    def snapshot(self) -> dict[str, Any]:
        refreshed_at = utc_now_iso()
        startup_status = self._tosu_manager.start_if_needed(self._tosu_client)

        try:
            live_state = self._fetch_live_state_with_retry(allow_startup_wait=startup_status in {"started", "starting"})
        except requests.exceptions.ConnectionError:
            return {
                "status": "waiting",
                "message": "Starting tosu in the background. If this stays empty, open osu! stable or lazer and wait a few seconds.",
                "refreshed_at": refreshed_at,
                "setup_required": not self._osu_api_client.configured,
                "sources": {"tosu": "starting" if startup_status != "missing" else "missing", "osu_api": "not_used", "prediction": "not_used"},
                "player": None,
                "beatmap": None,
                "prediction": None,
                "is_playing": False,
            }
        except requests.exceptions.HTTPError as exc:
            response_text = ""
            if getattr(exc, "response", None) is not None:
                try:
                    response_text = exc.response.text or ""
                except Exception:
                    response_text = ""
            normalized = unquote(response_text).lower()
            if "osu is not ready/running" in normalized:
                return {
                    "status": "waiting",
                    "message": "tosu is running. Open osu! stable or lazer and stay on the client, song-select, or gameplay screen.",
                    "refreshed_at": refreshed_at,
                    "setup_required": not self._osu_api_client.configured,
                    "sources": {"tosu": "ok", "osu_api": "not_used", "prediction": "not_used"},
                    "player": None,
                    "beatmap": None,
                    "prediction": None,
                "is_playing": False,
                }
            return {
                "status": "error",
                "message": "tosu responded with an unexpected error. Restart osu! and refresh again.",
                "refreshed_at": refreshed_at,
                "setup_required": not self._osu_api_client.configured,
                "sources": {"tosu": "error", "osu_api": "not_used", "prediction": "not_used"},
                "player": None,
                "beatmap": None,
                "prediction": None,
                "is_playing": False,
            }
        except requests.RequestException:
            return {
                "status": "error",
                "message": "Could not read live state from tosu.",
                "refreshed_at": refreshed_at,
                "setup_required": not self._osu_api_client.configured,
                "sources": {"tosu": "error", "osu_api": "not_used", "prediction": "not_used"},
                "player": None,
                "beatmap": None,
                "prediction": None,
                "is_playing": False,
            }

        manual = self._config.player_source == "manual" and bool(self._config.manual_username.strip())

        if manual:
            live_state = TosuLiveState(
                raw_payload=live_state.raw_payload,
                client_name=live_state.client_name,
                ruleset=live_state.ruleset,
                user_id=None,
                username=self._config.manual_username.strip(),
                user_pp=None,
                user_accuracy=None,
                user_play_count=None,
                user_global_rank=None,
                country_code=None,
                beatmap_id=live_state.beatmap_id,
                beatmapset_id=live_state.beatmapset_id,
                artist=live_state.artist,
                title=live_state.title,
                version=live_state.version,
                mapper=live_state.mapper,
                mods_raw=live_state.mods_raw,
                beatmap_star_rating=live_state.beatmap_star_rating,
                beatmap_bpm=live_state.beatmap_bpm,
                beatmap_ar=live_state.beatmap_ar,
                beatmap_od=live_state.beatmap_od,
                beatmap_cs=live_state.beatmap_cs,
                beatmap_hit_length_sec=live_state.beatmap_hit_length_sec,
                beatmap_total_length_sec=live_state.beatmap_total_length_sec,
                passcount=None,
                playcount=None,
                refreshed_at=live_state.refreshed_at,
            )

        offline = self._config.offline_mode
        if offline:
            live_state = TosuLiveState(
                raw_payload=live_state.raw_payload,
                client_name=live_state.client_name,
                ruleset=live_state.ruleset,
                user_id=None,
                username=self._config.manual_username.strip() or "offline",
                user_pp=self._config.offline_pp or None,
                user_accuracy=self._config.offline_accuracy or None,
                user_play_count=self._config.offline_play_count or None,
                user_global_rank=self._config.offline_global_rank or None,
                country_code=self._config.offline_country or None,
                beatmap_id=live_state.beatmap_id,
                beatmapset_id=live_state.beatmapset_id,
                artist=live_state.artist,
                title=live_state.title,
                version=live_state.version,
                mapper=live_state.mapper,
                mods_raw=live_state.mods_raw,
                beatmap_star_rating=live_state.beatmap_star_rating,
                beatmap_bpm=live_state.beatmap_bpm,
                beatmap_ar=live_state.beatmap_ar,
                beatmap_od=live_state.beatmap_od,
                beatmap_cs=live_state.beatmap_cs,
                beatmap_hit_length_sec=live_state.beatmap_hit_length_sec,
                beatmap_total_length_sec=live_state.beatmap_total_length_sec,
                passcount=None,
                playcount=None,
                refreshed_at=live_state.refreshed_at,
            )

        player = self._player_payload(live_state)
        beatmap = self._beatmap_payload(live_state)

        if live_state.ruleset.lower() != self._config.ruleset.lower():
            return {
                "status": "unsupported",
                "message": f"Current ruleset is '{live_state.ruleset}', but the model only supports '{self._config.ruleset}'.",
                "refreshed_at": refreshed_at,
                "setup_required": not self._osu_api_client.configured,
                "sources": {"tosu": "ok", "osu_api": "not_used", "prediction": "not_used"},
                "player": player.__dict__,
                "beatmap": beatmap.__dict__,
                "prediction": None,
                "is_playing": live_state.is_playing,
            }

        missing_beatmap = live_state.beatmap_id is None
        missing_player = manual and missing_beatmap
        if not manual:
            missing_player = missing_beatmap or not live_state.username
        if missing_player:
            return {
                "status": "waiting",
                "message": "Waiting for a current beatmap. Open a map or return to song-select or gameplay.",
                "refreshed_at": refreshed_at,
                "setup_required": not self._osu_api_client.configured,
                "sources": {"tosu": "ok", "osu_api": "not_used", "prediction": "not_used"},
                "player": player.__dict__,
                "beatmap": beatmap.__dict__,
                "prediction": None,
                "is_playing": live_state.is_playing,
            }

        if not offline and not self._osu_api_client.configured:
            return {
                "status": "waiting",
                "message": "Add osu! Client ID and Client Secret in Setup to enrich beatmap/player data and run prediction.",
                "refreshed_at": refreshed_at,
                "setup_required": True,
                "sources": {"tosu": "ok", "osu_api": "not_configured", "prediction": "not_used"},
                "player": player.__dict__,
                "beatmap": beatmap.__dict__,
                "prediction": None,
                "is_playing": live_state.is_playing,
            }

        if offline:
            enriched = live_state
        else:
            try:
                enriched = self._enrich_live_state(live_state)
                player = self._player_payload(enriched)
                beatmap = self._beatmap_payload(enriched)
            except Exception as exc:
                detail = f"{type(exc).__name__}: {exc}"
                return {
                    "status": "error",
                    "message": f"osu! API enrichment failed — {detail}",
                    "refreshed_at": refreshed_at,
                    "setup_required": True,
                    "sources": {"tosu": "ok", "osu_api": "error", "prediction": "not_used"},
                    "player": player.__dict__,
                    "beatmap": beatmap.__dict__,
                    "prediction": None,
                    "is_playing": live_state.is_playing,
                }

        try:
            payload = self._prediction_payload(enriched)
            prediction = self._prediction_card(payload)
        except Exception as exc:
            return {
                "status": "error",
                "message": f"Prediction failed after live data was collected. {type(exc).__name__}: {exc}",
                "refreshed_at": refreshed_at,
                "setup_required": False,
                "sources": {"tosu": "ok", "osu_api": "ok", "prediction": "error"},
                "player": player.__dict__,
                "beatmap": beatmap.__dict__,
                "prediction": None,
                "is_playing": live_state.is_playing,
            }

        return {
            "status": "ok",
            "message": "Prediction updated from current osu! state.",
            "refreshed_at": refreshed_at,
            "setup_required": False,
            "sources": {"tosu": "ok", "osu_api": "ok", "prediction": "local-models"},
            "player": player.__dict__,
            "beatmap": beatmap.__dict__,
            "prediction": prediction.__dict__,
            "is_playing": enriched.is_playing,
        }

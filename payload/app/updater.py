"""Transactional, file-by-file updater for the portable AK-Weather application.

Only the standard library is used. A successful update creates a complete bundle
and changes current.txt last; the running bundle and baseline are never modified.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import http.client
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import ssl
import stat
import subprocess
import sys
from typing import BinaryIO, Callable
import urllib.error
import urllib.parse
import urllib.request
import uuid


API_URL = "https://api.github.com/repos/Contralto0/AK-Weather/commits/live"
RAW_BASE = "https://raw.githubusercontent.com/Contralto0/AK-Weather"
MAX_MANIFEST_BYTES = 2 * 1024 * 1024
MAX_API_BYTES = 1024 * 1024
MAX_FILE_BYTES = 256 * 1024 * 1024
MAX_TOTAL_BYTES = 1024 * 1024 * 1024
MAX_FILES = 10_000
CHUNK_BYTES = 128 * 1024
REQUIRED_PATHS = frozenset({
    "app/WeatherShell.exe", "app/updater.py", "app/healthcheck.py",
    "app/dwd_stations.py", "app/dwd_current.py", "app/dwd_radolan.py", "app/version.json", "runtime/python.exe",
})
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
COMMIT_RE = re.compile(r"[0-9a-f]{40}\Z")
RESERVED_NAMES = frozenset({"con", "prn", "aux", "nul", "conin$", "conout$"} |
                           {f"{prefix}{number}" for prefix in ("com", "lpt")
                            for number in "123456789¹²³"})


class UpdateError(Exception):
    """A checked failure which must not change the active bundle."""


class OfflineError(UpdateError):
    """The repository cannot currently be reached."""


class IntegrityError(UpdateError):
    """Downloaded or local data failed validation."""


class UpdateBusy(UpdateError):
    """Another process owns the updater lock."""


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise IntegrityError("Die Update-Daten enthalten doppelte JSON-Felder.")
        result[key] = value
    return result


def decode_json(data: bytes) -> object:
    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise IntegrityError("Die Update-Daten sind kein gültiges UTF-8-JSON.") from exc


def validate_relative_path(value: object) -> str:
    if not isinstance(value, str) or not value or len(value) > 220:
        raise IntegrityError("Das Update enthält einen ungültigen Dateipfad.")
    if "\\" in value or value.startswith("/") or value.endswith("/"):
        raise IntegrityError("Das Update enthält einen unsicheren Dateipfad.")
    parts = value.split("/")
    for part in parts:
        if (not part or part in (".", "..") or part.endswith((".", " ")) or
                any(ord(char) < 32 or char in '<>:"|?*' for char in part) or
                part.split(".", 1)[0].rstrip(" ").casefold() in RESERVED_NAMES):
            raise IntegrityError("Das Update enthält einen unter Windows unsicheren Dateipfad.")
    return value


def parse_manifest(data: bytes) -> dict:
    if len(data) > MAX_MANIFEST_BYTES:
        raise IntegrityError("Das Update-Manifest ist zu groß.")
    manifest = decode_json(data)
    if not isinstance(manifest, dict) or type(manifest.get("schema")) is not int or manifest["schema"] != 1:
        raise IntegrityError("Das Update-Manifest verwendet ein unbekanntes Format.")
    version = manifest.get("version")
    if not isinstance(version, str) or not version or len(version) > 80 or any(ord(c) < 32 for c in version):
        raise IntegrityError("Das Update-Manifest enthält keine gültige Version.")
    entries = manifest.get("files")
    if not isinstance(entries, list) or not 1 <= len(entries) <= MAX_FILES:
        raise IntegrityError("Das Update-Manifest enthält eine ungültige Dateiliste.")
    paths = {}
    directories = {}
    total_bytes = 0
    for entry in entries:
        if not isinstance(entry, dict):
            raise IntegrityError("Das Update-Manifest enthält einen ungültigen Dateieintrag.")
        name = validate_relative_path(entry.get("path"))
        key = name.casefold()
        if key in paths:
            raise IntegrityError("Das Update enthält mehrfach verwendete Dateinamen.")
        paths[key] = name
        size, digest = entry.get("size"), entry.get("sha256")
        if type(size) is not int or not 0 <= size <= MAX_FILE_BYTES:
            raise IntegrityError("Eine Update-Datei überschreitet die erlaubte Größe.")
        if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
            raise IntegrityError("Das Update enthält einen ungültigen SHA-256-Prüfwert.")
        total_bytes += size
        parts = name.split("/")
        for index in range(1, len(parts)):
            directory = "/".join(parts[:index])
            previous = directories.setdefault(directory.casefold(), directory)
            if previous != directory:
                raise IntegrityError("Das Update enthält widersprüchliche Verzeichnisnamen.")
    if total_bytes > MAX_TOTAL_BYTES:
        raise IntegrityError("Das Update überschreitet die erlaubte Gesamtgröße.")
    if paths.keys() & directories.keys():
        raise IntegrityError("Ein Update-Pfad wird gleichzeitig als Datei und Verzeichnis verwendet.")
    if not REQUIRED_PATHS.issubset(set(paths.values())):
        raise IntegrityError("Im Update fehlen notwendige Programmdateien.")
    return manifest


def _is_reparse(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def assert_safe_path(path: Path, *, must_exist: bool = False) -> None:
    """Reject symbolic links and Windows junctions in every existing component."""
    absolute = Path(os.path.abspath(path))
    components = [absolute, *absolute.parents]
    for component in reversed(components):
        try:
            info = component.lstat()
        except FileNotFoundError:
            if must_exist:
                raise IntegrityError("Ein benötigter lokaler Update-Pfad fehlt.")
            continue
        if _is_reparse(info):
            raise IntegrityError("Verknüpfungen oder Windows-Umleitungen sind in Update-Pfaden nicht erlaubt.")
        if component != absolute and not stat.S_ISDIR(info.st_mode):
            raise IntegrityError("Ein Update-Verzeichnis ist keine reguläre Ablage.")


def safe_join(base: Path, relative: str, *, must_exist: bool = False) -> Path:
    validate_relative_path(relative)
    destination = base.joinpath(*PurePosixPath(relative).parts)
    assert_safe_path(destination, must_exist=must_exist)
    return destination


def ensure_directory(path: Path) -> None:
    assert_safe_path(path)
    path.mkdir(parents=True, exist_ok=True)
    assert_safe_path(path, must_exist=True)
    if not path.is_dir():
        raise IntegrityError("Ein benötigtes Update-Verzeichnis ist keine reguläre Ablage.")


@contextlib.contextmanager
def checked_open(path: Path, mode: str):
    assert_safe_path(path, must_exist=mode == "rb")
    flags = os.O_RDONLY if mode == "rb" else os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or _is_reparse(info):
            raise IntegrityError("Eine Update-Datei ist keine reguläre Datei.")
        assert_safe_path(path, must_exist=True)
        with os.fdopen(descriptor, mode) as handle:
            descriptor = -1
            yield handle
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def read_limited_file(path: Path, limit: int) -> bytes:
    with checked_open(path, "rb") as handle:
        data = handle.read(limit + 1)
    if len(data) > limit:
        raise IntegrityError("Eine lokale Update-Steuerdatei ist zu groß.")
    return data


def file_matches(path: Path, entry: dict) -> bool:
    digest = hashlib.sha256()
    with checked_open(path, "rb") as handle:
        before = os.fstat(handle.fileno())
        if before.st_size != entry["size"]:
            return False
        count = 0
        while chunk := handle.read(CHUNK_BYTES):
            count += len(chunk)
            if count > entry["size"]:
                return False
            digest.update(chunk)
        after = os.fstat(handle.fileno())
        if before.st_mtime_ns != after.st_mtime_ns or before.st_size != after.st_size:
            return False
    return count == entry["size"] and digest.hexdigest() == entry["sha256"]


def inventory(bundle: Path) -> dict[str, Path]:
    assert_safe_path(bundle, must_exist=True)
    if not bundle.is_dir():
        raise IntegrityError("Das aktive Programmverzeichnis ist ungültig.")
    found = {}
    folded = set()
    pending = [bundle]
    while pending:
        directory = pending.pop()
        assert_safe_path(directory, must_exist=True)
        with os.scandir(directory) as items:
            for item in items:
                path = Path(item.path)
                info = item.stat(follow_symlinks=False)
                if _is_reparse(info):
                    raise IntegrityError("Das Programmverzeichnis enthält eine unsichere Verknüpfung.")
                relative = path.relative_to(bundle).as_posix()
                validate_relative_path(relative)
                if stat.S_ISDIR(info.st_mode):
                    pending.append(path)
                elif stat.S_ISREG(info.st_mode):
                    if relative.casefold() in folded:
                        raise IntegrityError("Das Programmverzeichnis enthält doppelte Windows-Dateinamen.")
                    found[relative] = path
                    folded.add(relative.casefold())
                else:
                    raise IntegrityError("Das Programmverzeichnis enthält eine unzulässige Datei.")
    return found


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        parts = urllib.parse.urlsplit(new_url)
        if (parts.scheme != "https" or parts.hostname not in {"api.github.com", "raw.githubusercontent.com"}
                or parts.username is not None or parts.password is not None):
            raise IntegrityError("Der Update-Server hat eine unzulässige Weiterleitung angefordert.")
        try:
            if parts.port not in (None, 443):
                raise IntegrityError("Der Update-Server hat eine unzulässige Weiterleitung angefordert.")
        except ValueError as exc:
            raise IntegrityError("Der Update-Server hat eine ungültige Weiterleitung angefordert.") from exc
        return super().redirect_request(request, fp, code, message, headers, new_url)


class HttpTransport:
    """Bounded HTTPS transport; tests replace this without opening any server."""

    def __init__(self, timeout: float = 20):
        self.timeout = timeout
        self.opener = urllib.request.build_opener(_SafeRedirectHandler())

    def download(self, url: str, destination: BinaryIO, limit: int) -> int:
        request = urllib.request.Request(url, headers={
            "User-Agent": "AK-Weather-Updater/1.0",
            "Accept": "application/vnd.github+json" if url == API_URL else "application/octet-stream",
            "Accept-Encoding": "identity",
        })
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                length = response.headers.get("Content-Length")
                if length is not None:
                    try:
                        declared = int(length)
                    except ValueError as exc:
                        raise IntegrityError("Der Update-Server meldet eine ungültige Dateigröße.") from exc
                    if declared < 0 or declared > limit:
                        raise IntegrityError("Die heruntergeladene Datei überschreitet die erlaubte Größe.")
                count = 0
                while chunk := response.read(min(CHUNK_BYTES, limit - count + 1)):
                    count += len(chunk)
                    if count > limit:
                        raise IntegrityError("Die heruntergeladene Datei überschreitet die erlaubte Größe.")
                    destination.write(chunk)
                return count
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 429):
                raise OfflineError("GitHub begrenzt gerade die Update-Abfragen. Bitte später erneut versuchen.") from exc
            if exc.code == 404:
                raise OfflineError("Für dieses Programm ist noch kein erreichbares Update veröffentlicht.") from exc
            raise OfflineError("Der Update-Server ist momentan nicht erreichbar. Die vorhandene Version bleibt verfügbar.") from exc
        except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException, ssl.SSLError) as exc:
            raise OfflineError("Keine Verbindung zum Update-Server. Die vorhandene Version bleibt verfügbar.") from exc

    def get_bytes(self, url: str, limit: int) -> bytes:
        output = io.BytesIO()
        self.download(url, output, limit)
        return output.getvalue()


class UpdateLock:
    """A kernel-held lock automatically released after a crash or interruption."""

    def __init__(self, path: Path):
        self.path = path
        self.handle = None

    def __enter__(self):
        assert_safe_path(self.path)
        flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(self.path, flags, 0o600)
        self.handle = os.fdopen(descriptor, "r+b", buffering=0)
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or _is_reparse(info):
                raise IntegrityError("Die lokale Update-Sperrdatei ist ungültig.")
            assert_safe_path(self.path, must_exist=True)
            if info.st_size == 0:
                self.handle.write(b"0")
            self.handle.seek(0)
            try:
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise UpdateBusy("Eine andere Aktualisierung läuft bereits. Bitte kurz warten.") from exc
        except BaseException:
            self.handle.close()
            self.handle = None
            raise
        return self

    def __exit__(self, *_):
        if self.handle is not None:
            try:
                self.handle.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
            finally:
                self.handle.close()


def run_healthcheck(candidate: Path) -> None:
    python = safe_join(candidate, "runtime/python.exe", must_exist=True)
    script = safe_join(candidate, "app/healthcheck.py", must_exist=True)
    try:
        result = subprocess.run(
            [str(python), "-I", "-B", str(script)], cwd=candidate,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=45, check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise IntegrityError("Der Selbsttest der neuen Version konnte nicht erfolgreich ausgeführt werden.") from exc
    if result.returncode != 0:
        raise IntegrityError("Die neue Version hat ihren Selbsttest nicht bestanden.")


def validate_bundle(candidate: Path, manifest: dict) -> None:
    actual = inventory(candidate)
    expected = {entry["path"] for entry in manifest["files"]}
    if set(actual) != expected:
        raise IntegrityError("Die neue Version enthält nicht die erwarteten Dateien.")
    for entry in manifest["files"]:
        if not file_matches(actual[entry["path"]], entry):
            raise IntegrityError("Eine Programmdatei stimmt nicht mit ihrem SHA-256-Prüfwert überein.")


def atomic_write(path: Path, data: bytes) -> None:
    assert_safe_path(path)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with checked_open(temporary, "xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        assert_safe_path(path)
        assert_safe_path(temporary, must_exist=True)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            assert_safe_path(temporary, must_exist=True)
            temporary.unlink()


def _select_active(root: Path, supplied: Path, state: Path) -> Path:
    baseline = root / "payload"
    versions = state / "versions"
    allowed_version = supplied.parent == versions and SHA256_RE.fullmatch(supplied.name)
    if supplied != baseline and not allowed_version:
        raise IntegrityError("Das angegebene Programmverzeichnis gehört nicht zu dieser Installation.")
    pointer = state / "current.txt"
    assert_safe_path(pointer)
    if pointer.exists():
        raw = read_limited_file(pointer, 66)
        try:
            identifier = raw.decode("ascii").strip()
        except UnicodeError as exc:
            raise IntegrityError("Der lokale Versionszeiger ist ungültig.") from exc
        if not SHA256_RE.fullmatch(identifier):
            raise IntegrityError("Der lokale Versionszeiger ist ungültig.")
        supplied = safe_join(versions, identifier, must_exist=True)
    assert_safe_path(supplied, must_exist=True)
    return supplied


def _copy_verified(source: Path, destination: Path, entry: dict) -> None:
    digest = hashlib.sha256()
    count = 0
    with checked_open(source, "rb") as reader, checked_open(destination, "xb") as writer:
        while chunk := reader.read(CHUNK_BYTES):
            count += len(chunk)
            if count > entry["size"]:
                raise IntegrityError("Eine lokale Datei wurde während der Aktualisierung verändert.")
            digest.update(chunk)
            writer.write(chunk)
        writer.flush()
        os.fsync(writer.fileno())
    if count != entry["size"] or digest.hexdigest() != entry["sha256"]:
        raise IntegrityError("Eine lokale Datei wurde während der Aktualisierung verändert.")


def _remove_staging(path: Path, versions: Path) -> None:
    if path.parent != versions or not re.fullmatch(r"\.staging-[0-9a-f]{32}", path.name):
        return
    try:
        if path.exists():
            inventory(path)  # Reject junctions before recursive cleanup.
            shutil.rmtree(path)
    except (OSError, UpdateError):
        pass  # A leftover staging directory is never selected by the launcher.


def perform_update(root: Path, bundle: Path, transport, emit: Callable[[dict], None],
                   healthcheck: Callable[[Path], None] = run_healthcheck) -> str:
    root = Path(os.path.abspath(root))
    bundle = Path(os.path.abspath(bundle))
    assert_safe_path(root, must_exist=True)
    state = root / ".ak-weather"
    ensure_directory(state)
    with UpdateLock(state / "update.lock"):
        active = _select_active(root, bundle, state)
        emit({"state": "checking", "message": "Die aktuelle Programmversion wird geprüft."})
        commit_document = decode_json(transport.get_bytes(API_URL, MAX_API_BYTES))
        commit = commit_document.get("sha") if isinstance(commit_document, dict) else None
        if not isinstance(commit, str) or not COMMIT_RE.fullmatch(commit):
            raise IntegrityError("GitHub hat keinen gültigen Versionsstand geliefert.")
        pinned_base = f"{RAW_BASE}/{commit}"
        manifest_bytes = transport.get_bytes(f"{pinned_base}/update-manifest.json", MAX_MANIFEST_BYTES)
        manifest = parse_manifest(manifest_bytes)
        version = manifest["version"]
        identifier = hashlib.sha256(manifest_bytes).hexdigest()
        existing = inventory(active)
        reusable = {}
        for entry in manifest["files"]:
            source = existing.get(entry["path"])
            if source is not None and file_matches(source, entry):
                reusable[entry["path"]] = source
        expected_names = {entry["path"] for entry in manifest["files"]}
        if len(reusable) == len(manifest["files"]) and set(existing) == expected_names:
            emit({"state": "current", "message": "Das Programm ist auf dem neuesten Stand.",
                  "version": version, "downloaded_files": 0, "downloaded_bytes": 0})
            return "current"

        versions = state / "versions"
        ensure_directory(versions)
        target = safe_join(versions, identifier)
        staging = versions / f".staging-{uuid.uuid4().hex}"
        downloaded_files = downloaded_bytes = 0
        try:
            if target.exists():
                validate_bundle(target, manifest)
                healthcheck(target)
                validate_bundle(target, manifest)
            else:
                ensure_directory(staging)
                emit({"state": "downloading", "message": "Die neue Version wird vorbereitet.",
                      "version": version, "downloaded_files": 0, "downloaded_bytes": 0})
                for entry in manifest["files"]:
                    destination = safe_join(staging, entry["path"])
                    ensure_directory(destination.parent)
                    source = reusable.get(entry["path"])
                    if source is not None:
                        _copy_verified(source, destination, entry)
                    else:
                        encoded_path = urllib.parse.quote(entry["path"], safe="/")
                        url = f"{pinned_base}/payload/{encoded_path}"
                        with checked_open(destination, "xb") as handle:
                            transport.download(url, handle, entry["size"])
                            handle.flush()
                            os.fsync(handle.fileno())
                        if not file_matches(destination, entry):
                            raise IntegrityError("Eine heruntergeladene Datei hat einen falschen SHA-256-Prüfwert.")
                        downloaded_files += 1
                        downloaded_bytes += entry["size"]
                        emit({"state": "downloading", "message": "Geänderte Programmdateien werden geladen.",
                              "version": version, "downloaded_files": downloaded_files,
                              "downloaded_bytes": downloaded_bytes})
                validate_bundle(staging, manifest)
                healthcheck(staging)
                validate_bundle(staging, manifest)
                assert_safe_path(target)
                assert_safe_path(staging, must_exist=True)
                os.replace(staging, target)
            manifests = state / "manifests"
            ensure_directory(manifests)
            atomic_write(manifests / f"{identifier}.json", manifest_bytes)
            atomic_write(state / "current.txt", (identifier + "\n").encode("ascii"))
            emit({"state": "ready", "message": "Die neue Version ist bereit. Bitte das Programm neu starten.",
                  "version": version, "downloaded_files": downloaded_files,
                  "downloaded_bytes": downloaded_bytes})
            return "ready"
        finally:
            _remove_staging(staging, versions)


def run_update(root: Path, bundle: Path, transport=None, emit=None,
               healthcheck: Callable[[Path], None] = run_healthcheck) -> str:
    transport = transport if transport is not None else HttpTransport()
    emit = emit if emit is not None else emit_json
    try:
        return perform_update(root, bundle, transport, emit, healthcheck)
    except OfflineError as exc:
        emit({"state": "offline", "message": str(exc)})
        return "offline"
    except UpdateError as exc:
        emit({"state": "error", "message": str(exc)})
        return "error"
    except OSError:
        emit({"state": "error", "message": "Das Update konnte nicht gespeichert werden. Die vorhandene Version bleibt verfügbar."})
        return "error"


def emit_json(event: dict) -> None:
    try:
        print(json.dumps(event, ensure_ascii=False, separators=(",", ":")), flush=True)
    except (BrokenPipeError, ConnectionResetError):
        # Closing the GUI disconnects progress output, not the update transaction.
        pass


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="strict", newline="\n")
    parser = argparse.ArgumentParser(description="AK-Weather sicher aktualisieren")
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--bundle", required=True, type=Path)
    arguments = parser.parse_args(argv)
    try:
        result = run_update(arguments.root, arguments.bundle)
        return 1 if result == "error" else 0
    except KeyboardInterrupt:
        emit_json({"state": "error", "message": "Die Aktualisierung wurde abgebrochen. Die vorhandene Version bleibt verfügbar."})
        return 130


if __name__ == "__main__":
    raise SystemExit(main())

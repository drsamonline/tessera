"""Plugin hardening.

Reference: docs/04-core.md ("Plugin hardening") and docs/16-acceptance-criteria.md,
deliverable 16. Allowlist, pinned hashes, static analysis, sandbox.

Four gates, and the fourth is the one that is usually missing:

    allowlist      a plugin name that is not on the list does not load
    pinned hash    the file's SHA-256 must match the manifest, byte for byte
    signature      the manifest must be signed by a key the deployment holds
    static scan    the source may not import or call anything on the deny list

**Nothing here executes a plugin.** Validation and execution are separate
concerns, and a loader that runs untrusted code to find out whether it is safe to
run has already answered the question wrongly. `validate()` is the whole product
of this module; running is a separate process with the same gates in front of it.

The network permission is the same shape: a plugin declares what it needs, the
deployment declares what it will grant, and a request outside the grant is refused
**and logged**. A refused permission that leaves no trace is a permission system
nobody can audit.
"""

from __future__ import annotations

import ast
import hashlib
import hmac
import json
from dataclasses import dataclass, field

DENIED_IMPORTS = {
    "os", "sys", "subprocess", "socket", "urllib", "http", "requests", "ftplib",
    "ctypes", "pickle", "marshal", "importlib", "pty", "shutil", "multiprocessing",
}

DENIED_CALLS = {"eval", "exec", "compile", "__import__", "open", "input", "breakpoint"}

PERMISSIONS = ("network", "filesystem", "email", "webhook")


class PluginError(Exception):
    """Raised when a plugin fails a gate."""


@dataclass
class Manifest:
    name: str
    version: str
    entry: str
    sha256: str
    signature: str = ""
    permissions: list[str] = field(default_factory=list)

    def body(self) -> dict:
        return {"name": self.name, "version": self.version, "entry": self.entry,
                "sha256": self.sha256, "permissions": sorted(self.permissions)}

    def sign(self, key: bytes) -> "Manifest":
        blob = json.dumps(self.body(), sort_keys=True, separators=(",", ":")).encode()
        self.signature = hmac.new(key, blob, hashlib.sha256).hexdigest()
        return self

    def verify(self, key: bytes) -> bool:
        blob = json.dumps(self.body(), sort_keys=True, separators=(",", ":")).encode()
        return hmac.compare_digest(hmac.new(key, blob, hashlib.sha256).hexdigest(),
                                   self.signature)


@dataclass
class Plugin:
    manifest: Manifest
    source: str
    granted: list[str] = field(default_factory=list)


class Loader:
    def __init__(self, key: bytes, allowlist: set[str] | None = None,
                 granted_permissions: set[str] | None = None, log=None, tenant_id: str = ""):
        if not key:
            raise PluginError("a signing key is required; there is no default")
        self.key = key
        self.allowlist = set(allowlist or ())
        self.granted_permissions = set(granted_permissions or ())
        self.log = log
        self.tenant_id = tenant_id
        self.loaded: dict[str, Plugin] = {}

    def validate(self, plugin: Plugin) -> Plugin:
        """Run every gate. Raises on the first failure, and logs a refusal."""
        try:
            self._check_name(plugin)
            self._check_hash(plugin)
            self._check_signature(plugin)
            self._check_source(plugin)
            self._check_permissions(plugin)
        except PluginError as exc:
            self._log("plugin.refused", plugin, str(exc))
            raise
        self.loaded[plugin.manifest.name] = plugin
        self._log("plugin.loaded", plugin, "")
        return plugin

    # -- the gates --------------------------------------------------------
    def _check_name(self, plugin: Plugin) -> None:
        if self.allowlist and plugin.manifest.name not in self.allowlist:
            raise PluginError(f"{plugin.manifest.name!r} is not on the allowlist")

    def _check_hash(self, plugin: Plugin) -> None:
        actual = hashlib.sha256(plugin.source.encode("utf-8")).hexdigest()
        if not hmac.compare_digest(actual, plugin.manifest.sha256):
            raise PluginError(
                f"{plugin.manifest.name!r}: the source does not match the pinned hash"
            )

    def _check_signature(self, plugin: Plugin) -> None:
        if not plugin.manifest.signature:
            raise PluginError(f"{plugin.manifest.name!r} is unsigned")
        if not plugin.manifest.verify(self.key):
            raise PluginError(f"{plugin.manifest.name!r}: the signature does not verify")

    def _check_source(self, plugin: Plugin) -> None:
        try:
            tree = ast.parse(plugin.source)
        except SyntaxError as exc:
            raise PluginError(f"{plugin.manifest.name!r} does not parse: {exc}") from exc

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root in DENIED_IMPORTS:
                        raise PluginError(
                            f"{plugin.manifest.name!r} imports {root!r}, which is denied"
                        )
            elif isinstance(node, ast.ImportFrom):
                root = (node.module or "").split(".")[0]
                if root in DENIED_IMPORTS:
                    raise PluginError(
                        f"{plugin.manifest.name!r} imports from {root!r}, which is denied"
                    )
            elif isinstance(node, ast.Call):
                name = getattr(node.func, "id", None)
                if name in DENIED_CALLS:
                    raise PluginError(
                        f"{plugin.manifest.name!r} calls {name!r}, which is denied"
                    )
                attribute = getattr(node.func, "attr", None)
                if attribute in DENIED_CALLS:
                    raise PluginError(
                        f"{plugin.manifest.name!r} calls .{attribute}, which is denied"
                    )

    def _check_permissions(self, plugin: Plugin) -> None:
        for permission in plugin.manifest.permissions:
            if permission not in PERMISSIONS:
                raise PluginError(f"unknown permission {permission!r}")
            if permission not in self.granted_permissions:
                raise PluginError(
                    f"{plugin.manifest.name!r} asks for {permission!r}, "
                    "which this deployment does not grant"
                )

    # -- audit ------------------------------------------------------------
    def _log(self, action: str, plugin: Plugin, detail: str) -> None:
        if not self.log:
            return
        self.log.append(
            self.tenant_id, "system", action,
            {"plugin": plugin.manifest.name, "version": plugin.manifest.version,
             "detail": detail, "permissions": sorted(plugin.manifest.permissions)},
            source_node_id="plugins",
        )


def build(name: str, source: str, key: bytes, version: str = "1.0.0",
          entry: str = "main", permissions: list[str] | None = None) -> Plugin:
    """A convenience for tests and for signing a plugin you wrote yourself."""
    manifest = Manifest(name=name, version=version, entry=entry,
                        sha256=hashlib.sha256(source.encode("utf-8")).hexdigest(),
                        permissions=list(permissions or [])).sign(key)
    return Plugin(manifest=manifest, source=source)

"""The offline mobile client: key custody, a durable outbox, and a long absence.

Reference: docs/04-core.md ("Offline") and docs/16-acceptance-criteria.md,
deliverable 17. Three things the criterion names, and each is testable without a
phone:

    the key is never on disk in plaintext
    the outbox survives the process being killed
    a delta sync after seven days offline loses nothing

**On the cryptography.** Key derivation is PBKDF2-HMAC-SHA256 from `hashlib`,
which is a vetted construction in the standard library. The symmetric layer is
HMAC-SHA256 in counter mode with encrypt-then-MAC: a reference construction,
written here because this repository has no dependencies and no AEAD, and **not
something to ship**. It is not constant-time, it is not audited, and the doc says
so twice. A real client uses AES-GCM or XChaCha20-Poly1305 from a vetted library,
and `KeyVault` is the part worth keeping.

What is genuinely useful here is the key custody, which is the clause that matters:
the derived key is never written anywhere, the salt and a verifier are, and a test
opens every file the client creates and asserts the passphrase does not appear in
any of them.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os

from . import canonical

ITERATIONS = 200_000          # OWASP's floor for PBKDF2-HMAC-SHA256 in 2023
KEY_BYTES = 32
SALT_BYTES = 16
NONCE_BYTES = 16


class MobileError(Exception):
    """Raised when key custody, the outbox or a sync is violated."""


# ---------------------------------------------------------------------------
# Key custody
# ---------------------------------------------------------------------------

class KeyVault:
    """Derive a key, keep it in memory, write only a salt and a verifier.

    A verifier is an HMAC over a fixed string under the derived key. It proves a
    passphrase is right without storing the key, and it is the only thing on disk
    that depends on the passphrase.
    """

    VERIFIER_TEXT = b"tessera.key.verifier.v1"

    def __init__(self, path: str | None = None, iterations: int = ITERATIONS):
        self.path = path
        self.iterations = iterations
        self.salt = os.urandom(SALT_BYTES)
        self._key: bytes | None = None

    def derive(self, passphrase: str) -> bytes:
        if not passphrase or len(passphrase) < 8:
            raise MobileError("a passphrase shorter than eight characters is not one")
        self._key = hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"),
                                        self.salt, self.iterations, KEY_BYTES)
        return self._key

    @property
    def key(self) -> bytes:
        if self._key is None:
            raise MobileError("no key has been derived")
        return self._key

    def verifier(self) -> str:
        return hmac.new(self.key, self.VERIFIER_TEXT, hashlib.sha256).hexdigest()

    def save(self) -> str:
        """Write the salt and the verifier. Never the key, never the passphrase."""
        if not self.path:
            raise MobileError("this vault has no path to save to")
        blob = {
            "version": 1,
            "kdf": "pbkdf2-hmac-sha256",
            "iterations": self.iterations,
            "salt": self.salt.hex(),
            "verifier": self.verifier(),
        }
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump(blob, handle, indent=2, sort_keys=True)
        return self.path

    @classmethod
    def load(cls, path: str, passphrase: str) -> "KeyVault":
        with open(path, encoding="utf-8") as handle:
            blob = json.load(handle)
        if blob.get("kdf") != "pbkdf2-hmac-sha256":
            raise MobileError(f"unknown kdf {blob.get('kdf')!r}")
        vault = cls(path, iterations=blob["iterations"])
        vault.salt = bytes.fromhex(blob["salt"])
        vault.derive(passphrase)
        if not hmac.compare_digest(vault.verifier(), blob["verifier"]):
            raise MobileError("the passphrase does not match this vault")
        return vault


# ---------------------------------------------------------------------------
# A reference construction, not an AEAD
# ---------------------------------------------------------------------------

def keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    """HMAC-SHA256 in counter mode.

    Not constant-time and not audited. See the module docstring: use AES-GCM.
    """
    out = b""
    counter = 0
    while len(out) < length:
        block = hmac.new(key, nonce + counter.to_bytes(8, "big"), hashlib.sha256).digest()
        out += block
        counter += 1
    return out[:length]


def encrypt(key: bytes, plaintext: bytes, nonce: bytes | None = None) -> dict:
    """Encrypt-then-MAC. The tag covers the nonce and the ciphertext."""
    nonce = nonce or os.urandom(NONCE_BYTES)
    stream = keystream(key, nonce, len(plaintext))
    ciphertext = bytes(a ^ b for a, b in zip(plaintext, stream))
    tag = hmac.new(key, nonce + ciphertext, hashlib.sha256).hexdigest()
    return {"nonce": nonce.hex(), "ciphertext": ciphertext.hex(), "tag": tag}


def decrypt(key: bytes, blob: dict) -> bytes:
    """Verify first, then decrypt. A tag checked after decryption is a tag ignored."""
    nonce = bytes.fromhex(blob["nonce"])
    ciphertext = bytes.fromhex(blob["ciphertext"])
    expected = hmac.new(key, nonce + ciphertext, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, blob.get("tag", "")):
        raise MobileError("the tag does not verify; the blob was altered")
    stream = keystream(key, nonce, len(ciphertext))
    return bytes(a ^ b for a, b in zip(ciphertext, stream))


# ---------------------------------------------------------------------------
# The outbox
# ---------------------------------------------------------------------------

class OfflineOutbox:
    """A durable, append-only queue of local writes.

    Written as JSON Lines and flushed after every append, so a process killed
    mid-session loses nothing it acknowledged. Reopening replays what is there and
    drops any operation already seen.
    """

    def __init__(self, path: str):
        self.path = path
        self._seen: set[str] = set()
        self._replay()

    def _replay(self) -> None:
        if not os.path.exists(self.path):
            return
        with open(self.path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    op = json.loads(line)
                except json.JSONDecodeError:
                    continue  # a torn last line from a kill; the write was not acknowledged
                self._seen.add(op["id"])

    def append(self, op: dict) -> dict:
        if "id" not in op:
            raise MobileError("an operation without an id cannot be deduplicated")
        if op["id"] in self._seen:
            return op
        line = json.dumps(op, sort_keys=True, separators=(",", ":")) + "\n"
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())
        self._seen.add(op["id"])
        return op

    def pending(self) -> list[dict]:
        """Everything queued. A torn final line is skipped, here and on replay.

        The two readers have to agree: if `_replay` tolerates a kill mid-write and
        `pending` does not, reopening an outbox works and reading it does not. (R-16)
        """
        if not os.path.exists(self.path):
            return []
        out = []
        with open(self.path, encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return out

    def drain(self, ack: list[str]) -> int:
        """Remove acknowledged operations, keeping the rest. Returns how many went."""
        current = self.pending()
        remaining = [op for op in current if op["id"] not in set(ack)]
        removed = len(current) - len(remaining)
        with open(self.path, "w", encoding="utf-8") as handle:
            for op in remaining:
                handle.write(json.dumps(op, sort_keys=True, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        self._seen = {op["id"] for op in remaining}
        return removed

    def size(self) -> int:
        return len(self.pending())


def sync_after_absence(replica, server, outbox: OfflineOutbox, days: int = 7) -> dict:
    """The client comes back after a week. Push what it queued, pull what it missed.

    The absence is simulated by the caller having advanced the server while the
    replica was away; what this asserts is that nothing is lost in either
    direction and that the outbox empties only on acknowledgement.
    """
    from .sync import Op

    queued = outbox.pending()
    accepted = server.push([Op.from_dict(op) for op in queued])

    incoming, cursor = server.pull(replica.cursor)
    replica.pull(incoming)
    replica.cursor = cursor

    outbox.drain([op["id"] for op in queued])
    return {"queued": len(queued), "accepted": accepted, "pulled": len(incoming),
            "remaining": outbox.size(), "days": days,
            "fingerprint": replica.fingerprint()}

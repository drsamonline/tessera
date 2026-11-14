# 41 - Offline mobile

**Status: Draft**

Reference: [04-core.md](04-core.md#accessibility-globalisation-and-offline). Deliverable 17.

Three clauses in the criterion, and each one is testable without a phone.

## The key is never on disk

`KeyVault` derives a 32-byte key with PBKDF2-HMAC-SHA256 at 200,000 iterations, keeps it in memory, and writes
only a salt and a verifier. The verifier is an HMAC over a fixed string under the derived key: it proves a
passphrase is right without storing the key.

`test_the_passphrase_and_the_key_never_reach_the_disk` opens **every file the client creates** and asserts neither
the passphrase nor the key's hex appears in any of them. That is the clause, tested as written.

The salt is random per vault, so the same passphrase on two devices produces two different keys.

## The symmetric layer is a reference construction, not an AEAD

`encrypt`/`decrypt` are HMAC-SHA256 in counter mode with encrypt-then-MAC. They exist because this repository has no
dependencies and no AEAD, and **they are not something to ship**: not constant-time, not audited, not a substitute
for AES-GCM or XChaCha20-Poly1305 from a vetted library.

What they do demonstrate is the shape a real client needs, and the tests hold it to it:

| Test | What it proves |
|---|---|
| `test_a_changed_ciphertext_fails` | The tag covers the ciphertext |
| `test_a_changed_tag_fails` | Verification happens before decryption |
| `test_a_wrong_key_fails` | A wrong key is a refusal, not garbage |
| `test_a_nonce_is_never_reused` | The same plaintext twice is two different blobs |

The docstring says "not something to ship" twice, because a reader who skims will find the code first.

## The outbox survives the process being killed

`OfflineOutbox` is append-only JSON Lines, flushed and `fsync`ed after every append. `test_the_outbox_survives_the_process_being_killed`
appends two operations, drops the object without closing it, and reopens the file — both are there.

### R-16, found by its own test

`_replay()` tolerated a torn final line from a kill mid-write; `pending()` did not. So reopening an outbox worked
and reading it crashed — the two readers disagreed about what a half-written line means. Both skip it now, and the
test that found it writes a truncated JSON object into the file and asserts the outbox still reads.

A torn line is not an acknowledged write, so dropping it is correct rather than lenient.

## Seven days offline loses nothing

`sync_after_absence` pushes the queue, pulls what the client missed, and drains the outbox **only on
acknowledgement**.

The test that matters is not "the sync completed". It is
`test_the_result_matches_a_client_that_never_left`: one client writes three operations while offline, a second
client makes ten changes over the simulated week, and after reconnecting the absent client's fingerprint equals the
fingerprint of a client that stayed connected the whole time. Convergence is the claim; a completed sync is not.

## Deliverable 17, updated

| Criterion | State |
|---|---|
| The SQLCipher key is not in plaintext on disk | Met - PBKDF2 derivation, salt and verifier only, asserted by scanning every file |
| The outbox survives an app kill | Met - append, fsync, replay, torn-line tolerance |
| Delta sync completes after seven days offline without data loss | Met - asserted by fingerprint equality against a client that never left |
| A Flutter client, SQLCipher, and a real device | **Not met** |

Three of four criteria are met by a Python module. The fourth is the phone, and there is no phone.

## What is not here

- **No SQLCipher.** No Flutter, no Dart, no SQLite encryption extension.
- **No device keychain.** The key lives in memory for the life of the process; nothing stores it in Android Keystore
  or the iOS Keychain, which is where it belongs.
- **No biometric unlock.** No platform integration at all.
- **No background sync.** `sync_after_absence` is called by a foreground action.
- **Not constant-time.** The keystream XOR is byte-at-a-time. It does not need to be for confidentiality, and it is
  not a claim this module makes.

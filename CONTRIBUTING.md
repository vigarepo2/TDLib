# Contributing

Useful contributions include reproducible build fixes, target-specific smoke tests, dependency updates, and clearer setup instructions.

1. Open an issue for a new platform or a change to the published package layout. Include the intended consumer and its operating system, CPU architecture, and language binding.
2. Keep build inputs explicit in `config/build.json` and the relevant build recipe. A change that affects output must change the computed build fingerprint.
3. Add or update tests for compatibility checks, manifest validation, and publishing decisions when those behaviors change.
4. Run the **Validate** workflow on your branch or pull request. Native platform changes also need the relevant build job to pass before claiming support.
5. Update the README and linked guide when a user-facing command, tag, secret, or path changes.

The project uses one rolling release and rolling Docker tags. Preserve exact source commits and checksums in metadata so a consumer can tell which files it received.

Do not commit generated native libraries, entire upstream checkouts, Docker credentials, Telegram sessions, or application signing material. Small test fixtures are welcome when they exercise a meaningful failure case.

By contributing, you agree to license your contributions under this repository's [Boost Software License 1.0](LICENSE). Respect upstream licenses and retain notices when copying or redistributing source or binaries.

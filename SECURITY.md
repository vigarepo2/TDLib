# Security

Only the current rolling distribution is maintained here. Rebuilds record the exact upstream commit and dependency configuration in the release manifest. A passing build is not a guarantee that upstream software contains no vulnerabilities.

## Report a problem

For a vulnerability in this repository's build or publishing process, use [GitHub's private vulnerability reporting](https://github.com/vigarepo2/TDLib/security/advisories/new) when available. If private reporting is unavailable, open an issue asking for a private contact without publishing exploit details or sensitive information.

For a vulnerability in TDLib itself, follow [Telegram's security reporting instructions](https://core.telegram.org/techfaq#how-do-i-report-a-security-issue) and identify the exact TDLib commit. Please do not put Telegram sessions, phone numbers, login codes, API hashes, bot tokens, signing keys, or Docker Hub tokens in public issues or logs.

## Use the packages safely

- Obtain images from `vs69/tdlib` and archives from this repository's release page.
- Check archive SHA-256 hashes against the release manifest. For repeatable container deployments, record the image digest as well as its rolling tag.
- Keep account credentials and TDLib session databases in your application or a private volume. This build project needs no Telegram login credentials.
- Allow time to test updates in your application. TDLib's JSON schema and language bindings can change even when the upstream version string stays the same.

GitHub Actions uses repository secrets only in publishing jobs. Pull-request validation must never receive publishing credentials. Report any workflow change that appears to break that boundary.

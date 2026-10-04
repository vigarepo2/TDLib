# Maintaining the distribution

The repository has two jobs: publish traceable TDLib packages and let consumers reuse them safely. The application using TDLib remains responsible for its interface, credentials, session storage, and Telegram behavior.

## Build inputs and update detection

`config/build.json` records the upstream source, image destination, and platform toolchains. Build recipes live in `docker/` and `scripts/`; GitHub Actions connects those recipes into the publishing workflow.

The daily check resolves the current commit of the configured official upstream ref, currently `tdlib/td`'s `master`. The source version comes from upstream's `CMakeLists.txt`. A version string can remain unchanged across many commits, so the full commit is required when deciding whether a build is new.

The build fingerprint also accounts for the distribution's build inputs. A relevant packaging change therefore triggers a rebuild even when TDLib has not changed. An upstream network failure or an invalid manifest must be reported as a failure, not silently described as “no update.”

The scheduled check is not a general vulnerability scanner and does not automatically approve every new dependency release. Versioned toolchains in `config/build.json` remain deliberate inputs. Review updates to the Android NDK, OpenSSL, Emscripten, vcpkg, base images, and supported OS versions before changing them. When rebuilding to refresh inputs that the change detector does not track, use the manual force option.

## Publication model

The public Docker image is `vs69/tdlib`. Its rolling tags are:

```text
latest       debian       alpine
dev          debian-dev   alpine-dev
android      packages
```

`latest` and `debian` select the same Linux runtime variant. `dev` and `debian-dev` select the same Debian development variant. The Linux tags contain amd64 and arm64 images. The Android and packages tags carry files for extraction; the platform of a data-container manifest does not change the CPU architectures included in those files.

No per-version Docker tags are published. Exact upstream versions, commits, dependency inputs, checksums, and image digests belong in metadata. Consumers that need a fixed build should save the manifest and resolved digest with their application build. Do not assume an old digest will be retained indefinitely by a registry after its tags move.

GitHub has one rolling release with the tag `latest`. Its downloadable assets are:

| Asset | Contents |
| --- | --- |
| `manifest.json` | Upstream identity, build fingerprint, image digests, and package metadata |
| `SHA256SUMS` | Archive checksums |
| `tdlib-android.tar.gz` | Android native libraries, headers, Java source, and manifest |
| `tdlib-android.aar` | Android library archive for supported Android consumers |
| `tdlib-windows-x64.tar.gz` | Windows x64 native package |
| `tdlib-apple.tar.gz` | Apple libraries and XCFramework |
| `tdlib-web.tar.gz` | Browser package and WebAssembly assets |

The release title states the version read from official TDLib. If the selected source commit matches an upstream tag, release notes identify that tag. Otherwise the rolling GitHub release is marked as a prerelease and described as an upstream development snapshot. This identifies source provenance; it must not imply that this distribution is an official Telegram product.

Publishing several Docker tags and GitHub assets is not a single atomic registry transaction. A failure partway through publication can leave destinations temporarily out of step. Keep failed runs, inspect the release manifest and image labels, and rerun the corrected publishing workflow. Consumers must validate the package they actually receive rather than trusting `latest` to mean a specific engine.

## Build checks and their limits

Every target must use the selected source commit and retain its license notices. Package manifests record file hashes so consumers can detect corruption or mismatched files.

- Linux checks load `libtdjson` and execute synchronous JSON calls inside the resulting image; the final image's dependency resolution is part of the check.
- Android packaging checks the expected ABI set, ELF properties, exported interfaces, schema, Java binding, and required files. Native libraries must retain 16 KB page alignment.
- Windows and macOS checks exercise the native JSON library on the build runner.
- Browser checks load the generated WebAssembly and call the JSON interface.
- iOS packaging checks do not replace an application integration test on a simulator and a physical device.

No build needs a Telegram account. A smoke test proves that a library loads and answers selected local calls; it does not prove every Telegram feature or device configuration works. Before claiming a new target is supported, link to its successful native build and relevant integration checks.

## Scheduled run cleanup

The publishing workflow emits a marker when a scheduled check successfully determines that the source and build inputs are unchanged. After that run completes, **Remove unchanged scheduled checks** verifies the marker and the triggering run before deleting that run.

Deletion is restricted to successful scheduled checks that did not build or publish. Manual runs, successful builds, failed runs, and runs with missing or invalid evidence remain. The cleanup workflow also prunes older successful executions of itself while retaining its newest execution. This keeps routine history small without hiding build failures.

A no-change check can remain visible while it runs and while cleanup is queued. GitHub owns the scheduling and deletion APIs, so immediate removal is not guaranteed. Cleanup requires `actions: write`; publication requires `contents: write`. Keep each permission scoped to the workflow or job that needs it.

The daily schedule can be delayed by GitHub. Public repositories can also have scheduled workflows disabled after a long period of inactivity. Check the Actions page periodically; re-enable the schedule if GitHub disables it.

## Secrets and documentation

| Setting | Where | Purpose |
| --- | --- | --- |
| `DOCKER_PASSWORD` | Repository secret | Docker Hub account password for image uploads and overview updates |
| `DOCKER_USER` | Repository secret | Publishing account: `vs69` |

Do not add Telegram API IDs/hashes, phone numbers, bot tokens, login sessions, Android signing keys, or Docker passwords to this repository. They are not needed to compile TDLib.

The root README is the Docker Hub overview source. Use absolute links in it so they work on both sites. The publishing workflow syncs the overview after publication. **Validate** also syncs it after successful validation on a `main` push or manual run, so documentation changes do not require a native rebuild. Pull-request runs do not receive publishing credentials. A synchronization failure is visible in its job and can occur after image pushes succeed; inspect both destinations before describing publication as complete.

The overview synchronization job is separate from package publication. If Docker Hub rejects the metadata request, published images remain usable. Check the account login and repository ownership, or paste the README into Docker Hub manually.

## Repository About panel

The repository's About panel should use:

- **Description:** `Prebuilt TDLib for Linux, Android, Windows, Apple and the web. Daily upstream checks, reusable Docker images and verified platform packages.`
- **Website:** `https://hub.docker.com/r/vs69/tdlib`

An account with repository-administration access can set these using the gear beside **About** on the repository home page. With an appropriately authorized GitHub CLI session, the equivalent command is:

```sh
gh repo edit vigarepo2/TDLib \
  --description 'Prebuilt TDLib for Linux, Android, Windows, Apple and the web. Daily upstream checks, reusable Docker images and verified platform packages.' \
  --homepage 'https://hub.docker.com/r/vs69/tdlib'
```

Code-write access alone may not include permission to update repository settings.

## Consumer compatibility

Rolling images are convenient distribution points. Applications should still state which native engine and binding they expect.

TelePlay compares the Android manifest with its expected upstream commit, OpenSSL and NDK versions, Android API, ABI list, schema, wrapper, and file hashes. An unavailable or incompatible image can fall back to the app's existing trusted native bundle or pinned source build. A package that claims compatibility but fails integrity checks is an error rather than a reason to accept unverified files.

Changing `latest` alone is not an instruction to upgrade an application's binding. Coordinate an engine upgrade with application compilation, tests, and the relevant runtime checks. The same rule applies to external language adapters.

## Routine changes

1. Make the smallest relevant recipe or configuration update.
2. Run **Validate** and the applicable local script checks.
3. Run **Build and publish TDLib** after the change reaches the publishing branch; use force only when the recorded inputs otherwise remain unchanged.
4. Inspect every target result and the published manifest. Test downstream consumers against the intended engine.
5. Keep failure logs and update documentation when supported versions, package layouts, or setup requirements change.

The user-facing setup process is in the [quick start](QUICKSTART.md). Target-specific extraction and usage are in the [platform guide](platforms.md).

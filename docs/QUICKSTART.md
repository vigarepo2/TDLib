# Publish once, reuse in your apps

This guide sets up [vigarepo2/TDLib](https://github.com/vigarepo2/TDLib) to publish to [vs69/tdlib on Docker Hub](https://hub.docker.com/r/vs69/tdlib). GitHub runs the builds for you. You do not need to install Docker on your phone or keep a computer running.

The first publication compiles the engine for several platforms. It is the expensive build. Later app builds can download matching prebuilt libraries instead of compiling TDLib again.

## 1. Create the Docker Hub repository

1. Sign into [Docker Hub](https://hub.docker.com/) as **vs69**.
2. Open **Repositories**, then **Create repository**.
3. Use the name **tdlib** and choose **Public**.
4. Create it. Its address will be **https://hub.docker.com/r/vs69/tdlib**.

The repository name is lowercase. An image address such as `vs69/tdlib:android` is what build tools pull; the `hub.docker.com/r/...` address is the page people open in a browser.

## 2. Prepare your Docker Hub login

Use the Docker Hub username **vs69** and its account password. The workflow verifies login before compiling libraries.

Docker Hub requires an access token for command-line login when two-factor authentication is enabled. An ordinary account password works only when your account allows password-based Docker login.

## 3. Save the two values in GitHub

Open **[TDLib → Settings → Secrets and variables → Actions](https://github.com/vigarepo2/TDLib/settings/secrets/actions)**. Choose **New repository secret** for each value:

| Secret name | Value |
| --- | --- |
| `DOCKER_USER` | `vs69` |
| `DOCKER_PASSWORD` | Your Docker Hub account password |

Save both as repository secrets. Never paste the password into a README, issue, chat, source file, or workflow file. Public image downloads need no password.

On Android, open GitHub in your browser and enable **Desktop site** if the mobile app does not show repository settings.

## 4. Run the publishing workflow

1. Open **[Actions → Build and publish TDLib](https://github.com/vigarepo2/TDLib/actions/workflows/build-and-publish.yml)**.
2. Choose **Run workflow**.
3. Keep the branch on **main**.
4. Leave **Force rebuild** off for the first run. With no published package, the workflow builds automatically.
5. Press **Run workflow** and open the new run to watch its jobs.

The workflow selects an exact commit from official TDLib, builds the target packages, runs checks, and publishes rolling images and a GitHub release. The README is then synchronized to Docker Hub.

A first engine build can take a long time. Linux, Android, Windows, Apple, and browser targets each have native toolchains. A new upstream engine update also needs a new compilation. The time saving happens when your applications reuse the resulting libraries.

The `android` image becomes available when **Package Android SDK** finishes successfully, so TelePlay does not need to wait for Windows, Apple, browser, or Linux builds. The complete image set and GitHub release require the later publishing job to succeed. A green **Validate** run alone does not mean images were published.

## Which workflow does what?

| Workflow | Plain-language purpose | When to run it |
| --- | --- | --- |
| **Build and publish TDLib** | Makes and uploads the reusable engine packages | Once after setup; then automatically each day when an update is found |
| **Validate** | Checks scripts, configuration, and build definitions; on `main`, also refreshes the Docker Hub overview when configured | Automatically on pushes and pull requests; run manually to retry documentation sync without compiling TDLib |
| **Remove unchanged scheduled checks** | Removes completed daily checks that found no new work | Automatically; no normal manual step |

The daily check is scheduled for **04:23 UTC**. GitHub may delay scheduled runs. On a public repository, GitHub can disable schedules after prolonged repository inactivity; if that happens, re-enable the workflow from its Actions page.

## 5. Confirm publication

After the publishing run succeeds:

1. Open the [Docker Hub tags page](https://hub.docker.com/r/vs69/tdlib/tags). The rolling tags should appear there.
2. Open the [latest GitHub release](https://github.com/vigarepo2/TDLib/releases/tag/latest). It should contain `manifest.json`, `SHA256SUMS`, and the platform downloads.
3. Check the release's upstream version and commit. These identify the engine inside the packages.

If you have Docker on a computer, this small check loads the Linux library without logging into Telegram:

```sh
docker run --rm vs69/tdlib:latest
```

The output includes the version and a text-processing result. It then exits normally.

## 6. Build TelePlay

Once **Package Android SDK** publishes a compatible `vs69/tdlib:android` image, run your usual signed or unsigned build in the **TelePlay** repository. You can do this even while unrelated platform builds are running or need repair. TDLib publication does not itself produce a TelePlay APK.

TelePlay checks the public Android package against the engine it expects. A match lets it reuse those libraries. A different upstream version or binding is not silently substituted: the APK workflow stops early and points to this repository's build-and-publish workflow. TelePlay's APK workflows do not compile TDLib or use an old native release.

If you change only TelePlay screens or app logic, the native engine can normally be reused. If you deliberately update TelePlay's engine or native toolchain, both projects must agree on those inputs before this fast path applies.

## Common problems

| What you see | What to check |
| --- | --- |
| `DOCKER_PASSWORD` is missing | Add a repository **secret** with exactly that name in the TDLib repository |
| Docker push is denied | Check that `DOCKER_USER` is `vs69`, `DOCKER_PASSWORD` permits Docker login, and the public `tdlib` repository exists under that account |
| Images uploaded, but the overview update failed | Check the Docker Hub login, repository ownership and publishing log, or paste the README into Docker Hub manually. Already-published images remain available |
| `manifest unknown` or image not found | The first publishing run may not have completed, or you may have used the wrong tag |
| TelePlay reports an unavailable or incompatible engine | Publish `vs69/tdlib:android` and ensure its source and toolchain match TelePlay's pins. Updated APK workflows stop early instead of compiling native code |
| A scheduled run disappeared | It finished successfully and found no changes; the cleanup workflow removed only that eligible check |
| A build failed after an upstream update | Keep the failed run for diagnosis; update the affected build recipe and rerun the workflow after fixing it |
| Docker Hub reports a pull limit | Wait for the limit window or configure authenticated pulls where needed; public access is still subject to Docker Hub limits |

If only Docker Hub documentation failed, correct the account login or repository ownership and rerun the failed job, or run **Validate** on `main`. That retries the overview update without rebuilding the engine.

To rebuild with unchanged inputs, run **Build and publish TDLib** with **Force rebuild** selected. Do not use that option for every app update; its purpose is to rebuild the engine when needed, such as after a packaging fix or a dependency refresh.

For package extraction and language integration, continue with the [platform guide](platforms.md). For the update and publishing design, see [maintenance](MAINTAINERS.md).

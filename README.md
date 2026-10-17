# AfricanCreativity

A working, tenant-isolated creative workspace for lyrics, recordings, short instrumental music, audio arrangement and music-video production. Python 3.11+ and SQLite provide persistent accounts, media records, projects, credits and a durable single-worker queue. Vanilla JavaScript provides the responsive GUI. This is an original platform, not an integration with or replica of Suno/Sondo's proprietary models.

## Run locally

Install Python 3.11+ and FFmpeg (including ffprobe and libx264). On Debian:

```bash
sudo apt-get install python3 ffmpeg fonts-dejavu-core
python3 server.py --create-super-admin platformadmin
python3 server.py
```

Open http://127.0.0.1:8096. There is no default password. Sign in as your new platform administrator, provision a tenant and privately share its single-use administrator invitation. Accept the invitation from the sign-in page using a separate username; sign in as that tenant account to create music. Platform administrators manage tenant provisioning and quotas without general creative-file access.

The development environment has a separately provisioned key in the ignored `.env.local` file. It is never included in Git or container images. The app loads only allowlisted environment settings. On another machine, use protected server configuration; do not put secrets in commands, URLs, browser code or Git. Model access and provider balance are separate from the app's internal credit balance.

## Connected workflows

- **Music Lab:** Simple/Custom descriptions, editable original lyrics, OpenAI lyrics assistance and prompt enhancement, reusable style personas, model picker, temperature and prompt guidance, short instrumental MusicGen adapter, non-AI piano-note synth, and AI speech narration with a disclosed synthetic voice.
- **Library:** saved projects and media versions, title/prompt/lyrics search, type/liked/trash filters, upload, microphone recording, audio/video playback, byte-range seeking, WAV/MP3 conversion, ZIP download, reuse prompt, workspace assignment, trash/restore and permanent media removal.
- **Audio editor:** real crop, independent pitch/speed, reverse, volume, fade in/out and a selected compressor/EQ/echo-based reverb/delay/distortion/gate effect. Outputs are new assets; original audio remains.
- **Studio:** persisted audio clips, trim/start/duration/volume/pan/mute, drag ordering, browser playback/pause/stop, loop, metronome, tempo/meter settings, note grid/inspector, velocity, musical typing, on-screen keys, Web MIDI input/recording where supported, MIDI import/export, oscillator selection, WAV note rendering, mixed WAV and range/individual-track renders. Render notes to WAV and add that asset to mix it with other audio; MIDI export is independent of audio export.
- **Video Lab:** choose audio, upload permitted images/clips, describe a story, choose 16:9/9:16/1:1, AI text-based storyline/scene planning, edit prompts/captions/durations, drag or button reorder, save a storyboard, generate scene images, optionally generate Sora motion clips, assign uploaded/generated resources, approve a story, assemble MP4, preview and download. Scene resources persist; no timeline is reset at logout. Existing renders are immutable; new aspect ratios create new renders.
- **Organization/sharing:** personal or collaborative workspaces with viewer/editor members, playlists, album copies, public/link-only/private projects, public Explore and permission-controlled remix copies. Publishing a collection does not expose private member songs.
- **Administration:** tenants, plans as labels, credits, storage quotas, suspension/reactivation, one-time role-bound invitations, team disable/enable, password change, audit, job states and failed-job refunds. No card charging or paid-plan checkout is represented as working.

See [full requested feature coverage](docs/FEATURE_COVERAGE.md) for precise limits. Many proprietary generation and advanced DAW features remain unimplemented; they are explicitly identified rather than represented by dead buttons or fake audio.

## Engines and dependencies

### OpenAI

The server uses the Responses API for lyrics, prompts and JSON storyboards (`store:false`), Audio Speech API for narration, and Images API for scene artwork. Defaults: `gpt-4.1-mini`, `gpt-4o-mini-tts`, `gpt-image-1`. Set `OPENAI_MODEL`, `OPENAI_SPEECH_MODEL` or `OPENAI_IMAGE_MODEL` in protected configuration to select an available compatible model. Credentials never reach the browser. Text/storyboard requests contain user-entered prompts/lyrics. Narration sends its input text. Image generation currently uses text, not uploaded character photos. The app does not claim zero provider retention or rights ownership in outputs.

Optional Sora text-to-video is enabled only with `VIDEO_AI_ENABLED=1`; it requests four-second 720p `sora-2` clips, polls the official API, records provider job IDs, and downloads completed MP4s to the tenant. Account access, provider restrictions and billing apply. Input-photo likeness conditioning and lip-sync are not implemented. No live Sora/image-generation test has been performed. Failed or timed-out jobs refund **internal** credits; provider charges are not automatically refunded. Check recorded provider IDs before retrying an interrupted generation.

### Optional instrumental MusicGen / stems

These are disabled by default. Install `requirements-models.txt` in an isolated Python environment and run the application with that interpreter, with appropriate memory/GPU capacity and model download access. Then set `MUSICGEN_ENABLED=1` **and** `MUSICGEN_LICENSE_ACCEPTED=1` after reviewing the selected checkpoint's license. The `facebook/musicgen-small` checkpoint has noncommercial weight-license restrictions; this is not a grant to run a commercial music service. It generates short instrumentals, not sung lyrics, reference-audio covers, cloned voices or custom models. Duration is limited to 25 seconds.

`DEMUCS_ENABLED=1` enables the installed Demucs htdemucs two-stem vocal/accompaniment pipeline. The initial model download can be large. Advanced 12-part/custom-instrument separation is not implemented. Neither optional GPU/model pipeline was downloaded or live-tested here. Keep `HF_HOME` in a persistent, writable model-cache directory; model caches are not included in tenant media quotas.

## Deployment on your Debian server

After the source is pushed, run the Ansible playbook with a pinned reviewed revision:

```bash
ansible-playbook -i localhost, -c local ansible/deploy.yml \
  -e creativity_revision=main
```

The playbook installs FFmpeg, runs integration tests before changing the installation, backs up the stopped app, installs `/opt/africancreativity`, bootstraps `platformadmin` without logging its password, configures an unprivileged systemd service, starts the worker and verifies `/health`. Existing platform passwords are preserved. Supply `creativity_ai_env_file` only when the Ansible control machine holds the intended protected environment file; it is copied to `/etc/africancreativity/ai.env` with mode 0600. Secrets are not fetched from GitHub. Optional models require a separately configured Python environment; the default playbook does not install or license them.

The service listens on **127.0.0.1:8096**. Choose a domain and configure an HTTPS reverse proxy using [the example](deploy/nginx.conf.example). `creativity_secure_cookie` defaults to true, so browser sign-in requires HTTPS. This playbook does not change existing medical/panel sites, DNS, certificates or firewalls. For temporary loopback HTTP evaluation set `-e creativity_secure_cookie=false`; do not expose that setup publicly.

Docker is also supported: `docker compose up -d --build`, then `docker compose exec creativity python server.py --create-super-admin platformadmin`. The named data volume persists across image builds. Run behind HTTPS; adjust COOKIE_SECURE only for local HTTP evaluation.

## Security and recovery

All creative APIs derive tenant identity from authenticated sessions. Project owner/workspace permissions are checked before reads, writes and source-media jobs. Viewer access does not permit edits. Cross-tenant source references are rejected. Public assets require explicit project publication; link-only assets require a random capability token. Returning a project to private clears its share token; suspension revokes tenant sessions and public access. An authorized remix copy is independent of later source revocation.

Passwords use scrypt; session/invitation tokens are stored hashed. Mutations require a session CSRF token, sessions expire after eight hours, invitations after seven days. Login attempts are bounded per network address. Review proxy-aware rate limits for an Internet deployment; the loopback proxy address is otherwise shared. No MFA/SSO, malware scanning, automated rights verification, age assurance, legal compliance assessment or enterprise-scale hosting is claimed.

Limits: 20 MB uploads, 600-second accepted source-media duration, 16-megapixel images, 120-second video/selected mix ranges (full mixes capped at 180 seconds), 12 mix clips/scenes, 256 piano notes, 500 listed projects, 60 project asset sources in the studio dock, 200 jobs/tenant/day and 10 pending jobs/tenant. Plans label tenants; quotas and internal credits enforce actual use. HTTP media processing is resource-intensive: apply reverse-proxy request/concurrency limits and keep FFmpeg patched. This development HTTP server is a single-instance evaluation foundation, not a hardened multi-region service.

The single background worker claims durable jobs transactionally. Failed jobs refund once. On restart, interrupted jobs fail/refund instead of silently replaying potentially charged provider calls; queued jobs continue. Do not run multiple application instances against one SQLite database. Tenant suspension cancels queued jobs; running jobs must pass authorization again before results are saved. Provider execution itself may continue until it returns.

Backups are under `/var/backups/africancreativity` (root-only directory). Stop the service for a file-level backup including the database, WAL, media and source, or use SQLite's online backup API and a coordinated media snapshot. Test restoration in an isolated environment before depending on it. Protect and rotate configuration/keys separately. Permanent media removal retains accounting/job/audit tombstones and may not erase prior backups, exported files, text job results or authorized remix copies; define retention with the operator.

## Verification

```bash
python -m unittest discover -s tests -v
node --check static/app.js
node --check static/studio.js
cd tests/browser && npm ci && npm test
ansible-playbook -i localhost, --syntax-check ansible/deploy.yml
```

Backend tests cover real WAV/MP4 rendering, permissions, invitations, publication, credits, quotas and version checks. DOM tests cover navigation, provisioning, creation, storyboard persistence and MIDI round-trip. Browser media permissions, Web MIDI devices, speaker playback, live image/video generation and optional model quality still need device/live validation. Automated DOM tests are not visual browser QA.

Official integration references: [Responses](https://developers.openai.com/api/docs/guides/text), [Speech](https://developers.openai.com/api/docs/guides/text-to-speech), [Images](https://developers.openai.com/api/docs/guides/image-generation), [Sora](https://developers.openai.com/api/docs/guides/video-generation), [MusicGen](https://huggingface.co/docs/transformers/model_doc/musicgen), [checkpoint/model license](https://huggingface.co/facebook/musicgen-small).

© 2026 AfricanCreativity. Original implementation; no Suno/Sondo affiliation. Third-party software and model weights retain their licenses. No new open-source license is granted by this notice.

## Build and install optional add-ons

`ansible/install-addons.yml` imports the base deployment, installs selected requirements into a revision-specific virtual environment, checks dependencies with pip, verifies local media processing, optionally downloads/tests selected models as the unprivileged service user, then activates a systemd override. A failed activation restores the previous override. Existing tenant databases/media are preserved by the base deployment backup flow. Python 3.10–3.12 and at least 8 GB RAM are required for the pinned optional CPU model profile. Runtime model installation has not been executed in this development workspace; the installer verifies it on the target before activation.

Default modules are `audio-tools` and `note-tools`: audio measurements with an explicitly approximate tempo estimate, loudness mastering, section sequencing, note quantization, major-chord expansion and ascending arpeggiation. They are real bundled source, copied during deployment; Ansible does not invent missing application code. Access them in Library audio actions and Studio. Super-admin Engine status lists bundled add-ons.

From a repository checkout on the server:

```bash
ansible-playbook -i localhost, -c local ansible/install-addons.yml
```

Select optional modules with a variables file, for example `-e @/root/creativity-addons.yml`:

```yaml
creativity_addons:
  - audio-tools
  - note-tools
  - stems
creativity_verify_models: true
```

`musicgen` additionally requires `creativity_accept_musicgen_license: true` after the operator reviews its noncommercial model-weight license. Do not set this for commercial deployment without appropriate rights. `motion-video` additionally requires an existing protected `/etc/africancreativity/ai.env` containing the intended OpenAI key; it enables the adapter, not a guarantee of API entitlement. Generated provider video is not requested by the installer. The local key is not copied to the server by Git.

CPU Torch/TorchAudio are installed as a matching pinned pair from the official PyTorch wheel index. Optional dependency/model downloads require outbound access and disk capacity. Model verification can take several minutes on CPU. No voice cloning, sung-vocal engine or custom-model trainer is installed or represented as working. The detailed feature inventory remains the record of outstanding work.

### Replace the hosting placeholder with the application

For the existing `africancreativity.io` HTTPS vhost, run:

```bash
git -C /root/africancreativity pull --ff-only origin main && ansible-playbook -i localhost, -c local /root/africancreativity/ansible/fix-public-site.yml
```

This requires the existing domain-specific Nginx configuration and working TLS
certificate. It checks the backend health, backs up and replaces its simple root
`location /` block with a proxy to port 8096, runs `nginx -t`, reloads, and verifies
the public page contains the Africa Creativity brand. It restores the backup on
activation failure. It leaves DNS, certificates, account data and other domain
files untouched. Configurations with nested root-location blocks require manual
review; the playbook fails if it cannot find a matching proxy afterward.

### Self-service accounts and authentication update

Visitors can create a private workspace directly on the sign-in page, without
an invitation. Registration atomically stores the tenant, hashed password,
tenant-admin account, initial workspace and authenticated session in SQLite.
New public workspaces have 100 MB storage and zero generation credits; platform
administrators allocate credits. Public input cannot choose its role, tenant,
quotas or initial credits. Existing invitation flows remain available and now
sign the new member in automatically. Registration is limited to five attempts
per client IP per hour. No email verification or password-reset email is provided.

Passwords preserve their spaces. Sign-in accepts the original username or an
unambiguous case-insensitive match. Failed login throttling is scoped to client
IP and username so unrelated accounts do not share one localhost lockout. Only
loopback requests from the local Nginx proxy may supply X-Real-IP; keep the
backend bound to loopback and the proxy configured to overwrite this header.
Existing accounts and passwords are retained; rerunning bootstrap does not reset
the platform administrator password.

Apply to the existing installation without another bootstrap password prompt:

```bash
git -C /root/africancreativity pull --ff-only origin main && ansible-playbook -i localhost, -c local /root/africancreativity/ansible/deploy-auth-fixes.yml
```

This update uses existing tables and does not replace or reset the database,
AI configuration, isolated add-on runtime, media files or Nginx configuration.

### Complete registration and populated Explore

The account screen now provides visible Sign in / Create account controls.
Registration requires full name, email, password and password confirmation;
username, phone, country and workspace name are optional. A username is generated
when omitted. Invalid client-side username pattern restrictions are removed;
server validation remains authoritative. Users can sign in using email or their
username. Existing username-only accounts continue to work.

An additive `account_profiles` SQLite table stores a unique normalized email,
phone, country and timestamps linked to the existing user. Passwords remain
scrypt hashes in `users`. Profile read/update is authenticated, self-scoped and
CSRF-protected. Account & team contains a working Save profile action. Email
verification, email password reset and OAuth are not configured or represented
as working services. No automatic administrator privileges or paid AI credits
are granted to public registrations.

Deployment also runs `deploy/seed_public_releases.py`, which creates three
original local-synth instrumentals with real WAV assets and public projects in
a dedicated sample tenant. Cards are labeled Original sample; no fabricated
artists, plays or likes are added. Running the seed again does not duplicate
releases, and intentionally removed/hidden samples stay removed. Creator-owned
private releases are never made public. Explore includes search and type filters.

Use the existing one-command `ansible/deploy-auth-fixes.yml` deployment. It takes
a protected SQLite online backup, installs the account/frontend update, restarts
the service (which adds the new table), seeds samples as the unprivileged service
user, and verifies signup markup and public releases. Keep the backup private:
it contains account hashes and creator records. It does not reset credentials,
media, quotas, Nginx, AI keys or add-on runtime configuration.

### Android download

The public `/mobile` page is linked from sign-in and the signed-in sidebar.
`/downloads/africa-creativity.apk` is the signed Android 8+ online client (v1.0.0),
with an adjacent SHA-256 checksum. It uses https://africancreativity.io and the
same database-backed account, profile, project and release APIs. It supports
Android's file picker and asks for runtime microphone permission when recording
is requested from the trusted site. Other origins cannot obtain native capture
permissions. Cleartext, mixed content, file/content URL access, third-party
cookies and Android app backups are disabled; no native JavaScript bridge or
embedded credentials are provided.

This is a direct APK distribution, not a Google Play or iOS App Store release.
Device microphone/file-picker testing remains required. Browser-generated blob
exports and hardware Web MIDI are not implemented natively; use the system
browser for those operations. No offline generation or push service is claimed.

Build using JDK 17 and Android SDK platform 35 / build-tools 35.0.0:

```bash
ANDROID_HOME=/path/to/android-sdk bash scripts/build-mobile.sh
```

The private release key is outside Git in
`$HOME/.local/share/africancreativity-signing` or `CREATIVITY_SIGNING_DIR`.
Back it up privately. Every update must reuse this signing key and increment
manifest versionCode. The initial key backup is retained separately from the
public source/package. Never publish the signing archive or password.
The account deployment playbook also installs and checks the APK.

## Super-admin control center and tenant access

Sign in with the existing platform administrator account. The platform dashboard
summarizes tenants, members, workspaces, projects, storage, credits and queue states.
Its sidebar contains Dashboard, Tenants & quotas, Members & roles, Invitations,
Job queue, Usage & credits, Audit log, Engine status and Security.

- Tenants: search/filter, provision an organization, generate its administrator invitation,
  set plans and storage, adjust credits, suspend/reactivate, open members or ledger.
- Members: filter by organization, promote/demote tenant roles, disable/reactivate.
  Changes revoke sessions. Platform identities and the last active tenant admin are protected.
- Invitations: issue seven-day administrator tokens, review pending/expired/used records,
  revoke pending tokens. Only digests are stored; tokens are shown once.
- Queue: inspect processing metadata and cancel queued work with exactly-once refunds.
  Running jobs cannot be cancelled using this control.
- Ledger and audit: search/filter recent persisted credit movements and activity.
- Engines: inspect server-configured availability. Security: change the signed-in
  administrator's own password, retaining the current session and revoking others.

Tenant administrators retain their own Account & team, invitations, member role/access
controls, ledger and activity. Workspace owners can share projects with editors/viewers.
Tenant identifiers come from authenticated sessions; platform roles cannot be granted
through registration or team controls. The platform control center does not provide
private project content or impersonation. Operational lists show at most 1,000 recent
members/invitations/ledger/audit records or 500 jobs and disclose these limits in the GUI.
Plans/credits are internal allocations; payments, MFA, email delivery and provider
credential setup are not added by this update.

Deploy an existing installation (online SQLite snapshot and application file backups
are taken by the imported update playbook; startup adds the indexes without deleting data):

```bash
git -C /root/africancreativity pull --ff-only origin main && ansible-playbook -i localhost, -c local /root/africancreativity/ansible/deploy-admin.yml
```

Verify from the GUI using the existing platform login. The playbook verifies health,
the browser asset, and anonymous denial for each new administration API. Restore
application backup files and the protected SQLite snapshot for a rollback while
the app and worker are stopped; do not overwrite an active database.

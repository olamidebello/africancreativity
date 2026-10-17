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

## Automatically build additional creation engines

For an existing server installation:

```bash
git -C /root/africancreativity pull --ff-only origin main && ansible-playbook -i localhost, -c local /root/africancreativity/ansible/build-creation-engines.yml
```

The playbook updates backed-up application modules, renders and checks non-silent WAV
files under the service identity, enables selected engines in a dedicated systemd
override, restarts, and checks health. Failed activation restores the previous engine
selection. Existing optional AI runtimes and tenant databases are preserved. Sign in
again or reload to refresh capabilities; Music Lab lists the verified local engines.
Select a subset with `-e '{"creativity_creation_engines":["arpeggio","bassline"]}'`.

| Engine | Controls | Output |
|---|---|---|
| Arpeggio sequencer | Tempo, root note, pattern seed, duration | Procedural broken-chord WAV and saved score |
| Chord progression | Tempo, root note, duration | Procedural sustained-chord WAV and saved score |
| Bassline sequencer | Tempo, root note, duration | Procedural bass WAV and saved score |

These are original software algorithms, **not trained AI models**. Description text is
saved as project notes and is not interpreted by the local engines. Seed changes the
arpeggio pattern; the chord and bass engines use fixed progression patterns.
Composition jobs cost zero credits and use the normal tenant quota, queue and asset
permissions. WAVs are stored in Library and scores are retained in job results.

### Optional MusicGen Small and Medium

The existing `ansible/install-addons.yml` can now install/verify both checkpoints.
It requires explicit acceptance of the model license, sufficient RAM (8 GB for Small;
a conservative 16 GB CPU profile for Medium), and a real test generation before enabling
MusicGen. CPU rendering can be slow. This does not train a new foundation model.

```bash
ansible-playbook -i localhost, -c local /root/africancreativity/ansible/install-addons.yml -e '{"creativity_addons":["audio-tools","note-tools","musicgen"],"creativity_musicgen_models":["musicgen-small","musicgen-medium"],"creativity_accept_musicgen_license":true}'
```

Only use that opt-in command after reviewing applicable rights. Meta model cards:
https://huggingface.co/facebook/musicgen-small and
https://huggingface.co/facebook/musicgen-medium (weights: CC-BY-NC 4.0).
Optional model downloads/generation must be verified on the target hardware; local
unit tests do not claim to validate the heavyweight model installation.

### Promote a registered account from the server

Public and tenant APIs cannot grant super-admin. Root can promote exactly one existing,
active account by its registered email. The helper snapshots SQLite, changes the role,
revokes the account's sessions and writes a platform audit event. Tenant ownership
links and passwords remain intact; super-admin creative APIs are denied even if an
original tenant link remains. Use Invitations to appoint a replacement tenant admin
if the elevated account was the only tenant administrator.

```bash
ansible-playbook -i localhost, -c local /root/africancreativity/ansible/promote-admin.yml -e creativity_super_admin_email=dobcalldemo@gmail.com
```

Alternatively pass the same email extra variable to `build-creation-engines.yml` to
build engines and promote the account in one invocation. Sign in again after promotion.
No account is created if the email does not match; disabled accounts are rejected.

## YouTube import and export

Creators have a **YouTube** sidebar destination and **Publish to YouTube** actions on
MP4 assets. Each creator connects their own channel through Google OAuth; platform
administrators do not impersonate tenant publishers.

- Publish a rendered/uploaded MP4 with a user-controlled title (100 characters),
  description (5,000), visibility (private by default), audience choice and rights consent.
- Uploads run as zero-credit queued jobs with chunked YouTube resumable requests.
  Tenant authorization is checked before each chunk. A lost acknowledgement is marked
  **uncertain**, blocks duplicate uploads of the same asset/channel and requires review
  in YouTube Studio; the worker does not blindly replay external writes.
- History links to successful YouTube uploads. Provider errors are sanitized.
- Import a YouTube video link/ID as a saved title/link reference. No audiovisual
  downloading or ripping is implemented. Use the original file in Library for editing.
- Disconnect revokes access when Google is reachable, always deletes local tokens and
  imported references, and provides a Google permissions link for manual revocation.
  YouTube videos already published are never deleted by disconnecting.

Deploy the code and scheduled metadata expiry:

```bash
git -C /root/africancreativity pull --ff-only origin main && ansible-playbook -i localhost, -c local /root/africancreativity/ansible/deploy-youtube.yml
```

Direct publishing requires a real Google Cloud OAuth web client:
1. Enable **YouTube Data API v3** in your Google Cloud project.
2. Configure your OAuth consent screen, production privacy/support contacts and any
   required app verification. In testing mode, add intended Google accounts as test users.
3. Register exactly `https://africancreativity.io/api/youtube/callback` as a web redirect URI.
4. Copy `deploy/youtube.env.example` to a protected `/root/youtube.env` on the server,
   fill its client ID/secret, and keep it out of Git. Apply:
   `ansible-playbook -i localhost, -c local /root/africancreativity/ansible/deploy-youtube.yml -e creativity_youtube_env_file=/root/youtube.env`
5. As a tenant creator, open YouTube, accept the displayed terms/privacy notice and
   connect the intended channel. Approve upload and read permissions. Review a private
   test upload in YouTube Studio before using public publishing.

Client secrets are loaded from root-only `/etc/africancreativity/youtube.env`.
Refresh/access tokens are stored in per-user 0600 files inside protected application
data, never returned by APIs. Include these in the operator's secret-management and
backup policy. OAuth state is single-use, ten-minute, tied to the initiating live app
session, and uses PKCE; callback processing does not depend on a cross-site session cookie.
Disconnect, disabled accounts and local connection expiry remove local credentials.
A daily systemd timer expires reference metadata, finished history and associated
job API results after 30 days; connections expire locally after 30 days and can be
reconnected. Audit records contain internal event identifiers, not Google credentials.
Configure reverse-proxy logs to omit OAuth callback query strings.

Live Google consent, quota, channel permissions and uploads require operator credentials
and an actual authorized channel. Automated tests mock Google responses and validate
tenant boundaries, callback replay, session binding, exact upload bytes and duplicate guards;
they do not claim a live YouTube publish.

Official references:
https://developers.google.com/youtube/data/guides/using_resumable_upload_protocol
https://developers.google.com/identity/protocols/oauth2/web-server
https://developers.google.com/youtube/terms/developer-policies

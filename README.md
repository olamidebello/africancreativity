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

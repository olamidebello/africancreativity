# Self-hosted AI and additional creator workflows

The Self-hosted AI navigation item connects the browser to the existing
session-authenticated, CSRF-protected `/api/jobs` endpoint. The `open_engine`
job kind uses the existing jobs, projects, assets, audit and ledger tables.
No replacement database, public model server or browser-held API key is added.

## Install on an existing server

```bash
git -C /root/africancreativity pull --ff-only origin main
ansible-playbook -i localhost, -c local /root/africancreativity/ansible/build-recommended-features.yml
```

For only the new AI integration, use `ansible/install-open-engines.yml`.
Both require an initialized installation. The full entry point also applies the
existing account/admin update, verifies procedural composition engines, and
installs the separate configurable provider gateway. The open models use the
application job queue directly; they do not depend on that gateway.

Select engines with an extra variables file or:

```bash
ansible-playbook -i localhost, -c local ansible/install-open-engines.yml -e '{"open_engines_requested":["kokoro","whisper"]}'
```

The default requests all five. Engines outside the capacity profile are listed
and skipped. `-e open_engines_require_all=true` makes unsupported selections fail
at preflight. The profile uses 4 GB RAM for CPU narration/transcription, 12 GB
NVIDIA GPU memory plus 32 GB RAM for ACE-Step/Wan, and 16 GB GPU plus 48 GB RAM
for FLUX. Model offload still uses host memory. These are conservative selection
thresholds, not a guarantee of fit/performance on every GPU. The profile reads
the first GPU and does not combine GPU memory or install/update NVIDIA drivers.
Reserve 15 GiB free for CPU-only installation or 100 GiB for GPU engines.
Python 3.10–3.12 is supported by this dependency profile.

The installer downloads dependencies/checkpoints and generates real test output
under the unprivileged service identity before marking an engine ready. Package
consistency, media validity and non-silent audio are checked. Downloads/inference
may take a long time; failures stop activation. Real inference has not been run
in the development environment. Exact runtime compatibility and model quality
must pass the installer on the target. Core dependencies/source are pinned;
transitive dependencies and upstream model revisions are not fully locked.

## Connected features

| Engine/workflow | Implemented interface | Output and limits |
| --- | --- | --- |
| ACE-Step v1 3.5B | Prompt, optional original lyrics, duration, seed | 5–60 second WAV; sung lyrics or instrumental request |
| FLUX.1-schnell | Prompt and seed | 512 × 512 PNG |
| Wan2.1 T2V 1.3B Diffusers | Prompt, orientation and seed | 33-frame silent MP4 at 16 fps; 832 × 480 or portrait |
| Kokoro-82M | Narration text, five voice choices and speed | AI speech WAV; English voices; no voice cloning |
| faster-whisper Small | Select accessible Library audio/video | Saved transcript, detected language and SRT download in Jobs |
| Batch variations | Choose 1–3 variations | Separate durable jobs with successive seeds; partial failures report the submitted count |

Generated media appears as new Library assets. Artwork and motion clips can be
selected as resources in Music Video Lab; audio can be added to Studio. SRT files
are downloadable subtitles, not automatic burned-in captions. Whisper can
misrecognize lyrics, names and background audio; review text and timings.
A completed transcript is a private job result rather than a public media asset.
Existing Jobs supports progress refresh and queued-job cancellation. Running
inference is stopped after 30 minutes by the adapter; model loads are serialized
with a filesystem lock and process exit releases GPU memory between jobs.

These self-hosted jobs cost zero internal credits but retain the existing
200-jobs/day and 10-pending-jobs/tenant limits. Storage limits still apply.
Hardware, electricity and hosting are operator costs. A batch is sequential
submissions, not an atomic transaction: inspect Jobs before retrying a partial
batch. The existing source-media duration and upload limits remain applicable.
No private source filepath or executable can be supplied by a browser; source
IDs are checked against tenant/project access before queueing and execution.

The root-owned `open-engines.json` manifest in the installation directory contains
only runtime paths, cache paths and verification flags. It has no provider keys.
Each engine has an isolated interpreter; model subprocesses receive a small
allowlisted environment without OpenAI credentials. The existing app service,
provider keys and optional MusicGen runtime are not replaced. Manifest activation
failure restores the previous manifest. Application updates use existing file
and SQLite backups; automatic application-source rollback is not claimed by this
new installer. Back up model caches separately if expensive to reproduce.

## Scope and licenses

This implements generation adapters, transcription/subtitles and bounded batch
creation. It does not implement every feature of other platforms. Reference-song
covers/remixing, voice cloning, LoRA training, lip-sync, collaborative live DAW,
billing/royalties and distributor delivery remain separate work. The models do
not provide Suno engine identities or Suno service access.

Model/code terms remain applicable; free weights do not mean no license terms.
The selected ACE-Step v1, Wan2.1 and FLUX.1-schnell model cards list Apache 2.0;
Kokoro lists Apache-licensed weights. faster-whisper is MIT-licensed and uses
Whisper weights; preserve relevant notices and dependency licenses. No separate
paid model license is installed or purchased by this script. No ownership or
non-infringement guarantee for generated outputs is made.

Publisher references:
- https://huggingface.co/ACE-Step/ACE-Step-v1-3.5B
- https://github.com/ace-step/ACE-Step
- https://huggingface.co/Wan-AI/Wan2.1-T2V-1.3B-Diffusers
- https://huggingface.co/black-forest-labs/FLUX.1-schnell
- https://huggingface.co/hexgrad/Kokoro-82M
- https://github.com/SYSTRAN/faster-whisper

## Validation

The new tests exercise tenant denial, queue capacity, validation bounds, media
persistence, subtitle results, exactly-once refund and credential isolation.
Browser DOM tests cover unavailable models, batch seed variation, recording
selection and subtitle download visibility. Model calls are mocked in these
integration tests. Installer inference checks are the target-machine gate;
passing application tests does not verify downloaded-model compatibility or
production output quality.

## Repair and enable one engine at a time

```bash
git -C /root/africancreativity pull --ff-only origin main
ansible-playbook -i localhost, -c local /root/africancreativity/ansible/repair-enable-engines.yml
```

This entry point installs OS prerequisites, prepares each isolated environment,
updates packaging tools, installs model dependencies, downloads model files and
checks a real output. Whisper and Kokoro are attempted first. Each successful
engine is enabled immediately; the next engine's failure cannot discard it.
Previously verified engines not selected for repair are preserved.

The root-owned `open-engine-status.json` contains per-engine installing, ready,
blocked or failed status and the name of a failing installation stage. The GUI
shows these messages; use **Refresh engine status** to reload current capabilities
without signing out. Full dependency diagnostics stay in the server's Ansible
output. A failed repair retains that engine's last working manifest entry.

Disk is checked per engine (5 GiB for Whisper, 10 GiB for Kokoro, 60 GiB for each
GPU installation attempt). These replace the earlier aggregate disk preflight.
The installer continues after individual engine errors and prints a final report;
read it even if the play recap has no unrecovered failures. With
`open_engines_require_all=true`, a final assertion also flags partial outcomes.
No software installer can create missing physical GPU capacity. Hardware-blocked
engines remain unavailable unless a previously verified runtime was retained.

The repair also addresses the reported `typing-extensions` / missing `flit_core`
installation failure: packaging tools are upgraded from PyPI first, PyPI remains
the primary dependency index, and exact `+cpu` or `+cu128` Torch-family wheels
come from the additional PyTorch index. General Python build dependencies are
no longer limited to the PyTorch-only index. No system Python packages are
replaced; these changes apply to each isolated virtual environment.

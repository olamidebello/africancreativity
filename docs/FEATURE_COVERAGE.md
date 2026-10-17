# Requested feature coverage

This file accounts for every numbered item in both supplied inventories. “Implemented” describes this original platform’s bounded equivalent, not Suno/Sondo feature parity. “Provider-dependent” means code is wired but external access, model installation/licensing and live validation are still needed. “Partial” identifies the specific difference. “Not implemented” means the feature is absent, not a hidden working integration.

The new tenant provisioning and isolation are additional features, covered in README and tests. Advanced capabilities listed as absent need further implementation; they are not represented as production ready.

## Suno inventory

| ID | Requested feature | Status | Implementation / limits |
|---|---|---|---|
| 1 | Create | Implemented | See README for workflow and limits. |
| 2 | Simple | Implemented | See README for workflow and limits. |
| 3 | Custom | Implemented | See README for workflow and limits. |
| 4 | Library | Implemented | See README for workflow and limits. |
| 5 | Explore | Implemented | See README for workflow and limits. |
| 6 | Studio | Implemented | See README for workflow and limits. |
| 7 | Public artist profile | Not implemented | No working control or engine is claimed for this feature. |
| 8 | Account / subscription | Partial | Account, team and internal credits; no paid billing/subscription checkout. |
| 9 | Song description | Implemented | See README for workflow and limits. |
| 10 | Lyrics field | Implemented | See README for workflow and limits. |
| 11 | AI lyrics assistance | Provider-dependent | Provider adapter implemented; requires an enabled, accessible provider/model and live validation. |
| 12 | Style instructions | Implemented | See README for workflow and limits. |
| 13 | Prompt enhancement | Provider-dependent | Provider adapter implemented; requires an enabled, accessible provider/model and live validation. |
| 14 | Instrumental toggle | Partial | Instrumental engine only; no sung-vocal toggle. |
| 15 | Exclude controls | Not implemented | No working control or engine is claimed for this feature. |
| 16 | Voice-style guidance | Not implemented | No working control or engine is claimed for this feature. |
| 17 | Model picker | Implemented | See README for workflow and limits. |
| 18 | Create button | Implemented | See README for workflow and limits. |
| 19 | Weirdness slider | Partial | Temperature control, not the proprietary Weirdness algorithm. |
| 20 | Style Influence slider | Partial | MusicGen guidance scale, not the proprietary Style Influence algorithm. |
| 21 | Audio Influence slider | Not implemented | No working control or engine is claimed for this feature. |
| 22 | v6 | Not implemented | No working control or engine is claimed for this feature. |
| 23 | v6-wild | Not implemented | No working control or engine is claimed for this feature. |
| 24 | v6-mini | Not implemented | No working control or engine is claimed for this feature. |
| 25 | Plain-language section editing | Not implemented | No working control or engine is claimed for this feature. |
| 26 | Speech with soundtrack | Partial | AI narration; add soundtrack manually in Studio. |
| 27 | Suno Sounds | Not implemented | No working control or engine is claimed for this feature. |
| 28 | Create Custom Model | Not implemented | No working control or engine is claimed for this feature. |
| 29 | Bulk custom-model upload | Not implemented | No working control or engine is claimed for this feature. |
| 30 | Custom model selection | Not implemented | No working control or engine is claimed for this feature. |
| 31 | Upload Audio | Implemented | See README for workflow and limits. |
| 32 | Cover Song | Not implemented | No working control or engine is claimed for this feature. |
| 33 | Extend | Not implemented | No working control or engine is claimed for this feature. |
| 34 | Reuse Prompt | Implemented | See README for workflow and limits. |
| 35 | Remix | Implemented | Explicitly permitted public-source copies; no proprietary model remix. |
| 36 | Sample | Not implemented | No working control or engine is claimed for this feature. |
| 37 | Mashup | Not implemented | No working control or engine is claimed for this feature. |
| 38 | Inspire | Not implemented | No working control or engine is claimed for this feature. |
| 39 | Add Vocals | Not implemented | No working control or engine is claimed for this feature. |
| 40 | Voices | Not implemented | No working control or engine is claimed for this feature. |
| 41 | Create Voice | Not implemented | No working control or engine is claimed for this feature. |
| 42 | Use Your Voice | Not implemented | No working control or engine is claimed for this feature. |
| 43 | Voice verification | Not implemented | No working control or engine is claimed for this feature. |
| 44 | Style Personas | Implemented | See README for workflow and limits. |
| 45 | Allow remixing | Implemented | See README for workflow and limits. |
| 46 | Timeline / waveform | Partial | Waveform and numeric crop controls; studio audio rows, not a full DAW waveform timeline. |
| 47 | Lyrics panel | Partial | No working control or engine is claimed for this feature. |
| 48 | Section selection | Partial | Numeric start/end ranges, not structural song-section detection. |
| 49 | Replace Section | Not implemented | No working control or engine is claimed for this feature. |
| 50 | Quick Replace | Not implemented | No working control or engine is claimed for this feature. |
| 51 | Rewrite section lyrics | Not implemented | No working control or engine is claimed for this feature. |
| 52 | Reorder song sections | Partial | Studio can concatenate selected audio sections in list order; no automatic structural section detection. |
| 53 | Crop | Implemented | See README for workflow and limits. |
| 54 | Fade In | Implemented | See README for workflow and limits. |
| 55 | Fade Out | Implemented | See README for workflow and limits. |
| 56 | Fade-length handles | Partial | Numeric fade duration, not draggable handles. |
| 57 | Tempo display | Implemented | See README for workflow and limits. |
| 58 | Get Stems | Provider-dependent | Optional Demucs two-stem pipeline; disabled until installed. |
| 59 | Remaster | Partial | FFmpeg loudness mastering creates a new version; no AI remaster variations. |
| 60 | Song list | Implemented | See README for workflow and limits. |
| 61 | Liked | Implemented | See README for workflow and limits. |
| 62 | Playlists | Implemented | See README for workflow and limits. |
| 63 | Hooks | Not implemented | No working control or engine is claimed for this feature. |
| 64 | Create playlist | Implemented | See README for workflow and limits. |
| 65 | Add to playlist | Implemented | See README for workflow and limits. |
| 66 | Playlist filters | Not implemented | No working control or engine is claimed for this feature. |
| 67 | Pin playlist | Not implemented | No working control or engine is claimed for this feature. |
| 68 | Multi-select | Partial | Multiple media selections for ZIP; no batch project editor. |
| 69 | Workspaces | Implemented | See README for workflow and limits. |
| 70 | Create Workspace | Implemented | See README for workflow and limits. |
| 71 | Shareable Workspaces | Implemented | Tenant-local invited collaborators; no external guest accounts. |
| 72 | Albums | Implemented | See README for workflow and limits. |
| 73 | Convert playlist to album | Implemented | See README for workflow and limits. |
| 74 | Publish album | Partial | Public album metadata; member tracks require their own publication, no follower notifications. |
| 75 | Move to Trash | Implemented | See README for workflow and limits. |
| 76 | Permanently delete | Partial | Removes source/rendered media; retains accounting/audit/job tombstones and text results. |
| 77 | More Actions | Partial | Visible action buttons instead of an ellipsis menu. |
| 78 | Publish | Implemented | See README for workflow and limits. |
| 79 | Link-only sharing | Implemented | See README for workflow and limits. |
| 80 | Share | Implemented | See README for workflow and limits. |
| 81 | Download | Implemented | See README for workflow and limits. |
| 82 | Download All | Partial | Selected project assets in ZIP, capped at 100 MB. |
| 83 | File-type selection | Implemented | See README for workflow and limits. |
| 84 | ZIP download | Implemented | See README for workflow and limits. |
| 85 | Get Stems Extract | Provider-dependent | Provider adapter implemented; requires an enabled, accessible provider/model and live validation. |
| 86 | Auto Split up to 12 stems | Not implemented | No working control or engine is claimed for this feature. |
| 87 | Split from Mix | Partial | Optional vocals/accompaniment only; no arbitrary instrument target. |
| 88 | Advanced Split | Not implemented | No working control or engine is claimed for this feature. |
| 89 | Split Stems in Studio | Partial | Stem separation launched from Library audio editor, not clip context menu. |
| 90 | Individual stem downloads | Provider-dependent | Provider adapter implemented; requires an enabled, accessible provider/model and live validation. |
| 91 | Open in Studio | Implemented | See README for workflow and limits. |
| 92 | Chat Bar | Not implemented | No working control or engine is claimed for this feature. |
| 93 | Timeline | Implemented | See README for workflow and limits. |
| 94 | Play Pause Stop | Implemented | See README for workflow and limits. |
| 95 | Record audio or MIDI | Partial | Microphone recording in Library; note capture in Studio. Browser permission/device tests remain. |
| 96 | Metronome | Implemented | See README for workflow and limits. |
| 97 | Loop | Implemented | See README for workflow and limits. |
| 98 | Follow Playhead | Not implemented | No working control or engine is claimed for this feature. |
| 99 | Clock Settings | Not implemented | No working control or engine is claimed for this feature. |
| 100 | Tempo Settings | Implemented | See README for workflow and limits. |
| 101 | Time Signature | Implemented | See README for workflow and limits. |
| 102 | Take Lanes | Not implemented | No working control or engine is claimed for this feature. |
| 103 | Commit generated take | Not implemented | No working control or engine is claimed for this feature. |
| 104 | Dismiss preview | Not implemented | No working control or engine is claimed for this feature. |
| 105 | Take up/down | Not implemented | No working control or engine is claimed for this feature. |
| 106 | Arrangement Editor | Partial | Numeric arrangement controls, not a separate detailed modal DAW editor. |
| 107 | Trim handles | Partial | Numeric trim/duration, not draggable waveform handles. |
| 108 | Loop flags | Partial | Whole-arrangement loop, no arbitrary draggable loop region. |
| 109 | Reverse | Implemented | See README for workflow and limits. |
| 110 | Stretch | Partial | Offline speed processing, not shift-drag warp stretching. |
| 111 | Warp markers | Not implemented | No working control or engine is claimed for this feature. |
| 112 | Quantize | Partial | Piano-note starts/durations can be quantized; no audio warp quantization. |
| 113 | Pitch | Implemented | See README for workflow and limits. |
| 114 | Formant | Not implemented | No working control or engine is claimed for this feature. |
| 115 | Speed | Implemented | See README for workflow and limits. |
| 116 | Volume | Implemented | See README for workflow and limits. |
| 117 | Split clip | Not implemented | No working control or engine is claimed for this feature. |
| 118 | Disable clip | Implemented | See README for workflow and limits. |
| 119 | Clip Info | Partial | Project prompt/lyrics/metadata; no clip-specific tabbed panel. |
| 120 | Rename clip | Partial | Project title editable; existing asset/clip name controls not exposed. |
| 121 | Fade curves | Not implemented | No working control or engine is claimed for this feature. |
| 122 | Remove FX / Get Dry | Not implemented | No working control or engine is claimed for this feature. |
| 123 | Add effect | Partial | One selected effect per audio-edit form; backend validates up to eight. |
| 124 | Compressor | Partial | Basic FFmpeg compressor; no sidechain routing. |
| 125 | EQ | Partial | One 1 kHz peaking EQ amount; not a multiband visual EQ. |
| 126 | Reverb | Partial | Simple echo-based reverb, not convolution/spatial modeling. |
| 127 | Convolution | Not implemented | No working control or engine is claimed for this feature. |
| 128 | Delay | Partial | Fixed-delay echo with adjustable amount. |
| 129 | Distortion | Partial | Soft clipping with adjustable amount. |
| 130 | Gate | Implemented | See README for workflow and limits. |
| 131 | Effects chain | Partial | Backend ordered effect array; GUI selects one effect. |
| 132 | Bypass | Partial | Backend supports effect bypass; no GUI chain bypass switch. |
| 133 | Expand effect | Not implemented | No working control or engine is claimed for this feature. |
| 134 | Save/load effect presets | Not implemented | No working control or engine is claimed for this feature. |
| 135 | Create plugin with chat | Not implemented | No working control or engine is claimed for this feature. |
| 136 | Build plugin | Not implemented | No working control or engine is claimed for this feature. |
| 137 | Revise plugin | Not implemented | No working control or engine is claimed for this feature. |
| 138 | Save plugin | Not implemented | No working control or engine is claimed for this feature. |
| 139 | Automation | Not implemented | No working control or engine is claimed for this feature. |
| 140 | MIDI Learn | Not implemented | No working control or engine is claimed for this feature. |
| 141 | MIDI tracks | Partial | One note lane and imported MIDI notes, not multiple editable MIDI tracks. |
| 142 | Piano roll | Implemented | See README for workflow and limits. |
| 143 | Velocity editing | Implemented | See README for workflow and limits. |
| 144 | Pitch bend / modulation | Not implemented | No working control or engine is claimed for this feature. |
| 145 | Key Scale assist | Not implemented | No working control or engine is claimed for this feature. |
| 146 | Musical typing | Implemented | See README for workflow and limits. |
| 147 | On-screen keyboard | Implemented | See README for workflow and limits. |
| 148 | Chord modes | Partial | Major-triad expansion from existing piano notes; no broad chord-mode engine. |
| 149 | Arpeggiator | Partial | Ascending fixed-step arpeggiation of notes; no real-time hold/chord arpeggiator. |
| 150 | External MIDI input | Implemented | See README for workflow and limits. |
| 151 | Audio-to-MIDI | Not implemented | No working control or engine is claimed for this feature. |
| 152 | MIDI-to-generated audio | Partial | Local synthesizer renders notes; not a generative model interpretation. |
| 153 | Wavetable synth | Partial | Four oscillator waveforms, not a wavetable engine. |
| 154 | Synth presets | Not implemented | No working control or engine is claimed for this feature. |
| 155 | Oscillators filters envelopes LFOs | Partial | Oscillator waveform and fixed note envelope only; no filters/LFO editor. |
| 156 | Modulation matrix | Not implemented | No working control or engine is claimed for this feature. |
| 157 | Library dock | Partial | Library panel is always visible in Studio; no dock toggle. |
| 158 | All Songs Liked Stems Uploads dock filters | Partial | Audio resources from accessible projects; no dock category tabs. |
| 159 | Workspaces Studio Projects dock | Partial | Saved workspaces/projects via navigation, not dock tabs. |
| 160 | Search filters in dock | Partial | Search in Library; no Studio dock filtering. |
| 161 | Audition | Partial | Preview in Library; Studio dock has Add, not individual audition controls. |
| 162 | Song Details | Partial | Project details; no dedicated dock Song Details panel. |
| 163 | Stems tab | Not implemented | No working control or engine is claimed for this feature. |
| 164 | Insert all stems | Not implemented | No working control or engine is claimed for this feature. |
| 165 | Notes tab | Partial | Project notes, not per-song dock tabs. |
| 166 | Drag asset to timeline | Implemented | Add button; drag-to-insert not implemented. |
| 167 | Drag asset to chat | Not implemented | No working control or engine is claimed for this feature. |
| 168 | Mini-player | Partial | Native media player in project details, not a persistent dock mini-player. |
| 169 | Like/dislike previews | Partial | Like a project; dislike/preview ratings not implemented. |
| 170 | Export dropdown | Partial | Direct export buttons instead of a dropdown. |
| 171 | Full-song export | Implemented | See README for workflow and limits. |
| 172 | Selected-range export | Implemented | See README for workflow and limits. |
| 173 | Multitrack export | Implemented | See README for workflow and limits. |
| 174 | WAV MP3 export | Implemented | See README for workflow and limits. |
| 175 | Individual stem WAV export | Provider-dependent | Provider adapter implemented; requires an enabled, accessible provider/model and live validation. |

## Sondo inventory

| ID | Requested feature | Status | Implementation / limits |
|---|---|---|---|
| 1 | Home | Implemented | See README for workflow and limits. |
| 2 | Music Video Lab | Implemented | See README for workflow and limits. |
| 3 | Music Lab | Implemented | See README for workflow and limits. |
| 4 | Blog | Partial | Creator guide/tutorial page; no blog publishing system. |
| 5 | Language selector | Not implemented | No working control or engine is claimed for this feature. |
| 6 | Free Trial | Not implemented | No working control or engine is claimed for this feature. |
| 7 | Create MV | Implemented | See README for workflow and limits. |
| 8 | Privacy Policy | Partial | Draft implementation privacy notice; operator details needed. |
| 9 | Terms of Service | Partial | Draft terms; operator details needed. |
| 10 | Contact email | Not implemented | No working control or engine is claimed for this feature. |
| 11 | AI Audio Lab | Provider-dependent | Provider adapter implemented; requires an enabled, accessible provider/model and live validation. |
| 12 | Lyrics input | Implemented | See README for workflow and limits. |
| 13 | Music genre selection | Partial | Genre entered in style prompt; no dedicated genre selector. |
| 14 | Vocal gender selection | Not implemented | No working control or engine is claimed for this feature. |
| 15 | Instrumental generation | Provider-dependent | Provider adapter implemented; requires an enabled, accessible provider/model and live validation. |
| 16 | Vocal music generation | Not implemented | No working control or engine is claimed for this feature. |
| 17 | Text-to-song | Provider-dependent | Provider adapter implemented; requires an enabled, accessible provider/model and live validation. |
| 18 | Story-to-song | Provider-dependent | Provider adapter implemented; requires an enabled, accessible provider/model and live validation. |
| 19 | Multiple genres | Provider-dependent | Provider adapter implemented; requires an enabled, accessible provider/model and live validation. |
| 20 | Music-to-MV workflow | Implemented | See README for workflow and limits. |
| 21 | Song selection | Implemented | See README for workflow and limits. |
| 22 | Audio upload | Implemented | See README for workflow and limits. |
| 23 | Photo upload | Implemented | See README for workflow and limits. |
| 24 | MV description | Implemented | See README for workflow and limits. |
| 25 | Aspect-ratio selection | Implemented | See README for workflow and limits. |
| 26 | Create | Implemented | See README for workflow and limits. |
| 27 | Music analysis | Partial | Reads prompt/lyrics metadata for planning; no beat/semantic audio analysis. |
| 28 | Automatic script planning | Provider-dependent | Provider adapter implemented; requires an enabled, accessible provider/model and live validation. |
| 29 | Scene shot planning | Provider-dependent | Provider adapter implemented; requires an enabled, accessible provider/model and live validation. |
| 30 | Character-based cover generation | Partial | Text-prompt image generation; no uploaded-photo identity conditioning. |
| 31 | Script preview | Implemented | See README for workflow and limits. |
| 32 | Storyline modification | Implemented | See README for workflow and limits. |
| 33 | Create after approval | Implemented | See README for workflow and limits. |
| 34 | Merge Video | Implemented | See README for workflow and limits. |
| 35 | Settings | Implemented | See README for workflow and limits. |
| 36 | Cover editing | Partial | Use image resources for scenes; no dedicated public cover asset setter. |
| 37 | Video title editing | Implemented | See README for workflow and limits. |
| 38 | Options | Implemented | See README for workflow and limits. |
| 39 | 16:9 | Implemented | See README for workflow and limits. |
| 40 | 9:16 | Implemented | See README for workflow and limits. |
| 41 | Deep Thinking page | Partial | Editable storyboard in Video Lab; no separate Deep Thinking route. |
| 42 | Storyline section | Implemented | See README for workflow and limits. |
| 43 | Edit MV | Implemented | See README for workflow and limits. |
| 44 | Image Mode | Partial | Image generation/resource selection in scenes; not a separate mode. |
| 45 | Upload image | Implemented | See README for workflow and limits. |
| 46 | Image prompt | Implemented | See README for workflow and limits. |
| 47 | Create character | Provider-dependent | Provider adapter implemented; requires an enabled, accessible provider/model and live validation. |
| 48 | Video Mode | Partial | Motion resources selectable in scenes; not a separate mode. |
| 49 | Timeline | Implemented | See README for workflow and limits. |
| 50 | Image Resource Library | Implemented | See README for workflow and limits. |
| 51 | Assign image to clip | Implemented | See README for workflow and limits. |
| 52 | Clip prompt | Implemented | See README for workflow and limits. |
| 53 | Generate clip | Provider-dependent | Provider adapter implemented; requires an enabled, accessible provider/model and live validation. |
| 54 | Video Clip Library | Partial | Project media versions, not a separate clip-library route. |
| 55 | Drag to timeline | Partial | Resource dropdown assignment; no drag from a resource dock. |
| 56 | Drag to reorder | Implemented | See README for workflow and limits. |
| 57 | Preview text editing | Partial | Caption text fields per scene, not inline canvas text editing. |
| 58 | Export | Implemented | See README for workflow and limits. |
| 59 | Rhythm-aware editing | Not implemented | No working control or engine is claimed for this feature. |
| 60 | Emotion-guided visuals | Partial | Mood can guide AI prompts; no validated emotion detector. |
| 61 | Lyrics-responsive storytelling | Partial | Song lyrics may be passed in a new song-to-video planning flow; no lyric timestamps or sync. |
| 62 | Photo-based characters | Partial | Uploaded photos are used as scene images; no avatar creation or identity consistency model. |
| 63 | Animated scenes | Provider-dependent | Provider adapter implemented; requires an enabled, accessible provider/model and live validation. |
| 64 | Automatic editing | Partial | AI plans text scenes; user approves and assigns media before local assembly. |
| 65 | Mood guidance | Partial | Free-form mood prompts, not a preset picker. |
| 66 | Personal-event videos | Partial | General story prompts can describe events; no dedicated event templates. |
| 67 | Trending-track videos | Partial | Use only tracks you have permission to use; no trending-track importer or music license. |

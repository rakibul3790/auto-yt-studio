# History 5: "5 Moments in History That Sound Fake (But Really Happened)"

Edit pack for re-editing. Everything used to make the video is here, separated, with where it came from.

## Quick facts

- Length: 9:02.53 (542.53 s). 1920x1080, 30 fps, H.264 (libx264, CRF 18, preset medium, High profile, yuv420p), AAC 192 kbps 48 kHz stereo, faststart.
- Loudness: final mix levelled to -14 LUFS integrated, true peak about -1.5 dB (YouTube standard).
- Voice: ElevenLabs, voice id XA3P1cj7XJexe6Zq0ATX, model eleven_v3, with inline emotion tags. Made in 13 parts, each part once. Total cost 3,529 credits.
- Known voice slip: in Story 1 (Emu War) the voice skipped the word "later" in "Meredith later said". The captions still show it. Fix it in the edit if you want (cut the caption word or re-record that one line).
- Mid-roll ad point: end of Story 2, right before the BOSTON 1919 title card (see table below).
- Not uploaded anywhere.

## Folders

- `01_MAIN_FINAL_VIDEO/`: the finished video (picture, captions, voice, music, effects).
- `02_AUDIO/`: audio only.
  - `voice_FULL_lined_up_to_video.wav/.mp3`: the whole narration, already lined up from 0:00 to match the video.
  - `voice_parts/voice_part_01..13.mp3`: each ElevenLabs part as generated (see the part table).
  - `music_tracks/`: the 7 music tracks exactly as downloaded. `music_sections.json` says where each plays.
  - `music_bed_before_ducking.wav`: the 7 tracks joined with crossfades, before dipping under the voice.
  - `music_ducked.wav`: the music as heard in the video (dips under the voice).
  - `sound_effects.wav`: whooshes, impacts, shimmers etc. on their own track.
  - `final_mix_-14LUFS.wav`: the finished mix. voice + effects + ducked music = this mix (before levelling).
- `03_VIDEO_ONLY/`: picture without sound.
  - `video_ONLY_no_voice_no_music_no_captions.mp4`: clean picture (title cards and number graphics are in it).
  - `video_ONLY_no_voice_no_music_WITH_captions.mp4`: same picture with the captions burned in.
  - `video_no_captions_WITH_voice_and_music.mp4`: no captions, full sound.
- `04_ELEMENTS/`: building blocks.
  - `shots/`: every shot as rendered (crop, camera move, colour grade, graphic), in timeline order.
  - `overlays_transparent/`: title cards, number graphics and the animated captions as transparent .mov (PNG codec, alpha). Put them on a track above the picture.
  - `captions/`: `captions_animated.ass` (exact animated style), `captions_plain.srt` (plain subtitles), `Montserrat-ExtraBold.ttf` (the font).
  - `timeline.json`: every shot with start, length, transition, camera, sound effect, stock search, files.
  - `plan_used_for_render.json`: the full scene plan the renderer used (text, tags, beats, graphics).
- `05_ORIGINAL_SOURCES/`: every original file, untouched.
  - `stock_footage_as_downloaded/`: each stock clip and photo, whole, full resolution, exactly as downloaded.
  - `stock_sources.csv` / `.json`: for each file: site, id, page link, the search used, and which shots use it (the .json also says from which second of the original each shot starts).
  - `music_as_downloaded/`, `voice_parts_as_made_by_elevenlabs/`: the original music and voice files.
- `narration_with_emotion_tags.txt`: the exact text that was spoken, with every emotion tag, by voice part.

## Sections, voice parts and music

| Part | Starts at | Section | Music (Kevin MacLeod) |
|---|---|---|---|
| 1 | 0:00.00 | Hook (cold open) | investigations.mp3 from 0:00.00 |
| 2 | 0:32.34 | Story 1: The Great Emu War (Western Australia 1932) | monkeys-spinning-monkeys.mp3 from 0:30.43 |
| 3 | 1:29.90 |  |  |
| 4 | 2:01.12 | Story 2: The Dancing Plague (Strasbourg 1518) | spy-glass.mp3 from 1:59.38 |
| 5 | 2:32.20 |  |  |
| 6 | 3:31.50 | Story 3: The Great Molasses Flood (Boston 1919) | hitman.mp3 from 3:29.70 |
| 7 | 4:01.06 |  |  |
| 8 | 5:12.84 | Story 4: The man who sold the Eiffel Tower (Paris 1925) | scheming-weasel-faster.mp3 from 5:11.10 |
| 9 | 5:50.88 |  |  |
| 10 | 6:47.62 | Story 5: Hiroo Onoda, the soldier who kept fighting (Lubang Island 1944) | inspired.mp3 from 6:45.78 |
| 11 | 7:28.94 |  |  |
| 12 | 8:09.54 |  |  |
| 13 | 8:40.84 | Ending | carefree.mp3 from 8:39.13 |

Music: each track starts 1 s before its story begins and crossfades over 2 s. Each track is levelled to -20 LUFS, then ducked under the voice (it rises in pauses and falls while the voice talks). Mood scenes change the music level: sad x0.45, whisper x0.6, excited x1.15, angry x1.25.

Music licence: all tracks by Kevin MacLeod (incompetech.com), Creative Commons Attribution 4.0. Put this in the YouTube description:

```
"Investigations" Kevin MacLeod (incompetech.com)
"Monkeys Spinning Monkeys" Kevin MacLeod (incompetech.com)
"Spy Glass" Kevin MacLeod (incompetech.com)
"Hitman" Kevin MacLeod (incompetech.com)
"Scheming Weasel Faster" Kevin MacLeod (incompetech.com)
"Inspired" Kevin MacLeod (incompetech.com)
"Carefree" Kevin MacLeod (incompetech.com)
Licensed under Creative Commons: By Attribution 4.0 License
http://creativecommons.org/licenses/by/4.0/
```

## Emotion

Voice tags used (ElevenLabs v3 inline tags, in square brackets in the narration file): amused, calm, chuckles, confident, curious, emotional, excited, laughs, mysterious, sad, scoffs, serious, shocked, sighs, sly, softly, tense, uneasy, warm, whispers.

Picture follows the mood of each scene (colour grade added on top of the stock clip):

| Look | Grade (ffmpeg) | Used on scenes |
|---|---|---|
| excited | saturation 1.25, contrast 1.06, brightness +0.02 | 7, 10, 15, 18, 29, 31, 86, 90, 92, 96, 112, 124, 126 |
| sad | saturation 0.5, slightly darker, blue tint, vignette | 44, 71, 75, 106, 115, 119, 120 |
| angry | saturation 1.3, contrast 1.14, red tint, vignette, small camera shake | 54, 64, 66 |
| whisper | saturation 0.8, gamma 1.08 (soft), vignette | 11, 33, 35, 50, 53, 73, 84, 103, 118, 125 |

Scenes with no look keep the clip's own colours. Any clip that came out too dark is brightened (gamma 1.45, brightness +0.04).

## Captions

- Font: Montserrat ExtraBold (file in `04_ELEMENTS/captions/`).
- Size: 6.2% of the frame height (about 67 px at 1080p). Position: centred, lower third (centre at 80% of the height).
- White text, thick black outline, soft shadow. A few words per line, timed to each spoken word.
- Key words pop onto a yellow pill (#FFD60A, rounded) with dark text (#121212); words pop in with a small scale bounce.
- `captions_plain.srt` has the same words without animation, for YouTube subtitles or another editor.

## Title cards and graphics

Title cards (big text over footage): MARCH 1974, WESTERN AUSTRALIA 1932, STRASBOURG 1518, BOSTON 1919, PARIS 1925, LUBANG ISLAND 1944, and the end card SUBSCRIBE FOR MORE.
Number graphics: 20,000 EMUS, 10,000 ROUNDS, 400 DANCERS, 2.3M GALLONS, 35 MPH, 29 YEARS; and a compare graphic 986 EMUS vs 9,860 BULLETS. All are in `overlays_transparent/` as separate transparent files and in the shots.

## Transitions and camera

- Transitions overlap the next shot by their length: whip 0.22 s (with motion blur), zoom 0.30 s, slide 0.26 s, fade, flash and glitch are short. A plain cut has none. Each shot's transition is in the shot list.
- Camera moves on every shot: slow push in / pull out / drift / pan, done as a crop on the stock clip.
- Sound effects sit on transitions and title cards (whoosh, impact, shimmer, riser etc.).

## Shot list

Times are in the final video. "Original" is the file in `05_ORIGINAL_SOURCES/stock_footage_as_downloaded/`.

| # | Start | Length | Transition in | Kind | Camera | Sound | Stock search | Original | Site and id |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 0:00.00 | 1.77s | cut | text | drift | impact | dense jungle trees | 001_pixabay_pb163778.mp4 | Pixabay pb163778 |
| 2 | 0:01.77 | 2.02s | cut | clip | push_in | - | soldier walking jungle | 002_pixabay_pb21943.mp4 | Pixabay pb21943 |
| 3 | 0:03.79 | 1.88s | cut | clip | pan_left | - | dense jungle trees | 003_pixabay_pb234735.mp4 | Pixabay pb234735 |
| 4 | 0:05.67 | 1.67s | cut | clip | pull_out | - | old rifle | 004_pixabay_pb131958.mp4 | Pixabay pb131958 |
| 5 | 0:07.34 | 4.34s | whip_left | clip | pan_right | swish | jungle mist | 005_pixabay_pb369144.mp4 | Pixabay pb369144 |
| 6 | 0:11.68 | 1.42s | cut | clip | drift | - | jungle sunlight | 006_pixabay_pb82951.mp4 | Pixabay pb82951 |
| 7 | 0:13.10 | 3.36s | slide_up | clip | tilt_up | whoosh | old book pages | 007_pixabay_pb207982.mp4 | Pixabay pb207982 |
| 8 | 0:16.46 | 3.35s | cut | clip | push_in | - | emus running | 008_pixabay_pb80823.mp4 | Pixabay pb80823 |
| 9 | 0:19.81 | 2.64s | zoom | clip | pan_right | whoosh | people dancing street | 009_pixabay_pb17352.mp4 | Pixabay pb17352 |
| 10 | 0:22.45 | 2.49s | cut | clip | push_in | - | brown liquid pouring | 010_pixabay_pb98283.mp4 | Pixabay pb98283 |
| 11 | 0:24.94 | 2.82s | whip_right | clip | pan_left | swish | eiffel tower | 011_pixabay_pb16619.mp4 | Pixabay pb16619 |
| 12 | 0:27.76 | 3.44s | cut | clip | pull_out | - | emu close up | 012_pixabay_pbi8134086.jpg | Pixabay pbi8134086 |
| 13 | 0:31.20 | 3.71s | fade | text | drift | shimmer | wheat field | 013_pixabay_pb46140.mp4 | Pixabay pb46140 |
| 14 | 0:34.91 | 2.59s | cut | clip | pan_right | - | wheat field farmer | 014_pixabay_pbi1866559.jpg | Pixabay pbi1866559 |
| 15 | 0:37.50 | 2.93s | zoom | number | drift | whoosh, tick | emus field | 015_pixabay_pbi2791107.jpg | Pixabay pbi2791107 |
| 16 | 0:40.43 | 3.15s | cut | clip | drift | - | emus walking | 016_pixabay_pbi529977.jpg | Pixabay pbi529977 |
| 17 | 0:43.58 | 2.64s | cut | clip | tilt_up | - | farmer worried field | 017_pixabay_pb121982.mp4 | Pixabay pb121982 |
| 18 | 0:46.22 | 2.78s | cut | clip | push_in | - | soldiers marching | 018_pixabay_pb23662.mp4 | Pixabay pb23662 |
| 19 | 0:49.00 | 2.14s | whip_left | clip | pan_right | swish | military officer vintage | 019_pixabay_pbi1405926.jpg | Pixabay pbi1405926 |
| 20 | 0:51.14 | 3.53s | zoom | number | drift | whoosh, tick | ammunition bullets | 020_pixabay_pb43040.mp4 | Pixabay pb43040 |
| 21 | 0:54.67 | 3.28s | cut | clip | push_in | - | clock ticking | 021_pixabay_pb37006.mp4 | Pixabay pb37006 |
| 22 | 0:57.95 | 1.59s | slide_up | clip | pan_left | whoosh | emu funny | 022_pixabay_pbi3479510.jpg | Pixabay pbi3479510 |
| 23 | 0:59.54 | 1.99s | cut | clip | pull_out | - | emus running | 023_pixabay_pb233276.mp4 | Pixabay pb233276 |
| 24 | 1:01.53 | 2.15s | cut | clip | pan_right | - | birds scattering | 024_pixabay_pbi5348155.jpg | Pixabay pbi5348155 |
| 25 | 1:03.68 | 3.23s | zoom | clip | drift | whoosh | watering hole outback | 025_pixabay_pb316435.mp4 | Pixabay pb316435 |
| 26 | 1:06.91 | 2.36s | cut | clip | tilt_up | - | emus flock | 026_pixabay_pb249998.mp4 | Pixabay pb249998 |
| 27 | 1:09.27 | 2.54s | cut | clip | push_in | - | emu | 027_pixabay_pbi7179071.jpg | Pixabay pbi7179071 |
| 28 | 1:11.81 | 1.27s | cut | clip | pan_right | - | machine gun | 028_pixabay_pb375.mp4 | Pixabay pb375 |
| 29 | 1:13.08 | 2.79s | whip_right | clip | push_in | swish | old truck dirt road | 029_pixabay_pb210762.mp4 | Pixabay pb210762 |
| 30 | 1:15.87 | 3.00s | cut | clip | pan_left | - | bumpy dirt road | 030_pixabay_pb218798.mp4 | Pixabay pb218798 |
| 31 | 1:18.87 | 3.44s | cut | clip | pull_out | - | soldiers walking away | 031_pixabay_pb6387.mp4 | Pixabay pb6387 |
| 32 | 1:22.31 | 4.31s | cut | clip | pan_right | - | emu portrait | 032_pixabay_pbi8137534.jpg | Pixabay pbi8137534 |
| 33 | 1:26.62 | 2.76s | cut | clip | drift | - | emus running field | 033_pixabay_pb70858.mp4 | Pixabay pb70858 |
| 34 | 1:29.38 | 2.63s | whip_left | clip | tilt_up | swish | wheat field | 034_pixabay_pb21299.mp4 | Pixabay pb21299 |
| 35 | 1:32.01 | 1.80s | cut | clip | push_in | - | soldiers | 035_pixabay_pb61414.mp4 | Pixabay pb61414 |
| 36 | 1:33.81 | 4.34s | cut | clip | pan_right | - | old typewriter report | 036_pixabay_pb1335.mp4 | Pixabay pb1335 |
| 37 | 1:38.15 | 4.12s | flash | compare | drift | impact, tick | bullets | 037_pixabay_pbi2166491.jpg | Pixabay pbi2166491 |
| 38 | 1:42.27 | 2.81s | slide_up | clip | push_in | whoosh | emu close up | 038_pixabay_pbi3619658.jpg | Pixabay pbi3619658 |
| 39 | 1:45.08 | 2.32s | cut | clip | pan_left | - | old newspaper | 039_pixabay_pbi671800.jpg | Pixabay pbi671800 |
| 40 | 1:47.40 | 1.41s | zoom | clip | pull_out | whoosh | emus wheat | 040_pixabay_pb39982.mp4 | Pixabay pb39982 |
| 41 | 1:48.81 | 2.21s | cut | clip | pan_right | - | emu eating | 041_pixabay_pb44411.mp4 | Pixabay pb44411 |
| 42 | 1:51.02 | 2.30s | cut | clip | drift | - | emus running | 042_pixabay_pbi7286365.jpg | Pixabay pbi7286365 |
| 43 | 1:53.32 | 1.96s | whip_right | clip | tilt_up | swish | birds flying sunset | 043_pixabay_pb375658.mp4 | Pixabay pb375658 |
| 44 | 1:55.28 | 4.88s | cut | clip | push_in | - | old european town | 044_pixabay_pb167088.mp4 | Pixabay pb167088 |
| 45 | 2:00.16 | 5.22s | fade | text | drift | shimmer | medieval town | 045_pixabay_pb53834.mp4 | Pixabay pb53834 |
| 46 | 2:05.38 | 2.57s | cut | clip | pan_right | - | medieval street | 046_pixabay_pbi6583471.jpg | Pixabay pbi6583471 |
| 47 | 2:07.95 | 1.94s | cut | clip | push_in | - | woman dancing | 047_pixabay_pb29313.mp4 | Pixabay pb29313 |
| 48 | 2:09.89 | 2.63s | cut | clip | pan_left | - | empty street old town | 048_pixabay_pb216951.mp4 | Pixabay pb216951 |
| 49 | 2:12.52 | 3.45s | whip_left | clip | pull_out | swish | dancing feet | 049_pixabay_pb3627.mp4 | Pixabay pb3627 |
| 50 | 2:15.97 | 4.85s | cut | clip | pan_right | - | bare feet stone | 050_pixabay_pb1105.mp4 | Pixabay pb1105 |
| 51 | 2:20.82 | 3.76s | slide_up | clip | drift | whoosh | crowd dancing | 051_pixabay_pb236095.mp4 | Pixabay pb236095 |
| 52 | 2:24.58 | 3.81s | zoom | number | drift | whoosh, tick | crowd dancing | 052_pixabay_pb142030.mp4 | Pixabay pb142030 |
| 53 | 2:28.39 | 3.35s | cut | clip | tilt_up | - | people dancing night | 053_pixabay_pb172.mp4 | Pixabay pb172 |
| 54 | 2:31.74 | 3.65s | zoom | clip | push_in | whoosh | old medicine bottles | 054_pixabay_pbi711883.jpg | Pixabay pbi711883 |
| 55 | 2:35.39 | 2.57s | cut | clip | pan_right | - | people dancing | 055_pixabay_pb8758.mp4 | Pixabay pb8758 |
| 56 | 2:37.96 | 3.67s | cut | clip | push_in | - | wooden stage | 056_pixabay_pb1630.mp4 | Pixabay pb1630 |
| 57 | 2:41.63 | 2.21s | cut | clip | pan_left | - | musicians playing violin | 057_pixabay_pb13394.mp4 | Pixabay pb13394 |
| 58 | 2:43.84 | 2.23s | whip_right | clip | pull_out | swish | storm clouds | 058_pixabay_pb38125.mp4 | Pixabay pb38125 |
| 59 | 2:46.07 | 3.78s | cut | clip | pan_right | - | old manuscript | 059_pixabay_pbi436501.jpg | Pixabay pbi436501 |
| 60 | 2:49.85 | 2.60s | cut | clip | drift | - | candle dark | 060_pixabay_pb175213.mp4 | Pixabay pb175213 |
| 61 | 2:52.45 | 2.45s | cut | clip | tilt_up | - | cathedral | 061_pixabay_pb29224.mp4 | Pixabay pb29224 |
| 62 | 2:54.90 | 2.45s | cut | clip | push_in | - | chapel hills | 062_pixabay_pb22259.mp4 | Pixabay pb22259 |
| 63 | 2:57.35 | 1.94s | cut | clip | pan_right | - | candles church | 063_pixabay_pb7456.mp4 | Pixabay pb7456 |
| 64 | 2:59.29 | 2.59s | whip_left | clip | push_in | swish | sunrise old town | 064_pixabay_pb221299.mp4 | Pixabay pb221299 |
| 65 | 3:01.88 | 3.24s | cut | clip | pan_left | - | fog forest | 065_pixabay_pb258799.mp4 | Pixabay pb258799 |
| 66 | 3:05.12 | 3.31s | slide_up | clip | pull_out | whoosh | dry wheat field | 066_pixabay_pb21444.mp4 | Pixabay pb21444 |
| 67 | 3:08.43 | 4.61s | cut | clip | pan_right | - | grain sacks | 067_pixabay_pbi1836329.jpg | Pixabay pbi1836329 |
| 68 | 3:13.04 | 4.09s | cut | clip | drift | - | crowd silhouette | 068_pixabay_pb3606.mp4 | Pixabay pb3606 |
| 69 | 3:17.13 | 4.48s | zoom | clip | tilt_up | whoosh | medieval town night | 069_pixabay_pbi748912.jpg | Pixabay pbi748912 |
| 70 | 3:21.61 | 1.74s | cut | clip | push_in | - | people dancing | 070_pixabay_pb17351.mp4 | Pixabay pb17351 |
| 71 | 3:23.35 | 3.98s | whip_right | clip | pan_right | swish | boston city | 071_pixabay_pbi8911169.jpg | Pixabay pbi8911169 |
| 72 | 3:27.33 | 3.15s | cut | clip | push_in | - | industrial tank | 072_pixabay_pbi978248.jpg | Pixabay pbi978248 |
| 73 | 3:30.47 | 5.17s | fade | text | drift | shimmer | boston old street | 073_pixabay_pb1044.mp4 | Pixabay pb1044 |
| 74 | 3:35.64 | 4.08s | cut | clip | pan_left | - | old city street people | 074_pixabay_pb28206.mp4 | Pixabay pb28206 |
| 75 | 3:39.72 | 1.65s | cut | clip | pull_out | - | boston harbor | 075_pixabay_pb48067.mp4 | Pixabay pb48067 |
| 76 | 3:41.37 | 1.37s | cut | clip | pan_right | - | steel storage tank | 076_pixabay_pbi5037383.jpg | Pixabay pbi5037383 |
| 77 | 3:42.74 | 2.89s | cut | clip | drift | - | industrial tank | 077_pixabay_pbi644982.jpg | Pixabay pbi644982 |
| 78 | 3:45.63 | 3.73s | zoom | number | drift | whoosh, tick | molasses dripping | 078_pixabay_pbi4921212.jpg | Pixabay pbi4921212 |
| 79 | 3:49.36 | 2.81s | whip_left | clip | tilt_up | swish | rusty metal | 079_pixabay_pbi7855448.jpg | Pixabay pbi7855448 |
| 80 | 3:52.17 | 1.07s | cut | clip | push_in | - | liquid leaking | 080_pixabay_pb81173.mp4 | Pixabay pb81173 |
| 81 | 3:53.24 | 2.86s | cut | clip | pan_right | - | syrup dripping | 081_pixabay_pbi5338030.jpg | Pixabay pbi5338030 |
| 82 | 3:56.10 | 4.55s | slide_up | clip | push_in | whoosh | paint brush | 082_pixabay_pbi96240.jpg | Pixabay pbi96240 |
| 83 | 4:00.65 | 4.32s | cut | clip | pan_left | - | old street | 083_pixabay_pb114258.mp4 | Pixabay pb114258 |
| 84 | 4:04.97 | 2.20s | cut | clip | pull_out | - | metal rivets | 084_pixabay_pb143859.mp4 | Pixabay pb143859 |
| 85 | 4:07.17 | 3.37s | zoom | clip | pan_right | whoosh | steel rivets | 085_pixabay_pbi114141.jpg | Pixabay pbi114141 |
| 86 | 4:10.54 | 2.66s | cut | clip | drift | - | brown liquid wave | 086_pixabay_pbi3147972.jpg | Pixabay pbi3147972 |
| 87 | 4:13.20 | 4.62s | whip_right | clip | tilt_up | swish | brown liquid flowing | 087_pixabay_pb98283.mp4 | Pixabay pb98283 |
| 88 | 4:17.82 | 3.12s | zoom | number | drift | whoosh, tick | brown liquid flowing | 088_pixabay_pb98283.mp4 | Pixabay pb98283 |
| 89 | 4:20.94 | 2.63s | cut | clip | push_in | - | people running | 089_pixabay_pb3599.mp4 | Pixabay pb3599 |
| 90 | 4:23.57 | 3.94s | cut | clip | pan_right | - | flood damage | 090_pixabay_pb43370.mp4 | Pixabay pb43370 |
| 91 | 4:27.51 | 5.51s | cut | clip | push_in | - | elevated railway | 091_pixabay_pb32000.mp4 | Pixabay pb32000 |
| 92 | 4:33.02 | 6.16s | cut | clip | pan_left | - | horse cart old | 092_pixabay_pb62701.mp4 | Pixabay pb62701 |
| 93 | 4:39.18 | 4.27s | cut | clip | pan_right | - | rescue workers | 093_pixabay_pbi4532368.jpg | Pixabay pbi4532368 |
| 94 | 4:43.45 | 3.90s | cut | clip | drift | - | thick syrup | 094_pixabay_pbi1006972.jpg | Pixabay pbi1006972 |
| 95 | 4:47.35 | 2.32s | slide_up | clip | tilt_up | whoosh | blueprint | 095_pixabay_pbi2682641.jpg | Pixabay pbi2682641 |
| 96 | 4:49.67 | 2.43s | cut | clip | push_in | - | inspection steel | 096_pixabay_pb40054.mp4 | Pixabay pb40054 |
| 97 | 4:52.10 | 3.65s | cut | clip | pan_right | - | engineer signing | 097_pixabay_pb136286.mp4 | Pixabay pb136286 |
| 98 | 4:55.75 | 3.06s | zoom | clip | push_in | whoosh | summer street | 098_pixabay_pb124381.mp4 | Pixabay pb124381 |
| 99 | 4:58.81 | 3.54s | cut | clip | pan_left | - | honey sweet | 099_pixabay_pb273476.mp4 | Pixabay pb273476 |
| 100 | 5:02.35 | 3.03s | cut | clip | pull_out | - | old city | 100_pixabay_pb167089.mp4 | Pixabay pb167089 |
| 101 | 5:05.38 | 6.50s | whip_right | clip | pan_right | swish | paris street | 101_pixabay_pb63001.mp4 | Pixabay pb63001 |
| 102 | 5:11.88 | 4.08s | fade | text | drift | shimmer | paris vintage | 102_pixabay_pbi1185804.jpg | Pixabay pbi1185804 |
| 103 | 5:15.95 | 3.94s | cut | clip | drift | - | man reading newspaper | 103_pixabay_pbi1177083.jpg | Pixabay pbi1177083 |
| 104 | 5:19.89 | 2.08s | cut | clip | tilt_up | - | eiffel tower | 104_pixabay_pb212953.mp4 | Pixabay pb212953 |
| 105 | 5:21.97 | 2.54s | cut | clip | push_in | - | rust metal | 105_pixabay_pbi3397227.jpg | Pixabay pbi3397227 |
| 106 | 5:24.51 | 2.48s | cut | clip | pan_right | - | newspaper | 106_pixabay_pbi350376.jpg | Pixabay pbi350376 |
| 107 | 5:26.99 | 1.68s | cut | clip | push_in | - | eiffel tower night | 107_pixabay_pb40645.mp4 | Pixabay pb40645 |
| 108 | 5:28.67 | 2.82s | cut | clip | pan_left | - | old letter stamp | 108_pixabay_pbi1627600.jpg | Pixabay pbi1627600 |
| 109 | 5:31.49 | 4.01s | cut | clip | pull_out | - | typewriter | 109_pixabay_pb150250.mp4 | Pixabay pb150250 |
| 110 | 5:35.50 | 2.61s | whip_left | clip | pan_right | swish | scrap metal | 110_pixabay_pbi1508237.jpg | Pixabay pbi1508237 |
| 111 | 5:38.11 | 2.75s | cut | clip | drift | - | luxury hotel | 111_pixabay_pb246579.mp4 | Pixabay pb246579 |
| 112 | 5:40.86 | 2.22s | cut | clip | tilt_up | - | hotel room vintage | 112_pixabay_pb18897.mp4 | Pixabay pb18897 |
| 113 | 5:43.08 | 4.67s | slide_up | clip | push_in | whoosh | eiffel tower | 113_pixabay_pb213745.mp4 | Pixabay pb213745 |
| 114 | 5:47.75 | 2.30s | cut | clip | pan_right | - | finger on lips | 114_pixabay_pb45288.mp4 | Pixabay pb45288 |
| 115 | 5:50.05 | 3.90s | zoom | clip | push_in | whoosh | businessman vintage | 115_pixabay_pb30852.mp4 | Pixabay pb30852 |
| 116 | 5:53.95 | 3.11s | cut | clip | pan_left | - | paris street | 116_pixabay_pb42052.mp4 | Pixabay pb42052 |
| 117 | 5:57.06 | 4.34s | whip_right | clip | pull_out | swish | money cash | 117_pixabay_pb59134.mp4 | Pixabay pb59134 |
| 118 | 6:01.40 | 4.22s | cut | clip | pan_right | - | money envelope | 118_pixabay_pb174006.mp4 | Pixabay pb174006 |
| 119 | 6:05.62 | 1.99s | cut | clip | drift | - | money hand | 119_pixabay_pb172888.mp4 | Pixabay pb172888 |
| 120 | 6:07.61 | 1.10s | cut | clip | tilt_up | - | steam train | 120_pixabay_pb14953.mp4 | Pixabay pb14953 |
| 121 | 6:08.71 | 3.96s | cut | clip | push_in | - | man embarrassed | 121_pixabay_pb203251.mp4 | Pixabay pb203251 |
| 122 | 6:12.67 | 3.42s | whip_left | clip | pan_right | swish | reading newspaper | 122_pixabay_pb2241.mp4 | Pixabay pb2241 |
| 123 | 6:16.09 | 4.42s | cut | clip | push_in | - | eiffel tower | 123_pixabay_pb21800.mp4 | Pixabay pb21800 |
| 124 | 6:20.51 | 3.30s | slide_up | clip | pan_left | whoosh | police vintage | 124_pixabay_pbi970011.jpg | Pixabay pbi970011 |
| 125 | 6:23.81 | 1.45s | cut | clip | pull_out | - | running street | 125_pixabay_pb21782.mp4 | Pixabay pb21782 |
| 126 | 6:25.26 | 2.09s | cut | clip | pan_right | - | new york city | 126_pixabay_pb219131.mp4 | Pixabay pb219131 |
| 127 | 6:27.35 | 2.20s | cut | clip | drift | - | money printing | 127_pixabay_pb20857.mp4 | Pixabay pb20857 |
| 128 | 6:29.55 | 3.66s | zoom | clip | tilt_up | whoosh | eiffel tower sunset | 128_pixabay_pb203402.mp4 | Pixabay pb203402 |
| 129 | 6:33.21 | 3.60s | cut | clip | push_in | - | eiffel tower | 129_pixabay_pb300038.mp4 | Pixabay pb300038 |
| 130 | 6:36.81 | 2.85s | cut | clip | pan_right | - | eiffel tower night | 130_pixabay_pb106217.mp4 | Pixabay pb106217 |
| 131 | 6:39.66 | 3.75s | whip_right | clip | push_in | swish | jungle | 131_pixabay_pb148042.mp4 | Pixabay pb148042 |
| 132 | 6:43.41 | 3.15s | cut | clip | pan_left | - | jungle dark | 132_pixabay_pbi2181884.jpg | Pixabay pbi2181884 |
| 133 | 6:46.56 | 4.92s | fade | text | drift | shimmer | tropical island | 133_pixabay_pb38461.mp4 | Pixabay pb38461 |
| 134 | 6:51.47 | 4.67s | cut | clip | pull_out | - | tropical island aerial | 134_pixabay_pb386380.mp4 | Pixabay pb386380 |
| 135 | 6:56.14 | 3.49s | cut | clip | pan_right | - | soldier jungle | 135_pixabay_pb61418.mp4 | Pixabay pb61418 |
| 136 | 6:59.63 | 3.50s | cut | clip | drift | - | warships sea | 136_pixabay_pb71402.mp4 | Pixabay pb71402 |
| 137 | 7:03.13 | 2.90s | cut | clip | tilt_up | - | military officer | 137_pixabay_pbi7894287.jpg | Pixabay pbi7894287 |
| 138 | 7:06.03 | 2.69s | cut | clip | push_in | - | jungle sunlight | 138_pixabay_pb12687.mp4 | Pixabay pb12687 |
| 139 | 7:08.72 | 2.05s | whip_left | clip | pan_right | swish | peace dove | 139_pixabay_pb345138.mp4 | Pixabay pb345138 |
| 140 | 7:10.77 | 2.21s | cut | clip | push_in | - | empty beach | 140_pixabay_pb138592.mp4 | Pixabay pb138592 |
| 141 | 7:12.98 | 3.81s | cut | clip | pan_left | - | paper falling | 141_pixabay_pbi1392749.jpg | Pixabay pbi1392749 |
| 142 | 7:16.79 | 1.58s | cut | clip | pull_out | - | jungle | 142_pixabay_pb128746.mp4 | Pixabay pb128746 |
| 143 | 7:18.37 | 3.90s | slide_up | clip | pan_right | whoosh | old letters | 143_pixabay_pb41146.mp4 | Pixabay pb41146 |
| 144 | 7:22.27 | 1.44s | cut | clip | drift | - | jungle | 144_pixabay_pb191354.mp4 | Pixabay pb191354 |
| 145 | 7:23.71 | 2.26s | cut | clip | tilt_up | - | jungle hiding | 145_pixabay_pb74549.mp4 | Pixabay pb74549 |
| 146 | 7:25.97 | 2.49s | cut | clip | push_in | - | dense jungle | 146_pixabay_pbi5061217.jpg | Pixabay pbi5061217 |
| 147 | 7:28.46 | 3.98s | zoom | clip | pan_right | whoosh | philippines village | 147_pixabay_pb334302.mp4 | Pixabay pb334302 |
| 148 | 7:32.44 | 3.57s | cut | clip | push_in | - | island village | 148_pixabay_pb18794.mp4 | Pixabay pb18794 |
| 149 | 7:36.01 | 2.27s | cut | clip | pan_left | - | candle | 149_pixabay_pb165063.mp4 | Pixabay pb165063 |
| 150 | 7:38.28 | 3.59s | whip_right | clip | pull_out | swish | jungle | 150_pixabay_pbi6761846.jpg | Pixabay pbi6761846 |
| 151 | 7:41.87 | 3.05s | cut | clip | pan_right | - | lonely jungle | 151_pixabay_pb239778.mp4 | Pixabay pb239778 |
| 152 | 7:44.92 | 5.94s | cut | clip | drift | - | backpacker travel | 152_pixabay_pb29808.mp4 | Pixabay pb29808 |
| 153 | 7:50.86 | 3.03s | cut | clip | tilt_up | - | backpacker map | 153_pixabay_pb33237.mp4 | Pixabay pb33237 |
| 154 | 7:53.89 | 2.20s | cut | clip | push_in | - | panda | 154_pixabay_pb331151.mp4 | Pixabay pb331151 |
| 155 | 7:56.09 | 2.77s | cut | clip | pan_right | - | snowy mountain | 155_pixabay_pb236232.mp4 | Pixabay pb236232 |
| 156 | 7:58.86 | 2.41s | cut | clip | push_in | - | jungle campfire | 156_pixabay_pb139810.mp4 | Pixabay pb139810 |
| 157 | 8:01.27 | 4.32s | whip_left | clip | pan_left | swish | campfire night | 157_pixabay_pb2170.mp4 | Pixabay pb2170 |
| 158 | 8:05.59 | 3.44s | cut | clip | pull_out | - | jungle | 158_pixabay_pb132204.mp4 | Pixabay pb132204 |
| 159 | 8:09.03 | 4.08s | slide_up | clip | pan_right | whoosh | old bookshop | 159_pixabay_pbi1484941.jpg | Pixabay pbi1484941 |
| 160 | 8:13.11 | 2.13s | cut | clip | drift | - | airplane flying | 160_pixabay_pb9761.mp4 | Pixabay pb9761 |
| 161 | 8:15.24 | 6.74s | cut | clip | tilt_up | - | jungle clearing | 161_pixabay_pbi4365785.jpg | Pixabay pbi4365785 |
| 162 | 8:21.98 | 2.43s | zoom | clip | push_in | whoosh | jungle sunrise | 162_pixabay_pb336591.mp4 | Pixabay pb336591 |
| 163 | 8:24.41 | 3.26s | cut | clip | pan_right | - | sword | 163_pixabay_pb148014.mp4 | Pixabay pb148014 |
| 164 | 8:27.67 | 0.95s | cut | clip | push_in | - | old rifle | 164_pixabay_pb131935.mp4 | Pixabay pb131935 |
| 165 | 8:28.62 | 2.59s | zoom | number | drift | whoosh, tick | jungle | 165_pixabay_pb128756.mp4 | Pixabay pb128756 |
| 166 | 8:31.21 | 2.77s | cut | clip | pan_left | - | jungle mist | 166_pixabay_pb210305.mp4 | Pixabay pb210305 |
| 167 | 8:33.98 | 2.76s | whip_right | clip | pull_out | swish | sunset jungle | 167_pixabay_pbi5061252.jpg | Pixabay pbi5061252 |
| 168 | 8:36.74 | 3.39s | cut | clip | pan_right | - | sunrise sky | 168_pixabay_pb8451.mp4 | Pixabay pb8451 |
| 169 | 8:40.13 | 2.56s | cut | clip | drift | - | sunset sky | 169_pixabay_pb1844.mp4 | Pixabay pb1844 |
| 170 | 8:42.69 | 1.00s | cut | clip | tilt_up | - | emus running | 170_pixabay_pbi10463656.jpg | Pixabay pbi10463656 |
| 171 | 8:43.69 | 1.18s | cut | clip | push_in | - | people dancing | 171_pixabay_pb142029.mp4 | Pixabay pb142029 |
| 172 | 8:44.87 | 1.34s | cut | clip | pan_right | - | brown liquid | 172_pixabay_pb150882.mp4 | Pixabay pb150882 |
| 173 | 8:46.21 | 1.06s | cut | clip | push_in | - | eiffel tower | 173_pixabay_pb34669.mp4 | Pixabay pb34669 |
| 174 | 8:47.27 | 0.96s | cut | clip | pan_left | - | jungle | 174_pixabay_pb37088.mp4 | Pixabay pb37088 |
| 175 | 8:48.23 | 1.59s | cut | clip | pull_out | - | typing phone | 175_pixabay_pb47743.mp4 | Pixabay pb47743 |
| 176 | 8:49.82 | 3.43s | whip_left | clip | pan_right | swish | clock | 176_pixabay_pb50803.mp4 | Pixabay pb50803 |
| 177 | 8:53.25 | 1.57s | cut | clip | drift | - | old church | 177_pixabay_pb32596.mp4 | Pixabay pb32596 |
| 178 | 8:54.82 | 3.33s | cut | clip | tilt_up | - | storm clouds | 178_pixabay_pb16495.mp4 | Pixabay pb16495 |
| 179 | 8:58.15 | 4.37s | fade | text | drift | shimmer | sunset sky | 179_pixabay_pb264468.mp4 | Pixabay pb264468 |

Page links for every original are in `05_ORIGINAL_SOURCES/stock_sources.csv`.

Stock footage licences: Pexels and Pixabay content licences (free to use and edit, no credit needed). No news photos and no copyrighted archive footage were used.

## How to rebuild or change it

1. Put `03_VIDEO_ONLY/video_ONLY_no_voice_no_music_no_captions.mp4` on video track 1 (or the separate shots).
2. Add `02_AUDIO/voice_FULL_lined_up_to_video.wav` at 0:00. It is already in sync.
3. Add `02_AUDIO/sound_effects.wav` at 0:00 and `02_AUDIO/music_ducked.wav` at 0:00 (or rebuild the music from `music_tracks/` using the times in `music_sections.json`).
4. Add captions: `04_ELEMENTS/overlays_transparent/captions_transparent.mov` on top, or import `captions_animated.ass` / `captions_plain.srt`.
5. Export 1920x1080, 30 fps, and level the mix to -14 LUFS.

To swap a shot: find it in the shot list, take another clip (or another part of the original), keep the same start and length.

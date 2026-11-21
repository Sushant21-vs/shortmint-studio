# ShortMint Studio v33 — Automatic Captions + Six Narrator Voices

Built on **v32** (right-aligned header, v31 banner removal, v30 Settings). Existing accounts, project tools, promo codes, and credit logic are preserved.

## Features

**Speech → Text (optional)**
- Existing subtitle editor accepts editable .srt uploads, typed SRT, or one-click **Speech → Text**.
- New **Auto-caption when exporting** checkbox: when enabled and the subtitle field is empty, the video speech is transcribed before Short export.
- Generated captions use source-video timestamps and remain editable. Exports burn subtitles into finished MP4s using the existing rendering system.
- Runs in one of two modes: `OPENAI_API_KEY` (cloud Whisper API; good for lightweight Render instances) or optional locally installed `faster-whisper` (requires more RAM and CPU). Cloud audio is transmitted to the API provider only when requested.
- Cloud captioning is limited to **30 minutes per source video**, **3 jobs per account per hour**. This protects the owner from unlimited billable API requests.

**Text → Voice (optional)**
- Six preconfigured English voices (online neural speech service):
  - Female: **Ava** (warm), **Jenny** (bright), **Aria** (expressive).
  - Male: **Andrew** (natural), **Guy** (energetic), **Brian** (smooth).
- Select one of the six cards, type up to 2,000 characters, press **Preview selected voice** (previews use up to the first 300 characters), play/download the MP3, then optionally check **Include a voiceover in my exported Short**.
- **Replace original sound** or **Mix with original (22% volume)**. Narration is embedded in the exported MP4, even for multi-cut montages and cut lists.
- A narration script starts at the beginning of *each* exported Short. It must be no longer than the shortest Short; otherwise export fails with an explanatory error and any reserved member export credits are returned.
- **Use subtitle text** copies recognized words into the narration field. Check and shorten the script; source captions can be much longer than the exported Short.
- Voice previews are limited to **10 requests per account per 15 minutes**; generation is processed one request at a time.

## Install from the replacement ZIP

Replace the following GitHub paths with the included new versions:

```
app.py
voice_tools.py                 (new)
requirements.txt              (adds edge-tts and httpx)
.env.example                   (example config only)
static/index.html
static/app.js
static/voice-studio-v33.css   (new)
static/voice-studio-v33.js    (new)
static/privacy.html
UPDATE_V33_SPEECH_TO_TEXT_AND_6_VOICES.md
```

Commit to GitHub and let Render rebuild the Docker image. Installing `requirements.txt` during the rebuild is necessary; uploading only HTML/CSS will leave audio endpoints unavailable. Hard refresh the website after deployment.

## Enable hosted transcription in Render

1. Open your Render web service → **Environment** → **Add Environment Variable**.
2. Name: **`OPENAI_API_KEY`**.
3. Value: an API key generated in the API provider's account, with billing and usage limits configured. **Do not paste the key into GitHub, source files or the browser.**
4. Save/redeploy. Speech → Text and automatic export captions should then be available after restart.

**Important:** API transcription is a *paid third-party service* billed to the **site owner**, not included in the user's ChatGPT subscription. The API owner should set a spend limit and monitor usage. Audio from videos explicitly submitted for cloud transcription is transmitted to the API provider; inform users and obtain appropriate consent. Users must own or have permission to process the media. No key means the site can still export video and manually supplied subtitles, but cloud auto captions are unavailable.

### Alternative: self-hosted transcription

Install `requirements-auto-captions.txt` on an adequately sized CPU server, or build with the existing Docker build arg `WITH_AUTO_CAPTIONS=1`. The tiny speech model downloads at first use. This is **not recommended on Render Free** due to RAM, CPU and cold-start limits. No cloud API key is then needed.

## Text-to-speech deployment notes

`edge-tts` is installed by default with `requirements.txt` and uses an external online speech service. It needs outbound network access and may be unavailable or rate-limited; voice previews and narrated exports will show an error if that happens. Verify your intended use complies with the service provider's usage terms. For a commercial high-traffic platform, consider migrating to a contracted, rate-limited paid TTS API.

## Existing behavior and limitations

- User credit charging stays **1 credit per completed Short** for non-owner users; previewing voices and creating subtitles does not directly use Short credits. A failed narrated export refunds its reserved Short credits.
- On Render Free, **uploaded source videos and exported MP4s remain ephemeral**. Always download finished work.
- Spoken captions can contain transcription mistakes. Review them before publishing.
- These six selected voices are US-English presets. Do not rely on them for multilingual narration without testing pronunciation and provider voice support.
- Testing: 46 passing automated tests including a real FFmpeg MP4 voice mix with a mocked speech synthesizer. This does **not** prove the online neural voice service or a paid cloud API key will work on your Render deployment; test both after configuration.

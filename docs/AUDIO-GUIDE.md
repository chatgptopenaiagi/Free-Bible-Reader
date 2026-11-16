# Reading aloud

FREE BIBLE READER prepares speech on your Windows PC. You can hear selected words, a verse, a verse range, a chapter, several chapters or the current book. A voice reads the original selected edition's text; changing the interface language does not translate Scripture.

## Start with a short passage

1. Choose an edition, book and chapter.
2. Select a verse, or highlight the exact words you want to hear.
3. Choose **Audio → Read aloud**, use the selection's right-click reading action, or press **Play** in the bottom player.
4. Use **Pause** to hold your place, **Play** to continue and **Stop** to finish.

If no words or verse are selected, the ordinary Play action uses the first verse in the current chapter. It does not silently start the whole book. To choose a larger scope, open **Audio → Playback settings** or the player's settings button. The available scopes are Selected text, Selected verse, Verse range in this chapter, Current chapter, Chapter range in this book and Whole current book. Confirm the displayed first/last verse or chapter before choosing **Start reading aloud**.

The player remains at the bottom of the screen. On a narrow screen, engine and voice selectors may be hidden to leave room for playback buttons; the Audio menu and Playback settings still provide access to voice choices. The controls have accessible names as well as symbols.

## Choose a voice

Open **Audio → Voice Manager**. Filter by language or name, enter a short preview sentence if desired and choose **Voice preview** on an available voice. The list distinguishes **Available offline** from **Download required**. Selecting a voice does not change your Bible edition.

| Speech engine | What is available |
|---|---|
| Windows · SAPI | Voices already installed for the older Windows speech interface. On the tested PC, David Desktop and Zira Desktop were available in English. |
| Windows · modern voices | Voices discovered through the modern Windows speech interface. Availability can differ from SAPI. |
| Piper · neural offline speech | Optional downloaded voices. Romanian Mihai, English Joe and German Thorsten are offered by this version's verified voice catalog. |
| eSpeak NG · compact offline speech | The included lightweight fallback, including Romanian. It needs no neural-model download. Its sound differs from a neural voice. |

Windows voice availability depends on your PC. The application does not pretend a Romanian Windows voice exists when none is installed. **Open Windows voice settings** opens the relevant Windows settings; Windows manages those installations. Return to Voice Manager and choose **Refresh voices** afterward.

The app retains a valid installed voice you chose. Without one, it prefers a matching installed Piper voice, then suitable Windows speech, then an available eSpeak fallback. Fresh English on the tested PC selected SAPI David Desktop. Romanian uses installed Mihai when available, or Romanian eSpeak otherwise. Always preview the selected voice to judge its pronunciation and your audio output.

## Install Romanian Mihai

1. Connect to the internet and open **Voice Manager**.
2. Filter for **Mihai** or **Romanian**.
3. Choose **Download voice** on the Piper Mihai card. The progress display shows the download; you can cancel it.
4. Wait for **Voice installed and integrity verified**, then try **Voice preview**.
5. Select Piper and Mihai for reading aloud.

Mihai's model and accompanying configuration/card require about 63.3 MB in decimal units, or 60.3 MiB, plus temporary space during installation. The application checks the expected byte counts and SHA-256 values before enabling the downloaded voice. A failed or cancelled download is not marked installed. Closing Voice Manager cancels an active voice download.

The voice is saved in your separate local application data, normally `%LOCALAPPDATA%\FreeBibleReader\studio\voices`, not inside the program installation directory. A deliberately selected verification or portable profile uses its own studio folder. The installer does not contain downloaded neural models. English Joe and German Thorsten are optional downloads through the same manager; they are not installed automatically.

To remove a downloaded voice, choose its **Remove voice** action and confirm. This removes that managed model, not your Scripture, notes or bookmarks. Windows and bundled eSpeak voices are not removed through this action. If an unexpected extra file is present in a managed voice folder, the application preserves it and reports the problem rather than deleting unrelated files.

## Playback settings and long reading

Speaking speed ranges from 0.5× to 2×; volume ranges from 0% to 100%. Your system output device and Windows volume also affect what you hear. Changing speed during playback prepares the current source unit again at the new speed.

For chapters and books, the app prepares one verse at a time and moves forward after each clip ends. It does not download or generate an entire audiobook in advance. Previous/Next move within the chosen reading scope. While narration follows another chapter, the reader opens that edition's actual chapter and highlights the unit being read. Native labels and verse boundaries remain those of the selected source.

**Pause** also works while audio is being prepared: the clip waits for Play. **Stop** cancels pending speech and clears the narration highlight. Preparing a new passage or switching voices stops the earlier queue. If your browser blocks automatic playback, the status can say the audio is ready; press Play after interacting with the page.

Generated clips form a bounded temporary cache: at most 256 MiB and 100 WAV/metadata files. Old completed clips can be removed automatically; they are not a permanent recording library. The newest/current clip and files currently in use are protected where possible. A full or locked cache produces a visible error rather than unlimited growth. This cleanup does not delete voice models or personal documents.

## Offline use and privacy

After installation, eSpeak and available Windows voices work locally. Piper also works locally after its selected voice has been downloaded. Speech synthesis does not send the reading text to an online speech service. A deliberate voice download contacts the catalog's official model host; installing additional Windows voices uses Windows settings and its own network behavior.

The player receives generated WAVs from the application's loopback address. Clips and their metadata remain in the selected local studio profile. Speed, volume and the last voice choice are saved separately in the browser's local site storage; another browser profile or origin can have different preferences. Clearing that site data removes those browser preferences, not the downloaded voice files.

## If you do not hear speech

- Preview a short sentence and check Windows output device, Windows volume and the app volume.
- Confirm the voice says Available offline. Download a missing Piper voice or choose bundled eSpeak.
- If a saved voice disappeared, refresh the catalog and choose a currently available voice.
- If another speech operation is finishing, wait briefly and try again. Stop an unwanted reading queue first.
- For a very long selected passage, choose a shorter selection or the chapter/book scope, which handles one verse per clip.
- An integrity error means the downloaded model was not enabled; use Voice Manager to remove/reinstall the incomplete managed voice if offered.

Successful WAV generation and moving playback time do not by themselves prove that your speakers are audible or that every word is pronounced correctly. Preview your preferred voice with a familiar passage. The available voices, their licenses and software attribution are described in [the speech component notices](../licenses/TTS-SOURCES.md).

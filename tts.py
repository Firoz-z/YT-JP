import asyncio
import edge_tts

# Japanese voices: ja-JP-NanamiNeural (female), ja-JP-KeitaNeural (male)
VOICE_JP = "ja-JP-NanamiNeural"
VOICE_EN = "en-US-AriaNeural"


async def _speak(text: str, path: str, voice: str, rate: str = "+0%") -> None:
    await edge_tts.Communicate(text, voice, rate=rate).save(path)


def generate_speech(text: str, path: str, rate: str = "+0%",
                    lang: str = "jp") -> None:
    voice = VOICE_JP if lang == "jp" else VOICE_EN
    asyncio.run(_speak(text, path, voice, rate))

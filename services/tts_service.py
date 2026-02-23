"""
TTSService — Text-to-Speech for the Virtual Interviewer.

Primary:  OpenAI TTS API (high-quality, natural voices)
Fallback: gTTS (Google Text-to-Speech, free, no API key needed)

Set OPENAI_API_KEY in your .env to use the high-quality voice.
If the key is missing, gTTS is used automatically.
"""

import os
import io
from dotenv import load_dotenv

load_dotenv()


class TTSService:
    def __init__(self):
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.mode = "openai" if self.openai_key else "gtts"
        print(f"🔊 TTS Service initialized — using {'OpenAI TTS' if self.mode == 'openai' else 'gTTS (free fallback)'}.")

    def synthesize(self, text: str, voice: str = "onyx") -> bytes | None:
        """
        Converts text to MP3 audio bytes.

        Args:
            text:  The question/sentence to speak.
            voice: OpenAI voice name (onyx sounds professional/authoritative).
                   Options: alloy, echo, fable, onyx, nova, shimmer

        Returns:
            MP3 bytes on success, None on failure.
        """
        if self.mode == "openai":
            return self._synthesize_openai(text, voice)
        else:
            return self._synthesize_gtts(text)

    def _synthesize_openai(self, text: str, voice: str) -> bytes | None:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.openai_key)
            response = client.audio.speech.create(
                model="tts-1",          # tts-1-hd for higher quality (slower)
                voice=voice,
                input=text,
                response_format="mp3"
            )
            return response.content
        except Exception as e:
            print(f"❌ OpenAI TTS Error: {e}. Falling back to gTTS.")
            return self._synthesize_gtts(text)

    def _synthesize_gtts(self, text: str) -> bytes | None:
        try:
            from gtts import gTTS
            tts = gTTS(text=text, lang='en', slow=False)
            buf = io.BytesIO()
            tts.write_to_fp(buf)
            buf.seek(0)
            return buf.read()
        except Exception as e:
            print(f"❌ gTTS Error: {e}")
            return None


# --- TEST ---
if __name__ == "__main__":
    svc = TTSService()
    sample = "Hello! Welcome to your technical interview. Please tell me about yourself."
    audio = svc.synthesize(sample)
    if audio:
        with open("test_tts_output.mp3", "wb") as f:
            f.write(audio)
        print(f"✅ Audio saved: {len(audio)} bytes → test_tts_output.mp3")
    else:
        print("❌ TTS failed.")
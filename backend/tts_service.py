import edge_tts
import os
from loguru import logger

class TTSService:
    @staticmethod
    async def generate_speech(text: str, voice: str, output_path: str):
        try:
            logger.info(f"Generating speech for: {text[:50]}...")
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(output_path)
            return output_path
        except Exception as e:
            logger.error(f"TTS Service Error: {e}")
            raise e

    @staticmethod
    async def list_voices():
        voices = await edge_tts.VoicesManager.create()
        return voices.voices

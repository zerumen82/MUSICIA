from pydub import AudioSegment
import os
from loguru import logger

class MixerService:
    @staticmethod
    def mix_tracks(base_track_path: str, vocal_track_path: str, output_path: str, base_volume=0, vocal_volume=0):
        """
        Mixes two tracks with individual volume adjustments (in dB).
        """
        try:
            logger.info(f"Mixing {base_track_path} and {vocal_track_path}")
            
            base = AudioSegment.from_file(base_track_path)
            vocal = AudioSegment.from_file(vocal_track_path)
            
            # Apply volumes
            base = base + base_volume
            vocal = vocal + vocal_volume
            
            # Overlay (vocal over base)
            # We can loop the base if it's shorter, or just mix
            combined = base.overlay(vocal)
            
            combined.export(output_path, format="mp3")
            return output_path
        except Exception as e:
            logger.error(f"Mixer Service Error: {e}")
            raise e

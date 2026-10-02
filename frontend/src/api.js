/**
 * Cliente HTTP del backend de Musicia.
 *
 * La URL base viene del entorno (VITE_API_BASE_URL) con un valor por defecto
 * para desarrollo local. Ningún componente debe escribir la URL a mano.
 */
import axios from 'axios'

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'

/** Cadencia de consulta del estado de una generación (ms). */
export const JOB_POLL_INTERVAL_MS = 3000

const client = axios.create({ baseURL: API_BASE_URL, timeout: 30000 })

/**
 * El LM local del motor tarda bastante en componer una letra (carga el modelo
 * la primera vez y luego generates). Con el timeout normal de 30 s el botón
 * "escribir la letra por mí" moria siempre, así que usa su propio cliente.
 */
export const LYRICS_TIMEOUT_MS = 300000
const lyricsClient = axios.create({ baseURL: API_BASE_URL, timeout: LYRICS_TIMEOUT_MS })

/** Las operaciones de estudio (análisis rítmico, separación) tardan minutos. */
export const STUDIO_TIMEOUT_MS = 900000
const slowClient = axios.create({ baseURL: API_BASE_URL, timeout: STUDIO_TIMEOUT_MS })

const describeError = (error) => {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string') return detail
  return error?.message ?? 'Error desconocido'
}

export const api = {
  engineHealth: async () => {
    try {
      const { data } = await client.get('/health')
      return data
    } catch (error) {
      return { api: 'error', engine: { reachable: false, error: describeError(error) } }
    }
  },

  musicConfig: async () => {
    const { data } = await client.get('/music/config')
    return data
  },

  generateMusic: async (payload) => {
    try {
      const { data } = await client.post('/music/generate', payload)
      return data
    } catch (error) {
      throw new Error(describeError(error))
    }
  },

  /** Letra automática con el LM local del motor (borrador editable). */
  writeLyrics: async (payload) => {
    try {
      const { data } = await lyricsClient.post('/music/write_lyrics', payload)
      return data
    } catch (error) {
      throw new Error(describeError(error))
    }
  },

  /** Propuesta de cuadre de tempo/fase de una pareja de pistas (sin mezclar). */
  mixPlan: async (payload) => {
    try {
      const { data } = await slowClient.post('/audio/mix/plan', payload)
      return data
    } catch (error) {
      throw new Error(describeError(error))
    }
  },

  /** ¿Está instalado el motor de separación de voces? */
  separateStatus: async () => {
    try {
      const { data } = await slowClient.get('/audio/separate/status')
      return data
    } catch (error) {
      return { available: false, device: 'cpu', message: describeError(error) }
    }
  },

  /** Extrae voces y base de una pista (motor local; tarda minutos). */
  separate: async (payload) => {
    try {
      const { data } = await slowClient.post('/audio/separate', payload)
      return data
    } catch (error) {
      throw new Error(describeError(error))
    }
  },

  /** Tempo y fase del golpe de una pista. */
  groove: async (name) => {
    try {
      const { data } = await slowClient.get(`/audio/groove/${encodeURIComponent(name)}`)
      return data
    } catch (error) {
      throw new Error(describeError(error))
    }
  },

  /** Fuerza el tempo: 'half' | 'double' | 'bpm' (medio/doble tiempo para bootlegs). */
  setTempo: async (payload) => {
    try {
      const { data } = await slowClient.post('/audio/tempo', payload)
      return data
    } catch (error) {
      throw new Error(describeError(error))
    }
  },

  /** Exporta un loop de la pista. */
  makeLoop: async (payload) => {
    try {
      const { data } = await slowClient.post('/audio/loop', payload)
      return data
    } catch (error) {
      throw new Error(describeError(error))
    }
  },

  /** Funde varias pistas igualando tempo y nivel (mezcla de DJ). */
  crossfade: async (payload) => {
    try {
      const { data } = await slowClient.post('/audio/crossfade', payload)
      return data
    } catch (error) {
      throw new Error(describeError(error))
    }
  },

  /** Remix con IA: base nueva desde prompt + voz original (con job). */
  remixAi: async (payload) => {
    try {
      const { data } = await slowClient.post('/audio/remix/ai', payload)
      return data
    } catch (error) {
      throw new Error(describeError(error))
    }
  },

  remixAiStatus: async (jobId) => {
    try {
      const { data } = await slowClient.get(`/audio/remix/ai/${jobId}`)
      return data
    } catch (error) {
      throw new Error(describeError(error))
    }
  },

  musicStatus: async (jobId) => {
    try {
      const { data } = await client.get(`/music/status/${jobId}`)
      return data
    } catch (error) {
      throw new Error(describeError(error))
    }
  },

  audioUrl: (name) => `${API_BASE_URL}/music/audio/${encodeURIComponent(name)}`,

  /** Biblioteca: MP3 reales en backend/outputs/ */
  library: async () => {
    try {
      const { data } = await client.get('/music/library')
      return data
    } catch (error) {
      throw new Error(describeError(error))
    }
  },

  deleteAudio: async (name) => {
    try {
      const { data } = await client.delete(`/music/audio/${encodeURIComponent(name)}`)
      return data
    } catch (error) {
      throw new Error(describeError(error))
    }
  },

  /** Renombra una pista (biblioteca o subida). Si el nombre existe, la app numera. */
  renameAudio: async (name, newName) => {
    try {
      const { data } = await client.patch(`/music/audio/${encodeURIComponent(name)}`, { new_name: newName })
      return data
    } catch (error) {
      throw new Error(describeError(error))
    }
  },

  /** Post-proceso real: gain (dB), fades (ms) y recorte (s). */
  processAudio: async (payload) => {
    try {
      const { data } = await client.post('/audio/process', payload, { timeout: 120000 })
      return data
    } catch (error) {
      throw new Error(describeError(error))
    }
  },

  /** Sube un MP3/WAV y devuelve el análisis DSP + hipótesis (música/voz/mixta). */
  uploadAudio: async (file, onProgress) => {
    const form = new FormData()
    form.append('file', file)
    try {
      const { data } = await client.post('/audio/upload', form, {
        timeout: 120000,
        onUploadProgress: onProgress,
      })
      return data
    } catch (error) {
      throw new Error(describeError(error))
    }
  },

  /** Lista los audios subidos. */
  uploads: async () => {
    try {
      const { data } = await client.get('/audio/uploads')
      return data
    } catch (error) {
      throw new Error(describeError(error))
    }
  },

  uploadUrl: (name) => `${API_BASE_URL}/audio/uploads/file/${encodeURIComponent(name)}`,

  deleteUpload: async (name) => {
    try {
      const { data } = await client.delete(`/audio/uploads/${encodeURIComponent(name)}`)
      return data
    } catch (error) {
      throw new Error(describeError(error))
    }
  },

  /** Remix DSP real: tempo, pitch, reverse, gain, fades, recorte. */
  remix: async (payload) => {
    try {
      const { data } = await client.post('/audio/remix', payload, { timeout: 300000 })
      return data
    } catch (error) {
      throw new Error(describeError(error))
    }
  },

  /** Mejora un prompt con reglas de producción local (determinista). */
  enhancePrompt: async (payload) => {
    try {
      const { data } = await client.post('/music/enhance_prompt', payload)
      return data
    } catch (error) {
      throw new Error(describeError(error))
    }
  },

  /** Prompt sugerido para remixar/re-crear un audio subido (desde su análisis). */
  remixPrompt: async (payload) => {
    try {
      const { data } = await client.post('/audio/remix_prompt', payload)
      return data
    } catch (error) {
      throw new Error(describeError(error))
    }
  },

  /** Cola de trabajos de la sesión (activos primero). */
  musicJobs: async () => {
    try {
      const { data } = await client.get('/music/jobs')
      return data
    } catch (error) {
      throw new Error(describeError(error))
    }
  },

  /** Picos de amplitud para la forma de onda (buckets entre 50 y 2000). */
  audioPeaks: async (name, buckets = 400) => {
    try {
      const { data } = await client.get(`/audio/peaks/${encodeURIComponent(name)}?buckets=${buckets}`)
      return data
    } catch (error) {
      throw new Error(describeError(error))
    }
  },

  /** Mezcla real de 2 pistas con ganancias en dB (/audio/mix ya existía). */
  mixTracks: async (payload) => {
    try {
      const { data } = await client.post('/audio/mix', payload, { timeout: 120000 })
      return data
    } catch (error) {
      throw new Error(describeError(error))
    }
  },
}

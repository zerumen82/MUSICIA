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

/** Cortes seguidos del sondeo antes de dar el trabajo local por perdido. */
export const JOB_POLL_MAX_MISSES = 5

/**
 * Tope del chequeo de la pastilla. Tiene que ser mayor que
 * `acestep.health_timeout` (3 s): así un motor apagado contesta
 * "no está" y un silencio de la API no se confunde con eso.
 */
export const HEALTH_PROBE_MS = 8000

/**
 * El envío espera a la API, y la API espera al motor hasta request_timeout (60 s).
 * Tiene que ser mayor que esos 60 s: si no, axios corta antes y enseña su texto.
 */
export const GENERATE_SUBMIT_TIMEOUT_MS = 90000

/**
 * Corte de red o de tiempo. No es un fallo del trabajo: la pantalla no lo pinta.
 * Axios dice «timeout of 30000ms exceeded» cuando su reloj acaba antes que la API.
 */
export const isTransportBlip = (message) =>
  /no responde|respuesta ilegible|timeout of \d+ms exceeded|timeout exceeded|tardó demasiado|Network Error|ECONNABORTED|ECONNREFUSED/i.test(message ?? '')

export const isEnginePollBlip = isTransportBlip

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
  const message = error?.message ?? ''
  if (!error?.response && /timeout/i.test(message)) return 'La API tardó demasiado en contestar.'
  if (!error?.response && /Network Error|ECONNREFUSED|ECONNABORTED/i.test(message)) return 'La API no contesta.'
  return message || 'Error desconocido'
}

export const api = {
  engineHealth: async () => {
    try {
      const { data } = await client.get('/health', { timeout: HEALTH_PROBE_MS })
      return data
    } catch (error) {
      // Sin respuesta HTTP la API no ha dicho que el motor esté apagado.
      const noAnswer = !error?.response
      return {
        api: 'error',
        engine: { reachable: false, unknown: noAnswer, error: describeError(error) },
      }
    }
  },

  musicConfig: async () => {
    const { data } = await client.get('/music/config')
    return data
  },

  /** Modelo residente. No cambia el que está en la GPU. */
  musicModels: async () => {
    try {
      const { data } = await client.get('/music/models', { timeout: HEALTH_PROBE_MS })
      return data
    } catch {
      return null
    }
  },

  generateMusic: async (payload) => {
    try {
      const { data } = await client.post('/music/generate', payload, { timeout: GENERATE_SUBMIT_TIMEOUT_MS })
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

  /** Extrae voces y base. La API responde al momento y este cliente espera el job. */
  separate: async (payload, onUpdate) => {
    try {
      const { data: started } = await client.post('/audio/separate', payload)
      const jobId = started.job_id
      let misses = 0
      for (;;) {
        try {
          const { data: job } = await client.get(`/audio/separate/${jobId}`)
          misses = 0
          if (typeof onUpdate === 'function') onUpdate(job)
          if (job.status === 'succeeded') return job
          if (job.status === 'failed') {
            const failed = new Error(job.error ?? 'La separación falló')
            failed.hard = true
            throw failed
          }
        } catch (error) {
          if (error.hard) throw error
          const message = describeError(error)
          const gone = /no existe|no encontrada/i.test(message)
          misses += 1
          if (gone || misses >= JOB_POLL_MAX_MISSES) throw new Error(message)
        }
        await new Promise((r) => setTimeout(r, JOB_POLL_INTERVAL_MS))
      }
    } catch (error) {
      if (error.hard) throw error
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

  /** Funde varias pistas. El tempo solo se iguala si el ajuste es pequeño. */
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
  renameAudio: async (name, newName, sourceKind = null) => {
    try {
      const { data } = await client.patch(`/music/audio/${encodeURIComponent(name)}`, { new_name: newName, source_kind: sourceKind })
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

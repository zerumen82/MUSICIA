export function canAttemptEngineOperation(engine) {
  return Boolean(engine?.ok || engine?.idle || engine?.starting || engine?.error)
}

export function generationWaitMessage(job, engine) {
  if (job?.status !== 'queued' || job.job_id) return null
  if (engine?.starting) {
    return 'Conectando con el modelo; espera. El primer arranque puede tardar varios minutos.'
  }
  return 'Esperando respuesta del motor para iniciar la generación…'
}

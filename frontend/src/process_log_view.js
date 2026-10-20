export function currentProcessLogStreams(streams) {
  return streams.map((stream) => Object.fromEntries(
    Object.entries(stream).filter(([key]) => key !== 'backup_present' && key !== 'backup_text'),
  ))
}

import { api } from '@/api/client'

function filenameFrom(disposition: string | undefined, fallback: string): string {
  const match = /filename="?([^";]+)"?/i.exec(disposition ?? '')
  return match?.[1] ?? fallback
}

/** Fetch with the auth header (a plain <a href> can't send it), then open or save the file. */
export async function openFile(url: string, params: Record<string, unknown> = {}, fallbackName = 'download') {
  const res = await api.get<Blob>(url, { params, responseType: 'blob' })
  const blob = res.data
  const objectUrl = URL.createObjectURL(blob)
  const name = filenameFrom(res.headers['content-disposition'], fallbackName)
  if (blob.type === 'application/pdf') {
    window.open(objectUrl, '_blank', 'noopener')
  } else {
    const a = document.createElement('a')
    a.href = objectUrl
    a.download = name
    a.click()
  }
  setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000)
}

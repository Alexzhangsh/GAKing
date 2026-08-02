// @ai-generated
class CdnUrlUtil {
  private static cdnDomain: string = ''

  static setDomain(domain: string) {
    this.cdnDomain = domain
  }

  static getDomain(): string {
    return this.cdnDomain || 'https://cdn.example.com'
  }

  static buildUrl(path: string, width?: number, height?: number): string {
    if (!path) return ''
    
    if (path.startsWith('http://') || path.startsWith('https://')) {
      return path
    }

    let url = `${this.getDomain()}${path.startsWith('/') ? '' : '/'}${path}`
    
    if (width || height) {
      const sizeParam = []
      if (width) sizeParam.push(`w=${width}`)
      if (height) sizeParam.push(`h=${height}`)
      url += (url.includes('?') ? '&' : '?') + sizeParam.join('&')
    }

    return url
  }

  static buildImageUrl(path: string, options?: {
    width?: number
    height?: number
    mode?: 'fit' | 'fill' | 'cover'
    quality?: number
  }): string {
    if (!path) return ''

    if (path.startsWith('http://') || path.startsWith('https://')) {
      return path
    }

    let url = `${this.getDomain()}${path.startsWith('/') ? '' : '/'}${path}`
    const params: string[] = []

    if (options?.width) params.push(`w=${options.width}`)
    if (options?.height) params.push(`h=${options.height}`)
    if (options?.mode) params.push(`m=${options.mode}`)
    if (options?.quality) params.push(`q=${options.quality}`)

    if (params.length > 0) {
      url += (url.includes('?') ? '&' : '?') + params.join('&')
    }

    return url
  }

  static buildThumbnailUrl(path: string, size: number = 100): string {
    return this.buildImageUrl(path, { width: size, height: size, mode: 'fit', quality: 80 })
  }

  static buildCoverUrl(path: string, width: number, height: number): string {
    return this.buildImageUrl(path, { width, height, mode: 'cover', quality: 85 })
  }

  static buildFitUrl(path: string, width: number, height: number): string {
    return this.buildImageUrl(path, { width, height, mode: 'fit', quality: 90 })
  }
}

export default CdnUrlUtil
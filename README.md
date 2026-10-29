# Web de Urbex en Moto

Web estática del canal. Los vídeos y los Shorts se actualizan solos: una GitHub Action lee cada hora el feed público del canal (sin clave de API), regenera `videos.json` y, si hay algo nuevo, hace commit. Cloudflare Pages publica cada commit automáticamente.

## Archivos

| Archivo | Para qué sirve |
|---|---|
| `index.html` | La web. Pinta los vídeos leyendo `videos.json`. |
| `videos.json` | Lista de vídeos. Lo reescribe la Action; no hace falta tocarlo. |
| `scripts/update_videos.py` | Lee el feed RSS del canal y genera `videos.json`. |
| `.github/workflows/update-videos.yml` | Lanza el script cada hora. |

## Puesta en marcha

### 1. Subir el proyecto a GitHub
1. Crea un repositorio nuevo (por ejemplo `urbex-en-moto-web`).
2. Sube todos los archivos de esta carpeta, incluida la carpeta oculta `.github`.

### 2. Dejar que la Action pueda guardar cambios
1. En el repositorio: **Settings → Actions → General → Workflow permissions**.
2. Marca **Read and write permissions** y guarda.
3. Ve a la pestaña **Actions**, abre **Actualizar vídeos** y pulsa **Run workflow** para la primera carga.

### 3. Publicar en Cloudflare Pages
1. En Cloudflare: **Workers & Pages → Create → Pages → Connect to Git** y elige el repositorio.
2. Framework preset: **None**. Build command: vacío. Build output directory: `/`.
3. Al terminar tendrás la web en una dirección `*.pages.dev`.

### 4. Conectar el dominio
1. Compra el dominio. Un `.com` se puede comprar directamente en Cloudflare (Domain Registration). Un `.es` hay que comprarlo en un registrador que venda `.es`.
2. En el proyecto de Pages: **Custom domains → Set up a custom domain** y escribe el dominio.
3. Si el dominio no está en Cloudflare, cambia sus servidores DNS (nameservers) a los que te indique Cloudflare. Tarda desde minutos hasta unas horas.

## Probar en local

```bash
python3 scripts/update_videos.py   # actualiza videos.json
python3 -m http.server 8000        # abre http://localhost:8000
```

Abrir `index.html` con doble clic no carga los vídeos: el navegador bloquea leer `videos.json` desde el disco. Usa el servidor local.

## Cosas pendientes
- Cambiar `correo@pendiente.com` por el correo real del canal (en `index.html`).
- Añadir enlaces a Instagram o TikTok en el pie si los tenéis.

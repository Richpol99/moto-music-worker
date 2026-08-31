import os
import asyncio
from aiohttp import web
import subprocess

RCLONE_CONFIG_DATA = os.environ.get("RCLONE_CONFIG_DATA", "")
YOUTUBE_COOKIES = os.environ.get("YOUTUBE_COOKIES", "")

# Escribir rclone config reconstruyendo lineas rotas por el navegador de la tablet
os.makedirs("/root/.config/rclone", exist_ok=True)

lines = RCLONE_CONFIG_DATA.splitlines()
clean_lines = []
for line in lines:
    line = line.strip()
    if not line:
        continue
    # Si la linea empieza por [ o contiene = es una linea nueva de config
    if line.startswith("[") or "=" in line:
        clean_lines.append(line)
    else:
        # Si no tiene =, es porque el navegador la envolvió y se rompió del renglon anterior
        if clean_lines:
            clean_lines[-1] += line

with open("/root/.config/rclone/rclone.conf", "w") as f:
    f.write("\n".join(clean_lines) + "\n")

# Escribir cookies si existen
cookies_file = "/tmp/cookies.txt"
if YOUTUBE_COOKIES:
    with open(cookies_file, "w") as f:
        f.write(YOUTUBE_COOKIES)

async def handle_cache(request):
    video_id = request.query.get("id", "").strip()
    if not video_id:
        return web.json_response({"success": False, "error": "ID requerido"}, status=400)

    print(f"Descargando y subiendo {video_id} a Google Drive...")
    
    # Si tenemos cookies, las pasamos a yt-dlp
    cookies_arg = f"--cookies {cookies_file}" if os.path.exists(cookies_file) else ""
    cmd = f"yt-dlp {cookies_arg} -f 140 -o - 'https://www.youtube.com/watch?v={video_id}' | rclone rcat gdrive:music_cache/{video_id}.m4a"
    
    proc = await asyncio.create_subprocess_shell(
        cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
    )
    _, stderr = await proc.communicate()
    
    if proc.returncode == 0:
        print(f"¡Éxito! Song {video_id} guardada en GDrive.")
        return web.json_response({"success": True, "message": "Song cached successfully"})
    else:
        err_msg = stderr.decode().strip()
        print(f"Error descargando {video_id}: {err_msg}")
        proc_del = await asyncio.create_subprocess_exec(
            "rclone", "deletefile", f"gdrive:music_cache/{video_id}.m4a"
        )
        await proc_del.wait()
        return web.json_response({"success": False, "error": err_msg}, status=500)

app = web.Application()
app.router.add_get("/cache", handle_cache)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    web.run_app(app, host="0.0.0.0", port=port)

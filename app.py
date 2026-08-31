import os
import asyncio
from aiohttp import web
import subprocess

RCLONE_CONFIG_DATA = os.environ.get("RCLONE_CONFIG_DATA", "")
YOUTUBE_COOKIES = os.environ.get("YOUTUBE_COOKIES", "")

# Escribir rclone config
os.makedirs("/root/.config/rclone", exist_ok=True)
lines = RCLONE_CONFIG_DATA.splitlines()
clean_lines = []
for line in lines:
    line = line.strip()
    if not line:
        continue
    if line.startswith("[") or "=" in line:
        clean_lines.append(line)
    else:
        if clean_lines:
            clean_lines[-1] += line

with open("/root/.config/rclone/rclone.conf", "w") as f:
    f.write("\n".join(clean_lines) + "\n")

# Escribir cookies
cookies_file = "/tmp/cookies.txt"
if YOUTUBE_COOKIES:
    with open(cookies_file, "w") as f:
        f.write(YOUTUBE_COOKIES)

async def handle_cache(request):
    video_id = request.query.get("id", "").strip()
    if not video_id:
        return web.json_response({"success": False, "error": "ID requerido"}, status=400)

    print(f"Descargando y subiendo {video_id} a Google Drive...")
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

async def handle_resolve(request):
    video_id = request.query.get("id", "").strip()
    if not video_id:
        return web.json_response({"success": False, "error": "ID requerido"}, status=400)

    print(f"Resolviendo streaming URL para {video_id}...")
    cookies_arg = f"--cookies {cookies_file}" if os.path.exists(cookies_file) else ""
    cmd = f"yt-dlp {cookies_arg} -g -f 140 'https://www.youtube.com/watch?v={video_id}'"
    
    proc = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    
    if proc.returncode == 0:
        stream_url = stdout.decode().strip()
        return web.json_response({"success": True, "url": stream_url})
    else:
        err = stderr.decode().strip()
        print(f"Error resolviendo stream para {video_id}: {err}")
        return web.json_response({"success": False, "error": err}, status=500)

async def handle_stream(request):
    video_id = request.query.get("id", "").strip()
    if not video_id:
        return web.Response(status=400, text="ID requerido")

    temp_file = f"/tmp/{video_id}.m4a"
    if not os.path.exists(temp_file):
        print(f"Descargando {video_id} de GDrive a /tmp de Render para streaming...")
        cmd = ["rclone", "copyto", f"gdrive:music_cache/{video_id}.m4a", temp_file]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        await proc.wait()
        
    if os.path.exists(temp_file):
        # Auto-limpieza en Render después de 10 minutos
        async def cleanup():
            await asyncio.sleep(600)
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    print(f"Temporal de Render eliminado: {temp_file}")
            except Exception as ce:
                print(f"Error limpiando {temp_file}: {ce}")
        asyncio.create_task(cleanup())
        
        return web.FileResponse(temp_file)
    else:
        return web.Response(status=404, text="Archivo no encontrado en Google Drive")

app = web.Application()
app.router.add_get("/cache", handle_cache)
app.router.add_get("/resolve", handle_resolve)
app.router.add_get("/stream", handle_stream)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    web.run_app(app, host="0.0.0.0", port=port)

# SadTalkerAlex

Web local en español: sube un retrato, escribe el texto, elige una voz y genera un MP4 con SadTalker. Texto → voz con edge-tts → animación con SadTalker. No se reescribe el texto, aunque un sintetizador puede normalizar números, abreviaturas o símbolos al pronunciarlos. No se puede garantizar un movimiento perfecto con cualquier fotografía.

## Windows

Necesitas Python **3.10**, Git y FFmpeg en PATH. La configuración usa NVIDIA/CUDA si está disponible, resolución 256 y lote 1 para limitar el consumo de memoria. Los modelos y dependencias necesitan varios GB de disco; la primera ejecución puede descargar modelos auxiliares.

Desde PowerShell en esta carpeta:

```powershell
powershell -ExecutionPolicy Bypass -File .\instalar.ps1
```

Después abre **iniciar.bat** y entra en http://127.0.0.1:7860. Mantén abierta la consola mientras usas la web. Solo escucha en tu ordenador.

1. Elige una foto frontal con una sola cara claramente visible.
2. Escribe el texto (máximo 1500 caracteres); empieza con una frase corta.
3. Elige voz y movimiento. Pulsa **Generar vídeo**.
4. Reproduce o descarga el resultado.

La foto se procesa localmente. El texto se envía al servicio online de voz de Microsoft a través de edge-tts. No se clona la voz de la persona de la foto. Los archivos se conservan en `data/<id>/`; puedes borrar esa carpeta cuando no haya un trabajo en curso. Se genera un vídeo cada vez para evitar saturar la GPU. Una generación puede tardar varios minutos.

## Problemas

- La web indica los componentes que faltan. Vuelve a ejecutar `instalar.ps1` para completar la instalación.
- Si falla la generación, consulta `data/<id>/engine.log` y `error.log`. Para falta de memoria, cierra aplicaciones que usen GPU y acorta el texto.
- Si no hay voz, revisa la conexión a Internet y la disponibilidad del servicio de Microsoft.
- Al reiniciar la aplicación, el estado de los trabajos se pierde; los MP4 ya generados siguen en `data/`.

Puedes usar otra instalación con `SADTALKER_DIR` y `SADTALKER_PYTHON` (ruta completa del Python que contiene las dependencias de SadTalker).

Fuentes: [SadTalker](https://github.com/OpenTalker/SadTalker), [edge-tts](https://github.com/rany2/edge-tts). El motor se descarga en `vendor/`, excluido del repositorio. La web y el motor usan entornos separados para evitar conflictos de versiones.

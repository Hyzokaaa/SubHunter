# SubHunter

Descarga subtitulos para peliculas y series automaticamente. Busca en multiples proveedores y empareja cada subtitulo con su archivo de video.

![SubHunter](screenshot.png)

## Caracteristicas

- **Busqueda inteligente** — usa el hash del video para encontrar el subtitulo exacto, no solo el nombre
- **Multiples proveedores** — OpenSubtitles.com, OpenSubtitles.org, Addic7ed, Podnapisi, TVSubtitles
- **11 idiomas** — Espanol, English, Portugues, Francais, Italiano, Deutsch, y mas
- **Multi-idioma simultaneo** — descarga subtitulos en varios idiomas de una sola pasada
- **Auto-renombrar** — el .srt se nombra identico al video para que el reproductor lo detecte automaticamente
- **Carga aditiva** — agrega videos de multiples carpetas sin perder los anteriores
- **Deteccion de duplicados** — ignora archivos ya cargados y avisa
- **Click derecho** — menu contextual con acciones rapidas (descargar, quitar, seleccionar, limpiar)
- **Modo claro / oscuro** — tema cinematico oscuro con acentos dorados, o modo claro
- **Configuracion persistente** — recuerda idioma, tema, proveedores y credenciales entre sesiones

## Instalacion

### Desde el codigo fuente

```bash
git clone https://github.com/Hyzokaaa/SubHunter.git
cd SubHunter
pip install .
```

### Ejecucion directa (sin instalar)

```bash
git clone https://github.com/Hyzokaaa/SubHunter.git
cd SubHunter
pip install customtkinter subliminal babelfish
python main.py
```

### Ejecutable (.exe)

Descarga el .exe desde [Releases](https://github.com/Hyzokaaa/SubHunter/releases) y ejecutalo directamente. No necesita Python.

## Uso

1. Abre la app con `python main.py` o el .exe
2. Click en **Carpeta** o **Archivos** para cargar videos
3. Selecciona el idioma deseado
4. Click en **Descargar**
5. Los subtitulos se guardan junto a cada video

### Configuracion

Click en **Config** (arriba a la derecha) para:

- Cambiar el idioma por defecto
- Activar descarga en multiples idiomas
- Activar/desactivar proveedores
- Agregar credenciales de OpenSubtitles.com (opcional, cuenta gratis = 20 descargas/dia)

## Estructura

```
SubHunter/
  main.py                       # Entry point
  subhunter/
    app.py                      # Ventana principal
    core/
      config.py                 # Configuracion persistente (JSON)
      constants.py              # Extensiones, idiomas, proveedores
      downloader.py             # Motor de descarga (subliminal)
      theme.py                  # Temas claro/oscuro
    components/
      context_menu.py           # Menu click derecho
      glow_bar.py               # Barra de progreso con efecto glow
      settings_panel.py         # Panel de configuracion
      status_bar.py             # Barra de estado inferior
      toolbar.py                # Barra de acciones superior
      video_list.py             # Lista de videos con scroll
      video_row.py              # Fila individual de video
```

## Tecnologias

- **Python 3.10+**
- **CustomTkinter** — UI moderna
- **Subliminal** — motor de busqueda de subtitulos
- **Babelfish** — manejo de idiomas

## Licencia

[MIT](LICENSE)

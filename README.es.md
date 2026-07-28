# SubHunter

Descarga subtitulos para peliculas y series automaticamente. Busca en multiples proveedores y empareja cada subtitulo con su archivo de video.

**[Read in English](README.md)**

![SubHunter](screenshot.png)

## Caracteristicas

- **Busqueda inteligente** — usa el hash del video para encontrar el subtitulo exacto, no solo el nombre
- **Selector de proveedores** — muestra todos los subtitulos disponibles de cada proveedor y te deja elegir cual descargar
- **Fallback automatico** — si el proveedor seleccionado falla, intenta automaticamente con el siguiente
- **7 proveedores** — OpenSubtitles.com, OpenSubtitles.org, Subtitulamos.tv, Addic7ed, Gestdown, Podnapisi, TVSubtitles
- **11 idiomas** — Espanol, English, Portugues, Francais, Italiano, Deutsch, Chinese, Japanese, Korean, Arabic, Russian
- **Multi-idioma** — descarga subtitulos en varios idiomas de una sola pasada
- **Auto-renombrar** — el .srt se nombra identico al video para que el reproductor lo detecte automaticamente
- **Carga aditiva** — agrega videos de multiples carpetas sin perder los anteriores
- **Deteccion de duplicados** — ignora archivos ya cargados y avisa
- **Click derecho** — menu contextual con acciones rapidas (descargar, buscar alternativa, quitar, seleccionar, limpiar)
- **Modo claro / oscuro** — tema cinematico oscuro con acentos dorados, o modo claro
- **Configuracion persistente** — recuerda idioma, tema, proveedores y credenciales entre sesiones

## Descarga

### Ejecutable para Windows (.exe)

Descarga `SubHunter.exe` desde [Releases](https://github.com/Hyzokaaa/SubHunter/releases) y ejecutalo directamente. No necesita Python.

### Arch Linux (AUR)

```bash
yay -S subhunter
```

Tambien disponible con cualquier otro AUR helper (paru, etc.). Ver la [pagina del paquete en AUR](https://aur.archlinux.org/packages/subhunter).

### Desde el codigo fuente

```bash
git clone https://github.com/Hyzokaaa/SubHunter.git
cd SubHunter
pip install customtkinter subliminal babelfish
python main.py
```

### Instalar como paquete

```bash
git clone https://github.com/Hyzokaaa/SubHunter.git
cd SubHunter
pip install .
```

## Uso

1. Abre la app con `python main.py` o el .exe
2. Click en **Carpeta** o **Archivos** para cargar videos
3. Selecciona el idioma deseado
4. Click en **Descargar**
5. Elige de que proveedor descargar en el dialogo de seleccion
6. Los subtitulos se guardan junto a cada video

### Configuracion

Click en **Config** (arriba a la derecha) para:

- Cambiar el idioma por defecto
- Activar descarga en multiples idiomas
- Activar/desactivar proveedores
- Agregar credenciales de OpenSubtitles.com (opcional, cuenta gratis = 20 descargas/dia)

## Como funciona

A diferencia de busquedas simples por nombre, SubHunter usa [Subliminal](https://github.com/Diaoul/subliminal) para calcular un **hash del archivo de video**. Este hash identifica de forma unica tu release exacto, asi que el subtitulo que obtienes esta garantizado a estar sincronizado — sin problemas de timing, sin version incorrecta.

Cuando haces click en Descargar:
1. SubHunter busca en todos los proveedores activos subtitulos que coincidan con tu video
2. Un **dialogo de seleccion** te muestra cada opcion disponible con el nombre del proveedor y puntuacion de coincidencia
3. Eliges cual descargar (el mejor viene preseleccionado)
4. Si la descarga falla, **automaticamente intenta con la siguiente** mejor opcion

## Estructura del proyecto

```
SubHunter/
  main.py                          # Punto de entrada
  subhunter/
    app.py                         # Ventana principal
    core/
      config.py                    # Configuracion persistente (JSON)
      constants.py                 # Extensiones, idiomas, proveedores
      downloader.py                # Motor de descarga (subliminal)
      theme.py                     # Temas claro/oscuro
    components/
      context_menu.py              # Menu click derecho
      glow_bar.py                  # Barra de progreso con efecto glow
      settings_panel.py            # Panel de configuracion
      status_bar.py                # Barra de estado inferior
      subtitle_picker.py           # Dialogo de seleccion de proveedor
      toolbar.py                   # Barra de acciones superior
      video_list.py                # Lista de videos con scroll
      video_row.py                 # Fila individual de video
```

## Tecnologias

- **Python 3.10+**
- **CustomTkinter** — UI de escritorio moderna
- **Subliminal** — motor de busqueda de subtitulos
- **Babelfish** — manejo de idiomas

## Contribuir

Las contribuciones son bienvenidas. Abre un issue o envia un pull request.

## Licencia

[MIT](LICENSE)

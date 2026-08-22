# garmin-agent

Agente que descarga tus actividades de running desde Garmin Connect
periódicamente, sin que nadie (ni Claude, ni nadie más) vea tu contraseña —
tú la guardas solo en los Secrets de tu propio repo de GitHub, y el script
corre dentro de la infraestructura de GitHub Actions.

## Qué hace

1. Cada domingo (o cuando lo dispares manualmente), GitHub Actions corre
   `garmin_sync.py`.
2. El script se loguea a Garmin Connect con la librería no oficial
   [`garminconnect`](https://github.com/cyberjunky/python-garminconnect),
   trae tus actividades de running de los últimos `GARMIN_LOOKBACK_DAYS` días
   (14 por defecto) y las guarda en:
   - `data/activities.json`
   - `data/activities.csv`
   - `data/last_sync.json` (fecha del último sync y cuántas actividades hay)
3. El workflow hace commit y push de esos archivos al repo.
4. Desde ahí, se pueden leer para comparar contra tu plan de entrenamiento
   (por ejemplo, pegando el link raw del JSON/CSV en tu chat con Claude, o
   dándole acceso de lectura al repo).

## Setup (una sola vez)

1. **Crea un repo nuevo en GitHub** (puede ser privado). Sube estos archivos
   tal cual están.
2. **Agrega tus credenciales como Secrets**, no como texto plano en ningún
   archivo:
   - Ve a tu repo → Settings → Secrets and variables → Actions → New
     repository secret.
   - Crea `GARMIN_EMAIL` con tu correo de Garmin Connect.
   - Crea `GARMIN_PASSWORD` con tu contraseña de Garmin Connect.
3. **Revisa el horario del cron** en `.github/workflows/sync.yml` (está en
   UTC). Por defecto corre los domingos 9:00 UTC. Cámbialo si quieres otra
   frecuencia.
4. **Primer corrida**: ve a la pestaña "Actions" de tu repo → selecciona el
   workflow "Sync Garmin running data" → "Run workflow" para probarlo
   manualmente antes de esperar al cron.

## Correrlo localmente (opcional, para probar)

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

export GARMIN_EMAIL="tu_correo@ejemplo.com"
export GARMIN_PASSWORD="tu_password"
python garmin_sync.py
```

## Limitaciones importantes (léelas antes de confiar 100% en esto)

- **No es un API oficial.** `garminconnect` funciona haciendo ingeniería
  inversa del tráfico interno de la app/web de Garmin. Garmin puede cambiar
  algo y romper el script sin aviso.
- **MFA / verificación extra.** Si Garmin le pide a tu cuenta un código de
  verificación o detecta el login automatizado como sospechoso, el script
  fallará hasta que entres manualmente una vez desde el navegador o la app.
- **Guarda tu contraseña en GitHub Secrets, nunca en el código.** Los
  Secrets no son legibles ni siquiera por ti una vez guardados (solo se
  pueden sobrescribir), y no aparecen en los logs del workflow.
- **Repo privado recomendado** si te preocupa que tus datos de actividad
  (rutas, ritmo, ubicación aproximada) queden expuestos.
- Esto es un punto de partida, no un producto mantenido — si Garmin cambia
  su login y el script deja de funcionar, puede que necesites actualizar la
  librería (`pip install -U garminconnect`) o ajustar el script.

## Siguiente paso con tu plan de entrenamiento

Una vez que tengas datos reales sincronizándose en `data/activities.json`,
comparte el contenido de tu plan de 28 semanas (semana, sesión, distancia,
ritmo objetivo) para construir el dashboard que compara plan vs. real.

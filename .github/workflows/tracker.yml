name: Tracker Miraculous

on:
  schedule:
    - cron: '*/30 * * * *' # Se ejecuta cada 30 minutos
  workflow_dispatch: # Permite ejecutarlo manualmente

jobs:
  run-tracker:
    runs-on: ubuntu-latest
    permissions:
      contents: write

    steps:
      - name: Descargar el repositorio
        uses: actions/checkout@v4

      - name: Configurar Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: Instalar dependencias
        run: pip install requests m3u8

      - name: Ejecutar el script
        run: python tracker.py

      - name: Guardar cambios en el repositorio
        run: |
          # Solo intenta subir el archivo si Python logró crearlo
          if [ -f datos.json ]; then
            git config --local user.email "action@github.com"
            git config --local user.name "GitHub Action"
            git add datos.json
            git diff-index --quiet HEAD || (git commit -m "Actualización automática de idiomas" && git push)
            echo "Datos actualizados y subidos con éxito."
          else
            echo "El archivo datos.json no se generó. Posible bloqueo temporal de Apple TV."
          fi

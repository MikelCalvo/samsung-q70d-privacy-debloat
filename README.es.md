# Samsung Q70D: debloat de privacidad

[English](README.md) · [Procedimiento](docs/reproduction.md) · [Recuperación](docs/recovery.md) · [Seguridad](SECURITY.md)

Procedimiento específico para la Samsung Q70D que desactiva componentes seleccionados de publicidad, ACR y voz sin desinstalar el launcher ni las aplicaciones de streaming. Incluye generadores offline, el código del bloqueo visual persistente, inversas, pruebas con datos sintéticos y un adaptador de acceso temporal.

No es un debloater automático. Son cambios privilegiados: hay que leer el procedimiento, preparar la recuperación y comprobar el resultado. Los cambios originales se observaron en una TV; las herramientas públicas portables tienen sus propias pruebas offline y no se han vuelto a instalar en ella.

## Equipo de referencia

- Samsung Q70D de 55 pulgadas, TQ55Q70DATXXC.
- Tizen 8.0, ARMv7 de 32 bits.
- Firmware T-PTMLDDEUC-1400.0.
- Uso previsto: TDT, YouTube y Jellyfin.

No se extrapola a otros modelos, sufijos regionales o firmware. Deben coincidir hashes del proveedor, unidades, metadatos y comportamiento del acceso. No se cambian controles para forzar la compatibilidad.

## Qué se hizo

- Se deshabilitaron mediante flags 23 de 499 componentes: 8 de publicidad/ACR y 15 de voz. Se conservaron IDs y flags de las otras 476 filas. No se desinstalaron paquetes.
- Se pusieron tres preferencias Boolean en false y se crearon cinco marcadores de condiciones que afectan a seis servicios seleccionados.
- Se bloquearon `contents-recognition-service.service` y `contents-ui-detector-service.service` con dos máscaras runtime. Un wrapper ejecutado por el `AT-HUB.service` existente conserva y ejecuta primero el script Samsung original firmado, y después reaplica el bloqueo.
- Tras un nuevo arranque real del kernel, una lectura independiente confirmó ambas unidades masked-runtime, inactive y MainPID=0, sin sus ejecutables seleccionados activos.
- El propietario confirmó los consentimientos opcionales rechazados, el micrófono físico de la TV apagado y HbbTV desactivado desde el menú. Esto no demuestra que se desconecte eléctricamente el micrófono separado del mando.

El root de mantenimiento es temporal. El hook privilegiado persiste solo para bloquear esos dos servicios; no instala un servicio de acceso root remoto. Home Assistant no es necesario.

## Empezar sin tocar la TV

Linux, Python 3.11 o posterior, Bash, AWK y sqlite3. Las pruebas no requieren TV, root, internet ni archivos Samsung.

```sh
python3 -m unittest discover -s tests -v
python3 tools/check_public_tree.py
python3 tools/recognition.py --help
python3 tools/registry.py --help
python3 tools/tv_session.py --help
```

No ejecutes los scripts generados para la TV en tu ordenador. Guarda snapshots, capturas del estado previo, planes y recibos fuera del repositorio.

Los documentos técnicos están en inglés:

1. [Reproducción por etapas](docs/reproduction.md), con puntos de comprobación para personas y agentes.
2. [Acceso temporal](docs/access.md), dependencias externas fijadas y límites de limpieza.
3. [Plan de registro, voz y marcadores](docs/registry-tool.md), generado desde el snapshot y el estado previo propios, nunca desde los valores históricos del perfil público.
4. [Generador del bloqueo visual](docs/recognition-tool.md) y [mecanismo de persistencia](docs/recognition-persistence.md). Instalación, activación y verificación tras reinicio son pasos distintos.
5. [Recuperación](docs/recovery.md) y [validación](docs/validation.md). Un timeout no autoriza repetir una operación con otro nombre.

## Límites

No se garantiza telemetría cero ni se han medido mejoras de rendimiento, RAM o espacio. Puede haber una ventana de reconocimiento al principio del arranque, antes de AT-HUB.

Se prepararon archivos de recuperación y se comprobó su admisión de solo lectura. La ida y vuelta completa se probó offline con fixtures, no mediante una restauración real en la TV. La aceptación general tampoco equivale a una matriz completa de reproducción por aplicación y entrada.

No se garantiza supervivencia a actualizaciones ni cancelación remota o recuperación atómica ante cortes de corriente. Una compilación o unos archivos distintos requieren revisión; no desactives actualizaciones de seguridad para conservar el cambio.

## Créditos y licencia

Código original, datos seleccionados y documentación con licencia MIT. El acceso root utiliza chris-ritsen/samsung-tv-root y el trabajo que ese proyecto acredita. Véanse [THIRD_PARTY.md](THIRD_PARTY.md) y [fuentes](docs/sources.md).

El repositorio no debe contener nuestra red, configuración de automatización, credenciales, IDs únicos, evidencias privadas ni archivos Samsung. Para contribuir, consulta [CONTRIBUTING.md](CONTRIBUTING.md).

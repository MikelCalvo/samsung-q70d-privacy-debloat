# Community findings: bounded Q70D follow-up

The original 23-component profile and two visual-service masks are a baseline,
not a claim that every microphone, sensor or telemetry path has been removed.
The follow-up assessment below concerns the same Q70D / Tizen 8 / ARMv7 build.
It is not a generic package-removal list.

## What was reproduced locally

Read-only native observations confirmed that the existing visual masks and hook
were still intact. Selected vendor executables were copied privately, checked
against source hashes and inspected without executing them on the controller.
No Samsung bytes or raw device captures are distributed here.

- `wifi-presence.service` runs `/usr/bin/com.samsung.tv.wifi-presence` and has a
  separate `wifi-presence.path` activator. Static call sites connect ARP scanning
  to result processing and a CLogger KPI call. The observed process was running.
  This supports a targeted discovery/privacy review; it does not establish that
  a particular scan or Internet upload occurred during the observation.
- `com.samsung.tv.tvsensor-iot-service` is an on-boot application, not a systemd
  service with that app ID. Its implementation includes sound-class callbacks,
  light-sensor callbacks, camera/IoT integration and sensor KPI calls. The native
  sound-detection preference was false; that is not evidence that the whole
  application or every other sensor path was inactive.
- `org.tizen.voice-client` is the voice-control/audio processor named by the
  Bixby application's manifest. The same package contains `org.tizen.stt-client`.
  Static audio, network and logging call sites exist. The client was enabled
  with automatic restart, but no current client process was observed. An
  enabled component is not proof of an active recording.
- `org.tizen.voice-app` identifies itself as Bixby and has two app IDs sharing
  its executable. Its launcher has an existing negative-condition marker.
- `remote-management.service` actually executes `/usr/bin/rmdemon`. It was
  inactive, conditional and D-Bus activatable. Disabling only the similarly
  named UI app would not establish that this daemon was blocked.
- `remote-shop-care-hub.service` was inactive and conditional. A preventive
  block would close an unused activation path, not demonstrate a reduction in
  currently running work.

These are capability and point-in-time state findings. They do not prove
continuous capture, consent bypass on this set, exfiltration, performance gains
or zero telemetry.

## Components intentionally kept

`remote-server.service` is not the same component as `remote-management.service`.
The former has a reverse dependency from
`bt-settings-external-controller-service.service`; indiscriminately blocking
anything named `remote` risks the physical remote control.

`user-presence.service` includes power, dimming and mute/unmute behavior. It is
not interchangeable with the ARP-scanning `wifi-presence` component. General
sensor, sound-server, Bluetooth, accessibility/TTS and connectivity services are
not blanket-disable targets.

`com.samsung.tv.vif` exposes voice-integration actions involving media, subtitles
and search. The first extension preserves it because its complete consumer graph
has not been verified. This leaves an explicit residual surface; it is not a
claim that its presence is either required for ordinary viewing or harmless.

## Functional trade-offs

Closing voice-client/STT/Bixby routes sacrifices TV voice control, voice search
and dictation, including uses initiated by a remote or connected audio device.
Some assistant-associated speech playback can also disappear. It is not an
electrical disconnection of the remote's microphone and does not govern every
third-party application's independent recording implementation.

Removing the sensor IoT application can remove Samsung sensor notifications,
connected-camera functions, light/Hue synchronization and presence features.
Local Home Assistant remote control and SmartThings sensor automation are
separate use cases: verify the functions actually used rather than assuming
that preserving one preserves the other.

Any operational extension needs its own captured before-state, field-specific
inverse, exact unit identities, foreign-state refusal and post-change family
checks. Keep original visual-block recovery separate. A reboot test and actual
TDT/YouTube/streaming/audio/remote acceptance must not be inferred from offline
fixtures or a reachable API.

## Source context

The community posts prompted the assessment, but their broad claims are not
substitutes for the narrower local findings above:

- https://x.com/log4j/status/2113781968601055366
- https://x.com/log4j/status/2113762242327892456
- https://x.com/log4j/status/2113756782304596232
- https://x.com/log4j/status/2113740242624917953
- https://x.com/log4j/status/2114360638893850664

The sensor-event image is an explanatory table, not itself a packet capture.
Samsung documents Pet Care / Family Care detection for selected products; that
explains potential functionality, not the correctness of this firmware's
consent enforcement:
https://news.samsung.com/us/samsung-celebrates-debut-samsung-vision-ai-tvs-special-offer/

Samsung also documents consent/PIN-based remote support. That is a legitimate
purpose for remote-management capability, not an implementation security audit:
https://www.samsung.com/uk/support/remote-service/

The proposed new community persistence route was described as ARM64. This
reference TV is ARMv7 32-bit; no compatibility is inferred and no global UEP
change is part of this follow-up:
https://x.com/log4j/status/2113979924348281263

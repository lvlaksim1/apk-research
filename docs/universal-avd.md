# Универсальный Android-эмулятор для исследования APK

Дата проверки: 31.10.2026. Среда **не привязана к конкретному приложению или исследовательскому репозиторию**. Используется с существующим `apk-research`, ChatGPT Mobile Research и любыми будущими исследованиями Android.

## Установленная конфигурация

| Параметр | Значение |
|---|---|
| AVD | `APK_Research_API36` |
| Android | 16 (API 36) |
| Образ | `system-images;android-36;google_apis_playstore;x86_64` |
| ABI | `x86_64,arm64-v8a`, `libndk_translation.so` |
| CPU / RAM | 4 vCPU / 4 ГБ |
| Диск приложения | 16 ГБ, на D: |
| Экран | 1080×2400, 420 dpi |
| ADB | `emulator-5570` |
| АVD-данные | `D:\AndroidAVD\APK_Research_API36.avd` |
| Код инструментов | `tools/universal-avd/` |
| Установленные скрипты | `D:\Tools\APKResearch\` |
| LDPlayer | Не затронут; не используется этим контроллером |

Системный образ Google Play находится в существующем Android SDK на диске C:, **файлы и данные нового виртуального устройства — на D:**. Профиль создавался с уникальным именем; два прежних Android Studio AVD не изменялись.

## Использование

В PowerShell:

```powershell
$tool = 'D:\Tools\APKResearch\APKResearch.ps1'

# Состояние эмулятора, API, ABI и native bridge
powershell -NoProfile -ExecutionPolicy Bypass -File $tool -Action Status

# Запуск / остановка только этого AVD (проверяется имя по adb emu avd name)
powershell -NoProfile -ExecutionPolicy Bypass -File $tool -Action Start
powershell -NoProfile -ExecutionPolicy Bypass -File $tool -Action Stop

# Установка исследуемых APK; может быть одна APK или split-комплект
powershell -NoProfile -ExecutionPolicy Bypass -File $tool -Action Install -PackageFile 'D:\research\sample.apk'
powershell -NoProfile -ExecutionPolicy Bypass -File $tool -Action Install -PackageFile 'D:\research\sample.apk+'

# Запуск установленного приложения
powershell -NoProfile -ExecutionPolicy Bypass -File $tool -Action Launch -PackageName 'com.example.app'
```

## Установка инструментов на другой ПК

Для воспроизведения нужна Windows с аппаратной виртуализацией, Android SDK (emulator, platform-tools, cmdline-tools) и образ Android 16 Google Play:

```powershell
& "$env:LOCALAPPDATA\Android\Sdk\cmdline-tools\latest\bin\sdkmanager.bat" "system-images;android-36;google_apis_playstore;x86_64"
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\universal-avd\Install-Tools.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File D:\Tools\APKResearch\APKResearch.ps1 -Action Create
```

Установка инструментария создаёт только наши командные файлы и ярлыки в папке пользователя. Android SDK и данные AVD не включены в Git.

## Подключение Android через Happ (VPN)

Проверено 31.10.2026 на Windows 10. Happ продолжает работать на ПК, менять его настройки не требуется. Локальный HTTP CONNECT-прокси Xray/Happ слушает `127.0.0.1:10809` (проверить при запуске). Для Android Emulator адрес `10.0.2.2` обозначает хост Windows, поэтому HTTP(S) приложения, использующие системный Android-прокси, идут по пути:

`Android app → 10.0.2.2:10809 → Happ local HTTP proxy → VPN`.

Это **не полноценный Android VPN/TUN**: трафик приложений, игнорирующих системный HTTP proxy, а также UDP/QUIC может идти отдельно. Использовать сетевые PCAP и поведение приложения для подтверждения выбранного маршрута.

```powershell
$tool = 'D:\Tools\APKResearch\APKResearch.ps1'
powershell -NoProfile -ExecutionPolicy Bypass -File $tool -Action ProxyStatus
powershell -NoProfile -ExecutionPolicy Bypass -File $tool -Action ProxyOn
powershell -NoProfile -ExecutionPolicy Bypass -File $tool -Action ProxyOff
```

Кнопки этих действий доступны в меню «Пуск → APK Research Emulator». `ProxyOn` проверяет уникальное имя AVD, слушающий на localhost порт Happ и отсутствие другого Android-прокси. `ProxyOff` удаляет только `10.0.2.2:10809` (либо указанный `-ProxyPort`), не удаляет произвольный сторонний прокси. Включённый Android proxy сохраняется в настройках AVD; для уже запущенных приложений может потребоваться их перезапуск. Windows VPN, другие AVD и LDPlayer не меняются.

Реальная приёмка: прямой неавторизованный `HEAD /backend-api/` на `android.chat.openai.com` вернул **403**, а через локальный Happ HTTP proxy — **404**. После установки `10.0.2.2:10809` ранее отображавшая региональная ошибка в приложении ChatGPT исчезла, открылся гостевой режим, два синтетических сообщения получили ответы. Подробный протокол — в [проекте исследования ChatGPT Android](https://github.com/lvlaksim1/chatgpt-mobile-research).

## Изоляция проектов

Для нового исследования **не нужно создавать новый GitHub-репозиторий с эмулятором**. Можно использовать уже созданный профиль. Если необходима отдельная чистая Android-среда, создайте независимый AVD из того же системного образа:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File $tool -Action Create -Name APK_Research_ProjectB
powershell -NoProfile -ExecutionPolicy Bypass -File $tool -Action Start -Name APK_Research_ProjectB -Port 5572
powershell -NoProfile -ExecutionPolicy Bypass -File $tool -Action Status -Name APK_Research_ProjectB -Port 5572
```

Каждый профиль хранит собственные данные в `D:\AndroidAVD\<имя>.avd` и имеет собственный порт ADB. Уже созданный профиль `Create` отказывается перезаписывать. Установка/остановка всегда требует совпадения имени AVD и устройства на соответствующем порту. **Очистка данных и удаление профилей в универсальном скрипте не предусмотрены**, чтобы избежать случайной потери материалов исследований.

## Фактическая проверка (31.10.2026)

- Android SDK Emulator acceleration: AEHD 2.2 `installed and usable`.
- `adb -s emulator-5570 shell getprop ro.build.version.sdk` → `36`.
- `adb -s emulator-5570 shell getprop ro.product.cpu.abilist` → `x86_64,arm64-v8a`.
- `adb -s emulator-5570 shell getprop ro.dalvik.vm.native.bridge` → `libndk_translation.so`.
- `adb -s emulator-5570 shell getprop sys.boot_completed` → `1`.
- На чистый AVD установлены все четыре `com.openai.chatgpt` split-APK (версия 1.2026.286, `primaryCpuAbi=arm64-v8a`), команда `adb install-multiple` завершилась `Success`. `MainActivity` стартовала; PID приложения был получен.
- После этого `APKResearch.ps1 -Action Install -PackageFile ...apk+` также вернул `Success` и прошёл проверку версии пакета.
- Сетевые запросы/авторизация/голосовые функции приложения этим тестом **не проверялись**.

## Границы безопасности и обратимости

Скрипты не работают с LDPlayer, не удаляют другие AVD, изменяют Android proxy **только по отдельным явным командам ProxyOn/ProxyOff** и только после проверки его состояния, не перехватывают трафик и не извлекают токены/данные приложений. Перед включением сетевых анализаторов в `apk-research` необходимо отдельно проверить выбранный ADB serial и принадлежность профиля. Вывод ADB, скриншоты, токены и содержимое приложений не коммитятся.

Полный сохранённый эмулятор не хранится на GitHub — только сценарии и документированные настройки. Это позволяет повторить создание среды на следующем ПК.

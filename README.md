# Сборщик вакансий моряков

v0.1.0-alpha

Инструмент собирает вакансии с трёх крюинговых сайтов, фильтрует их по
**должности** и **типу судна** и сохраняет в один **Excel-файл с кликабельными
ссылками** на каждую вакансию.

Сайты-источники:
- [crewell.net](https://crewell.net/en/)
- [ukrcrewing.com.ua](https://ukrcrewing.com.ua/en/)
- [maritime-zone.com](https://maritime-zone.com/en/) — за защитой Cloudflare (см. ниже)

Пользоваться можно двумя способами: через **графическое окно** (просто, для всех,
см. ниже) или из **командной строки** (для продвинутых).

## Графический интерфейс (для новичка)

Окно с галочками: отмечаете нужные **должности** и **типы судов**, выбираете сайты
и жмёте **«Старт»**. В журнале виден прогресс, по завершении — кнопки
**«Открыть Excel»** и **«Открыть папку»**. Файл `config.yaml` и терминал не нужны.

- **Готовый `.exe` (без Python).** Раздавайте папку `dist\SeamanJobs` целиком
  (можно zip). Конечный пользователь запускает `SeamanJobs.exe` двойным кликом —
  ничего устанавливать не нужно, браузер для maritime-zone уже внутри.
- **Из исходников.** Двойной клик по `Запустить.bat` (или `python gui.py`).

> Полные детали для maritime-zone приходят, когда в окне включена опция
> «maritime-zone: показать окно браузера» (откроется окно Chromium). Без неё с
> этого сайта собираются данные списка (должность, судно, зарплата, даты, ссылка).

## Что собирается по каждой вакансии

Должность, тип судна, зарплата (+ разобранные min/max/валюта), дата посадки,
длительность контракта, компания, дата публикации, просмотры, ID, дата сбора и
**кликабельная ссылка**. Для совпавших вакансий дополнительно подгружается
**описание/детали** со страницы вакансии (флаг, DWT, тип двигателя, судовладелец,
требования, для ukrcrewing — контактный телефон и e-mail).

## Облачная версия (Streamlit) — тест по ссылке

Лёгкая веб-версия для **crewell + ukrcrewing** (без браузера) — открывается по ссылке,
ничего ставить не нужно. maritime-zone в облако не входит (Cloudflare) — он в десктоп-`.exe`.

Локальный запуск (нужен **Python 3.10+**; Streamlit не ставится на 3.9.7):
```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

> Для деплоя версия Python на вашем ПК неважна — Streamlit Cloud использует свой
> Python 3.11+. Локальный запуск нужен лишь для предпросмотра.

Деплой на бесплатный Streamlit Community Cloud:
1. Зайти на [share.streamlit.io](https://share.streamlit.io) под своим GitHub.
2. New app → репозиторий `YanisDigital/Seaman-jobs`, ветка `main`, main file
   `streamlit_app.py` → **Deploy**.
3. Получаете публичную ссылку — её и отправляете знакомым.

Streamlit Cloud сам ставит зависимости из `requirements.txt` (он намеренно лёгкий, без
playwright/pyinstaller).

## Требования (десктоп)

- Python 3.9+
- Зависимости из `requirements-desktop.txt`
- Для maritime-zone — браузер Chromium (через playwright)

## Установка (Windows, десктоп)

```powershell
# из папки проекта
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-desktop.txt
# браузер для maritime-zone (Cloudflare):
.\.venv\Scripts\python.exe -m playwright install chromium
```

> Если установка `playwright` падает на сборке `greenlet` («Microsoft Visual C++
> 14.0 required»), поставьте бинарное колесо:
> `.\.venv\Scripts\python.exe -m pip install --only-binary=:all: greenlet`,
> затем повторите установку playwright.
>
> Если playwright не установлен вовсе — инструмент просто пропустит maritime-zone,
> два других сайта работают без него.

## Настройка — `config.yaml`

```yaml
positions:        # нужные должности (ключевые слова, подстрока, без регистра)
  - master
  - chief engineer
vessel_types:     # нужные типы судов
  - bulk
  - container
sites:            # какие сайты опрашивать
  - crewell
  - ukrcrewing
  - maritime_zone
request:
  delay_seconds: 1.0      # пауза между запросами
  max_pages_per_site: 0   # 0 = все страницы; >0 = ограничить
  fetch_details: true     # дозагружать страницы-детали
maritime_zone:
  headless: true          # см. раздел про maritime-zone
```

Фильтр: вакансия попадает в результат, если её должность совпала с одним из
`positions` **И** тип судна — с одним из `vessel_types`. Синонимы добавляйте
отдельными строками (например, и `master`, и `captain`). Пустой список = не
фильтровать по этому параметру.

## Запуск

```powershell
.\.venv\Scripts\python.exe main.py                 # все сайты из config.yaml
.\.venv\Scripts\python.exe main.py --site crewell  # только один сайт
.\.venv\Scripts\python.exe main.py --limit 2       # макс. 2 страницы с сайта (для теста)
.\.venv\Scripts\python.exe main.py --no-details    # быстро, без страниц-деталей
.\.venv\Scripts\python.exe main.py --output D:\jobs # своя папка для .xlsx
```

Результат: `output\vacancies_ГГГГ-ММ-ДД_ЧЧММ.xlsx` — одна строка на вакансию,
закреплённая шапка, включён автофильтр, ссылки в колонке **«Ссылка»** кликабельны.

## Сборка автономного .exe

Чтобы раздать приложение людям без Python:

```powershell
# один раз — окружение и браузер:
.\.venv\Scripts\python.exe -m pip install -r requirements-desktop.txt
.\.venv\Scripts\python.exe -m playwright install chromium
# собрать:
.\build.bat
```

Готовое приложение: `dist\SeamanJobs\SeamanJobs.exe`. Раздавайте **всю папку**
`dist\SeamanJobs` (можно заархивировать в zip) — внутри уже лежит браузер Chromium
для maritime-zone, поэтому на чужом компьютере ничего ставить не нужно. Папка
весит ~550 МБ из-за встроенного браузера Chromium.

> Неподписанный `.exe` может вызвать предупреждение Windows SmartScreen/антивируса —
> это нормально для самосборных программ («Подробнее» → «Выполнить в любом случае»).

## maritime-zone.com и Cloudflare

Сайт защищён Cloudflare, поэтому используется headless-браузер (playwright):

- **Список вакансий** проходит проверку и в фоновом режиме (`headless: true`) —
  собираются все ключевые поля (должность, судно, зарплата, даты, компания, ссылка).
- **Страницы-детали** в фоновом режиме обычно НЕ проходят проверку. Тогда
  описание остаётся пустым (данные списка сохраняются), а в лог выводится подсказка.
- Чтобы получать **полное описание** и для maritime-zone, поставьте в `config.yaml`
  `maritime_zone.headless: false` — откроется окно браузера, и проверка проходит.

## Полезно знать

- **Кириллица в консоли.** Вывод переключается на UTF-8 автоматически; данные в
  Excel сохраняются корректно независимо от консоли.
- **Вежливость и ToS.** Между запросами есть пауза (`delay_seconds`), используется
  обычный User-Agent. Собираются только публичные вакансии. Не запускайте слишком
  часто; при необходимости свериться с `robots.txt` сайтов.
- **Изменение вёрстки сайтов.** Селекторы каждого сайта изолированы в
  `scraper/sites/<сайт>.py`; при изменении сайта правится только один файл.

## Структура проекта

```
main.py                     # CLI и оркестрация
config.yaml                 # фильтры и настройки
scraper/
  models.py                 # модель Vacancy + разбор зарплаты
  settings.py               # загрузка config.yaml
  http_client.py            # сессия, заголовки, задержки, повторы
  filtering.py              # фильтр по должности/типу судна
  excel_writer.py           # запись .xlsx с гиперссылками
  playwright_fetch.py       # headless-браузер для Cloudflare
  sites/
    base.py                 # общий интерфейс скрейпера
    crewell.py
    ukrcrewing.py
    maritime_zone.py
output/                     # сюда сохраняются .xlsx
```

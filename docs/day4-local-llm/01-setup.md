# 01 — Установка и подключение к IDE

## Выбранная связка

Вместо Continue.dev использовалась более легковесная пара:

- **LM Studio** как inference-сервер (OpenAI-compatible API).
- **OpenCode** — VS Code-совместимый клиент с чатом и автокомплитом.
- **Codex CLI** — для агентного режима (многошаговые задачи, запуск shell, правка файлов).

Причина: обе IDE-утилиты ходят в OpenAI-совместимый эндпоинт LM Studio, поэтому
модель доступна и в чате, и в автокомплите, и в агентном режиме без дубля конфига.

### Топология

```
VS Code / Terminal
   ├── OpenCode         ─┐
   └── Codex CLI        ─┤──►  http://192.168.1.126:8080/v1  (LM Studio, 36GB Mac)
                         │        └── модель в MLX, Metal backend
```

Локальный Mac (24GB) оказался слишком маленьким для любой модели ≥ 9B при
рабочем контексте → вся тяжёлая инференция вынесена на вторую машину в LAN.
Клиент (IDE) продолжает жить на 24GB-ноутбуке.

## Конфиг клиентов

### OpenCode — `~/.config/opencode/config.json`

```json
{
  "$schema": "https://opencode.ai/config.json",
  "model": "remote/qwen3.6-35b-a3b-mlx",
  "provider": {
    "remote": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Remote LM Studio (.126:8080)",
      "options": { "baseURL": "http://192.168.1.126:8080/v1" },
      "models": {
        "qwen3.6-35b-a3b-mlx": {
          "name": "Qwen3.6 35B A3B MLX",
          "contextLength": 65000,
          "temperature": true
        }
      }
    }
  }
}
```

Важно: `temperature: true` в OpenCode — это **флаг наличия способности**, не
числовое значение. Схема сломается, если поставить `"temperature": 0.3`.
Само числовое значение температуры задаётся на стороне LM Studio.

### Codex CLI — `~/.codex/config.toml`

```toml
model_provider = "local"
model = "qwen3.6-35b-a3b-mlx"

[model_providers.local]
name = "Local Server"
base_url = "http://192.168.1.126:8080/v1"
wire_api = "responses"

[tools]
web_search = false
```

Ключевые моменты:

- `wire_api = "responses"`. Старое значение `"chat"` удалено из Codex, а LM
  Studio поддерживает `/v1/responses` — совпало.
- `web_search = false` — убирает варнинг про unsupported tool type.
- MCP-сервер для поиска (пробовали `duckduckgo-mcp-server`) пришлось
  отключить: Codex оборачивает MCP-инструменты под `"type": "namespace"`,
  а LM Studio принимает только `"function"`. Пока несовместимо.

## Системный промпт (правила из Дня 1)

Файл `AGENTS.md` из корня репозитория пробрасывается как system prompt —
OpenCode и Codex подхватывают его автоматически при старте сессии в
рабочей директории проекта. Ключевые правила, попавшие в промпт:

- Проект на **React + TypeScript + Vite**, тестовый стек — Vitest + Testing Library.
- Отступы 2 пробела, только `.ts/.tsx`, без `.js`.
- Именование: PascalCase для компонентов и хуков.
- Тесты рядом с исходником (`Foo.test.tsx` ↔ `Foo.tsx`).
- Коммиты в формате Conventional Commits.

Локальная модель получает ровно тот же свод правил, что облачный
ассистент в Дне 1 — это делает сравнение честным.

## Контекст

| Параметр | Значение | Почему |
|---|---|---|
| `loaded_context_length` | 65 000 | Перекрывает 30–60k рабочих диалогов с запасом |
| Context Overflow | **Rolling Window** | «Truncate Middle» выбрасывает середину — а там ровно текущая задача |
| Файлы в контексте | Выборочно через команды OpenCode | Весь репозиторий ≈ 3–5k токенов, грузим целиком при необходимости |

Пробовали 128k — выходит за предел по VRAM на 36GB машине после нескольких
ходов диалога (см. [OOM-историю](02-models-and-quants.md)).

## Параметры генерации (для кода)

Настраиваются в LM Studio → вкладка Settings/Sampling для загруженной модели:

| Параметр | Значение | Комментарий |
|---|---|---|
| Temperature | **0.4** | Низкая — код требует детерминизма, но не 0.1 (иначе зацикливание) |
| Top K | **40** | 20 оказалось слишком узко — токены коллапсировали в повтор |
| Top P | **0.9** | Стандарт для кода |
| Min P | **0.05** | Отрезает «хвостовой мусор» — главный рычаг против зацикливаний |
| Repeat Penalty | **1.1** | 1.2+ мешает легитимным повторам (`}`, `return`, отступы) |
| Context Overflow | **Rolling Window** | Не «Truncate Middle» |

Порядок влияния на стабильность вывода (от максимального):
`Min P 0.05` → `Temperature 0.4–0.5` → `Top K 40` → остальное.

:us: [English version](#pcmsi-eng)  
:ru: [Русская версия](#pcmsi-rus)

____

# PCMSI (ENG)
> PCMSI is a powerful, scalable monitoring and alerting system inspired by Grafana, but with a unique smart agent architecture.

Main features:
- Manage agents and configure them directly on the master server.
- Receive initial metrics (CPU, RAM, disk, network, custom metrics).
- Build flexible dashboards with graphs, tables, and widgets.
- Configure alerts based on thresholds and anomalies.
- Manage user access with different roles.
- Network scanning — automatically search for devices on the network.
- Dashboards — drag and drop widgets, save templates.
- Alerts — send protocol messages (Telegram, Discord) when rules are implemented.
- Metric history — long-term storage with reduced pruning and aggregation.

#### Developed by [Borodkin Dmitry](https://github.com/arkain123)

![GitHub License](https://img.shields.io/github/license/arkain123/PCMSI)
![Last Commit](https://img.shields.io/github/last-commit/arkain123/PCMSI)
![Downloads](https://img.shields.io/github/downloads/arkain123/PCMSI/total)
![Code Size](https://img.shields.io/github/languages/code-size/arkain123/PCMSI)
![Repo size](https://img.shields.io/github/repo-size/arkain123/PCMSI)

### Important information
1. Все компоненты PCMSI распространяются под лицензией  
   [GNU GPL 3.0](https://www.gnu.org/licenses/gpl-3.0.html).

### Decoding of commit changes descriptions marks

These symbols and marks are used to shorten some change descriptions.  
Use them to quickly understand what a specific change does.

| Mark      | Meaning             |
| :-------: | ------------------- |
|   `HF`    | Hotfix              |
|   `F`     | Fix                 |
|   `+`     | New feature         |
|   `-`     | Removed             |
|   `>`     | Edited/Renamed      |
|   `>>`    | Moved               |
|   `!`     | Important change    |
|   `M`     | Git branch merge    |
| _No mark_ | Unclassified change |

## How to install

1) Install Python 3.14
2) Clone the project:  
   `git clone https://github.com/arkain123/PCMSI.git`
3) Go to the project folder:  
   `cd PCMSI`
4) Grant execution permission to the deploy script:  
   `chmod +x deploy.sh`
5) Run the deploy script:  
   `./deploy.sh`
6) You can run with automated deploy with systemd unit using:
   `./deploy.sh --with-systemd`

## How to run

1) After a successful installation, run:  
   `./start.sh`
2) Open your browser and go to `http://localhost:8999` (or the port shown in the console).

## How to install the agent

1) Use the agent directory from this project
2) In agent/config.yaml , specify the key, ID, and master address
3) Run it using `python agent.py`

### Links

* [GitHub](https://github.com/arkain123/PCMSI)
* [Wiki](https://arkain123.github.io/PCMSI/)

____

# PCMSI (RUS)
> PCMSI — это мощная, масштабируемая система мониторинга и алертинга, вдохновлённая лучшими практиками Grafana, но с уникальной архитектурой на основе «умных» агентов.

Отличительные особенности:
- Управлять агентами и их конфигурацией прямо на мастер-сервере.
- Получать метрики в реальном времени (CPU, RAM, диск, сеть, пользовательские метрики).
- Строить гибкие дашборды с графиками, таблицами и виджетами.
- Настраивать алерты по пороговым значениям и аномалиям.
- Управлять доступом пользователей с разными ролями.
- Сканирование сети — автоматический поиск устройств в сети.
- Дашборды — перетаскивание виджетов, сохранение шаблонов.
- Алерты — отправка уведомлений (Telegram, Discord) при срабатывании правил.
- История метрик — долговременное хранение с возможностью сжатия и агрегации.

#### Разработано [Бородкиным Дмитрием](https://github.com/arkain123)

![GitHub License](https://img.shields.io/github/license/arkain123/PCMSI)
![Last Commit](https://img.shields.io/github/last-commit/arkain123/PCMSI)
![Downloads](https://img.shields.io/github/downloads/arkain123/PCMSI/total)
![Code Size](https://img.shields.io/github/languages/code-size/arkain123/PCMSI)
![Repo size](https://img.shields.io/github/repo-size/arkain123/PCMSI)

### Важная информация
1. Всё в PCMSI находится под лицензией  
   [GNU GPL 3.0](https://www.gnu.org/licenses/gpl-3.0.html).

### Расшифровка меток в описаниях изменений коммитов

С помощью этих меток вы можете обозначить/узнать, что именно изменилось в коммите.

| Метка      | Значение               |
| :--------: | ---------------------- |
|   `HF`     | Хотфикс                |
|   `F`      | Фикс                   |
|   `+`      | Новая фича             |
|   `-`      | Удалено                |
|   `>`      | Изменено/Переименовано |
|   `>>`     | Перемещено             |
|   `!`      | Важное изменение       |
|   `M`      | Слияние веток Git      |
| _Нет метки_| Неклассиф. изменение   |

## Как установить

1) Установите Python 3.14
2) Склонируйте проект:  
   `git clone https://github.com/arkain123/PCMSI.git`
3) Перейдите в папку проекта:  
   `cd PCMSI`
4) Дайте права на выполнение скрипта развёртывания:  
   `chmod +x deploy.sh`
5) Запустите скрипт развёртывания:  
   `./deploy.sh`
6) Также можно использовать автоматическое развертывание с systemd кофингом используя:
   `./deploy.sh --with-systemd`

## Как запустить

1) После успешной сборки выполните:  
   `./start.sh`
2) Откройте браузер и перейдите по адресу `http://localhost:8999` (или порту, указанному в консоли).

## Как установить агента

1) Используйте из этого проекта каталог agent
2) В agent/config.yaml укажите ключ, ID и адрес мастер
3) Запустите используя `python agent.py`

### Ссылки

* [GitHub](https://github.com/arkain123/PCMSI)
* [Документация](https://arkain123.github.io/PCMSI/)

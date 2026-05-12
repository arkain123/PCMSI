#!/bin/bash
set -e

echo "============================================"
echo "  PCMSI Monitoring — Deploy"
echo "============================================"

# Определение ОС
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
else
    echo "Не удалось определить ОС"
    exit 1
fi

install_system_deps() {
    echo "Устанавливаю системные зависимости..."
    if [ "$OS" = "ubuntu" ]; then
        sudo apt update
        sudo apt install -y python3 python3-pip python3-venv nmap git curl
    elif [ "$OS" = "arch" ]; then
        sudo pacman -Syu --noconfirm
        sudo pacman -S --noconfirm python python-pip python-virtualenv nmap git curl
    else
        echo "Поддерживаются только Ubuntu и Arch Linux"
        exit 1
    fi
}

setup_project() {
    echo "Настраиваю проект..."
    if [ ! -d "venv" ]; then
        python3 -m venv venv
    fi
    source venv/bin/activate
    pip install --upgrade pip
    if [ -f requirements.txt ]; then
        pip install -r requirements.txt
    else
        echo "X requirements.txt не найден. Создайте его командой: pip freeze > requirements.txt"
        exit 1
    fi

    echo "Применяю миграции и создаю БД..."
    python manage.py migrate
    echo "Собираю статические файлы..."
    python manage.py collectstatic --noinput
    echo "V Проект готов."
}

create_systemd_service() {
    echo "Создаю systemd-сервис для Gunicorn..."
    sudo tee /etc/systemd/system/pcmsi.service > /dev/null <<EOF
[Unit]
Description=PCMSI Monitoring Gunicorn daemon
After=network.target

[Service]
User=$USER
Group=www-data
WorkingDirectory=$(pwd)
ExecStart=$(pwd)/venv/bin/gunicorn --workers 3 --bind 0.0.0.0:8000 pcmsi.wsgi:application
Restart=always

[Install]
WantedBy=multi-user.target
EOF
    sudo systemctl daemon-reload
    sudo systemctl enable pcmsi
    echo "V Сервис pcmsi создан. Запустите: sudo systemctl start pcmsi"
}

# ---------- Запуск ----------
install_system_deps
setup_project

echo ""
echo "============================================"
echo "  Развёртывание завершено!"
echo "  ! Логин: admin"
echo "  ! Пароль: 12345678"
echo "  НЕМЕДЛЕННО СМЕНИТЕ ПАРОЛЬ ПОСЛЕ ВХОДА!"
echo "============================================"
echo ""
echo "Для быстрого теста выполните:"
echo "  source venv/bin/activate && python manage.py runserver 0.0.0.0:8000"
echo ""
echo "Хотите настроить автозапуск через systemd? Запустите скрипт с флагом --with-systemd"
if [ "$1" = "--with-systemd" ]; then
    create_systemd_service
fi
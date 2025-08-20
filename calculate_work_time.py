import argparse
import csv
from datetime import datetime
from collections import defaultdict
import sys

# Формат даты в логах
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

def parse_log_line(line):
    """Парсит строку лога, возвращает (login, action, timestamp, session_id) или None"""
    try:
        # Убираем кавычки и разделяем
        parts = [part.strip().strip('"') for part in line.strip().split(';')]
        if len(parts) < 4:
            return None
        login, action, timestamp_str, session_id = parts[:4]
        timestamp = datetime.strptime(timestamp_str, DATE_FORMAT)
        return login, action, timestamp, session_id
    except Exception as e:
        print(f"Ошибка при парсинге строки: {line} — {e}", file=sys.stderr)
        return None

def calculate_work_time(log_file_path, target_login=None):
    # Хранит последний Start для каждой сессии (по session_id)
    start_times = {}
    # Хранит общее время для каждого пользователя
    total_time = defaultdict(lambda: 0)
    # Хранит список ошибок (Stop без Start)
    missing_start_logs = []

    with open(log_file_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter=';', quotechar='"')
        for row in reader:
            if len(row) < 4:
                continue
            line = ';'.join(row)  # Восстанавливаем строку с кавычками
            parsed = parse_log_line(line)
            if not parsed:
                continue

            login, action, timestamp, session_id = parsed

            # Фильтрация по логину, если задан
            if target_login and login != target_login:
                continue

            if action == "Start":
                # Сохраняем время старта по session_id
                start_times[session_id] = (login, timestamp)
            elif action == "Stop":
                if session_id in start_times:
                    start_login, start_time = start_times[session_id]
                    if start_login == login:
                        duration = (timestamp - start_time).total_seconds()
                        total_time[login] += duration
                        # Удаляем использованный Start
                        del start_times[session_id]
                    else:
                        missing_start_logs.append(f"Stop для {login} в {timestamp}: session_id {session_id} принадлежит другому пользователю")
                else:
                    missing_start_logs.append(f"Stop без Start для {login} в {timestamp}, session_id: {session_id}")

    # Проверка: остались ли незавершённые сессии (Start без Stop)
    for session_id, (login, start_time) in start_times.items():
        if not target_login or login == target_login:
            missing_start_logs.append(f"Start без Stop для {login} в {start_time}, session_id: {session_id}")

    return dict(total_time), missing_start_logs

def format_duration(seconds):
    """Форматирует секунды в ЧЧ:ММ:СС"""
    hours, remainder = divmod(int(seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

def main():
    parser = argparse.ArgumentParser(description="Вычисление времени работы пользователя по логам Start/Stop")
    parser.add_argument("log_file", help="Путь к файлу лога")
    parser.add_argument("--login", "-l", help="Фильтр по логину. Если не указан — обрабатываются все логины.", default=None)
    args = parser.parse_args()

    try:
        total_time, errors = calculate_work_time(args.log_file, args.login)
    except FileNotFoundError:
        print(f"Файл не найден: {args.log_file}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Ошибка при обработке лога: {e}", file=sys.stderr)
        sys.exit(1)

    if args.login:
        # Только один пользователь
        time_sec = total_time.get(args.login, 0)
        print(f"Общее время работы для {args.login}: {format_duration(time_sec)}")
        if errors:
            print("\nПредупреждения:")
            for err in errors:
                if args.login in err:
                    print(f"  - {err}")
    else:
        # Все пользователи
        if total_time:
            print("Общее время работы пользователей:")
            for login in sorted(total_time.keys()):
                print(f"  {login}: {format_duration(total_time[login])}")
        else:
            print("Не найдено ни одного корректного интервала Start-Stop.")

        if errors:
            print("\nПредупреждения (Start без Stop или Stop без Start):")
            for err in errors:
                print(f"  - {err}")

if __name__ == "__main__":
    main()

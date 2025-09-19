import argparse
import csv
from datetime import datetime
from collections import defaultdict
import sys
import os
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import threading

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

class WorkTimeCalculatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Калькулятор времени работы")
        self.root.geometry("700x500")
        self.root.minsize(600, 400)

        # Настройка стиля
        self.style = ttk.Style()
        self.style.configure("TFrame", padding=10)
        self.style.configure("TButton", padding=5)
        self.style.configure("TLabel", padding=5)

        # Создаем основные фреймы
        self.main_frame = ttk.Frame(root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Фрейм для выбора файла
        self.file_frame = ttk.LabelFrame(self.main_frame, text="Выбор лог-файла")
        self.file_frame.pack(fill=tk.X, padx=5, pady=5)

        self.file_path = tk.StringVar()
        ttk.Entry(self.file_frame, textvariable=self.file_path, width=50).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)
        ttk.Button(self.file_frame, text="Обзор...", command=self.browse_file).pack(side=tk.RIGHT, padx=5, pady=5)

        # Фрейм для выбора логина
        self.login_frame = ttk.LabelFrame(self.main_frame, text="Фильтр по логину (опционально)")
        self.login_frame.pack(fill=tk.X, padx=5, pady=5)

        self.login_var = tk.StringVar()
        ttk.Entry(self.login_frame, textvariable=self.login_var, width=30).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)

        # Кнопка запуска
        self.button_frame = ttk.Frame(self.main_frame)
        self.button_frame.pack(fill=tk.X, padx=5, pady=10)

        self.calculate_btn = ttk.Button(self.button_frame, text="Рассчитать время", command=self.start_calculation)
        self.calculate_btn.pack(side=tk.RIGHT, padx=5)

        self.cancel_btn = ttk.Button(self.button_frame, text="Отмена", command=self.cancel_calculation, state=tk.DISABLED)
        self.cancel_btn.pack(side=tk.RIGHT, padx=5)

        # Фрейм для результатов
        self.results_frame = ttk.LabelFrame(self.main_frame, text="Результаты")
        self.results_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Создаем вкладки для результатов
        self.notebook = ttk.Notebook(self.results_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Вкладка с результатами
        self.results_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.results_tab, text="Результаты")

        self.results_text = scrolledtext.ScrolledText(self.results_tab, wrap=tk.WORD, state=tk.DISABLED)
        self.results_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Вкладка с ошибками
        self.errors_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.errors_tab, text="Предупреждения")

        self.errors_text = scrolledtext.ScrolledText(self.errors_tab, wrap=tk.WORD, state=tk.DISABLED)
        self.errors_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Статус бар
        self.status_var = tk.StringVar()
        self.status_var.set("Готов к работе")
        self.status_bar = ttk.Label(root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Переменные для управления процессом
        self.calculation_thread = None
        self.stop_calculation = False

    def browse_file(self):
        file_path = filedialog.askopenfilename(
            title="Выберите лог-файл",
            filetypes=[("CSV файлы", "*.csv"), ("Все файлы", "*.*")]
        )
        if file_path:
            self.file_path.set(file_path)

    def start_calculation(self):
        if not self.file_path.get():
            messagebox.showerror("Ошибка", "Пожалуйста, выберите лог-файл")
            return

        if not os.path.exists(self.file_path.get()):
            messagebox.showerror("Ошибка", "Указанный файл не существует")
            return

        # Подготовка к выполнению
        self.status_var.set("Выполняется расчет...")
        self.calculate_btn.config(state=tk.DISABLED)
        self.cancel_btn.config(state=tk.NORMAL)
        self.stop_calculation = False
        self.results_text.config(state=tk.NORMAL)
        self.results_text.delete(1.0, tk.END)
        self.results_text.config(state=tk.DISABLED)
        self.errors_text.config(state=tk.NORMAL)
        self.errors_text.delete(1.0, tk.END)
        self.errors_text.config(state=tk.DISABLED)

        # Запускаем расчет в отдельном потоке
        self.calculation_thread = threading.Thread(target=self.run_calculation)
        self.calculation_thread.daemon = True
        self.calculation_thread.start()

    def cancel_calculation(self):
        self.stop_calculation = True
        self.status_var.set("Отмена расчета...")

    def run_calculation(self):
        try:
            log_file = self.file_path.get()
            login = self.login_var.get() or None

            total_time, errors = calculate_work_time(log_file, login)

            # Проверяем, не была ли отменена операция
            if self.stop_calculation:
                self.status_var.set("Расчет отменен пользователем")
                self._update_ui_after_calculation(None, None, cancelled=True)
                return

            # Обновляем интерфейс с результатами
            self._update_ui_after_calculation(total_time, errors)

        except Exception as e:
            self.status_var.set(f"Ошибка: {str(e)}")
            self._update_ui_after_calculation(None, [f"Ошибка при обработке: {str(e)}"])

    def _update_ui_after_calculation(self, total_time, errors, cancelled=False):
        # Возвращаем интерфейс в исходное состояние
        self.calculate_btn.config(state=tk.NORMAL)
        self.cancel_btn.config(state=tk.DISABLED)

        if cancelled:
            self.status_var.set("Расчет отменен")
            return

        if total_time is None:
            self.status_var.set("Ошибка при расчете")
            return

        # Отображаем результаты
        self.results_text.config(state=tk.NORMAL)
        if total_time:
            if self.login_var.get():
                # Только один пользователь
                time_sec = total_time.get(self.login_var.get(), 0)
                self.results_text.insert(tk.END, f"Общее время работы для {self.login_var.get()}:\n")
                self.results_text.insert(tk.END, f"{format_duration(time_sec)}\n")
            else:
                # Все пользователи
                self.results_text.insert(tk.END, "Общее время работы пользователей:\n")
                for login in sorted(total_time.keys()):
                    self.results_text.insert(tk.END, f"{login}: {format_duration(total_time[login])}\n")
        else:
            self.results_text.insert(tk.END, "Не найдено ни одного корректного интервала Start-Stop.")
        self.results_text.config(state=tk.DISABLED)

        # Отображаем ошибки
        self.errors_text.config(state=tk.NORMAL)
        if errors:
            for err in errors:
                self.errors_text.insert(tk.END, f"- {err}\n")
        else:
            self.errors_text.insert(tk.END, "Ошибок и предупреждений не обнаружено.")
        self.errors_text.config(state=tk.DISABLED)

        self.status_var.set("Расчет завершен")

def main():
    root = tk.Tk()
    app = WorkTimeCalculatorApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()

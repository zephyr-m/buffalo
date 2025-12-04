#!/usr/bin/env python3
"""
Менеджер буфера обмена с историей
Горячие клавиши: Ctrl+Shift+V - показать/скрыть историю, Ctrl+X - выход
"""

import tkinter as tk
from tkinter import ttk
import pyperclip
import threading
import time
from datetime import datetime
from pynput import keyboard
import json
import os

class ClipboardManager:
    def __init__(self, root=None):
        self.root = root
        self.history = []
        self.max_history = 50
        self.last_clipboard = ""
        self.running = True
        self.window = None
        self.data_file = os.path.join(os.path.dirname(__file__), 'clipboard_history.json')
        self.keys_pressed = set()
        self.window_visible = False
        self.clipboard_lock = threading.Lock()
        self.save_lock = threading.Lock()
        self.last_ctrl_press = 0  # Время последнего нажатия Ctrl
        self.history_scrollable = None  # Контейнер для карточек
        
        # Загружаем историю
        self.load_history()
        
        # Запускаем мониторинг буфера в фоне
        self.monitor_thread = threading.Thread(target=self.monitor_clipboard, daemon=True)
        self.monitor_thread.start()
        
        # Настраиваем горячие клавиши
        self.setup_hotkeys()
        
        print("🦬 Buffalo запущен!")
        print("🔥 Двойной Ctrl - показать/скрыть Buffalo")
        print("🔥 Esc - скрыть окно")
        print("🛑 Остановка: sudo supervisorctl stop clipboard-manager")
        print(f"📚 Загружено {len(self.history)} записей")

    def load_history(self):
        """Загружаем историю из файла"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.history = data.get('history', [])
                    print(f"📚 Загружено {len(self.history)} записей из истории")
        except Exception as e:
            print(f"⚠️ Ошибка загрузки истории: {e}")

    def save_history(self):
        """Сохраняем историю в файл"""
        with self.save_lock:
            try:
                # Атомарная запись через временный файл
                temp_file = self.data_file + '.tmp'
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump({'history': self.history}, f, ensure_ascii=False, indent=2)
                
                # Атомарное переименование
                os.replace(temp_file, self.data_file)
            except Exception as e:
                print(f"⚠️ Ошибка сохранения истории: {e}")
                # Удаляем поврежденный временный файл
                try:
                    os.remove(temp_file)
                except:
                    pass

    def monitor_clipboard(self):
        """Мониторинг изменений буфера обмена"""
        while self.running:
            try:
                current_clipboard = pyperclip.paste()
                
                # Проверяем изменения с блокировкой от race condition
                with self.clipboard_lock:
                    if (current_clipboard != self.last_clipboard and 
                        current_clipboard.strip() and 
                        len(current_clipboard.strip()) > 1):
                        
                        self.add_to_history(current_clipboard)
                        self.last_clipboard = current_clipboard
                    
            except Exception as e:
                print(f"⚠️ Ошибка мониторинга: {e}")
            
            time.sleep(0.3)  # Уменьшил интервал для лучшей отзывчивости

    def add_to_history(self, text):
        """Добавляем текст в историю"""
        # Фильтруем специальные символы и проверяем длину
        try:
            clean_text = text.encode('utf-8', errors='replace').decode('utf-8')
            # Игнорируем короткие записи и длинные (больше 50 символов)
            if len(clean_text.strip()) < 2 or len(clean_text.strip()) > 50:
                return
        except:
            return  # Игнорируем проблемные тексты
        
        # Убираем дубликаты
        self.history = [item for item in self.history if item['text'] != clean_text]
        
        # Добавляем новую запись в начало
        entry = {
            'text': clean_text,
            'timestamp': datetime.now().isoformat(),
            'preview': clean_text[:80] + ('...' if len(clean_text) > 80 else '')
        }
        
        self.history.insert(0, entry)
        
        # Ограничиваем размер истории
        if len(self.history) > self.max_history:
            self.history = self.history[:self.max_history]
        
        # Сохраняем в главном потоке через root.after
        if self.root:
            self.root.after(0, self.save_history)
        else:
            self.save_history()
        
        print(f"📋 Добавлено: {entry['preview']}")

    def setup_hotkeys(self):
        """Настройка горячих клавиш"""
        def on_press(key):
            try:
                if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
                    # Проверяем двойное нажатие Ctrl
                    current_time = time.time()
                    if current_time - self.last_ctrl_press < 0.4:  # 400мс
                        # Двойной Ctrl - toggle окна
                        self.show_history_window()
                        self.last_ctrl_press = 0  # Сбрасываем
                    else:
                        self.last_ctrl_press = current_time
                    self.keys_pressed.add('ctrl')
                elif key == keyboard.Key.shift_l or key == keyboard.Key.shift_r:
                    self.keys_pressed.add('shift')
                elif key == keyboard.Key.esc:
                    # Esc - скрыть окно (если открыто)
                    if self.window_visible:
                        self.show_history_window()  # toggle закроет
                        
            except AttributeError:
                pass

        def on_release(key):
            try:
                if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
                    self.keys_pressed.discard('ctrl')
                elif key == keyboard.Key.shift_l or key == keyboard.Key.shift_r:
                    self.keys_pressed.discard('shift')
            except AttributeError:
                pass

        self.key_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self.key_listener.start()

    def show_history_window(self):
        """Показываем окно с историей"""
        # Если окно уже открыто - прячем его (toggle)
        if self.window_visible:
            self.hide_history_window()
            return
            
        self.window_visible = True
        
        # Если окно не создано - создаем
        if not self.window or not self.window.winfo_exists():
            self.create_history_window()
        else:
            # Обновляем содержимое перед показом
            self.refresh_history()
        
        # Показываем окно
        self.window.deiconify()
        
        # Прижимаем к левому краю ПОСЛЕ показа
        screen_height = self.window.winfo_screenheight()
        self.window.geometry(f"560x{int(screen_height * 0.9)}+0+50")
        
        self.window.lift()
        self.window.attributes('-topmost', True)

    def hide_history_window(self):
        """Прячем окно"""
        if self.window and self.window.winfo_exists():
            self.window.withdraw()
            self.window_visible = False
        else:
            self.window_visible = False

    def clear_history(self):
        """Очищаем всю историю"""
        self.history = []
        self.save_history()
        print("🗑️ История очищена")
        # Уничтожаем окно
        if self.window and self.window.winfo_exists():
            self.window.destroy()
            self.window = None
            self.window_visible = False

    def refresh_history(self):
        """Обновляем содержимое окна без пересоздания"""
        if not self.history_scrollable or not self.history_scrollable.winfo_exists():
            return
        
        # Очищаем все виджеты
        for widget in self.history_scrollable.winfo_children():
            widget.destroy()
        
        # Заново заполняем
        self.populate_history_cards(self.history_scrollable)

    def delete_entry(self, text):
        """Удаляем конкретную запись"""
        self.history = [item for item in self.history if item['text'] != text]
        self.save_history()
        print(f"🗑️ Удалено: {text[:30]}...")
        # Обновляем содержимое окна
        self.refresh_history()

    def create_history_window(self):
        """Создаем окно истории"""
        if self.root:
            self.window = tk.Toplevel(self.root)
        else:
            self.window = tk.Tk()
        
        self.window.title("🦬 Buffalo")
        
        # Получаем размеры экрана
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        
        # Ширина 560px (на 30% уже), высота 90% экрана
        window_width = 560
        window_height = int(screen_height * 0.9)
        
        # Окно поверх всех
        self.window.attributes('-topmost', True)
        
        # Прижимаем окно к левому краю
        self.left_align_window(window_width, window_height)
        
        # Скрываем окно сразу (показываем только по Ctrl+F)
        self.window.withdraw()
        
        # Основной фрейм с градиентом (имитация через цвет)
        main_frame = tk.Frame(self.window, bg='#f8f9fa', padx=0, pady=0)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Заголовок с кнопкой очистки - темный фон
        header_frame = tk.Frame(main_frame, bg='#2c3e50', padx=15, pady=12)
        header_frame.pack(fill=tk.X)
        
        title_label = tk.Label(header_frame, text="🦬 Buffalo", 
                              font=('Segoe UI', 13, 'bold'), 
                              bg='#2c3e50', fg='#ecf0f1')
        title_label.pack(side='left')
        
        clear_btn = tk.Button(header_frame, text="🗑️ Очистить", 
                            font=('Segoe UI', 9, 'bold'),
                            bg='#e74c3c', fg='white',
                            relief='flat', bd=0,
                            padx=12, pady=6,
                            cursor='hand2',
                            activebackground='#c0392b',
                            activeforeground='white',
                            command=self.clear_history)
        clear_btn.pack(side='right')
        
        # Hover эффект для кнопки очистки
        def on_enter(e):
            clear_btn.config(bg='#c0392b')
        def on_leave(e):
            clear_btn.config(bg='#e74c3c')
        clear_btn.bind("<Enter>", on_enter)
        clear_btn.bind("<Leave>", on_leave)
        
        # Скроллируемая область для истории
        history_canvas = tk.Canvas(main_frame, bg='#f8f9fa', highlightthickness=0)
        history_scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=history_canvas.yview)
        self.history_scrollable = tk.Frame(history_canvas, bg='#f8f9fa')
        
        self.history_scrollable.bind(
            "<Configure>",
            lambda e: history_canvas.configure(scrollregion=history_canvas.bbox("all"))
        )
        
        history_canvas.create_window((0, 0), window=self.history_scrollable, anchor="nw")
        history_canvas.configure(yscrollcommand=history_scrollbar.set)
        
        # Привязываем скролл колесом мыши (Linux)
        def on_mousewheel_up(event):
            history_canvas.yview_scroll(-1, "units")
        def on_mousewheel_down(event):
            history_canvas.yview_scroll(1, "units")
        
        history_canvas.bind_all("<Button-4>", on_mousewheel_up)
        history_canvas.bind_all("<Button-5>", on_mousewheel_down)
        
        history_canvas.pack(side="left", fill="both", expand=True)
        history_scrollbar.pack(side="right", fill="y")
        
        # Заполняем данными
        self.populate_history_cards(self.history_scrollable)
        
        # Обработчик закрытия окна
        def on_window_close():
            self.window_visible = False
            self.window.destroy()
        
        # Обработчик потери фокуса - автоматически прячем окно
        def on_focus_out(event):
            # Прячем окно только если фокус ушел на другое приложение (не на дочерние виджеты)
            if self.window_visible and event.widget == self.window:
                # Небольшая задержка чтобы проверить куда ушел фокус
                self.window.after(100, lambda: self._check_focus())
        
        self.window.protocol("WM_DELETE_WINDOW", on_window_close)
        self.window.bind("<FocusOut>", on_focus_out)
    
    def _check_focus(self):
        """Проверяем что фокус действительно ушел за пределы окна"""
        try:
            if self.window and self.window_visible:
                focused = self.window.focus_get()
                # Если фокус не на нашем окне и не на его дочерних виджетах - прячем
                if focused is None or not str(focused).startswith(str(self.window)):
                    self.hide_history_window()
        except:
            pass

    def left_align_window(self, width, height):
        """Прижимаем окно к левому краю экрана"""
        self.window.update_idletasks()
        
        # Проверяем границы экрана
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        
        # Ограничиваем размеры окна размерами экрана
        width = min(width, screen_width - 100)
        height = min(height, screen_height - 100)
        
        x = 0  # Прижимаем к левому краю
        y = max(0, 50)  # Небольшой отступ сверху
        
        self.window.geometry(f"{width}x{height}+{x}+{y}")

    def populate_history_cards(self, parent):
        """Заполняем карточками истории"""
        if not self.history:
            no_data_label = tk.Label(parent, text="История пуста", 
                                   font=('Segoe UI', 12), 
                                   bg='#2d2d2d', fg='#888888')
            no_data_label.pack(pady=20)
            return
        
        for i, entry in enumerate(self.history):
            self.create_card(parent, entry, i, show_count=False)

    def create_card(self, parent, entry, index, show_count=False):
        """Создаем карточку для записи"""
        # Внешний фрейм - рамка (белая)
        border_frame = tk.Frame(parent, bg='#ffffff', padx=1, pady=1)
        border_frame.pack(fill=tk.X, pady=4, padx=8)
        
        # Внутренний фрейм - карточка
        card_frame = tk.Frame(border_frame, bg='#ffffff')
        card_frame.pack(fill=tk.BOTH, expand=True)
        
        # Контент с отступами
        inner_frame = tk.Frame(card_frame, bg='#ffffff')
        inner_frame.pack(fill=tk.X, padx=10, pady=8)
        
        # Контейнер для текста и кнопки
        content_frame = tk.Frame(inner_frame, bg='#ffffff')
        content_frame.pack(fill=tk.X, pady=2)
        
        # Текст команды
        text_preview = entry['preview'].replace('\n', ' ').replace('\r', ' ')
        text_label = tk.Label(content_frame, text=text_preview, 
                             font=('Consolas', 10), 
                             bg='#ffffff', fg='#2c3e50',
                             anchor='w', justify='left')
        text_label.pack(side='left', fill='x', expand=True)
        
        # Кнопка удаления
        delete_btn = tk.Button(content_frame, text="🗑️", 
                             font=('Segoe UI', 11),
                             bg='#e74c3c', fg='white',
                             relief='flat', bd=0,
                             padx=8, pady=4,
                             cursor='hand2',
                             activebackground='#c0392b',
                             activeforeground='white',
                             command=lambda: self.delete_entry(entry['text']))
        delete_btn.pack(side='right', padx=(8, 0))
        
        # Кнопка копирования
        copy_btn = tk.Button(content_frame, text="📋", 
                           font=('Segoe UI', 11),
                           bg='#3498db', fg='white',
                           relief='flat', bd=0,
                           padx=8, pady=4,
                           cursor='hand2',
                           activebackground='#2980b9',
                           activeforeground='white',
                           command=lambda: self.copy_and_hide(entry['text']))
        copy_btn.pack(side='right', padx=(8, 0))
        
        # Эффект hover для кнопки копирования
        def copy_on_enter(e):
            copy_btn.config(bg='#2980b9')
        def copy_on_leave(e):
            copy_btn.config(bg='#3498db')
        copy_btn.bind("<Enter>", copy_on_enter)
        copy_btn.bind("<Leave>", copy_on_leave)
        
        # Эффект hover для кнопки удаления
        def delete_on_enter(e):
            delete_btn.config(bg='#c0392b')
        def delete_on_leave(e):
            delete_btn.config(bg='#e74c3c')
        delete_btn.bind("<Enter>", delete_on_enter)
        delete_btn.bind("<Leave>", delete_on_leave)
        
        # Эффект hover для карточки
        def card_on_enter(e):
            border_frame.config(bg='#3498db')  # Синяя рамка
            card_frame.config(bg='#e8f4f8')
            inner_frame.config(bg='#e8f4f8')
            content_frame.config(bg='#e8f4f8')
            text_label.config(bg='#e8f4f8')
        
        def card_on_leave(e):
            border_frame.config(bg='#ffffff')  # Белая рамка
            card_frame.config(bg='#ffffff')
            inner_frame.config(bg='#ffffff')
            content_frame.config(bg='#ffffff')
            text_label.config(bg='#ffffff')
        
        # Клик по карточке = копирование
        def on_card_click(e):
            self.copy_and_hide(entry['text'])
        
        border_frame.bind("<Enter>", card_on_enter)
        border_frame.bind("<Leave>", card_on_leave)
        border_frame.bind("<Button-1>", on_card_click)
        card_frame.bind("<Enter>", card_on_enter)
        card_frame.bind("<Leave>", card_on_leave)
        card_frame.bind("<Button-1>", on_card_click)
        inner_frame.bind("<Enter>", card_on_enter)
        inner_frame.bind("<Leave>", card_on_leave)
        inner_frame.bind("<Button-1>", on_card_click)
        text_label.bind("<Enter>", card_on_enter)
        text_label.bind("<Leave>", card_on_leave)
        text_label.bind("<Button-1>", on_card_click)

    def copy_and_hide(self, text):
        """Копируем текст и скрываем окно"""
        try:
            pyperclip.copy(text)
            print(f"📋 Скопировано: {text[:50]}...")
        except Exception as e:
            print(f"⚠️ Ошибка копирования: {e}")
        finally:
            self.hide_history_window()

    def stop(self):
        """Останавливаем менеджер"""
        self.running = False
        if hasattr(self, 'key_listener'):
            self.key_listener.stop()
        print("👋 Менеджер буфера остановлен")

def main():
    """Главная функция"""
    try:
        # Создаем скрытое главное окно
        root = tk.Tk()
        root.withdraw()
        
        # Запускаем менеджер
        manager = ClipboardManager(root)
        
        # Обработчик закрытия
        def on_closing():
            manager.stop()
            root.quit()
        
        root.protocol("WM_DELETE_WINDOW", on_closing)
        
        # Запускаем главный цикл
        try:
            root.mainloop()
        except KeyboardInterrupt:
            print("\n🛑 Получен сигнал остановки")
            manager.stop()
            
    except Exception as e:
        print(f"💥 Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

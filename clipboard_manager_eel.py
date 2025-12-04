#!/usr/bin/env python3
"""
Мультибуфер обмена с HTML интерфейсом через Eel
Горячие клавиши: Ctrl+F - показать/скрыть, Esc - скрыть
"""

import eel
import pyperclip
import threading
import time
from datetime import datetime
from pynput import keyboard
import json
import os

class ClipboardManager:
    def __init__(self):
        self.history = []
        self.max_history = 50
        self.last_clipboard = ""
        self.running = True
        self.data_file = os.path.join(os.path.dirname(__file__), 'clipboard_history.json')
        self.keys_pressed = set()
        self.window_visible = False
        self.clipboard_lock = threading.Lock()
        self.save_lock = threading.Lock()
        
        # Загружаем историю
        self.load_history()
        
        # Запускаем мониторинг буфера в фоне
        self.monitor_thread = threading.Thread(target=self.monitor_clipboard, daemon=True)
        self.monitor_thread.start()
        
        # Настраиваем горячие клавиши
        self.setup_hotkeys()
        
        print("📋 Мультибуфер запущен!")
        print("🔥 Ctrl+F - показать/скрыть (любая раскладка)")
        print("🔥 Esc - скрыть окно")
        print(f"📚 Загружено {len(self.history)} записей")

    def load_history(self):
        """Загружаем историю из файла"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.history = data.get('history', [])
        except Exception as e:
            print(f"⚠️ Ошибка загрузки истории: {e}")

    def save_history(self):
        """Сохраняем историю в файл"""
        with self.save_lock:
            try:
                temp_file = self.data_file + '.tmp'
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump({'history': self.history}, f, ensure_ascii=False, indent=2)
                os.replace(temp_file, self.data_file)
            except Exception as e:
                print(f"⚠️ Ошибка сохранения: {e}")
                try:
                    os.remove(temp_file)
                except:
                    pass

    def monitor_clipboard(self):
        """Мониторинг изменений буфера обмена"""
        while self.running:
            try:
                current_clipboard = pyperclip.paste()
                
                with self.clipboard_lock:
                    if (current_clipboard != self.last_clipboard and 
                        current_clipboard.strip() and 
                        2 <= len(current_clipboard.strip()) <= 50):
                        
                        self.add_to_history(current_clipboard)
                        self.last_clipboard = current_clipboard
                    
            except Exception as e:
                print(f"⚠️ Ошибка мониторинга: {e}")
            
            time.sleep(0.3)

    def add_to_history(self, text):
        """Добавляем текст в историю"""
        try:
            clean_text = text.encode('utf-8', errors='replace').decode('utf-8')
            if not (2 <= len(clean_text.strip()) <= 50):
                return
        except:
            return
        
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
        
        self.save_history()
        print(f"📋 Добавлено: {entry['preview']}")

    def setup_hotkeys(self):
        """Настройка горячих клавиш"""
        def on_press(key):
            try:
                if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
                    self.keys_pressed.add('ctrl')
                elif key == keyboard.Key.esc:
                    if self.window_visible:
                        self.hide_window()
                elif hasattr(key, 'char') and key.char:
                    char = key.char.lower()
                    if char in ['f', 'а']:
                        self.keys_pressed.add('f')
                        if {'ctrl', 'f'} == self.keys_pressed:
                            self.toggle_window()
            except AttributeError:
                pass

        def on_release(key):
            try:
                if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
                    self.keys_pressed.discard('ctrl')
                elif hasattr(key, 'char') and key.char:
                    char = key.char.lower()
                    if char in ['f', 'а']:
                        self.keys_pressed.discard('f')
            except AttributeError:
                pass

        self.key_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self.key_listener.start()

    def toggle_window(self):
        """Toggle видимости окна"""
        if self.window_visible:
            self.hide_window()
        else:
            self.show_window()

    def show_window(self):
        """Показываем окно"""
        self.window_visible = True
        eel.show_window()

    def hide_window(self):
        """Прячем окно"""
        self.window_visible = False
        eel.hide_window()

    def get_history(self):
        """Возвращаем историю для JS"""
        return self.history

    def clear_history(self):
        """Очищаем всю историю"""
        self.history = []
        self.save_history()
        print("🗑️ История очищена")

    def delete_entry(self, text):
        """Удаляем конкретную запись"""
        self.history = [item for item in self.history if item['text'] != text]
        self.save_history()
        print(f"🗑️ Удалено: {text[:30]}...")

    def copy_to_clipboard(self, text):
        """Копируем текст в буфер"""
        try:
            with self.clipboard_lock:
                self.last_clipboard = text
                pyperclip.copy(text)
            print(f"📋 Скопировано: {text[:50]}...")
            self.hide_window()
        except Exception as e:
            print(f"⚠️ Ошибка копирования: {e}")

# Глобальный менеджер
manager = None

# Expose функции для JS
@eel.expose
def get_history():
    return manager.get_history()

@eel.expose
def clear_history():
    manager.clear_history()

@eel.expose
def delete_entry(text):
    manager.delete_entry(text)

@eel.expose
def copy_to_clipboard(text):
    manager.copy_to_clipboard(text)

def main():
    global manager
    
    # Инициализируем Eel
    eel.init('web')
    
    # Создаем менеджер
    manager = ClipboardManager()
    
    # Запускаем окно
    try:
        eel.start('index.html', 
                  size=(560, 900), 
                  position=(0, 50),
                  mode='chrome',
                  close_callback=lambda *args: None)
    except Exception as e:
        print(f"💥 Ошибка запуска: {e}")

if __name__ == "__main__":
    main()

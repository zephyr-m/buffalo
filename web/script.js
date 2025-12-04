// Загружаем историю при старте
window.addEventListener('DOMContentLoaded', () => {
    loadHistory();
});

let lastHistoryLength = 0;

// Функции для управления видимостью из Python
eel.expose(show_window);
function show_window() {
    document.body.style.opacity = '1';
    document.body.style.pointerEvents = 'auto';
}

eel.expose(hide_window);
function hide_window() {
    document.body.style.opacity = '0';
    document.body.style.pointerEvents = 'none';
}

// Загрузка истории
async function loadHistory() {
    const history = await eel.get_history()();
    
    // Обновляем только если изменилось количество
    if (history.length !== lastHistoryLength) {
        lastHistoryLength = history.length;
        renderHistory(history);
    }
}

// Отрисовка истории
function renderHistory(history) {
    const container = document.getElementById('history');
    const empty = document.getElementById('empty');
    
    container.innerHTML = '';
    
    if (!history || history.length === 0) {
        empty.classList.add('show');
        return;
    }
    
    empty.classList.remove('show');
    
    history.forEach(entry => {
        const card = createCard(entry);
        container.appendChild(card);
    });
}

// Создание карточки
function createCard(entry) {
    const card = document.createElement('div');
    card.className = 'card';
    
    const text = document.createElement('div');
    text.className = 'card-text';
    text.textContent = entry.text;
    
    const actions = document.createElement('div');
    actions.className = 'card-actions';
    
    const copyBtn = document.createElement('button');
    copyBtn.className = 'btn';
    copyBtn.textContent = '📋';
    copyBtn.onclick = (e) => {
        e.stopPropagation();
        copyToClipboard(entry.text);
    };
    
    const deleteBtn = document.createElement('button');
    deleteBtn.className = 'btn btn-delete';
    deleteBtn.textContent = '🗑️';
    deleteBtn.onclick = (e) => {
        e.stopPropagation();
        deleteEntry(entry.text);
    };
    
    actions.appendChild(copyBtn);
    actions.appendChild(deleteBtn);
    
    card.appendChild(text);
    card.appendChild(actions);
    
    // Клик по карточке = копирование
    card.onclick = () => copyToClipboard(entry.text);
    
    return card;
}

// Копирование в буфер
async function copyToClipboard(text) {
    await eel.copy_to_clipboard(text)();
}

// Удаление записи
async function deleteEntry(text) {
    await eel.delete_entry(text)();
    loadHistory();
}

// Очистка всей истории
document.getElementById('clearBtn').addEventListener('click', async () => {
    await eel.clear_history()();
    loadHistory();
});

// Проверяем изменения каждые 2 секунды (не перерисовываем если не изменилось)
setInterval(loadHistory, 2000);

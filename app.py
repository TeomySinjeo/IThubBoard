import os
import sqlite3
import time
from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = 'super_secret_key_ithubb' # Нужно для работы сессий

ADMIN_PASSWORD = "admin123" # Пароль для админа (можете поменять)

def get_db_connection():
    conn = sqlite3.connect('ithubb.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            category TEXT NOT NULL,
            contact TEXT,
            author_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_deleted BOOLEAN DEFAULT 0,
            delete_reason TEXT
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS feedbacks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            score INTEGER NOT NULL,
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

@app.route('/')
def index():
    init_db()
    search_query = request.args.get('q', '')
    category_filter = request.args.get('category', '')
    
    # Пагинация
    page = int(request.args.get('page', 1))
    per_page = 6
    offset = (page - 1) * per_page

    conn = get_db_connection()
    
    # Считаем общее количество для пагинации
    count_query = 'SELECT COUNT(*) FROM announcements WHERE is_deleted = 0'
    count_params = []
    
    query = 'SELECT * FROM announcements WHERE is_deleted = 0'
    params = []

    if search_query:
        query += ' AND (title LIKE ? OR body LIKE ?)'
        count_query += ' AND (title LIKE ? OR body LIKE ?)'
        params.extend([f'%{search_query}%', f'%{search_query}%'])
        count_params.extend([f'%{search_query}%', f'%{search_query}%'])
    
    if category_filter:
        query += ' AND category = ?'
        count_query += ' AND category = ?'
        params.append(category_filter)
        count_params.append(category_filter)

    total_items = conn.execute(count_query, count_params).fetchone()[0]
    has_more = (offset + per_page) < total_items

    query += ' ORDER BY created_at DESC LIMIT ? OFFSET ?'
    params.extend([per_page, offset])
    
    announcements = conn.execute(query, params).fetchall()
    conn.close()
    
    return render_template('index.html', 
                           announcements=announcements, 
                           search_query=search_query, 
                           category_filter=category_filter,
                           page=page,
                           has_more=has_more)

@app.route('/create', methods=['GET', 'POST'])
def create():
    if request.method == 'POST':
        # Защита от спама
        last_post_time = session.get('last_post_time', 0)
        current_time = time.time()
        if current_time - last_post_time < 30:
            return "Подождите 30 секунд перед созданием нового объявления.", 429

        title = request.form['title']
        body = request.form['body']
        category = request.form['category']
        contact = request.form.get('contact', '')
        author_name = request.form.get('author_name', 'Аноним')
        
        conn = get_db_connection()
        conn.execute('INSERT INTO announcements (title, body, category, contact, author_name) VALUES (?, ?, ?, ?, ?)',
                     (title, body, category, contact, author_name))
        conn.commit()
        conn.close()
        
        session['last_post_time'] = current_time
        return redirect(url_for('index', success='1'))
    return render_template('create.html')

@app.route('/announcement/<int:id>')
def view(id):
    conn = get_db_connection()
    # Ищем объявление, даже если оно удалено (чтобы показать причину)
    announcement = conn.execute('SELECT * FROM announcements WHERE id = ?', (id,)).fetchone()
    conn.close()
    if announcement is None:
        return "Объявление не найдено", 404
    return render_template('view.html', announcement=announcement)

# --- АДМИН ПАНЕЛЬ ---
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == ADMIN_PASSWORD:
            session['is_admin'] = True
            return redirect(url_for('admin'))
        else:
            return render_template('admin.html', error="Неверный пароль!")

    if not session.get('is_admin'):
        return render_template('admin.html', is_auth=False)

    # Если админ авторизован - показываем все объявления и отзывы
    conn = get_db_connection()
    announcements = conn.execute('SELECT * FROM announcements ORDER BY created_at DESC').fetchall()
    feedbacks = conn.execute('SELECT * FROM feedbacks ORDER BY created_at DESC').fetchall()
    conn.close()
    
    return render_template('admin.html', is_auth=True, announcements=announcements, feedbacks=feedbacks)

@app.route('/admin/delete/<int:id>', methods=['POST'])
def admin_delete(id):
    if not session.get('is_admin'):
        return redirect(url_for('admin'))
    
    reason = request.form.get('reason', 'Нарушение правил')
    
    conn = get_db_connection()
    conn.execute('UPDATE announcements SET is_deleted = 1, delete_reason = ? WHERE id = ?', (reason, id))
    conn.commit()
    conn.close()
    
    return redirect(url_for('admin'))

@app.route('/admin/logout')
def admin_logout():
    session.pop('is_admin', None)
    return redirect(url_for('index'))

@app.route('/submit_feedback', methods=['POST'])
def submit_feedback():
    score = request.form.get('score')
    comment = request.form.get('comment', '')
    
    if score:
        conn = get_db_connection()
        conn.execute('INSERT INTO feedbacks (score, comment) VALUES (?, ?)', (score, comment))
        conn.commit()
        conn.close()
        return {"status": "success"}
    return {"status": "error"}, 400

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
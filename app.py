from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)

# Отримуємо абсолютний шлях до папки з app.py
basedir = os.path.abspath(os.path.dirname(__file__))

# Абсолютний шлях до бази
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'data', 'gallery.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(basedir, 'static', 'uploads')
app.config['SECRET_KEY'] = 'change_this_secret_for_production'
print("Database path:", os.path.join(basedir, 'data', 'gallery.db'))

db = SQLAlchemy(app)

# Models
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='user')

    def check_password(self, pwd):
        return check_password_hash(self.password_hash, pwd)


class Collection(db.Model):
    __tablename__ = 'collections'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)


class Artwork(db.Model):
    __tablename__ = 'artworks'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    image_filename = db.Column(db.String(255))
    author = db.Column(db.String(100))
    price = db.Column(db.Numeric(10, 2))
    collection_id = db.Column(db.Integer, db.ForeignKey('collections.id'), nullable=True)


class Favorite(db.Model):
    __tablename__ = 'favorites'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    artwork_id = db.Column(db.Integer, db.ForeignKey('artworks.id'))


class CartItem(db.Model):
    __tablename__ = 'cart_items'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    artwork_id = db.Column(db.Integer, db.ForeignKey('artworks.id'))
    quantity = db.Column(db.Integer, default=1)


class News(db.Model):
    __tablename__ = 'news'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text)


class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    name = db.Column(db.String(200))
    email = db.Column(db.String(200))
    phone = db.Column(db.String(50))
    address = db.Column(db.Text)
    notes = db.Column(db.Text)
    filenames = db.Column(db.Text)  # comma-separated filenames


# helpers
def admin_required(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get('role') != 'admin':
            flash('Потрібен вхід адміністратора', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper

@app.route('/')
def index():
    artworks = Artwork.query.all()
    return render_template('home.html', artworks=artworks, author_name='Ксенія Замараєва')

@app.route('/news')
def news():
    items = News.query.order_by(News.id.desc()).all()
    return render_template('news.html', items=items)

@app.route('/favorites')
def favorites():
    if not session.get('user_id'):
        flash('Увійдіть, щоб бачити вибране', 'info')
        return redirect(url_for('login'))
    favs = Favorite.query.filter_by(user_id=session['user_id']).all()
    arts = [db.session.get(Artwork, f.artwork_id) for f in favs]
    return render_template('favorites.html', artworks=arts)


@app.route('/remove_favorite/<int:art_id>')
def remove_favorite(art_id):
    if not session.get('user_id'):
        flash('Увійдіть', 'info')
        return redirect(url_for('login'))
    f = Favorite.query.filter_by(user_id=session['user_id'], artwork_id=art_id).first()
    if f:
        db.session.delete(f); db.session.commit()
        flash('Видалено з вибраного', 'success')
    else:
        flash('Елемент не знайдено у вибраному', 'warning')
    return redirect(url_for('favorites'))

@app.route('/cart')
def cart():
    if not session.get('user_id'):
        flash('Увійдіть, щоб бачити кошик', 'info')
        return redirect(url_for('login'))
    items = CartItem.query.filter_by(user_id=session['user_id']).all()
    arts = [(db.session.get(Artwork, it.artwork_id), it.quantity) for it in items]
    return render_template('cart.html', items=arts)

# Auth
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        u = request.form['username']
        p = request.form['password']
        user = User.query.filter_by(username=u).first()
        if user and user.check_password(p):
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            flash('Успішний вхід', 'success')
            return redirect(url_for('admin_panel') if user.role=='admin' else url_for('index'))
        flash('Невірний логін або пароль', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Вихід виконано', 'info')
    return redirect(url_for('index'))

# Public actions
@app.route('/add_favorite/<int:art_id>')
def add_favorite(art_id):
    if not session.get('user_id'):
        flash('Увійдіть', 'info')
        return redirect(url_for('login'))
    f = Favorite(user_id=session['user_id'], artwork_id=art_id)
    db.session.add(f); db.session.commit()
    flash('Додано у вибране', 'success')
    return redirect(url_for('favorites'))

@app.route('/add_to_cart/<int:art_id>')
def add_to_cart(art_id):
    if not session.get('user_id'):
        flash('Увійдіть', 'info')
        return redirect(url_for('login'))
    ci = CartItem(user_id=session['user_id'], artwork_id=art_id, quantity=1)
    db.session.add(ci); db.session.commit()
    flash('Додано у кошик', 'success')
    return redirect(url_for('cart'))


@app.route('/remove_from_cart/<int:art_id>')
def remove_from_cart(art_id):
    if not session.get('user_id'):
        flash('Увійдіть', 'info')
        return redirect(url_for('login'))
    ci = CartItem.query.filter_by(user_id=session['user_id'], artwork_id=art_id).first()
    if ci:
        db.session.delete(ci); db.session.commit()
        flash('Твір видалено з кошика', 'success')
    else:
        flash('Елемент не знайдено в кошику', 'warning')
    return redirect(url_for('cart'))


@app.route('/place_order', methods=['POST'])
def place_order():
    if not session.get('user_id'):
        flash('Увійдіть', 'info')
        return redirect(url_for('login'))
    # Collect order details from form (this is shown in cart when user clicks "Оформити замовлення")
    name = request.form.get('name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    address = request.form.get('address')
    notes = request.form.get('notes')
    # No file uploads expected here (these are handled on the compose_order page)
    order = Order(user_id=session.get('user_id'), name=name, email=email, phone=phone, address=address, notes=notes, filenames='')
    db.session.add(order)
    # Clear cart
    CartItem.query.filter_by(user_id=session['user_id']).delete()
    db.session.commit()
    flash('Замовлення оформлено. Дякуємо! Ми з вами звʼяжемося.', 'success')
    return redirect(url_for('index'))


@app.route('/compose_order', methods=['GET','POST'])
def compose_order():
    if not session.get('user_id'):
        flash('Увійдіть, щоб сформувати замовлення', 'info')
        return redirect(url_for('login'))
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        address = request.form.get('address')
        notes = request.form.get('notes')
        saved_files = []
        files = request.files.getlist('reference_files')
        for f in files:
            if f and f.filename:
                filename = secure_filename(f.filename)
                # prefix to avoid collisions
                prefix = f"u{session.get('user_id')}_"
                filename = prefix + filename
                path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                f.save(path)
                saved_files.append(filename)
        filenames_str = ','.join(saved_files)
        order = Order(user_id=session.get('user_id'), name=name, email=email, phone=phone, address=address, notes=notes, filenames=filenames_str)
        db.session.add(order); db.session.commit()
        flash('Повідомлення відправлено, дякую за замовлення! Я розгляну ваше замовлення протягом декількох годин і звʼяжуся з вами.', 'success')
        return redirect(url_for('index'))
    return render_template('compose_order.html')


@app.route('/draw_yourself')
def draw_yourself():
    # Placeholder page for the future game
    return render_template('draw_yourself.html')

# Admin
@app.route('/admin')
@admin_required
def admin_panel():
    artworks = Artwork.query.all()
    collections = Collection.query.all()
    news_items = News.query.all()
    users = User.query.all()
    return render_template('admin.html', artworks=artworks, collections=collections, news=news_items, users=users)

@app.route('/admin/artwork/add', methods=['GET','POST'])
@admin_required
def admin_add_artwork():
    if request.method=='POST':
        title = request.form['title']
        desc = request.form.get('description')
        author = request.form.get('author')
        price = request.form.get('price') or None
        coll = request.form.get('collection_id') or None
        file = request.files.get('image')
        filename = None
        if file and file.filename:
            filename = file.filename
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        art = Artwork(title=title, description=desc, author=author, price=price, image_filename=filename, collection_id=coll)
        db.session.add(art); db.session.commit()
        flash('Твір додано', 'success')
        return redirect(url_for('admin_panel'))
    collections = Collection.query.all()
    return render_template('artwork_form.html', collections=collections)

@app.route('/admin/news/add', methods=['GET','POST'])
@admin_required
def admin_add_news():
    if request.method=='POST':
        title = request.form['title']; content = request.form['content']
        n = News(title=title, content=content); db.session.add(n); db.session.commit()
        flash('Новина додана', 'success'); return redirect(url_for('admin_panel'))
    return render_template('news_form.html')

@app.route('/uploads/<path:filename>')
def uploads(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


if __name__=='__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    if not os.path.exists('data/gallery.db'):
        db.create_all()
    app.run(debug=True)

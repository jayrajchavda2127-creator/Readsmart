import os
import os
from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, session, make_response, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Book, Review, ReadingProgress, Profile, UserFavorite, ContactUs, UserActivity, UserAchievement, Admin, Subscription, FriendRequest, ReadTogetherSession, ChatMessage
from datetime import datetime
import PyPDF2
import razorpay
import hmac
import hashlib

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_super_secret_key_here'
basedir = os.path.abspath(os.path.dirname(__file__))
# Connect to XAMPP/phpMyAdmin default MySQL database named 'readsmart'
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:@localhost/readsmart'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(basedir, 'static', 'Uploads')

# Razorpay
RAZORPAY_KEY_ID = 'rzp_live_U4JBleBHAFhhaG'
RAZORPAY_KEY_SECRET = 'd5f5qkrw1BLRTCR6ofA5t6Dw'
rzp_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

db.init_app(app)

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    books = Book.query.limit(20).all()
    return render_template('index.html', books=books)

@app.route('/library')
def library():
    books = Book.query.all()
    books_data = []
    if current_user.is_authenticated:
        favorites = [f.book_id for f in UserFavorite.query.filter_by(user_id=current_user.id).all()]
    else:
        favorites = []

    for book in books:
        books_data.append({
            'book': book,
            'is_favourite': book.id in favorites
        })

    # Gather unique categories
    all_categories = sorted(set(b.category for b in books if b.category))

    return render_template('library.html', books_data=books_data, categories=all_categories)

@app.route('/favourite_books')
@login_required
def favourite_books():
    favorites = UserFavorite.query.filter_by(user_id=current_user.id).all()
    book_ids = [f.book_id for f in favorites]
    books = Book.query.filter(Book.id.in_(book_ids)).all() if book_ids else []
    
    books_data = []
    for book in books:
        books_data.append({
            'book': book,
            'is_favourite': True
        })
    return render_template('library.html', books_data=books_data, page_title="Your Favourite Books")

@app.route('/toggle_favourite/<int:book_id>')
@login_required
def toggle_favourite(book_id):
    fav = UserFavorite.query.filter_by(user_id=current_user.id, book_id=book_id).first()
    if fav:
        db.session.delete(fav)
    else:
        new_fav = UserFavorite(user_id=current_user.id, book_id=book_id)
        db.session.add(new_fav)
    db.session.commit()
    return redirect(url_for('library'))

@app.route('/read/<int:book_id>')
@login_required
def read(book_id):
    # Special user or active subscriber only
    is_special = current_user.email == 'you@gmail.com'
    has_sub = is_special or (current_user.subscription and current_user.subscription.is_active)
    if not has_sub:
        flash('Subscribe to ReadZey Premium to read books.', 'info')
        return redirect(url_for('subscription'))

    book = Book.query.get_or_404(book_id)
    progress = ReadingProgress.query.filter_by(user_id=current_user.id, book_id=book_id).first()
    if not progress:
        progress = ReadingProgress(user_id=current_user.id, book_id=book_id, current_page=1, total_pages=book.total_pages)
        db.session.add(progress)
        db.session.commit()
    return render_template('read.html', book=book, current_page=progress.current_page)

@app.route('/update_progress', methods=['POST'])
@login_required
def update_progress():
    book_id = request.form.get('book_id')
    current_page = request.form.get('current_page')
    if book_id and current_page:
        progress = ReadingProgress.query.filter_by(user_id=current_user.id, book_id=book_id).first()
        if progress:
            progress.current_page = int(current_page)
            db.session.commit()
            return jsonify({'status': 'success'})
    return jsonify({'status': 'error'}), 400

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    is_edit_mode = request.args.get('edit') == '1'
    user_profile = Profile.query.filter_by(user_id=current_user.id).first()
    
    if request.method == 'POST':
        current_user.username = request.form.get('username')
        current_user.email = request.form.get('email')
        
        photo = request.files.get('photo')
        if photo and photo.filename:
            if not os.path.exists(app.config['UPLOAD_FOLDER']):
                os.makedirs(app.config['UPLOAD_FOLDER'])
            filename = f"user_{current_user.id}_{photo.filename}"
            photo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            if not user_profile:
                user_profile = Profile(user_id=current_user.id, profile_photo=filename)
                db.session.add(user_profile)
            else:
                user_profile.profile_photo = filename
                
        db.session.commit()
        flash('Profile updated successfully.', 'success')
        return redirect(url_for('profile'))

    progress = ReadingProgress.query.filter_by(user_id=current_user.id).all()
    stats = {
        'books': len(set(p.book_id for p in progress)),
        'pages': sum(p.current_page for p in progress),
        'total_pages': sum(p.total_pages for p in progress)
    }
    
    activities = UserActivity.query.filter_by(user_id=current_user.id).order_by(UserActivity.created_at.desc()).limit(5).all()
    badges = UserAchievement.query.filter_by(user_id=current_user.id).all()
    
    books_progress = []
    for p in progress:
        book = Book.query.get(p.book_id)
        if book:
            review = Review.query.filter_by(user_id=current_user.id, book_title=book.title).first()
            books_progress.append({
                'book_id': book.id,
                'title': book.title,
                'current_page': p.current_page,
                'total_pages': p.total_pages,
                'review': review.review_text if review else None
            })

    return render_template('profile.html', 
                           current_user_profile=user_profile,
                           is_edit_mode=is_edit_mode,
                           stats=stats,
                           activities=activities,
                           badges=badges,
                           books=books_progress,
                           favorites_count=len(UserFavorite.query.filter_by(user_id=current_user.id).all()))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login_input = request.form.get('email') # this might be email or admin username
        password = request.form.get('password')
        
        # Check if admin
        admin = Admin.query.filter_by(username=login_input).first()
        if admin and check_password_hash(admin.password, password):
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
            
        # Check if regular user
        user = User.query.filter_by(email=login_input).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('index'))
            
        return render_template('login.html', error='Invalid email/username or password.')
        
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if User.query.filter_by(email=email).first():
            return render_template('register.html', error='Email already registered.', username=username, email=email)
            
        new_user = User(
            username=username, 
            email=email, 
            password=generate_password_hash(password),
            is_verified=True
        )
        db.session.add(new_user)
        db.session.commit()
        
        db.session.add(Profile(user_id=new_user.id))
        db.session.add(UserActivity(user_id=new_user.id, activity_type='Account Created', description='Welcome to ReadSmart!'))
        db.session.commit()
        
        login_user(new_user)
        return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/admin_upload', methods=['GET', 'POST'])
def admin_upload():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
        
    if request.method == 'POST':
        title = request.form.get('title')
        cover = request.files.get('cover')
        pdf_file = request.files.get('file')
        
        if cover and pdf_file and title:
            cover_filename = cover.filename
            pdf_filename = pdf_file.filename
            
            cover_path = os.path.join(app.root_path, 'static', 'cover', cover_filename)
            pdf_path = os.path.join(app.root_path, 'static', 'pdfs', pdf_filename)
            
            os.makedirs(os.path.dirname(cover_path), exist_ok=True)
            os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
            
            cover.save(cover_path)
            pdf_file.save(pdf_path)
            
            total_pages = 0
            try:
                with open(pdf_path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    total_pages = len(reader.pages)
            except Exception as e:
                print("Error reading PDF:", e)
                
            new_book = Book(title=title, cover=f"cover/{cover_filename}", pdfs=f"pdfs/{pdf_filename}",
                            total_pages=total_pages,
                            author=request.form.get('author', '').strip() or None,
                            category=request.form.get('category', 'General'),
                            description=request.form.get('description', '').strip() or None)
            db.session.add(new_book)
            db.session.commit()
            flash(f"Book uploaded successfully with {total_pages} pages!", "success")
            return redirect(url_for('admin_upload'))
            
    return render_template('admin_upload.html')

@app.route('/about_us')
def about_us():
    return render_template('about_us.html')

@app.route('/contact_us', methods=['GET', 'POST'])
def contact_us():
    if request.method == 'POST':
        email = request.form.get('email')
        problem = request.form.get('problem')
        msg = ContactUs(user_id=current_user.id if current_user.is_authenticated else None, user_email=email, problem=problem)
        db.session.add(msg)
        db.session.commit()
        flash("Message sent! We'll get back to you.", "success")
        return redirect(url_for('contact_us'))
    return render_template('contact_us.html')

@app.route('/privacy_policy')
def privacy_policy():
    return render_template('privacy_policy.html')

@app.route('/terms_of_service')
def terms_of_service():
    return render_template('terms_of_service.html')

@app.route('/featured')
def featured():
    # Fetch top 12 books as "featured"
    books = Book.query.limit(12).all()
    books_data = []
    
    if current_user.is_authenticated:
        favorites = [f.book_id for f in UserFavorite.query.filter_by(user_id=current_user.id).all()]
    else:
        favorites = []
        
    for book in books:
        books_data.append({
            'book': book,
            'is_favourite': book.id in favorites
        })
    return render_template('featured.html', featured_books=books_data)

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if session.get('admin_logged_in'):
        return redirect(url_for('admin_dashboard'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        admin = Admin.query.filter_by(username=username).first()
        if admin and check_password_hash(admin.password, password):
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            return render_template('admin_login.html', error="Invalid credentials")
    return render_template('admin_login.html')

@app.route('/admin_dashboard', methods=['GET', 'POST'])
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    if request.method == 'POST':
        user_id = request.form.get('user_id')
        action = request.form.get('action')
        user = User.query.get(user_id)
        if user and action in ['active', 'blocked']:
            user.status = action
            db.session.commit()
            return redirect(url_for('admin_dashboard'))
            
    users = User.query.all()
    total_books = Book.query.count()
    return render_template('admin_dashboard.html', users=users, total_books=total_books, total_users=len(users))

@app.route('/admin_logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))

@app.route('/admin_delete_book')
def admin_delete_book_view():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    books = Book.query.all()
    return render_template('admin_delete_book.html', books=books, message=request.args.get('message'))

@app.route('/admin_delete_book', methods=['POST'])
def admin_delete_book():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    book_id = request.form.get('book_id')
    book = Book.query.get(book_id)
    if book:
        # Delete local files (skip checking if it's default sample for safety)
        if book.cover and os.path.exists(os.path.join(app.root_path, 'static', book.cover)):
            os.remove(os.path.join(app.root_path, 'static', book.cover))
        if book.pdfs and os.path.exists(os.path.join(app.root_path, 'static', book.pdfs)):
            os.remove(os.path.join(app.root_path, 'static', book.pdfs))
        
        db.session.delete(book)
        db.session.commit()
        return redirect(url_for('admin_delete_book_view', message='Book deleted successfully!'))
    return redirect(url_for('admin_delete_book_view', message='Book not found!'))


# --- API Endpoints for Android App ---

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    if not data:
        return jsonify({'status': 'error', 'message': 'Missing data'}), 400
    
    email = data.get('email')
    password = data.get('password')
    
    user = User.query.filter_by(email=email).first()
    if user and check_password_hash(user.password, password):
        login_user(user)
        return jsonify({
            'status': 'success',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email
            }
        })
    return jsonify({'status': 'error', 'message': 'Invalid credentials'}), 401

@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.get_json()
    if not data:
        return jsonify({'status': 'error', 'message': 'Missing data'}), 400
        
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    
    if User.query.filter_by(email=email).first():
        return jsonify({'status': 'error', 'message': 'Email already registered'}), 409
        
    new_user = User(
        username=username, 
        email=email, 
        password=generate_password_hash(password),
        is_verified=True
    )
    db.session.add(new_user)
    db.session.commit()
    
    db.session.add(Profile(user_id=new_user.id))
    db.session.add(UserActivity(user_id=new_user.id, activity_type='Account Created', description='Welcome to ReadSmart!'))
    db.session.commit()
    
    login_user(new_user)
    return jsonify({
        'status': 'success',
        'user': {
            'id': new_user.id,
            'username': new_user.username,
            'email': new_user.email
        }
    })

@app.route('/api/books', methods=['GET'])
def api_books():
    books = Book.query.all()
    books_list = []
    
    favorites = []
    if current_user.is_authenticated:
        favorites = [f.book_id for f in UserFavorite.query.filter_by(user_id=current_user.id).all()]
        
    for book in books:
        books_list.append({
            'id': book.id,
            'title': book.title,
            'cover': book.cover,
            'total_pages': book.total_pages,
            'is_favourite': book.id in favorites
        })
    return jsonify(books_list)

@app.route('/api/book/<int:book_id>', methods=['GET'])
def api_book_details(book_id):
    book = Book.query.get_or_404(book_id)
    progress = None
    if current_user.is_authenticated:
        progress = ReadingProgress.query.filter_by(user_id=current_user.id, book_id=book_id).first()
    
    return jsonify({
        'id': book.id,
        'title': book.title,
        'cover': book.cover,
        'pdf_url': book.pdfs,
        'total_pages': book.total_pages,
        'current_page': progress.current_page if progress else 1
    })

@app.route('/api/profile', methods=['GET'])
@login_required
def api_profile():
    user_profile = Profile.query.filter_by(user_id=current_user.id).first()
    progress = ReadingProgress.query.filter_by(user_id=current_user.id).all()
    
    stats = {
        'books_read': len(set(p.book_id for p in progress)),
        'pages_read': sum(p.current_page for p in progress),
        'total_pages': sum(p.total_pages for p in progress)
    }
    
    activities = UserActivity.query.filter_by(user_id=current_user.id).order_by(UserActivity.created_at.desc()).limit(10).all()
    activity_list = [{'id': a.user_id, 'type': a.activity_type, 'desc': a.description, 'date': a.created_at.isoformat()} for a in activities]
    
    return jsonify({
        'username': current_user.username,
        'email': current_user.email,
        'profile_photo': user_profile.profile_photo if user_profile else None,
        'stats': stats,
        'activities': activity_list
    })

@app.route('/api/toggle_favourite/<int:book_id>', methods=['POST'])
@login_required
def api_toggle_favourite(book_id):
    fav = UserFavorite.query.filter_by(user_id=current_user.id, book_id=book_id).first()
    is_fav = False
    if fav:
        db.session.delete(fav)
    else:
        new_fav = UserFavorite(user_id=current_user.id, book_id=book_id)
        db.session.add(new_fav)
        is_fav = True
    db.session.commit()
    return jsonify({'status': 'success', 'is_favourite': is_fav})

@app.route('/api/logout', methods=['POST'])
@login_required
def api_logout():
    logout_user()
    return jsonify({'status': 'success'})

@app.route('/api/pdfs/<path:filename>')
def api_get_pdf(filename):
    # Helper to serve PDFs from static/pdfs
    return send_file(os.path.join(app.root_path, 'static', 'pdfs', filename))


# ───────────────────────────────────────────────
# BOOK DETAIL PAGE
# ───────────────────────────────────────────────
@app.route('/book/<int:book_id>')
def book_detail(book_id):
    book = Book.query.get_or_404(book_id)
    reviews = Review.query.filter_by(book_id=book_id).order_by(Review.created_at.desc()).all()
    avg_rating = round(sum(r.rating for r in reviews if r.rating) / len([r for r in reviews if r.rating]), 1) if any(r.rating for r in reviews) else None
    is_favourite = False
    user_review = None
    if current_user.is_authenticated:
        fav = UserFavorite.query.filter_by(user_id=current_user.id, book_id=book_id).first()
        is_favourite = fav is not None
        user_review = Review.query.filter_by(user_id=current_user.id, book_id=book_id).first()
    return render_template('book_detail.html', book=book, reviews=reviews, avg_rating=avg_rating,
                           is_favourite=is_favourite, user_review=user_review)


@app.route('/book/<int:book_id>/review', methods=['POST'])
@login_required
def submit_review(book_id):
    book = Book.query.get_or_404(book_id)
    review_text = request.form.get('review_text', '').strip()
    rating = request.form.get('rating')
    if not review_text:
        flash('Review cannot be empty.', 'error')
        return redirect(url_for('book_detail', book_id=book_id))
    existing = Review.query.filter_by(user_id=current_user.id, book_id=book_id).first()
    if existing:
        existing.review_text = review_text
        existing.rating = int(rating) if rating else None
    else:
        new_review = Review(user_id=current_user.id, book_id=book_id,
                            book_title=book.title, review_text=review_text,
                            rating=int(rating) if rating else None)
        db.session.add(new_review)
    db.session.commit()
    flash('Review submitted!', 'success')
    return redirect(url_for('book_detail', book_id=book_id))


# ───────────────────────────────────────────────
# SUBSCRIPTION (Razorpay)
# ───────────────────────────────────────────────
@app.route('/subscription')
@login_required
def subscription():
    sub = Subscription.query.filter_by(user_id=current_user.id).first()
    return render_template('subscription.html', sub=sub, razorpay_key_id=RAZORPAY_KEY_ID)


@app.route('/create_razorpay_order', methods=['POST'])
@login_required
def create_razorpay_order():
    try:
        order_data = {
            'amount': 9900,          # ₹99 in paise
            'currency': 'INR',
            'receipt': f'sub_{current_user.id}',
            'payment_capture': 1
        }
        order = rzp_client.order.create(data=order_data)
        return jsonify({
            'order_id': order['id'],
            'amount': order['amount'],
            'currency': order['currency']
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/subscribe', methods=['POST'])
@login_required
def subscribe():
    payment_id  = request.form.get('razorpay_payment_id')
    order_id    = request.form.get('razorpay_order_id')
    signature   = request.form.get('razorpay_signature')

    # Verify signature
    msg = f'{order_id}|{payment_id}'.encode()
    expected = hmac.new(RAZORPAY_KEY_SECRET.encode(), msg, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, signature or ''):
        flash('Payment verification failed. Please contact support.', 'error')
        return redirect(url_for('subscription'))

    # Activate subscription
    existing = Subscription.query.filter_by(user_id=current_user.id).first()
    if existing:
        existing.is_active = True
        existing.start_date = datetime.utcnow()
    else:
        sub = Subscription(user_id=current_user.id, plan='premium', price=99.0, is_active=True)
        db.session.add(sub)

    db.session.commit()
    flash('Payment successful! Welcome to ReadZey Premium 🎉', 'success')
    return redirect(url_for('subscription'))


@app.route('/unsubscribe', methods=['POST'])
@login_required
def unsubscribe():
    sub = Subscription.query.filter_by(user_id=current_user.id).first()
    if sub:
        sub.is_active = False
        db.session.commit()
        flash('Subscription cancelled.', 'info')
    return redirect(url_for('subscription'))


# ───────────────────────────────────────────────
# FRIEND REQUESTS
# ───────────────────────────────────────────────
@app.route('/send_friend_request/<int:to_user_id>', methods=['POST'])
@login_required
def send_friend_request(to_user_id):
    if to_user_id == current_user.id:
        flash('You cannot send a request to yourself.', 'error')
        return redirect(url_for('profile'))
    existing = FriendRequest.query.filter_by(sender_id=current_user.id, receiver_id=to_user_id).first()
    if existing:
        flash('Friend request already sent.', 'info')
        return redirect(request.referrer or url_for('profile'))
    fr = FriendRequest(sender_id=current_user.id, receiver_id=to_user_id, status='pending')
    db.session.add(fr)
    db.session.commit()
    flash('Friend request sent!', 'success')
    return redirect(request.referrer or url_for('profile'))


@app.route('/accept_friend_request/<int:request_id>', methods=['POST'])
@login_required
def accept_friend_request(request_id):
    fr = FriendRequest.query.get_or_404(request_id)
    if fr.receiver_id != current_user.id:
        flash('Not authorized.', 'error')
        return redirect(url_for('profile'))
    fr.status = 'accepted'
    db.session.commit()
    flash(f'You are now friends with {fr.sender.username}!', 'success')
    return redirect(url_for('social'))


@app.route('/reject_friend_request/<int:request_id>', methods=['POST'])
@login_required
def reject_friend_request(request_id):
    fr = FriendRequest.query.get_or_404(request_id)
    if fr.receiver_id != current_user.id:
        flash('Not authorized.', 'error')
        return redirect(url_for('profile'))
    fr.status = 'rejected'
    db.session.commit()
    return redirect(url_for('social'))


@app.route('/social')
@login_required
def social():
    is_special = current_user.email == 'you@gmail.com'
    has_sub = is_special or (current_user.subscription and current_user.subscription.is_active)

    friends_as_sender   = FriendRequest.query.filter_by(sender_id=current_user.id,   status='accepted').all()
    friends_as_receiver = FriendRequest.query.filter_by(receiver_id=current_user.id, status='accepted').all()
    friends   = [fr.receiver for fr in friends_as_sender] + [fr.sender for fr in friends_as_receiver]

    pending_received = FriendRequest.query.filter_by(receiver_id=current_user.id, status='pending').all()
    pending_sent     = FriendRequest.query.filter_by(sender_id=current_user.id,   status='pending').all()

    all_users  = User.query.filter(User.id != current_user.id).all()
    friend_ids = {u.id for u in friends}
    sent_ids   = {fr.receiver_id for fr in pending_sent}
    books      = Book.query.all()

    my_sessions = ReadTogetherSession.query.filter(
        (ReadTogetherSession.host_id  == current_user.id) |
        (ReadTogetherSession.guest_id == current_user.id)
    ).order_by(ReadTogetherSession.created_at.desc()).all()

    # Pending RT invites sent TO me
    pending_rt = [s for s in my_sessions if s.status == 'pending' and s.guest_id == current_user.id]

    return render_template('social.html',
        friends=friends,
        pending_received=pending_received,
        pending_sent=pending_sent,
        all_users=all_users,
        friend_ids=friend_ids,
        sent_ids=sent_ids,
        books=books,
        my_sessions=my_sessions,
        pending_rt=pending_rt,
        has_sub=has_sub
    )


# ───────────────────────────────────────────────
# READ TOGETHER
# ───────────────────────────────────────────────
@app.route('/read_together/invite', methods=['POST'])
@login_required
def invite_read_together():
    is_special = current_user.email == 'you@gmail.com'
    has_sub = is_special or (current_user.subscription and current_user.subscription.is_active)
    if not has_sub:
        flash('You need a Premium subscription to use Read Together.', 'info')
        return redirect(url_for('subscription'))

    friend_id = request.form.get('friend_id', type=int)
    book_id   = request.form.get('book_id',   type=int)
    if not friend_id or not book_id:
        flash('Select a friend and a book.', 'error')
        return redirect(url_for('social'))
    existing = ReadTogetherSession.query.filter_by(
        host_id=current_user.id, guest_id=friend_id,
        book_id=book_id, status='pending').first()
    if existing:
        flash('Invitation already sent.', 'info')
        return redirect(url_for('social'))
    sess = ReadTogetherSession(host_id=current_user.id, guest_id=friend_id,
                               book_id=book_id, status='pending')
    db.session.add(sess)
    db.session.commit()
    flash('Read Together invitation sent! 📖', 'success')
    return redirect(url_for('social'))


@app.route('/read_together/accept/<int:session_id>', methods=['POST'])
@login_required
def accept_read_together(session_id):
    is_special = current_user.email == 'you@gmail.com'
    has_sub = is_special or (current_user.subscription and current_user.subscription.is_active)
    if not has_sub:
        flash('You need a Premium subscription to join a Read Together session.', 'info')
        return redirect(url_for('subscription'))
    sess = ReadTogetherSession.query.get_or_404(session_id)
    if sess.guest_id != current_user.id:
        flash('Not authorized.', 'error')
        return redirect(url_for('social'))
    sess.status = 'active'
    db.session.commit()
    return redirect(url_for('read_together', session_id=session_id))


@app.route('/read_together/decline/<int:session_id>', methods=['POST'])
@login_required
def decline_read_together(session_id):
    sess = ReadTogetherSession.query.get_or_404(session_id)
    if sess.guest_id != current_user.id:
        flash('Not authorized.', 'error')
        return redirect(url_for('social'))
    sess.status = 'ended'
    db.session.commit()
    flash('Invitation declined.', 'info')
    return redirect(url_for('social'))


@app.route('/read_together/<int:session_id>')
@login_required
def read_together(session_id):
    sess = ReadTogetherSession.query.get_or_404(session_id)
    if current_user.id not in [sess.host_id, sess.guest_id]:
        flash('Access denied.', 'error')
        return redirect(url_for('library'))
    if sess.status == 'pending':
        flash('Waiting for the other person to accept.', 'info')
        return redirect(url_for('social'))
    book = sess.book
    messages = ChatMessage.query.filter_by(session_id=session_id).order_by(ChatMessage.created_at).all()
    progress = ReadingProgress.query.filter_by(user_id=current_user.id, book_id=book.id).first()
    current_page = sess.current_page
    return render_template('read_together.html', session=sess, book=book,
                           messages=messages, current_page=current_page)


@app.route('/read_together/<int:session_id>/chat', methods=['POST'])
@login_required
def send_chat(session_id):
    sess = ReadTogetherSession.query.get_or_404(session_id)
    if current_user.id not in [sess.host_id, sess.guest_id]:
        return jsonify({'status': 'error'}), 403
    msg_text = request.form.get('message', '').strip()
    if msg_text:
        msg = ChatMessage(session_id=session_id, sender_id=current_user.id, message=msg_text)
        db.session.add(msg)
        db.session.commit()
    return redirect(url_for('read_together', session_id=session_id))


@app.route('/read_together/<int:session_id>/messages')
@login_required
def get_chat_messages(session_id):
    sess = ReadTogetherSession.query.get_or_404(session_id)
    if current_user.id not in [sess.host_id, sess.guest_id]:
        return jsonify({'status': 'error'}), 403
    messages = ChatMessage.query.filter_by(session_id=session_id).order_by(ChatMessage.created_at).all()
    return jsonify([{
        'id': m.id,
        'sender': m.sender.username,
        'sender_id': m.sender_id,
        'message': m.message,
        'time': m.created_at.strftime('%H:%M')
    } for m in messages])


@app.route('/read_together/<int:session_id>/sync_page', methods=['POST'])
@login_required
def sync_page(session_id):
    sess = ReadTogetherSession.query.get_or_404(session_id)
    if current_user.id not in [sess.host_id, sess.guest_id]:
        return jsonify({'status': 'error'}), 403
    page = request.form.get('page', type=int)
    if page:
        sess.current_page = page
        db.session.commit()
    return jsonify({'status': 'ok', 'page': sess.current_page})


@app.route('/read_together/<int:session_id>/get_page')
@login_required
def get_session_page(session_id):
    sess = ReadTogetherSession.query.get_or_404(session_id)
    if current_user.id not in [sess.host_id, sess.guest_id]:
        return jsonify({'status': 'error'}), 403
    return jsonify({'page': sess.current_page})


def init_db():
    with app.app_context():
        db.create_all()
        # Create some sample books if empty
        if not Book.query.first():
            b1 = Book(title='Sample Book 1', cover='cover/sample1.jpg', pdfs='pdfs/sample.pdf', total_pages=10)
            db.session.add(b1)
            db.session.commit()
        
        # Create default admin if missing
        if not Admin.query.filter_by(username='yash').first():
            badmin = Admin(username='yash', password=generate_password_hash('aloneyash'))
            db.session.add(badmin)
            db.session.commit()

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', debug=True, port=8000)

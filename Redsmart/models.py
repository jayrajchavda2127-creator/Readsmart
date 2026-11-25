from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    is_verified = db.Column(db.Boolean, default=False)
    verification_code = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(50), default='active')
    reset_token = db.Column(db.String(100), nullable=True)

class Book(db.Model):
    __tablename__ = 'books'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    price = db.Column(db.Float, default=0.0)
    cover = db.Column(db.String(255), nullable=True)
    pdfs = db.Column(db.String(255), nullable=True)
    total_pages = db.Column(db.Integer, default=0)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(100), nullable=True, default='General')
    author = db.Column(db.String(255), nullable=True)

class Review(db.Model):
    __tablename__ = 'reviews'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'), nullable=False)
    book_title = db.Column(db.String(255), nullable=True)
    review_text = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('reviews', lazy=True))
    book = db.relationship('Book', backref=db.backref('reviews', lazy=True))

class ReadingProgress(db.Model):
    __tablename__ = 'reading_progress'
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'), primary_key=True)
    current_page = db.Column(db.Integer, default=1)
    total_pages = db.Column(db.Integer, default=0)

class Profile(db.Model):
    __tablename__ = 'profile'
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    profile_photo = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class UserFavorite(db.Model):
    __tablename__ = 'user_favorites'
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'), primary_key=True)

class ContactUs(db.Model):
    __tablename__ = 'contact_us'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    user_email = db.Column(db.String(150), nullable=False)
    problem = db.Column(db.Text, nullable=False)

class UserActivity(db.Model):
    __tablename__ = 'user_activity'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    activity_type = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class UserAchievement(db.Model):
    __tablename__ = 'user_achievements'
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    badge_name = db.Column(db.String(100), primary_key=True)
    badge_icon = db.Column(db.String(255), nullable=True)

class Admin(db.Model):
    __tablename__ = 'admin'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)

# --- Subscription ---
class Subscription(db.Model):
    __tablename__ = 'subscriptions'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    plan = db.Column(db.String(50), default='premium')
    price = db.Column(db.Float, default=99.0)
    start_date = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    user = db.relationship('User', backref=db.backref('subscription', uselist=False))

# --- Friend Requests ---
class FriendRequest(db.Model):
    __tablename__ = 'friend_requests'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending / accepted / rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_requests')
    receiver = db.relationship('User', foreign_keys=[receiver_id], backref='received_requests')

# --- Read Together Session ---
class ReadTogetherSession(db.Model):
    __tablename__ = 'read_together_sessions'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    host_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    guest_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending / active / ended
    current_page = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    host = db.relationship('User', foreign_keys=[host_id], backref='hosted_sessions')
    guest = db.relationship('User', foreign_keys=[guest_id], backref='joined_sessions')
    book = db.relationship('Book', backref='read_sessions')

# --- Chat Message ---
class ChatMessage(db.Model):
    __tablename__ = 'chat_messages'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(db.Integer, db.ForeignKey('read_together_sessions.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sender = db.relationship('User', backref='chat_messages')
    session = db.relationship('ReadTogetherSession', backref='messages')
